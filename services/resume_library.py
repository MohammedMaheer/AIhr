"""Read-only, workspace-scoped upload browsing. Never invokes an AI provider."""
import os
from urllib.parse import urlsplit

from fastapi import HTTPException
from services.resume_folders import workspace_scope


def source_location(path, default_bucket):
    parsed = urlsplit(path or '')
    if parsed.scheme == 'gs' and parsed.netloc:
        return parsed.netloc, parsed.path.lstrip('/')
    if not parsed.scheme and path and not path.startswith('/') and '..' not in path.split('/'):
        return default_bucket, path
    return None, None


def list_uploads(db, user, *, limit=25, offset=0, query='', default_bucket=''):
    scope, params = workspace_scope(user)
    if query:
        scope += ' AND position(lower(%s) in lower(file_name)) > 0'
        params.append(query[:200])
    with db.get_cursor() as (cur, _):
        cur.execute(f'SELECT count(*) AS count FROM resume_uploads WHERE {scope}', params)
        total = cur.fetchone()['count']
        cur.execute(f'''SELECT u.id,file_name,file_path,file_size,mime_type,upload_timestamp,c.gcs_bucket_name
            FROM resume_uploads u LEFT JOIN tenant_companies c ON c.id=u.company_id
            WHERE {scope} ORDER BY upload_timestamp DESC,u.id DESC LIMIT %s OFFSET %s''',
                    [*params, limit, offset])
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row['upload_timestamp'] = row['upload_timestamp'].isoformat() if row['upload_timestamp'] else None
        bucket, key = source_location(row['file_path'], row.pop('gcs_bucket_name') or default_bucket)
        if bucket and key:
            row['file_path'] = f'gs://{bucket}/{key}'
    return dict(success=True, uploads=rows, total=total, limit=limit, offset=offset)


def upload_record(db, user, upload_id):
    scope, params = workspace_scope(user)
    with db.get_cursor() as (cur, _):
        cur.execute(f'''SELECT u.id,file_name,file_path,company_id,c.gcs_bucket_name FROM resume_uploads u
            LEFT JOIN tenant_companies c ON c.id=u.company_id WHERE u.id=%s AND {scope}''', [upload_id, *params])
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'CV not found')
        return dict(row)


def preview_upload(db, user, upload_id, default_bucket=None):
    row = upload_record(db, user, upload_id)
    bucket, key = source_location(row['file_path'], row['gcs_bucket_name'] or default_bucket or os.getenv('GCS_BUCKET_NAME', ''))
    text = ''
    if bucket and key:
        with db.get_cursor() as (cur, _):
            folder, _, filename = key.rpartition('/')
            cur.execute('''SELECT left(extracted_text,80000) AS text FROM resume_embeddings
                WHERE storage_bucket=%s AND folder=%s AND filename=%s AND company_id IS NOT DISTINCT FROM %s
                LIMIT 1''', (bucket, folder, filename, row['company_id']))
            extracted = cur.fetchone()
            text = extracted['text'] or '' if extracted else ''
    extension = (key or row['file_name'] or '').rsplit('.', 1)[-1].lower()
    kind = 'text' if extension == 'txt' else 'pdf' if extension in ('pdf', 'doc', 'docx') else None
    return dict(success=True, id=row['id'], file_name=row['file_name'],
                file_path=f'gs://{bucket}/{key}' if bucket and key else row['file_path'], text=text,
                preview_kind=kind, preview_url=f'/api/resume-library/{upload_id}/document' if kind else None)
