import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from services.llm_cache import PreparationCache


USER = {"id": 1, "user_type": "tenant_admin", "company": {"company_id": 7}}


def test_full_query_operation_user_and_company_are_part_of_key():
    key = PreparationCache.key("query", "a" * 600 + "python", USER)
    assert key != PreparationCache.key("query", "a" * 600 + "java", USER)
    assert key != PreparationCache.key("keywords", "a" * 600 + "python", USER)
    assert key != PreparationCache.key("query", "a" * 600 + "python", {**USER, "id": 2})
    assert key != PreparationCache.key("query", "a" * 600 + "python", {**USER, "company": {"company_id": 8}})


def test_missing_identity_or_company_bypasses_cache():
    assert PreparationCache.key("query", "python", {}) is None
    assert PreparationCache.key("query", "python", {"id": 1, "user_type": "tenant_admin"}) is None
    assert PreparationCache.key("query", "python", {"id": 1, "user_type": "super_admin"})


def test_reuse_preserves_payload_and_returns_independent_copies():
    cache = PreparationCache()
    original = {"success": True, "keywords": ["Python", "PostgreSQL"]}
    first = cache.get_or_compute("key", lambda: original, lambda _: True)
    first["keywords"].clear()
    second = cache.get_or_compute("key", lambda: pytest.fail("unexpected API call"), lambda _: True)
    assert second == {"success": True, "keywords": ["Python", "PostgreSQL"]}
    second["keywords"].append("other")
    assert len(cache.get_or_compute("key", lambda: {}, lambda _: True)["keywords"]) == 2


def test_failure_is_not_cached_and_next_request_can_recover():
    cache = PreparationCache()
    with pytest.raises(ValueError):
        cache.get_or_compute("key", lambda: (_ for _ in ()).throw(ValueError("provider failed")), lambda _: True)
    assert cache.get_or_compute("key", lambda: {"success": True}, lambda _: True)["success"]
    assert not cache._pending


def test_fallback_result_is_not_persisted():
    cache = PreparationCache()
    cache.get_or_compute("key", lambda: {"success": False}, lambda _: False)
    assert cache.get_or_compute("key", lambda: {"fresh": True}, lambda _: True) == {"fresh": True}


def test_expiry_and_lru_bound():
    now = [0]
    cache = PreparationCache(max_entries=2, ttl_seconds=10, clock=lambda: now[0])
    for key in ("a", "b", "c"):
        cache.get_or_compute(key, lambda: {}, lambda _: True)
    assert list(cache._entries) == ["b", "c"]
    now[0] = 11
    cache.get_or_compute("fresh", lambda: {}, lambda _: True)
    assert list(cache._entries) == ["fresh"]


def test_parallel_identical_requests_make_one_provider_call():
    cache = PreparationCache()
    started = threading.Event()
    release = threading.Event()
    calls = []

    def compute():
        calls.append(1)
        started.set()
        assert release.wait(5)
        return {"success": True, "keywords": ["Python"]}

    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(cache.get_or_compute, "same", compute, lambda _: True)
        assert started.wait(5)
        others = [pool.submit(cache.get_or_compute, "same", compute, lambda _: True) for _ in range(3)]
        release.set()
        results = [future.result(5) for future in [first, *others]]
    assert calls == [1]
    assert all(value == results[0] for value in results)


def test_disabled_cache_always_computes():
    calls = []
    cache = PreparationCache(max_entries=0)
    for _ in range(2):
        cache.get_or_compute("same", lambda: calls.append(1) or {}, lambda _: True)
    assert len(calls) == 2


