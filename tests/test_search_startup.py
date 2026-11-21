"""Schema preparation is explicit, bounded and outside all retrieval modes."""
from unittest.mock import MagicMock

import pytest

from vps_local import discovery_shim as discovery
from test_durable_search import queue_db  # noqa: F401


@pytest.mark.parametrize('advanced',[False,True])
@pytest.mark.parametrize('preview',[False,True])
def test_retrieval_never_runs_schema_ddl(monkeypatch,advanced,preview):
    pool,connection,cursor=MagicMock(),MagicMock(),MagicMock()
    pool.getconn.return_value=connection
    connection.cursor.return_value.__enter__.return_value=cursor
    cursor.fetchall.return_value=[]
    monkeypatch.setattr(discovery,'_get_pool',lambda:pool)
    monkeypatch.setattr(discovery,'_embed_query',lambda text:[.1]*384)
    monkeypatch.setattr(discovery,'ADVANCED_SEARCH_ENABLED',advanced)
    schema=MagicMock(side_effect=AssertionError('Retrieval must not initialize schema'))
    monkeypatch.setattr(discovery,'_ensure_advanced_search_schema',schema)
    assert discovery._vector_search('candidate profiles',10,'company_id: ANY("1")',profile_preview=preview)==[]
    schema.assert_not_called()
    assert not any(call.args[0].lstrip().upper().startswith(('ALTER','CREATE','DROP')) for call in cursor.execute.call_args_list)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(connection)


def test_explicit_startup_prepares_columns_on_real_postgres(queue_db,monkeypatch):
    with queue_db.get_cursor() as (cursor,_):
        cursor.execute('CREATE TABLE resume_embeddings(id SERIAL PRIMARY KEY,extracted_text TEXT)')
    monkeypatch.setattr(discovery,'_advanced_schema_ensured',False)
    monkeypatch.setattr(discovery,'_get_pool',lambda:queue_db.pool)
    discovery.initialize_search_schema()
    with queue_db.get_cursor() as (cursor,_):
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='resume_embeddings'")
        names={row['column_name'] for row in cursor.fetchall()}
    assert {'candidate_years','candidate_location','candidate_skills','search_tags','source_received_at'} <= names


def test_startup_schema_is_bounded_committed_and_idempotent(monkeypatch):
    pool,connection,cursor=MagicMock(),MagicMock(),MagicMock()
    pool.getconn.return_value=connection
    connection.cursor.return_value.__enter__.return_value=cursor
    monkeypatch.setattr(discovery,'_advanced_schema_ensured',False)
    monkeypatch.setattr(discovery,'_get_pool',lambda:pool)
    schema=MagicMock()
    monkeypatch.setattr(discovery,'_ensure_advanced_search_schema',schema)
    discovery.initialize_search_schema()
    discovery.initialize_search_schema()
    schema.assert_called_once_with(cursor)
    assert [call.args[0] for call in cursor.execute.call_args_list]==[
        "SET LOCAL lock_timeout = '5000ms'","SET LOCAL statement_timeout = '30000ms'"]
    connection.commit.assert_called_once()
    pool.putconn.assert_called_once_with(connection)


def test_failed_startup_schema_does_not_leave_a_false_ready_flag(monkeypatch):
    pool,connection=MagicMock(),MagicMock()
    pool.getconn.return_value=connection
    monkeypatch.setattr(discovery,'_advanced_schema_ensured',False)
    monkeypatch.setattr(discovery,'_get_pool',lambda:pool)
    connection.commit.side_effect=RuntimeError('Commit failed')
    def schema(cursor):discovery._advanced_schema_ensured=True
    monkeypatch.setattr(discovery,'_ensure_advanced_search_schema',schema)
    with pytest.raises(RuntimeError,match='Commit failed'):
        discovery.initialize_search_schema()
    assert discovery._advanced_schema_ensured is False
    connection.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(connection)
