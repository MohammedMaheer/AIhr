"""Validate outreach inputs before mail/calendar side effects."""
from email.errors import HeaderParseError
from email.headerregistry import Address
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TRANSPORTS = {'auto', 'smtp', 'gmail', 'google', 'microsoft', 'graph', 'teams', 'outlook'}
PROVIDERS = {'none', 'in_person', 'in-person', 'phone', 'teams', 'microsoft', 'ms_teams',
             'ms-teams', 'meet', 'google', 'google_meet', 'google-meet'}


def text_fields(data, fields):
    for field, limit in fields.items():
        value = data.get(field)
        if value is None:
            data[field] = ''
        elif not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"Field '{field}' must be text of at most {limit} characters")


def optional_id(value, field):
    if value is None or value == '':
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value.isascii() or not value.isdecimal() or len(value) > 10:
            raise ValueError(f"Field '{field}' must be a positive record ID")
        value = int(value)
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError(f"Field '{field}' must be a positive record ID")
    return value


def address(value, *, required=False):
    if not value:
        if required:
            raise ValueError('candidate_email is required')
        return ''
    try:
        if '\r' in value or '\n' in value:
            raise ValueError()
        parsed = Address(addr_spec=value.strip())
        if not (parsed.username and parsed.domain):
            raise ValueError()
        return parsed.addr_spec
    except (ValueError, IndexError, HeaderParseError):
        raise ValueError('Candidate email must be a single valid email address') from None


def validate_interview(data):
    text_fields(data, {'candidate_name': 255, 'candidate_email': 255, 'position': 500,
                      'location': 2000, 'notes': 10000, 'custom_message': 8192,
                      'interviewer': 500, 'interview_date': 32, 'interview_time': 32,
                      'time_zone': 128, 'interview_type': 100, 'meeting_provider': 40,
                      'email_prefer': 40, 'company': 255})
    data['candidate_name'] = data['candidate_name'].strip()
    if any('\r' in data[field] or '\n' in data[field] for field in ('candidate_name', 'position', 'company')):
        raise ValueError('Candidate name, job title and company must be single-line text')
    if not data['candidate_name']:
        raise ValueError("Field 'candidate_name' is required")
    data['interview_type'] = data['interview_type'] or 'video'
    if data['interview_type'] not in {'phone', 'video', 'in-person', 'technical', 'final'}:
        raise ValueError('Unknown interview type')
    data['meeting_provider'] = (data['meeting_provider'] or 'none').strip().lower()
    if data['meeting_provider'] not in PROVIDERS:
        raise ValueError('Unknown meeting provider')
    if 'send_invite_email' in data and not isinstance(data['send_invite_email'], bool):
        raise ValueError("Field 'send_invite_email' must be true or false")
    data['candidate_email'] = address(data['candidate_email'], required=bool(data.get('send_invite_email')))
    data['position'] = data['position'].strip()
    if data.get('send_invite_email') and not data['position']:
        raise ValueError('Job title is required when sending an interview invitation')
    data['email_prefer'] = data['email_prefer'] or 'auto'
    if data['email_prefer'] not in TRANSPORTS:
        raise ValueError('Unknown email transport')
    for field in ('email_template_id', 'search_result_id'):
        data[field] = optional_id(data.get(field), field)
    return data


def validate_email(data):
    text_fields(data, {'candidate_name': 500, 'candidate_email': 320, 'position': 500,
                      'custom_message': 8192, 'interview_date': 32, 'interview_time': 32,
                      'interview_location': 2000, 'meeting_join_url': 8000,
                      'raw_subject': 32768, 'raw_body': 32768, 'kind': 40, 'prefer': 40,
                      'company': 255, 'time_zone': 128})
    data['candidate_email'] = address(data['candidate_email'], required=True)
    if any('\r' in data[field] or '\n' in data[field] for field in ('candidate_name', 'position', 'company')):
        raise ValueError('Candidate name, job title and company must be single-line text')
    data['prefer'] = data['prefer'] or 'auto'
    if data['prefer'] not in TRANSPORTS:
        raise ValueError('Unknown email transport')
    for field in ('template_id', 'search_result_id'):
        data[field] = optional_id(data.get(field), field)
    if data['meeting_join_url']:
        from services.email_branding import safe_url
        if not safe_url(data['meeting_join_url']):
            raise ValueError('Meeting join link must be a valid HTTPS URL without embedded credentials')
    try:
        if data['interview_date']:
            date.fromisoformat(data['interview_date'])
        if data['interview_time']:
            clock = time.fromisoformat(data['interview_time'])
            if clock.tzinfo:
                raise ValueError()
        if data['time_zone']:
            ZoneInfo(data['time_zone'])
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError('Provide a valid interview date, time and timezone') from None
    return data


def validate_future(start_iso):
    if datetime.fromisoformat(start_iso) <= datetime.now(timezone.utc):
        raise ValueError('Choose an interview date and time in the future')
