"""Source-attributed email retrieval and negative eligibility fixtures; no paid AI."""
import asyncio
import copy
import hashlib
import io
import json

from docx import Document
import pytest

import main
from services.email_context import build_context, clean_message, validated_context, MAX_BODY_CHARS
from services.task_queue import SearchWorker
from test_durable_search import assessment, queue_db  # noqa: F401
from test_folder_tag_e2e import flow, BUCKET, FOLDER, FOLDERS, MIME  # noqa: F401
from vps_local import discovery_shim as index


def document(skills='Figma UI designer', *, location='Dubai', years=5):
    doc = Document()
    doc.add_heading('Fictional Test Applicant', 0)
    doc.add_paragraph(f'Skills: {skills}.\nExperience: {years} years.\nLocation: {location}.\nEnglish.')
    target = io.BytesIO()
    doc.save(target)
    return target.getvalue()


def message(identity='one', body='My application for fjord navigation', *, count=1, content=None):
    return {'id': identity, 'from': 'Fictional Applicant <applicant@example.invalid>',
            'subject': 'Application', 'date': '2026-04-30T23:59:59Z', 'body_plain': body,
            'attachments': [{'filename': identity + f'-{i}.docx', 'original_filename': 'applicant.docx',
                'content': content or document(), 'content_type': MIME, 'stable_identity': True}
                for i in range(count)]}


def ingest(flow, messages, folder=FOLDER):
    result = asyncio.run(main.process_scraped_attachments(messages, folder, flow.actor['user']))
    assert result['email_stats']['failed_uploads'] == 0, result
    assert all(row['vector_indexed'] for row in result['results']), result
    return result


@pytest.mark.parametrize('value,expected', [
    ('My experience in banking\n> Required Python and AWS', 'My experience in banking'),
    ('My application\nOn Friday a recruiter wrote:\nRequired Python', 'My application'),
    ('My application\n-----Original Message-----\nJava', 'My application'),
    ('My application\nFrom: recruiter@example.invalid\nRequired Java', 'My application'),
    ('My application\nBest regards,\nRecruiter Python AWS', 'My application'),
    ('<p>My application</p><blockquote>Java AWS</blockquote>', 'My application'),
    ('<div>My application</div><div class="gmail_quote">Java AWS</div>', 'My application'),
    ('<p>My application</p><script>Java AWS</script>', 'My application'),
    ('<script>Java AWS</script>', ''),
    ('<p>My application</p><div id="divRplyFwdMsg">From recruiter</div><p>Java AWS required</p>', 'My application'),
    ('<p>My application</p><div style="display: none">Java AWS</div>', 'My application'),
    ('<p>My application</p><div class="gmail_signature">Java AWS</div>', 'My application'),
    ('My\x00 application', 'My application'),
    (None, ''),
])
def test_quoted_hidden_and_signature_content_is_not_searchable(value, expected):
    assert clean_message(value) == expected


def test_context_is_bounded_provenance_aware_and_does_not_store_raw_message_ids():
    value = message(body='x' * (MAX_BODY_CHARS * 20))
    context = build_context(value)
    text, metadata = validated_context(context)
    assert len(text) <= MAX_BODY_CHARS + 251
    assert metadata['message_sha256'] == hashlib.sha256(b'one').hexdigest()
    assert metadata['association'] == 'single_resume' and metadata['purpose'] == 'retrieval_only'
    assert metadata['sender'] == 'applicant@example.invalid'
    assert 'message_id' not in metadata
    assert build_context(message(count=2))['metadata']['association'] == 'shared_message'
    assert build_context({}) is None


@pytest.mark.parametrize('change', ['text', 'digest', 'count', 'association', 'purpose', 'version'])
def test_invalid_or_tampered_context_is_rejected(change):
    value = copy.deepcopy(build_context(message()))
    if change == 'text': value['text'] += ' forged text'
    elif change == 'digest': value['metadata']['text_sha256'] = 'invalid'
    elif change == 'count': value['metadata']['attachment_count'] = True
    elif change == 'association': value['metadata']['association'] = 'verified_cv'
    elif change == 'purpose': value['metadata']['purpose'] = 'qualification'
    else: value['metadata']['version'] = 999
    with pytest.raises(ValueError): validated_context(value)


