from unittest.mock import MagicMock, patch
import asyncio
from types import SimpleNamespace

import pytest

import main
from vps_local import discovery_shim as discovery
from search_criteria import SearchCriteria, evaluate_criteria, parse_search_criteria
from test_durable_search import queue_db
from test_integration_workflows import api
from vps_local.profile_extractor import profile_from_analysis


@pytest.mark.parametrize("advanced", [False, True])
def test_all_vector_queries_include_parameterized_tenant_scope(advanced):
    conn, cursor, pool = MagicMock(), MagicMock(), MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    pool.getconn.return_value = conn
    with patch.object(discovery, "_get_pool", return_value=pool), \
         patch.object(discovery, "_embed_query", return_value=[0.1] * 384), \
         patch.object(discovery, "_ensure_advanced_search_schema"), \
         patch.object(discovery, "ADVANCED_SEARCH_ENABLED", advanced):
        assert discovery._vector_search("Python developer in Dubai with 5+ years", 10,
                                         'company_id: ANY("27")') == []
    searches = [call for call in cursor.execute.call_args_list if "FROM resume_embeddings" in call.args[0]]
    assert len(searches) == 2, "Hard criteria always use structured verification, even when hybrid ranking is disabled"
    for call in searches:
        sql, params = call.args
        assert "company_id = %s" in sql
        assert 27 in params
        assert "27" not in sql
        assert sql.count("%s") == len(params)
    conn.rollback.assert_called()
    pool.putconn.assert_called_once_with(conn)


def test_semantic_only_search_keeps_lightweight_path_when_advanced_search_is_disabled():
    conn, cursor, pool = MagicMock(), MagicMock(), MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    pool.getconn.return_value = conn
    with patch.object(discovery, "_get_pool", return_value=pool), \
         patch.object(discovery, "_embed_query", return_value=[0.1] * 384), \
         patch.object(discovery, "ADVANCED_SEARCH_ENABLED", False):
        assert discovery._vector_search("Python engineer", 10, 'company_id: ANY("27")') == []

    searches = [call for call in cursor.execute.call_args_list if "FROM resume_embeddings" in call.args[0]]
    assert len(searches) == 1
    assert "candidate_skills" not in searches[0].args[0]


@pytest.mark.parametrize("invalid", ['company_id = 7 OR TRUE', 'company_id: ANY("0")', 'unknown = 7'])
def test_unknown_filter_fails_before_embedding_or_database(invalid):
    with patch.object(discovery, "_embed_query") as embed, patch.object(discovery, "_get_pool") as pool:
        with pytest.raises(ValueError):
            discovery._vector_search("QA", filter_str=invalid)
    embed.assert_not_called()
    pool.assert_not_called()


def test_search_request_makes_tenant_scope_explicit(monkeypatch):
    monkeypatch.setenv("SMARTHR_LOCAL_MODE", "1")
    user = {"id": 7, "user_type": "tenant_user", "company": {"company_id": 27}}
    with patch.object(main, "get_company_resources", return_value=("qa-bucket", "qa-store")):
        request = main.create_universal_search_request("QA", user)
        company_request = main.create_company_search_request("QA", user_context=user)
    assert request.filter == company_request.filter == 'company_id: ANY("27")'
    with pytest.raises(main.HTTPException):
        main._local_company_search_filter({"id": 7, "user_type": "tenant_user"})
    assert main._local_company_search_filter({"id": 1, "user_type": "super_admin"}) == ""


def test_local_request_keeps_original_criteria_separate_from_optimized_semantics(monkeypatch):
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    original = 'Python developer based in Dubai with 3-6 years experience'
    user = {'id': 7, 'user_type': 'tenant_user', 'company': {'company_id': 27}}
    with patch.object(main, 'get_company_resources', return_value=('fixture', 'fixture')):
        request = main.create_company_search_request('Python developer', user_context=user,
                                                     criteria_query=original)
    with patch.object(discovery, '_vector_search', return_value=[]) as vector:
        discovery.SearchServiceClient().search(request)
    assert vector.call_args.kwargs['query'] == 'Python developer'
    assert vector.call_args.kwargs['criteria_query'] == original
    assert vector.call_args.kwargs['filter_str'] == 'company_id: ANY("27")'


