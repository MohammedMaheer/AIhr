"""Evidence-based CV tags and explicit upload/email-date search filters."""
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re

TAG_PATTERNS = {
    'IT infrastructure': r'\b(?:it infrastructure|infrastructure engineer|system[s]? administrator|network engineer|network administrator|network security|ccna|ccnp|vmware)\b',
    'Graphic design': r'\b(?:graphic designer|graphic design|adobe illustrator|adobe photoshop)\b',
    'UI design': r'\b(?:ui designer|ux designer|ui/ux|ux/ui|user interface design|figma)\b',
    'Web design': r'\b(?:web designer|web design|wordpress|webflow)\b',
    'Software development': r'\b(?:software engineer|software developer|full.stack developer|backend developer|front.end developer|application developer)\b',
    'Data and AI': r'\b(?:data scientist|data engineer|data analyst|machine learning engineer|artificial intelligence|business intelligence)\b',
    'Management': r'\b(?:project manager|program manager|operations manager|general manager|team lead|department head|managing director)\b',
    'Finance and accounting': r'\b(?:accountant|finance manager|financial analyst|accounts payable|accounts receivable|auditor)\b',
    'HR and recruitment': r'\b(?:human resources|hr manager|hr executive|recruiter|talent acquisition)\b',
    'Sales and marketing': r'\b(?:sales manager|sales executive|marketing manager|digital marketing|business development)\b',
}


def tags_from_text(text):
    normalized = ' '.join((text or '').split())
    return [name for name, pattern in TAG_PATTERNS.items() if re.search(pattern, normalized, re.I)]


def normalize_filters(value):
    if value is None:
        return {}
    if isinstance(value, str):
        if len(value) > 5000:
            raise ValueError('Invalid CV filters.')
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            raise ValueError('Invalid CV filters.') from None
    if not isinstance(value, dict) or set(value) - {'tags', 'date_from', 'date_to', 'date_basis'}:
        raise ValueError('Invalid CV filters.')
    tags = value.get('tags', [])
    if not isinstance(tags, list) or len(tags) > len(TAG_PATTERNS) or any(not isinstance(tag, str) or tag not in TAG_PATTERNS for tag in tags):
        raise ValueError('Choose valid CV tags.')
    out = {'tags': sorted(set(tags))} if tags else {}
    for field in ('date_from', 'date_to'):
        if value.get(field):
            try:
                out[field] = date.fromisoformat(value[field]).isoformat()
            except (ValueError, TypeError):
                raise ValueError('Choose a valid date range.') from None
    if out.get('date_from', '0001-01-01') > out.get('date_to', '9999-12-31'):
        raise ValueError('The start date must not be after the end date.')
    basis = value.get('date_basis', 'uploaded')
    if basis not in ('uploaded', 'received'):
        raise ValueError('Choose Uploaded or Email received dates.')
    if out.get('date_from') or out.get('date_to'):
        out['date_basis'] = basis
    return out


def filters_sql(value):
    filters = normalize_filters(value)
    clauses, params = [], []
    if filters.get('tags'):
        clauses.append('search_tags && %s::text[]')
        params.append(filters['tags'])
    column = 'source_received_at' if filters.get('date_basis') == 'received' else 'source_uploaded_at'
    if filters.get('date_from'):
        clauses.append(f'{column} >= %s::date')
        params.append(filters['date_from'])
    if filters.get('date_to'):
        clauses.append(f"{column} < %s::date + interval '1 day'")
        params.append(filters['date_to'])
    return ' AND '.join(clauses) or 'TRUE', params


def received_date(value):
    if not isinstance(value, str) or len(value) > 150:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def record_metadata(db, bucket, key, company_id, *, received=None):
    folder, _, filename = key.rpartition('/')
    with db.get_cursor() as (cur, _):
        cur.execute('''UPDATE resume_embeddings e SET source_uploaded_at = (
                SELECT max(upload_timestamp) FROM resume_uploads u
                WHERE u.company_id IS NOT DISTINCT FROM e.company_id
                  AND (u.file_path=%s OR u.file_path=%s)),
                source_received_at=COALESCE(%s,source_received_at)
            WHERE storage_bucket=%s AND folder=%s AND filename=%s AND company_id IS NOT DISTINCT FROM %s''',
                    (key, f'gs://{bucket}/{key}', received_date(received), bucket, folder, filename, company_id))


def refresh_existing_metadata(db):
    """Only cached text/known upload dates; no file reads, AI calls or vector writes."""
    updated = 0
    with db.get_cursor() as (cur, _):
        cur.execute('SELECT id,extracted_text FROM resume_embeddings ORDER BY id')
        rows = [(row['id'], tags_from_text(row['extracted_text'])) for row in cur.fetchall()]
        for resume_id, tags in rows:
            cur.execute('UPDATE resume_embeddings SET search_tags=%s WHERE id=%s AND search_tags IS DISTINCT FROM %s',
                        (tags, resume_id, tags))
            updated += cur.rowcount
        cur.execute('''UPDATE resume_embeddings e SET source_uploaded_at = sources.uploaded_at
            FROM (SELECT e2.id,max(u.upload_timestamp) AS uploaded_at FROM resume_embeddings e2
                JOIN resume_uploads u ON u.company_id IS NOT DISTINCT FROM e2.company_id
                AND (u.file_path='gs://' || e2.storage_bucket || '/' || concat_ws('/',NULLIF(e2.folder,''),e2.filename)
                     OR u.file_path=concat_ws('/',NULLIF(e2.folder,''),e2.filename))
                GROUP BY e2.id) sources
            WHERE sources.id=e.id AND e.source_uploaded_at IS DISTINCT FROM sources.uploaded_at''')
        dated = cur.rowcount
    return {'tagged_records_updated': updated, 'upload_dates_updated': dated}
