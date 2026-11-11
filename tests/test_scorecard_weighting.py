import copy

import pytest

from main import adjust_scorecard_with_keyword_analysis


def scorecard(categories):
    return {
        'candidate_overview': {'overall_match_score': 50},
        'score_breakdown': {name: {'score': value} for name, value in categories.items()},
    }


def keywords(matched, total):
    return {'jd_keywords_matched': matched, 'total_jd_keywords': total}


def test_keyword_and_non_keyword_weights_sum_to_one():
    result = adjust_scorecard_with_keyword_analysis(
        scorecard({'keyword_technical_match': 0, 'experience': 100, 'education': 100}),
        keywords(10, 10),
    )
    assert result['candidate_overview']['overall_match_score'] == 98


def test_multiple_keyword_categories_share_the_keyword_weight():
    result = adjust_scorecard_with_keyword_analysis(
        scorecard({'keyword_technical_match': 0, 'technical_match': 0, 'experience': 100}),
        keywords(10, 10),
    )
    assert result['candidate_overview']['overall_match_score'] == 82


@pytest.mark.parametrize('categories,expected', [
    ({'experience': 60}, 62),
    ({'keyword_a': 60, 'technical_match_b': 80}, 74),
])
def test_single_or_keyword_only_breakdowns_are_normalized(categories, expected):
    result = adjust_scorecard_with_keyword_analysis(scorecard(categories), keywords(5, 10))
    assert result['candidate_overview']['overall_match_score'] == expected


def test_missing_keyword_category_is_added_and_applied():
    result = adjust_scorecard_with_keyword_analysis(scorecard({'experience': 100}), keywords(10, 10))
    assert result['score_breakdown']['keyword_technical_match']['score'] == 95
    assert result['candidate_overview']['overall_match_score'] == 98


@pytest.mark.parametrize('metrics', [
    {},
    {'jd_keywords_matched': 1, 'total_jd_keywords': 0},
    {'jd_keywords_matched': 5, 'total_jd_keywords': 4},
    {'jd_keywords_matched': True, 'total_jd_keywords': 4},
    {'jd_keywords_matched': float('nan'), 'total_jd_keywords': 4},
])
def test_invalid_keyword_metrics_leave_scorecard_unchanged(metrics):
    original = scorecard({'keyword_technical_match': 80, 'experience': 70})
    expected = copy.deepcopy(original)
    assert adjust_scorecard_with_keyword_analysis(original, metrics) == expected


def test_invalid_score_values_are_ignored_without_unbounded_scores():
    data = scorecard({'keyword_technical_match': 90, 'experience': 120, 'education': float('nan')})
    result = adjust_scorecard_with_keyword_analysis(data, keywords(5, 10))
    assert result['candidate_overview']['overall_match_score'] == 88