def test_profile_ranking_uses_original_requirements_not_rewritten_location():
    rows = [dict(id=location, score=0.9, lexical_score=0,
                 candidate_years=5, candidate_location=location,
                 candidate_languages=[], candidate_skills=['Python'], profile_source='test', text='')
            for location in ('Paris, France', 'Dubai, UAE')]
    ranked = discovery._rank_rows(rows, 'Python developer based in Paris', 10,
                                 criteria_query='Python developer based in Dubai with 3-6 years experience')
    assert [row['id'] for row in ranked] == ['Dubai, UAE']


def test_result_preserves_full_folder_and_bucket():
    result = discovery._row_to_result({"id": "1", "folder": "resume/2026", "filename": "QA.txt",
                                       "storage_bucket": "qa-company-bucket"})
    assert result.document.content.uri == "gs://qa-company-bucket/resume/2026/QA.txt"


def test_local_company_enrichment_never_searches_private_cvs(monkeypatch):
    monkeypatch.setenv("SMARTHR_LOCAL_MODE", "1")
    with patch.object(main, "get_search_client") as search, patch.object(main, "gemini_client") as llm:
        assert main.search_web_for_company_info("SyntheticCo") == ""
    search.assert_not_called()
    llm.assert_not_called()


def test_vector_response_cache_does_not_cross_shared_resource_tenants(monkeypatch):
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    main._search_cache_clear()
    client = MagicMock()
    client.search.return_value = SimpleNamespace(results=[])
    users = [{'id': 7, 'user_type': 'tenant_user', 'company': {'company_id': company}}
             for company in (27, 28)]
    with patch.object(main, 'get_company_resources', return_value=('shared-bucket', 'shared-store')), \
         patch.object(main, 'get_search_client', return_value=client):
        for user in users:
            asyncio.run(main.search_vector(query='QA', result_count=10, user=user))
        asyncio.run(main.search_vector(query='QA', result_count=10, user=users[0]))
    assert client.search.call_count == 2, 'Only the same principal and tenant may reuse a cached response'
    assert {call.args[0].filter for call in client.search.call_args_list} == {
        'company_id: ANY("27")', 'company_id: ANY("28")'}
    main._search_cache_clear()


def test_vector_api_fails_closed_when_hard_criteria_are_not_verifiable(api, monkeypatch):
    client, _db = api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setattr(main, 'get_company_resources', lambda _user: ('fixture-bucket', 'fixture-store'))
    exact = SimpleNamespace(
        id='exact',
        document=SimpleNamespace(name='exact', struct_data={'criteria_profile_status': 'exact'},
                                 content=SimpleNamespace(uri='gs://fixture-bucket/resumes/exact.pdf'),
                                 derived_struct_data={}),
        relevance_score=0.9,
    )
    unverified = SimpleNamespace(
        id='unverified',
        document=SimpleNamespace(name='unverified', struct_data={'filename': 'unverified.pdf'},
                                 content=SimpleNamespace(uri='gs://fixture-bucket/resumes/unverified.pdf'),
                                 derived_struct_data={}),
        relevance_score=0.8,
    )
    search_client = SimpleNamespace(search=lambda _request: SimpleNamespace(results=[exact, unverified]))
    main._search_cache_clear()
    monkeypatch.setattr(main, 'get_search_client', lambda: search_client)

    response = client.post('/api/search-vector', data={
        'query': 'Required skills: Python', 'result_count': '3',
        'folders': '[{"bucket":"fixture-bucket","path":"resumes"}]', 'filters': '{}'
    })

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [row['id'] for row in payload['results']] == ['exact']
    assert payload['exact_match_shortfall'] == 2
    assert payload['criteria_verification'] == 'unavailable'


