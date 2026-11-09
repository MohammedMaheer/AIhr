"""Read offline-recovered full text only for the exact authorized original bytes."""
import hashlib

from psycopg2.errors import UndefinedTable

from services.resume_folders import workspace_scope

def lookup_recovered_text(db, user, bucket, key, content):
    if not user or not isinstance(content, bytes) or not content or len(content) > 16 * 1024 * 1024:
        return None
    if not isinstance(key, str) or '\\' in key or any(part in ('', '.', '..') for part in key.split('/')):
        return None
    folder, _, filename = key.rpartition('/')
    scope, params = workspace_scope(user)
    digest = hashlib.sha256(content).hexdigest()
    try:
        with db.get_cursor() as (cursor, _):
            cursor.execute(f'''SELECT e.extracted_text, r.text_sha256
                FROM resume_text_recoveries r JOIN resume_embeddings e ON e.id=r.resume_embedding_id
                WHERE e.storage_bucket=%s AND e.folder=%s AND e.filename=%s
                  AND ({scope}) AND r.source_sha256=%s AND r.quality_status='accepted'
                LIMIT 2''', [bucket, folder, filename, *params, digest])
            rows = cursor.fetchall()
    except UndefinedTable:
        # An older installation continues using its normal extractor until migrated.
        return None
    if len(rows) != 1:
        return None
    text = rows[0]['extracted_text']
    if (not isinstance(text, str) or len(text.strip()) < 200 or len(text) > 80_000
            or '\x00' in text or hashlib.sha256(text.encode()).hexdigest() != rows[0]['text_sha256']):
        return None
    return text
