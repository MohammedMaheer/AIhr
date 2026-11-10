from contextlib import nullcontext
from decimal import Decimal

import pytest

from test_durable_search import queue_db


def add_search(db, *, user=7, company=1, days=1, result_count=0, scores=()):
    with db.get_cursor() as (cursor, _):
        cursor.execute('''INSERT INTO search_history(created_by_user_id,company_id,result_count,search_timestamp)
            VALUES(%s,%s,%s,NOW()-(%s * INTERVAL '1 day')) RETURNING id''',
                       (user, company, result_count, days))
        search_id = cursor.fetchone()['id']
        for score in scores:
            cursor.execute('INSERT INTO search_results(search_id,match_score) VALUES(%s,%s)',
                           (search_id, score))
    return search_id


def test_search_counts_and_averages_are_not_weighted_by_result_rows(queue_db):
    add_search(queue_db, days=1, result_count=2, scores=(10,))
    add_search(queue_db, days=15, result_count=2, scores=(20, 40, 60, 80))
    add_search(queue_db, days=45)
    add_search(queue_db, user=8, result_count=100, scores=(100,))
    add_search(queue_db, company=2, result_count=90, scores=(90,))

    stats = queue_db.get_user_search_stats(7, 1)

    assert set(stats) == {'total_searches', 'searches_this_week', 'searches_this_month',
                          'avg_results_per_search', 'avg_match_score'}
    assert stats['total_searches'] == 3
    assert stats['searches_this_week'] == 1
    assert stats['searches_this_month'] == 2
    assert float(stats['avg_results_per_search']) == pytest.approx(4 / 3)
    assert stats['avg_match_score'] == Decimal('42')


@pytest.mark.parametrize('company,expected', [(None, 3), (1, 2), (2, 1), (999, 0)])
def test_search_statistics_preserve_user_and_optional_company_scope(queue_db, company, expected):
    add_search(queue_db, result_count=3, scores=(10, 20, 30))
    add_search(queue_db)
    add_search(queue_db, company=2)
    add_search(queue_db, user=8, result_count=100, scores=(100,))

    stats = queue_db.get_user_search_stats(7, company)

    assert stats['total_searches'] == expected
    assert stats['searches_this_week'] == expected
    assert stats['searches_this_month'] == expected
    if not expected:
        assert stats['avg_results_per_search'] is None
        assert stats['avg_match_score'] is None


def test_searches_without_results_still_count_and_keep_missing_score_null(queue_db):
    add_search(queue_db)
    add_search(queue_db)

    stats = queue_db.get_user_search_stats(7, 1)

    assert stats['total_searches'] == 2
    assert stats['avg_results_per_search'] == 0
    assert stats['avg_match_score'] is None
    empty = queue_db.get_user_search_stats(999, 1)
    assert empty['total_searches'] == empty['searches_this_week'] == empty['searches_this_month'] == 0
    assert empty['avg_results_per_search'] is empty['avg_match_score'] is None


def test_search_date_cutoffs_remain_inclusive(queue_db, monkeypatch):
    with queue_db.get_cursor() as (cursor, connection):
        for offset in ("INTERVAL '7 days'", "INTERVAL '7 days 1 second'",
                       "INTERVAL '30 days'", "INTERVAL '30 days 1 second'"):
            cursor.execute(f'''INSERT INTO search_history(created_by_user_id,company_id,result_count,search_timestamp)
                VALUES(7,1,0,NOW()-{offset})''')
        # One transaction keeps PostgreSQL NOW() fixed at the exact cutoffs.
        monkeypatch.setattr(queue_db, 'get_cursor', lambda: nullcontext((cursor, connection)))
        stats = queue_db.get_user_search_stats(7, 1)

    assert stats['total_searches'] == 4
    assert stats['searches_this_week'] == 1
    assert stats['searches_this_month'] == 3