@pytest.mark.parametrize('advanced', [False, True])
def test_email_only_terms_retrieve_without_contaminating_cv_or_embeddings(flow, monkeypatch, advanced):
    monkeypatch.setattr(index, 'ADVANCED_SEARCH_ENABLED', advanced)
    embedded = []
    monkeypatch.setattr(index, '_embed_query', lambda text: embedded.append(text) or [1, 0, 0])
    flow.bulk(FOLDER, [('unrelated.docx', document('Accountant Excel'))])
    ingest(flow, [message(body='I am applying for fjord navigation. EMAIL_ONLY_SENTINEL')])
    assert len(embedded) == 2 and all('EMAIL_ONLY_SENTINEL' not in text for text in embedded)
    rows = index._vector_search('fjord navigation', 10, 'company_id: ANY("1")', FOLDERS)
    assert rows[0]['filename'] == 'one-0.docx' and rows[0]['email_context_match']
    result = index._row_to_result(rows[0])
    assert 'EMAIL_ONLY_SENTINEL' not in result.document.derived_struct_data['snippets'][0]['snippet']
    assert 'source_email' not in result.document.struct_data
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute("SELECT extracted_text,candidate_skills,source_email_context FROM resume_embeddings WHERE filename='one-0.docx'")
        row = cursor.fetchone()
    assert 'EMAIL_ONLY_SENTINEL' in row['source_email_context']
    assert 'EMAIL_ONLY_SENTINEL' not in row['extracted_text']
    assert 'fjord' not in ' '.join(row['candidate_skills']).lower()


def test_shared_or_quoted_email_never_becomes_a_candidate_match(flow):
    quoted = message('quoted', 'My CV\n> fjord navigation')
    shared = message('shared', 'fjord navigation', count=2)
    ingest(flow, [quoted, shared])
    rows = index._vector_search('fjord navigation', 10, 'company_id: ANY("1")', FOLDERS)
    assert not any(row.get('email_context_match') for row in rows)


@pytest.mark.parametrize('advanced', [False, True])
def test_role_context_does_not_require_email_to_repeat_cv_requirements(flow, monkeypatch, advanced):
    monkeypatch.setattr(index, 'ADVANCED_SEARCH_ENABLED', advanced)
    role = 'Fjord Navigation Engineer'
    query = role + ' based in Dubai with 3-6 years of experience. Required skills: Figma.'
    ingest(flow, [message(body='Application for ' + role + '. EMAIL_ONLY_SENTINEL')])
    original = index._vector_search(query, 10, 'company_id: ANY("1")', FOLDERS)
    assert original and not original[0]['email_context_match']
    improved = index._vector_search(query, 10, 'company_id: ANY("1")', FOLDERS, email_context_query=role)
    assert improved and improved[0]['email_context_match']
    assert improved[0]['criteria_profile_status'] == 'exact'
    assert 'EMAIL_ONLY_SENTINEL' not in improved[0]['text']
    assert not index._vector_search(role + ' based in Paris. Required skills: Figma', 10,
        'company_id: ANY("1")', FOLDERS, email_context_query=role)
    unverified = index._vector_search(role + '. Required skills: Python', 10,
        'company_id: ANY("1")', FOLDERS, email_context_query=role)
    assert all(row['criteria_profile_status'] != 'exact' for row in unverified)


@pytest.mark.parametrize('value', [42, [], 'x' * 251])
def test_context_query_is_typed_and_bounded(value):
    with pytest.raises(ValueError): index.SearchRequest(query='Figma', email_context_query=value)


def test_context_role_query_does_not_replace_cv_lexical_query(monkeypatch):
    from unittest.mock import MagicMock
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    index._add_email_context_rows(cursor, [], query='Figma developer Dubai five years',
        email_query='UI Designer', qvec=[1, 0, 0],scope_sql='company_id=%s',scope_params=[1],limit=10)
    sql, params = cursor.execute.call_args.args
    assert params[1] == 'Figma developer Dubai five years'
    assert params[2] == params[-4] == params[-3] == 'UI Designer'
    assert sql.count('%s') == len(params)