def test_different_queries_do_not_wait_for_each_other():
    cache = PreparationCache()
    started = threading.Event()
    release = threading.Event()

    def slow_compute():
        started.set()
        assert release.wait(5)
        return {"slow": True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(cache.get_or_compute, "slow", slow_compute, lambda _: True)
        assert started.wait(5)
        fast = pool.submit(cache.get_or_compute, "other", lambda: {"fast": True}, lambda _: True)
        try:
            assert fast.result(2) == {"fast": True}
        finally:
            release.set()
        assert slow.result(5) == {"slow": True}


def test_fallback_and_missing_fields_in_main_preparation_are_retried(monkeypatch):
    import main

    monkeypatch.setattr(main, "_jd_preparation_cache", PreparationCache())
    results = iter([
        {"success": True, "fallback_used": True, "all_keywords": ["Python"]},
        {"success": True, "all_keywords": []},
        {"success": True, "all_keywords": ["Python"]},
    ])
    monkeypatch.setattr(main, "extract_standardized_keywords_from_jd", lambda *_: next(results))
    assert main._prepare_search_input("keywords", "Python", USER)["fallback_used"]
    assert not main._prepare_search_input("keywords", "Python", USER)["all_keywords"]
    assert main._prepare_search_input("keywords", "Python", USER)["all_keywords"] == ["Python"]
    assert main._prepare_search_input("keywords", "Python", USER)["all_keywords"] == ["Python"]


def test_main_preparation_reuses_both_operations_without_counting_cached_tokens(monkeypatch):
    import main

    monkeypatch.setattr(main, "_jd_preparation_cache", PreparationCache())
    calls = []

    def compute(query, tracker):
        calls.append(query)
        tracker.add_call("preparation", "same-model", 100, 30)
        return {"success": True, "all_keywords": ["Python"], "optimized_query": "Python developer"}

    monkeypatch.setattr(main, "extract_standardized_keywords_from_jd", compute)
    monkeypatch.setattr(main, "extract_keywords_for_single_query", compute)
    first, repeated = main.TokenTracker(), main.TokenTracker()
    for operation in ("keywords", "query"):
        initial = main._prepare_search_input(operation, "Python developer", USER, first)
        cached = main._prepare_search_input(operation, "Python developer", USER, repeated)
        assert initial == cached
    assert len(calls) == 2
    assert first.get_summary()["total_tokens"] == 260
    assert repeated.get_summary()["total_tokens"] == 0


def test_company_preparation_is_explicit_and_does_not_share_document_caches():
    peer = {**USER, 'id': 2, 'user_type': 'tenant_user'}
    for operation in ('query', 'keywords'):
        assert PreparationCache.key(operation, 'Exact JD', USER, company_preparation=True) == PreparationCache.key(
            operation, 'Exact JD', peer, company_preparation=True)
        assert PreparationCache.key(operation, 'Exact JD', USER) != PreparationCache.key(operation, 'Exact JD', peer)
    assert PreparationCache.key('document-text-v1', 'Exact bytes', USER, company_preparation=True) != PreparationCache.key(
        'document-text-v1', 'Exact bytes', peer, company_preparation=True)
    assert PreparationCache.key('keywords', 'Exact JD', USER, company_preparation=True) != PreparationCache.key(
        'keywords', 'Exact JD changed', peer, company_preparation=True)


def test_company_preparation_keeps_provider_model_and_operation_separate(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'deepseek')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'model-one')
    original = PreparationCache.key('keywords', 'Exact JD', USER, company_preparation=True)
    assert original != PreparationCache.key('query', 'Exact JD', USER, company_preparation=True)
    monkeypatch.setenv('DEEPSEEK_MODEL', 'model-two')
    assert original != PreparationCache.key('keywords', 'Exact JD', USER, company_preparation=True)
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    assert original != PreparationCache.key('keywords', 'Exact JD', USER, company_preparation=True)


@pytest.mark.parametrize('user', [
    {**USER, 'company': {'company_id': 8}},
    {**USER, 'user_type': 'super_admin'},
    {**USER, 'company': {'company_code': 'no-verified-id'}},
    {**USER, 'company': {'company_id': True}},
    {**USER, 'company': {'company_id': '9' * 5000}},
])
def test_company_preparation_never_crosses_unverified_scope(user):
    peer = {**user, 'id': 2}
    original = PreparationCache.key('keywords', 'Exact JD', USER, company_preparation=True)
    changed = PreparationCache.key('keywords', 'Exact JD', peer, company_preparation=True)
    assert original != changed
    if user.get('user_type') == 'super_admin' or not isinstance((user.get('company') or {}).get('company_id'), int):
        assert PreparationCache.key('keywords', 'Exact JD', user, company_preparation=True) != changed


def test_team_reuses_exact_preparation_without_changing_outputs_or_charging_tokens(monkeypatch):
    import main
    monkeypatch.setattr(main, '_jd_preparation_cache', PreparationCache())
    calls = []
    def prepare(query, tracker):
        calls.append(query)
        tracker.add_call('preparation', 'unchanged-model', 1000, 200)
        return {'success': True, 'all_keywords': ['Python', 'SQL'], 'optimized_query': query}
    monkeypatch.setattr(main, 'extract_standardized_keywords_from_jd', prepare)
    monkeypatch.setattr(main, 'extract_keywords_for_single_query', prepare)
    first, peer = main.TokenTracker(), main.TokenTracker()
    for operation in ('keywords', 'query'):
        original = main._prepare_search_input(operation, 'Same complete original JD', USER, first)
        repeated = main._prepare_search_input(operation, 'Same complete original JD', {**USER, 'id': 2, 'user_type': 'tenant_user'}, peer)
        assert original == repeated
    assert len(calls) == 2
    assert first.get_summary()['total_tokens'] == 2400
    assert peer.get_summary()['total_tokens'] == 0
    other = main.TokenTracker()
    main._prepare_search_input('keywords', 'Same complete original JD', {**USER, 'company': {'company_id': 8}}, other)
    assert len(calls) == 3 and other.get_summary()['total_tokens'] == 1200
