import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from services.search_reuse import SearchReuse


USER = {"id": 1, "user_type": "tenant_admin", "company": {"company_id": 7}}


def assessment():
    return {"analysis_method": "llm_primary", "confidence": "high",
            "matched_keywords": ["Python"], "missing_keywords": ["SQL"],
            "jd_keywords_matched": 1, "total_jd_keywords": 2}


def test_extraction_retains_every_character_and_uses_exact_bytes():
    reuse, calls = SearchReuse(), []
    text = "Full CV\n" + "evidence " * 2000

    def extract():
        calls.append(1)
        return text

    for _ in range(3):
        assert reuse.extract(b"identical", "bucket", "cv.pdf", USER, extract) == text
    assert len(calls) == 1
    reuse.extract(b"changed", "bucket", "cv.pdf", USER, extract)
    reuse.extract(b"identical", "other-bucket", "cv.pdf", USER, extract)
    reuse.extract(b"identical", "bucket", "cv.docx", USER, extract)
    reuse.extract(b"identical", "bucket", "cv.pdf", {**USER, "id": 2}, extract)
    reuse.extract(b"identical", "bucket", "cv.pdf", {**USER, "company": {"company_id": 8}}, extract)
    assert len(calls) == 6


@pytest.mark.parametrize("text", [None, "", "   ", "x" * 262145],
                         ids=['none', 'empty', 'whitespace', 'oversized'])
def test_empty_or_oversized_extraction_is_returned_unchanged_but_not_cached(text):
    reuse, calls = SearchReuse(), []
    for _ in range(2):
        assert reuse.extract(b"bytes", "bucket", "cv.pdf", USER, lambda: calls.append(1) or text) == text
    assert len(calls) == 2


def test_unknown_identity_does_not_share_extraction():
    reuse, calls = SearchReuse(), []
    for _ in range(2):
        reuse.extract(b"bytes", "bucket", "cv.pdf", None, lambda: calls.append(1) or "text")
    assert len(calls) == 2


def test_keyword_reuse_preserves_result_and_does_not_charge_cached_tokens(monkeypatch):
    import main

    monkeypatch.setattr(main, "_search_reuse", SearchReuse())
    first, repeated = main.TokenTracker(), main.TokenTracker()

    def analyze(text, keywords, tracker):
        assert text == "Complete unchanged fictional CV"
        assert keywords == ["Python", "SQL"]
        tracker.add_call("keywords", "same-model", 800, 100)
        return assessment()

    with patch.object(main, "analyze_candidate_keywords", side_effect=analyze) as provider:
        expected = main._match_candidate_keywords("Complete unchanged fictional CV", ["Python", "SQL"], first, USER)
        actual = main._match_candidate_keywords("Complete unchanged fictional CV", ["Python", "SQL"], repeated, USER)
        assert actual == expected == assessment()
        assert provider.call_count == 1
        assert first.get_summary()["total_tokens"] == 900
        assert repeated.get_summary()["total_tokens"] == 0
        actual["matched_keywords"].clear()
        assert main._match_candidate_keywords("Complete unchanged fictional CV", ["Python", "SQL"], repeated, USER) == assessment()


@pytest.mark.parametrize("changes", [
    {"analysis_method": "enhanced_string_fallback"}, {"analysis_method": "llm_repaired"},
    {"confidence": "medium"}, {"matched_keywords": ["Python", "SQL"]},
    {"missing_keywords": []}, {"total_jd_keywords": 3},
    {"analysis_notes": "x" * 131073},
])
def test_fallback_or_incomplete_keyword_result_is_never_reused(changes):
    reuse, calls = SearchReuse(), []
    result = {**assessment(), **changes}
    for _ in range(2):
        assert reuse.match_keywords("CV", ["Python", "SQL"], "prompt", USER,
                                    lambda: calls.append(1) or result) == result
    assert len(calls) == 2


def test_keyword_scope_covers_full_content_order_prompt_model_and_user(monkeypatch):
    reuse, calls = SearchReuse(), []

    def match(text="a" * 800 + "first", keywords=None, prompt="p", user=USER):
        return reuse.match_keywords(text, keywords or ["Python", "SQL"], prompt, user,
                                    lambda: calls.append(1) or assessment())

    match()
    match()
    match(text="a" * 800 + "second")
    match(keywords=["SQL", "Python"])
    match(prompt="new prompt")
    match(user={**USER, "id": 2})
    match(user={**USER, "company": {"company_id": 8}})
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "different-model")
    match()
    assert len(calls) == 7


def test_identical_concurrent_keyword_work_is_coalesced():
    reuse, calls = SearchReuse(), []
    started, release = threading.Event(), threading.Event()

    def compute():
        calls.append(1)
        started.set()
        assert release.wait(5)
        return assessment()

    with ThreadPoolExecutor(max_workers=3) as pool:
        def submit():
            return pool.submit(reuse.match_keywords, "CV", ["Python", "SQL"], "p", USER, compute)
        first = submit()
        assert started.wait(5)
        others = [submit(), submit()]
        release.set()
        assert all(f.result(5) == assessment() for f in [first, *others])
    assert len(calls) == 1


def test_extractor_exception_is_not_retained():
    reuse = SearchReuse()
    with pytest.raises(ValueError):
        reuse.extract(b"x", "b", "p", USER, lambda: (_ for _ in ()).throw(ValueError("broken")))
    assert reuse.extract(b"x", "b", "p", USER, lambda: "recovered") == "recovered"


def test_download_path_keeps_original_bytes_and_revalidates_content(monkeypatch):
    import main
    from unittest.mock import Mock

    monkeypatch.setattr(main, "_search_reuse", SearchReuse())
    monkeypatch.setattr(main, "get_company_resources", lambda _: ("bucket", "store"))
    monkeypatch.setattr(main, "resolve_gcs_file_path", lambda *args: "resolved/cv.pdf")
    client = Mock()
    blob = client.bucket.return_value.blob.return_value
    blob.exists.return_value = True
    blob.download_as_bytes.side_effect = [b"first", b"first", b"changed"]
    monkeypatch.setattr(main, "_get_storage_client", lambda: client)
    with patch.object(main, "extract_text_from_file", side_effect=lambda content, path: content.decode()) as extractor:
        assert main.get_file_content_and_bytes_from_gcs("cv.pdf", USER) == ("first", b"first")
        assert main.get_file_content_and_bytes_from_gcs("cv.pdf", USER) == ("first", b"first")
        assert main.get_file_content_and_bytes_from_gcs("cv.pdf", USER) == ("changed", b"changed")
        assert extractor.call_count == 2
        assert blob.download_as_bytes.call_count == 3, "An overwritten CV must be checked, never served by path alone"