def test_scoped_email_lookup_can_use_its_partial_text_index(flow):
    ingest(flow, [message()])
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute("""CREATE INDEX fixture_email_fts ON resume_embeddings USING gin(to_tsvector('simple',source_email_context))
            WHERE source_email_metadata->>'association'='single_resume' AND source_email_metadata->>'purpose'='retrieval_only'""")
        # Isolate index eligibility, not the planner's preference on a one-row fixture.
        cursor.execute('DROP INDEX e2e_identity')
        cursor.execute('SET LOCAL enable_seqscan=off')
        plans = []
        class Explain:
            def execute(self, sql, params):
                assert 'OFFSET 0' not in sql, 'The ANN scope barrier must not disable email text-index pushdown'
                cursor.execute('EXPLAIN (FORMAT JSON) ' + sql, params)
                plans.append(cursor.fetchone()['QUERY PLAN'])
            def fetchall(self): return []
        index._add_email_context_rows(Explain(), [], query='fjord navigation', qvec=[1, 0, 0],
            scope_sql='company_id=%s AND storage_bucket=%s AND folder=%s',scope_params=[1, BUCKET, FOLDER],limit=10)
    assert 'fixture_email_fts' in json.dumps(plans)


@pytest.mark.parametrize('advanced', [False, True])
@pytest.mark.parametrize('role,skills', [('Developer', 'Python and SQL'), ('Accountant', 'Excel'), ('Network Engineer', 'CCNA')])
def test_ten_candidates_are_cv_verified_despite_false_email_claims(flow, monkeypatch, advanced, role, skills):
    monkeypatch.setattr(index, 'ADVANCED_SEARCH_ENABLED', advanced)
    query = f'{role} based in Dubai with 3-6 years of experience. Required skills: {skills}'
    messages = [message('good-' + str(i), query, content=document(skills)) for i in range(10)]
    messages += [message('wrong-city', query, content=document(skills, location='Paris')),
                 message('wrong-years', query, content=document(skills, years=12)),
                 message('wrong-skill', query, content=document('Graphic design and Photoshop'))]
    ingest(flow, messages)
    rows = index._vector_search(query, 10, 'company_id: ANY("1")', FOLDERS)
    assert len(rows) == 10
    assert all(row['filename'].startswith('good-') and row['criteria_profile_status'] == 'exact' for row in rows)
    scores = [row['score'] for row in rows]
    assert scores == sorted(scores, reverse=True)
    assert len({row['id'] for row in rows}) == 10
    response = flow.client.post('/api/search-vector', data={'query': query, 'result_count': '10',
        'folders': json.dumps(FOLDERS)})
    assert response.status_code == 200, response.text
    assert len(response.json()['results']) == 10
    assert response.json()['exact_match_shortfall'] == 0


def test_body_only_skills_cannot_satisfy_exact_requirements_or_pad_ten(flow):
    ingest(flow, [message('false', 'Python SQL developer based in Dubai with 5 years of experience', content=document('Figma')),
                  message('real', 'Python SQL developer', content=document('Python and SQL'))])
    response = flow.client.post('/api/search-vector', data={'query': 'Required skills: Python and SQL', 'result_count': '10',
        'folders': json.dumps(FOLDERS)})
    assert response.status_code == 200, response.text
    assert len(response.json()['results']) == 1
    assert response.json()['exact_match_shortfall'] == 9
    assert response.json()['results'][0]['content']['file_path'].endswith('real-0.docx')


def test_email_retrieval_respects_company_folder_tag_and_inclusive_date(flow):
    ingest(flow, [message('inside')])
    ingest(flow, [message('sibling')], FOLDER + '-old')
    outside = message('outside'); outside['date'] = '2026-05-01T00:00:00Z'
    ingest(flow, [outside])
    ingest(flow, [message('wrong-tag', content=document('Accountant with Excel'))])
    flow.actor['user'] = flow.db.get_hr_task_user(8, 2)
    ingest(flow, [message('tenant-two')])
    flow.actor['user'] = flow.db.get_hr_task_user(7, 1)
    filters = {'tags': ['UI design'], 'date_basis': 'received', 'date_from': '2026-04-01', 'date_to': '2026-04-30'}
    rows = index._vector_search('fjord navigation', 10, 'company_id: ANY("1")', FOLDERS, filters)
    assert [row['filename'] for row in rows] == ['inside-0.docx']
    assert rows[0]['email_context_match']
    assert index._vector_search('fjord navigation', 10, 'company_id: ANY("1")',
        [{'bucket': BUCKET, 'path': 'Missing'}], filters) == []


