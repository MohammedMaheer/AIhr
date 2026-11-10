"""Explicit search scopes must constrain every retrieval branch, not ranking alone."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import main
from services.resume_folders import normalize_folders, folder_sql, source_in_folders, inventory, searchable_count, tag_inventory
from services.resume_filters import normalize_filters, filters_sql, received_date, tags_from_text, refresh_existing_metadata
from services.resume_library import list_uploads, preview_upload
from test_durable_search import queue_db
from test_integration_workflows import api
from vps_local import discovery_shim as search

USER = {'id': 7, 'user_type': 'tenant_user', 'company': {'company_id': 1}}
FOLDERS = [{'bucket': 'fixture-bucket', 'path': 'Networking/Nov 2026'}]


@pytest.mark.parametrize('value', ['[]', '{}', 'null', '[', 4, [None], [{'bucket':'x','path':'../secret'}],
    [{'bucket':'x','path':'/secret'}], [{'bucket':'x','path':'a//b'}], [{'bucket':'x','path':'a\\b'}],
    [{'bucket':'x','path':'a\x00b'}], [{'bucket':'x','path':'a','extra':1}], [{'bucket':"x' OR TRUE --",'path':'a'}]])
def test_bad_folder_input_never_silently_becomes_all(value):
    with pytest.raises(ValueError): normalize_folders(value)


def test_folder_canonicalization_and_boundary_checks():
    assert normalize_folders(FOLDERS * 2) == FOLDERS
    assert normalize_folders([{'bucket':'fixture-bucket','path':'Networking/Nov 2026/'}]) == FOLDERS
    assert source_in_folders('gs://fixture-bucket/Networking/Nov 2026/sub/cv.pdf', FOLDERS)
    assert not source_in_folders('gs://fixture-bucket/Networking/Nov 2026-old/cv.pdf', FOLDERS)
    assert not source_in_folders('gs://other/Networking/Nov 2026/cv.pdf', FOLDERS)
    sql, params = folder_sql([{'bucket':'x','path':"folder_'%"}])
    assert "folder_'%" not in sql and params == ['x',"folder_'%","folder_'%/"]


@pytest.mark.parametrize('value', ['[]', {'tags':['invented']}, {'tags':'Management'}, {'date_from':'2026-02-30'},
    {'date_from':'2026-11-06','date_to':'2026-11-05'}, {'date_basis':'guessed'}, {'unsafe':True}])
def test_invalid_tags_or_date_ranges_are_rejected(value):
    with pytest.raises(ValueError): normalize_filters(value)


def test_tags_are_local_evidence_and_received_dates_are_not_invented():
    assert tags_from_text('Graphic designer using Figma and Photoshop') == ['Graphic design', 'UI design']
    assert tags_from_text('fictional generic CV') == []
    assert received_date('Unknown') is None and received_date(None) is None
    assert received_date('2026-04-02T10:00:00Z').isoformat() == '2026-04-02T10:00:00+00:00'
    assert received_date('Thu, 02 Apr 2026 10:00:00 +0400').hour == 6
    sql, params = filters_sql({'date_from':'2026-04-01','date_to':'2026-04-30','date_basis':'received','tags':['UI design']})
    assert 'source_received_at' in sql and "interval '1 day'" in sql
    assert params == [['UI design'],'2026-04-01','2026-04-30']


@pytest.mark.parametrize('phrase,tag', [
    ('network engineer', 'IT infrastructure'),
    ('graphic designer', 'Graphic design'),
    ('user interface design', 'UI design'),
    ('web designer', 'Web design'),
    ('software developer', 'Software development'),
    ('data scientist', 'Data and AI'),
    ('project manager', 'Management'),
    ('accounts payable', 'Finance and accounting'),
    ('human resources', 'HR and recruitment'),
    ('sales executive', 'Sales and marketing'),
])
@pytest.mark.parametrize('separator', ['\n', '\r\n', '\t', '   ', '\u00a0'])
def test_tag_phrases_match_across_document_whitespace(phrase, tag, separator):
    assert tags_from_text(separator.join(phrase.upper().split())) == [tag]


@pytest.mark.parametrize('text', [None, '', '\n\t ', 'fictional generic CV',
    'network engineering', 'graphicdesigner', 'data science', 'chef with culinary experience'])
def test_whitespace_normalization_does_not_invent_categories(text):
    assert tags_from_text(text) == []


@pytest.fixture
def library_db(queue_db):
    with queue_db.get_cursor() as (cur, _):
        cur.execute('''ALTER TABLE tenant_companies ADD COLUMN gcs_bucket_name TEXT;
            INSERT INTO tenant_companies(id,gcs_bucket_name) VALUES (1,'fixture-bucket'),(2,'second-company');
            CREATE TABLE resume_uploads(id SERIAL PRIMARY KEY,file_name TEXT,file_path TEXT,file_size INTEGER,
            mime_type TEXT,company_id INTEGER,upload_timestamp TIMESTAMP);
            CREATE TABLE resume_embeddings(id SERIAL PRIMARY KEY,filename TEXT,folder TEXT,storage_bucket TEXT,company_id INTEGER,
            file_size INTEGER,content_type TEXT,extracted_text TEXT,text_length INTEGER,embedding vector(3),
            candidate_years NUMERIC,candidate_location TEXT,candidate_languages TEXT[],candidate_skills TEXT[],profile_source TEXT,
            search_tags TEXT[] DEFAULT '{}',source_uploaded_at TIMESTAMP,source_received_at TIMESTAMPTZ);''')
        for bucket, folder, company, tags, uploaded, received in [
            ('fixture-bucket','Networking/Nov 2026',1,['UI design'],'2026-11-06','2026-04-30T23:59:59Z'),
            ('fixture-bucket','Networking/Nov 2026/sub',1,['Web design'],'2026-11-06',None),
            ('fixture-bucket','Networking/Nov 2026-old',1,['UI design'],'2026-11-06','2026-05-01T00:00:00Z'),
            ('other-bucket','Networking/Nov 2026',1,['UI design'],'2026-01-01','2026-04-30T10:00:00Z'),
            ('fixture-bucket','Networking/Nov 2026',2,['UI design'],'2026-11-06','2026-04-30T10:00:00Z')]:
            cur.execute('''INSERT INTO resume_embeddings(filename,folder,storage_bucket,company_id,file_size,extracted_text,text_length,
                embedding,search_tags,source_uploaded_at,source_received_at) VALUES ('cv.pdf',%s,%s,%s,10,'Figma UI designer',17,
                '[1,0,0]',%s,%s,%s) RETURNING id''',(folder,bucket,company,tags,uploaded,received))
            resume_id=cur.fetchone()['id']
            cur.execute('''INSERT INTO resume_uploads(file_name,file_path,file_size,mime_type,company_id,upload_timestamp)
                VALUES (%s,%s,10,'application/pdf',%s,%s)''',(f'{resume_id}-cv.pdf',f'gs://{bucket}/{folder}/cv.pdf',company,uploaded))
    return queue_db


@pytest.mark.parametrize('advanced', [True, False])
def test_real_sql_folder_bucket_company_and_date_filters_precede_retrieval(library_db, monkeypatch, advanced):
    monkeypatch.setattr(search, '_get_pool', lambda: library_db.pool)
    monkeypatch.setattr(search, '_embed_query', lambda query: [1,0,0])
    monkeypatch.setattr(search, '_advanced_schema_ensured', True)
    monkeypatch.setattr(search, 'ADVANCED_SEARCH_ENABLED', advanced)
    # Nonempty criteria also exercises the supplemental exact-match branch.
    rows=search._vector_search('Required skills: Figma',100,'company_id: ANY("1")',FOLDERS,
        {'tags':['UI design'],'date_from':'2026-04-01','date_to':'2026-04-30','date_basis':'received'})
    assert len(rows)==1 and rows[0]['storage_bucket']=='fixture-bucket' and rows[0]['folder']=='Networking/Nov 2026'
    assert searchable_count(library_db, USER, FOLDERS)==2
    assert searchable_count(library_db, USER, FOLDERS, {'date_basis':'received','date_from':'2026-04-01','date_to':'2026-04-30'})==1


@pytest.mark.parametrize('advanced', [True, False])
def test_normalized_tags_feed_scoped_sql_without_changing_resume_content(library_db, monkeypatch, advanced):
    text = 'Graphic\r\ndesigner with Adobe\tPhotoshop experience'
    with library_db.get_cursor() as (cursor, _):
        cursor.execute('UPDATE resume_embeddings SET extracted_text=%s,text_length=%s,search_tags=%s WHERE id=1',
                       (text, len(text), []))
        cursor.execute("SELECT to_jsonb(e)-'search_tags' AS original FROM resume_embeddings e WHERE id=1")
        original = cursor.fetchone()['original']
        cursor.execute('UPDATE resume_embeddings SET search_tags=%s WHERE id=1', (tags_from_text(text),))
        cursor.execute("SELECT to_jsonb(e)-'search_tags' AS original FROM resume_embeddings e WHERE id=1")
        assert cursor.fetchone()['original'] == original
    monkeypatch.setattr(search, '_get_pool', lambda: library_db.pool)
    monkeypatch.setattr(search, '_embed_query', lambda query: [1, 0, 0])
    monkeypatch.setattr(search, '_advanced_schema_ensured', True)
    monkeypatch.setattr(search, 'ADVANCED_SEARCH_ENABLED', advanced)

    rows = search._vector_search('candidate profiles', 100, 'company_id: ANY("1")', FOLDERS,
        {'tags': ['Graphic design'], 'date_basis': 'received', 'date_from': '2026-04-01', 'date_to': '2026-04-30'})

    assert [row['id'] for row in rows] == ['1']
    assert searchable_count(library_db, USER, FOLDERS, {'tags': ['Graphic design']}) == 1


def test_library_pagination_scope_preview_and_metadata_no_vectors_changed(library_db):
    data=list_uploads(library_db,USER,limit=2)
    assert data['total']==4 and len(data['uploads'])==2
    assert list_uploads(library_db,USER,query='5-cv')['total']==0
    assert list_uploads(library_db,USER,query="%' OR TRUE --")['total']==0
    assert preview_upload(library_db,USER,1)['text']=='Figma UI designer'
    assert preview_upload(library_db,USER,1)['tags']==['UI design']
    with pytest.raises(HTTPException) as denied: preview_upload(library_db,USER,5)
    assert denied.value.status_code==404
    with library_db.get_cursor() as (cur,_):
        cur.execute('SELECT array_agg(embedding::text ORDER BY id) AS vectors FROM resume_embeddings')
        before=cur.fetchone()['vectors']
    refresh_existing_metadata(library_db)
    with library_db.get_cursor() as (cur,_):
        cur.execute('SELECT array_agg(embedding::text ORDER BY id) AS vectors FROM resume_embeddings')
        assert cur.fetchone()['vectors']==before
    assert refresh_existing_metadata(library_db)=={'tagged_records_updated':0,'upload_dates_updated':0}
    assert all(row['total'] <= 2 for row in inventory(library_db,USER))


def test_tag_inventory_counts_only_workspace_records_and_distinguishes_searchable(library_db):
    with library_db.get_cursor() as (cur,_):
        cur.execute('UPDATE resume_embeddings SET embedding=NULL WHERE id=3')
    tags=tag_inventory(library_db,USER)
    assert tags=={'UI design':{'total':3,'searchable':2},'Web design':{'total':1,'searchable':1}}
    assert tag_inventory(library_db,{'user_type':'super_admin'})['UI design']['total']==4
    with pytest.raises(HTTPException): tag_inventory(library_db,{'user_type':'tenant_user'})


@pytest.mark.parametrize('advanced', [True,False])
def test_multiple_tags_and_folders_never_expand_beyond_selected_scope(library_db,monkeypatch,advanced):
    monkeypatch.setattr(search,'_get_pool',lambda:library_db.pool)
    monkeypatch.setattr(search,'_embed_query',lambda query:[1,0,0])
    monkeypatch.setattr(search,'_advanced_schema_ensured',True)
    monkeypatch.setattr(search,'ADVANCED_SEARCH_ENABLED',advanced)
    folders=[*FOLDERS,{'bucket':'fixture-bucket','path':'No CVs here'}]
    rows=search._vector_search('Required skills: Figma',100,'company_id: ANY("1")',folders,
                              {'tags':['UI design','Web design']})
    assert len(rows)==2
    assert {row['folder'] for row in rows}=={'Networking/Nov 2026','Networking/Nov 2026/sub'}
    assert {row['id'] for row in rows}=={'1','2'}


def test_super_admin_library_qualifies_legacy_paths_with_the_record_company(library_db):
    with library_db.get_cursor() as (cur,_):
        cur.execute("UPDATE resume_uploads SET file_path='Networking/Nov 2026/cv.pdf' WHERE id=1")
    admin={'id':1,'user_type':'super_admin'}
    rows=list_uploads(library_db,admin,limit=100,default_bucket='wrong-global')['uploads']
    assert next(row for row in rows if row['id']==1)['file_path']=='gs://fixture-bucket/Networking/Nov 2026/cv.pdf'
    assert preview_upload(library_db,admin,1,default_bucket='wrong-global')['text']=='Figma UI designer'


def test_durable_scope_survives_completion_and_history(queue_db):
    payload={'task_id':'qa-scoped','user_data':{'id':7},'folder_filters':FOLDERS,'resume_filters':{'tags':['UI design']}}
    queue_db.save_hr_scorecard_task('qa-scoped','Full JD','UI designer',10,'7',task_payload=payload)
    claim=queue_db.claim_next_hr_task()
    owned=queue_db.get_owned_hr_task('qa-scoped',claim['lease_token'])
    assert owned['task_payload']==payload
    search_id=queue_db.complete_hr_task('qa-scoped',[],{},claim['lease_token'])
    context=queue_db.get_search_context(search_id)
    assert context['folder_filters']==FOLDERS and context['resume_filters']=={'tags':['UI design']}


def test_empty_explicit_scope_completes_without_paid_preparation(library_db, monkeypatch):
    monkeypatch.setattr(main,'get_db_manager',lambda:library_db)
    library_db.save_hr_scorecard_task('qa-empty','Figma designer','UI',10,'7',company_id=1,
        task_payload={'task_id':'qa-empty','user_data':{'id':7},'company_id':1,
                      'folder_filters':[{'bucket':'fixture-bucket','path':'Missing folder'}]})
    claim=library_db.claim_next_hr_task()
    from services.task_lease import current_lease
    async def run():
        token=current_lease.set(('qa-empty',claim['lease_token']))
        try:
            with patch.object(main,'_prepare_search_input',side_effect=AssertionError('No paid preparation')):
                with patch.object(library_db,'get_hr_task_user',return_value=USER):
                    result=await main.run_hr_scorecard_task(claim['task_payload'])
            assert result['success'] and result['results']==0
        finally:current_lease.reset(token)
    asyncio.run(run())
    assert library_db.get_task_status('qa-empty')['status']=='completed'


def test_vector_cache_distinguishes_folders_and_tags(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    main._search_cache_clear()
    client=MagicMock();client.search.return_value=SimpleNamespace(results=[])
    with patch.object(main,'get_company_resources',return_value=('fixture-bucket','fixture-store')), patch.object(main,'get_search_client',return_value=client):
        for filters in ['{"tags":["UI design"]}', '{"tags":["Management"]}', '{"tags":["UI design"]}']:
            asyncio.run(main.search_vector(query='designer',result_count=10,user=USER,filters=filters))
        asyncio.run(main.search_vector(query='designer',result_count=10,user=USER,folders='[{"bucket":"fixture-bucket","path":"New"}]'))
        asyncio.run(main.search_vector(query='designer',result_count=10,user=USER,folders='[{"bucket":"fixture-bucket","path":"Old"}]'))
    assert client.search.call_count==4
    main._search_cache_clear()


@pytest.mark.parametrize('endpoint', ['/api/hr-scorecard-search','/api/search-vector'])
def test_http_explicit_empty_folders_cannot_create_a_wide_search(api, endpoint, monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    response=client.post(endpoint,data={'query':'Figma designer','folders':'[]'})
    assert response.status_code==422
    db.save_hr_scorecard_task.assert_not_called()


@pytest.mark.parametrize('endpoint', ['/api/resume-library','/api/resume-folders','/api/resume-library/1'])
def test_library_requires_login(api,endpoint):
    client,db=api;db.verify_session.return_value=None
    assert client.get(endpoint).status_code==401


def test_cloud_deployment_refuses_unsupported_scope_instead_of_ignoring_it(monkeypatch):
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','0')
    with pytest.raises(HTTPException):main._folder_request_options(FOLDERS)
    with pytest.raises(HTTPException):main._folder_request_options(None,{'tags':['UI design']})
