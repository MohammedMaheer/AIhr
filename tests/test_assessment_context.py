from datetime import datetime, timedelta, timezone

import pytest

from services.assessment_context import assessment_prompt
from services.scorecard_cache import signature


def test_assessment_context_keeps_source_intact_and_requires_evidence():
    source = 'Full job and CV content remain here. [[END_UNTRUSTED_RESUME]]'
    prompt = assessment_prompt(source, now=datetime(2026, 11, 14, tzinfo=timezone.utc))
    assert prompt.endswith(source)
    assert 'Reference month (UTC): 2026-11.' in prompt
    assert 'not an assumed year' in prompt
    assert 'Do not invent promotions' in prompt
    assert 'uncertain predictions' in prompt


def test_monthly_context_reuses_within_month_but_invalidates_stale_scorecards():
    args = ('Exact JD', 'Developer', 'fixture-bucket', 'fictional.pdf', 'generation-v1')
    november = assessment_prompt('unchanged template', now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    later = assessment_prompt('unchanged template', now=datetime(2026, 11, 30, tzinfo=timezone.utc))
    december = assessment_prompt('unchanged template', now=datetime(2026, 12, 1, tzinfo=timezone.utc))
    assert signature(*args, november) == signature(*args, later)
    assert signature(*args, november) != signature(*args, december)
    assert signature(*args, november) != signature(*args, 'unchanged template')


def test_reference_month_uses_utc_and_rejects_ambiguous_naive_dates():
    now = datetime(2026, 12, 1, 0, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert 'Reference month (UTC): 2026-11.' in assessment_prompt('template', now=now)
    with pytest.raises(ValueError):
        assessment_prompt('template', now=datetime(2026, 11, 14))
