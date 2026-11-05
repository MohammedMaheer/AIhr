"""Validate local interview times before any provider side effects."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utc_start(data):
    try:
        start = datetime.fromisoformat(f"{data['interview_date']}T{data.get('interview_time') or '09:00'}")
        duration = data.get("duration")
        if duration is None or duration == '':
            duration = 30
        if isinstance(duration, str):
            duration = duration.strip()
            if not duration.isascii() or not duration.isdecimal() or len(duration) > 3:
                raise ValueError()
            duration = int(duration)
        if type(duration) is not int or not 1 <= duration <= 480:
            raise ValueError()
        zone = ZoneInfo(data.get("time_zone") or "UTC")
        if start.tzinfo is not None:
            raise ValueError()
        local = start.replace(tzinfo=zone)
        utc = local.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) != start:
            raise ValueError("Nonexistent local time")
        return utc.isoformat(), duration
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Provide a valid interview date, time, timezone and duration (1-480 minutes).") from exc