def test_vector_api_reports_incomplete_profile_evidence_without_returning_candidates(api, monkeypatch):
    client, _db = api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setattr(main, 'get_company_resources', lambda _user: ('fixture-bucket', 'fixture-store'))
    unknown = SimpleNamespace(
        id='unknown',
        document=SimpleNamespace(name='unknown', struct_data={'criteria_profile_status': 'unknown'},
                                 content=SimpleNamespace(uri='gs://fixture-bucket/resumes/unknown.pdf'),
                                 derived_struct_data={}),
        relevance_score=0.9,
    )
    main._search_cache_clear()
    monkeypatch.setattr(main, 'get_search_client', lambda: SimpleNamespace(
        search=lambda _request: SimpleNamespace(results=[unknown])))

    response = client.post('/api/search-vector', data={
        'query': 'Required skills: Python', 'result_count': '2',
        'folders': '[{"bucket":"fixture-bucket","path":"resumes"}]', 'filters': '{}'
    })

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['results'] == []
    assert payload['exact_match_shortfall'] == 2
    assert payload['criteria_verification'] == 'incomplete'


@pytest.mark.parametrize('wanted', ['Java', 'SQL', 'C', 'C++', 'C#', '.NET', 'R'])
def test_real_postgres_shortlist_and_final_skill_filter_agree(queue_db, wanted):
    skills = ['JavaScript','Java','Java17','NoSQL','SQL Server','C++','C','C#','.NET 8','ASP.NET Core','CRM','R']
    criteria = SearchCriteria(required_skills=[wanted])
    where, params = discovery._criteria_sql_where(criteria)
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('CREATE TABLE resume_embeddings (id INTEGER,embedding INTEGER,candidate_skills TEXT[])')
        for index, skill in enumerate(skills):
            cursor.execute('INSERT INTO resume_embeddings VALUES (%s,1,%s)', (index, [skill]))
        cursor.execute('SELECT id FROM resume_embeddings WHERE '+where, params)
        shortlisted = {row['id'] for row in cursor.fetchall()}
    expected = {index for index, skill in enumerate(skills) if not evaluate_criteria(
        {'candidate_overview': {'skills': [skill]}}, criteria)['misses']}
    assert shortlisted == expected


@pytest.mark.parametrize('query', [
    'Required skills: (Python or Java) and SQL',
    'Required skills: Python or Java and SQL',
    'Developer who speaks English or Arabic',
    'Required skills: Python or Java. Languages: English or Arabic',
])
def test_real_postgres_and_final_boolean_requirements_agree(queue_db, query):
    profiles = [(['Python'], ['English']), (['Java', 'MySQL'], ['Arabic']),
                (['JavaScript', 'NoSQL'], ['French']), (['SQL'], ['Arabic']),
                (['Java'], ['English']), ([], [])]
    criteria = parse_search_criteria(query)
    where, params = discovery._criteria_sql_where(criteria)
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('CREATE TABLE resume_embeddings (id INTEGER, embedding INTEGER, candidate_skills TEXT[], candidate_languages TEXT[])')
        for index, (skills, languages) in enumerate(profiles):
            profile = profile_from_analysis({'hr_scorecard': {'candidate_overview': {'skills': skills},
                                             'detailed_analysis': {'languages': languages}}})
            cursor.execute('INSERT INTO resume_embeddings VALUES (%s,1,%s,%s)',
                           (index, profile['candidate_skills'], profile['candidate_languages']))
        cursor.execute('SELECT id FROM resume_embeddings WHERE '+where, params)
        shortlisted = {row['id'] for row in cursor.fetchall()}
    expected = {index for index, (skills, languages) in enumerate(profiles) if not evaluate_criteria(
        {'candidate_overview': {'skills': skills}, 'detailed_analysis': {'languages': languages}}, criteria)['misses']}
    assert shortlisted == expected