def test_durable_scorecard_prompt_remains_full_cv_only(flow, monkeypatch):
    ingest(flow, [message(body='fjord navigation EMAIL_ONLY_SENTINEL')])
    monkeypatch.setattr(main, '_prepare_search_input', lambda kind, *args: {'all_keywords': ['Figma']} if kind == 'keywords'
        else {'optimized_query': 'fjord navigation'})
    monkeypatch.setattr(flow.db, 'get_cached_resume_analysis', lambda *args, **kwargs: None)
    monkeypatch.setattr(flow.db, 'save_cached_resume_analysis', lambda *args, **kwargs: None)
    seen = []
    async def analyze(text, *args, **kwargs):
        assert 'EMAIL_ONLY_SENTINEL' not in text and 'Fictional Test Applicant' in text
        seen.append(kwargs['file_path'])
        value = assessment()
        value['hr_scorecard']['candidate_overview'].update(position_applied_for='Designer', experience_years=5)
        return value
    monkeypatch.setattr(main, 'analyze_resume_with_hr_scorecard', analyze)
    monkeypatch.setattr(main, 'using_deepseek', lambda: True)
    response = flow.client.post('/api/hr-scorecard-search', data={'query': 'fjord navigation', 'result_count': '10',
        'folders': json.dumps(FOLDERS)})
    assert response.status_code == 200, response.text
    task_id = response.json()['task_id']
    job = flow.db.claim_next_hr_task()
    asyncio.run(SearchWorker(lambda: flow.db, main.run_hr_scorecard_task).process(flow.db, job))
    status = flow.db.get_task_status(task_id)
    assert status['status'] == 'completed' and seen == [FOLDER + '/one-0.docx']


def test_durable_job_reports_role_context_without_changing_cv_scoring(flow, monkeypatch):
    role = 'Fjord Navigation Engineer'
    query = role + ' based in Dubai with 3-6 years of experience. Required skills: Figma.'
    ingest(flow, [message(body='Application for ' + role + '. EMAIL_ONLY_SENTINEL')])
    monkeypatch.setattr(main, '_prepare_search_input', lambda kind, *args: {'all_keywords': ['Figma']} if kind == 'keywords'
        else {'optimized_query': query + ' extra optimizer terms'})
    monkeypatch.setattr(flow.db, 'get_cached_resume_analysis', lambda *args, **kwargs: None)
    monkeypatch.setattr(flow.db, 'save_cached_resume_analysis', lambda *args, **kwargs: None)
    async def analyze(text, original_query, title, *args, **kwargs):
        assert 'EMAIL_ONLY_SENTINEL' not in text
        assert original_query == query and title == role
        value = assessment()
        value['hr_scorecard']['candidate_overview'].update(location='Dubai', experience_years=5, skills=['Figma'])
        return value
    monkeypatch.setattr(main, 'analyze_resume_with_hr_scorecard', analyze)
    monkeypatch.setattr(main, 'using_deepseek', lambda: True)
    response = flow.client.post('/api/hr-scorecard-search', data={'query':query,'job_title':role,'result_count':'10',
        'folders':json.dumps(FOLDERS)})
    assert response.status_code == 200, response.text
    job = flow.db.claim_next_hr_task()
    asyncio.run(SearchWorker(lambda:flow.db, main.run_hr_scorecard_task).process(flow.db,job))
    status = flow.db.get_task_status(response.json()['task_id'])
    assert status['status'] == 'completed', status
    progress = status['progress']
    if isinstance(progress, str): progress = json.loads(progress)
    assert progress['retrieval_email_context_matches'] == 1
    assert progress['returned_results'] == 1 and progress['exact_match_shortfall'] == 9
    assert progress['cache_hits'] == 0
