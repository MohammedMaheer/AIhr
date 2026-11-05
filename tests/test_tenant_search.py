from unittest.mock import MagicMock, patch
import asyncio
from types import SimpleNamespace

import pytest

import main
from vps_local import discovery_shim as discovery
from search_criteria import SearchCriteria, evaluate_criteria, parse_search_criteria
from test_durable_search import queue_db
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
    assert len(searches) == (2 if advanced else 1)
    for call in searches:
        sql, params = call.args
        assert "company_id = %s" in sql
        assert 27 in params
        assert "27" not in sql
        assert sql.count("%s") == len(params)
    conn.rollback.assert_called()
    pool.putconn.assert_called_once_with(conn)


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
