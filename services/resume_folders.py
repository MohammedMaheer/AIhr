"""Validated storage-folder scopes shared by search, queues and the CV library."""
import json
import re
from urllib.parse import urlsplit


def normalize_folders(value):
    if value is None:
        return []
    explicit = isinstance(value, str)
    if explicit:
        if len(value) > 32000:
            raise ValueError('Too many folder selections.')
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            raise ValueError('Choose valid folders.') from None
    if not isinstance(value, list) or len(value) > 50 or (explicit and not value):
        raise ValueError('Choose at least one folder, or select All folders.')
    normalized = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {'bucket', 'path'}:
            raise ValueError('Choose valid folders.')
        bucket, path = item['bucket'], item['path']
        if not isinstance(bucket, str) or not re.fullmatch(r'[a-zA-Z0-9._-]{1,222}', bucket):
            raise ValueError('Invalid folder storage.')
        if not isinstance(path, str) or len(path) > 512 or any(ord(c) < 32 for c in path):
            raise ValueError('Invalid folder name.')
        path = path.rstrip('/')
        if path.startswith('/') or '\\' in path or any(p in ('.', '..', '') for p in path.split('/') if path):
            raise ValueError('Use a folder name without empty or relative path segments.')
        normalized.add((bucket, path))
    return [dict(bucket=bucket, path=path) for bucket, path in sorted(normalized)]


def folder_sql(folders):
    """Column names are fixed; all user values remain bound parameters."""
    clauses, params = [], []
    for item in normalize_folders(folders):
        if not item['path']:
            clauses.append('(storage_bucket = %s)')
            params.append(item['bucket'])
        else:
            clauses.append("(storage_bucket = %s AND (rtrim(folder, '/') = %s OR starts_with(rtrim(folder, '/') || '/', %s)))")
            params.extend((item['bucket'], item['path'], item['path'] + '/'))
    return '(' + ' OR '.join(clauses) + ')' if clauses else 'TRUE', params


def source_in_folders(uri, folders):
    if not folders:
        return True
    parsed = urlsplit(uri or '')
    if parsed.scheme != 'gs':
        return False
    key = parsed.path.lstrip('/')
    return any(parsed.netloc == item['bucket'] and
               (not item['path'] or key.startswith(item['path'] + '/')) for item in folders)


def workspace_scope(user):
    from fastapi import HTTPException
    if user.get('user_type') == 'super_admin':
        return 'TRUE', []
    company = user.get('company') or {}
    company_id = (company.get('company_id') or company.get('id')) if isinstance(company, dict) else getattr(company, 'id', None)
    if not company_id:
        raise HTTPException(403, 'Company context required')
    return 'company_id = %s', [company_id]


def inventory(db, user):
    scope, params = workspace_scope(user)
    with db.get_cursor() as (cur, _):
        cur.execute(f"""SELECT storage_bucket AS bucket, rtrim(folder, '/') AS path,
                count(*) AS total, count(embedding) AS searchable
            FROM resume_embeddings WHERE {scope}
            GROUP BY storage_bucket,rtrim(folder, '/') ORDER BY lower(rtrim(folder, '/')),storage_bucket""", params)
        return [dict(row) for row in cur.fetchall()]


def searchable_count(db, user, folders, filters=None, *, timeout_ms=None):
    from services.resume_filters import filters_sql
    scope, params = workspace_scope(user)
    selected, selected_params = folder_sql(folders)
    filtered, filtered_params = filters_sql(filters)
    with db.get_cursor() as (cur, _):
        if timeout_ms is not None:
            cur.execute("SELECT set_config('statement_timeout', %s, true)", (str(max(1, int(timeout_ms))),))
        cur.execute(f'SELECT count(*) AS count FROM resume_embeddings WHERE embedding IS NOT NULL AND {scope} AND {selected} AND {filtered}',
                    [*params, *selected_params, *filtered_params])
        return cur.fetchone()['count']


def tag_inventory(db, user):
    scope, params = workspace_scope(user)
    with db.get_cursor() as (cur, _):
        cur.execute(f'''SELECT label, count(*) AS total,
                count(embedding) AS searchable
            FROM resume_embeddings CROSS JOIN LATERAL unnest(search_tags) AS tags(label)
            WHERE {scope} GROUP BY label ORDER BY label''', params)
        return {row['label']: {'total': row['total'], 'searchable': row['searchable']}
                for row in cur.fetchall()}
