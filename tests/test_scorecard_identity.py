"""Cache identity checks need no provider credentials, model or database."""
from services.scorecard_cache import signature


ARGS = ('Full role', 'Engineer', 'fixture-bucket', 'cv.pdf', 'generation-1', 'scorecard-v1')


def test_identical_assessment_inputs_reuse_signature():
    options = dict(keywords=['Python', 'SQL'], auxiliary_prompts=('entity-v1', 'matching-v1'))
    assert signature(*ARGS, **options) == signature(*ARGS, **options)


def test_changed_keyword_evidence_does_not_reuse_a_scorecard():
    original = signature(*ARGS, keywords=['Python', 'SQL'])
    assert signature(*ARGS, keywords=['Python', 'Java']) != original
    assert signature(*ARGS, keywords=['SQL', 'Python']) != original
    assert signature(*ARGS, keywords=[]) != original


def test_changed_auxiliary_prompt_does_not_reuse_a_scorecard():
    original = signature(*ARGS, auxiliary_prompts=('entity-v1', 'matching-v1'))
    assert signature(*ARGS, auxiliary_prompts=('entity-v2', 'matching-v1')) != original
    assert signature(*ARGS, auxiliary_prompts=('entity-v1', 'matching-v2')) != original


def test_missing_resume_generation_still_bypasses_cache():
    assert signature(*ARGS[:4], None, ARGS[5], keywords=['Python']) is None


def test_provider_normalization_still_separates_actual_deepseek_models(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', ' DeepSeek ')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'first-model')
    first = signature(*ARGS)
    monkeypatch.setenv('LLM_PROVIDER', 'deepseek')
    assert signature(*ARGS) == first
    monkeypatch.setenv('DEEPSEEK_MODEL', 'second-model')
    assert signature(*ARGS) != first
