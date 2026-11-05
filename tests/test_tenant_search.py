from unittest.mock import MagicMock, patch

import pytest

import main
from vps_local import discovery_shim as discovery


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
