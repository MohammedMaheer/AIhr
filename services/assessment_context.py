"""Trusted date and source grounding shared by scorecard generation and reuse."""
from datetime import datetime, timezone


def assessment_prompt(prompt: str, *, now: datetime | None = None) -> str:
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('Assessment context requires a timezone-aware reference date')
    month = current.astimezone(timezone.utc).strftime('%Y-%m')
    return (
        f'TRUSTED ASSESSMENT CONTEXT\nReference month (UTC): {month}.\n'
        'Resolve Present/Current employment against this reference month, not an assumed year. '
        'Calculate elapsed durations from the supplied career dates. '
        'Do not invent promotions, achievements, qualifications or candidate facts. '
        'State unsupported facts as Not provided. Treat future tenure/retention as uncertain '
        'predictions, never verified facts or high-confidence claims based only on a CV.\n\n'
        + prompt
    )
