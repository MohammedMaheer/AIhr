"""Acceptance gate for complete, document-backed candidate assessments."""
import math


def verified_scorecard(analysis):
    if not isinstance(analysis, dict) or analysis.get('success') is not True:
        return False
    if analysis.get('input_source') != 'full_document':
        return False
    if analysis.get('scorecard_type') not in {'comprehensive_hr', 'split_approach'}:
        return False
    scorecard = analysis.get('hr_scorecard')
    if not isinstance(scorecard, dict) or not isinstance(scorecard.get('candidate_overview'), dict):
        return False
    if not scorecard['candidate_overview'] or not isinstance(scorecard.get('score_breakdown'), dict):
        return False
    score = analysis.get('match_score')
    return (not isinstance(score, bool) and isinstance(score, (int, float))
            and math.isfinite(score) and 0 <= score <= 100)
