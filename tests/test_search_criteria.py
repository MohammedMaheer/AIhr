"""Unit tests for the hard-criteria parser and post-filter.

Run with:
    python -m unittest tests.test_search_criteria
"""

import unittest

from search_criteria import (
    PENALTY_PER_MISS,
    SearchCriteria,
    apply_criteria_to_result,
    apply_criteria_to_results,
    evaluate_criteria,
    parse_search_criteria,
)


def _candidate(years=None, location=None, languages=None, score=90):
    return {
        "gemini_analysis": {
            "match_score": score,
            "hr_scorecard": {
                "candidate_overview": {
                    "experience_years": f"{years} Years" if years is not None else None,
                    "location": location,
                    "overall_match_score": score,
                },
                "detailed_analysis": {
                    "languages": languages or [],
                },
            },
        }
    }


class ParseSearchCriteriaTests(unittest.TestCase):
    def test_empty_query_returns_empty_criteria(self):
        self.assertTrue(parse_search_criteria("").is_empty())
        self.assertTrue(parse_search_criteria(None).is_empty())

    def test_plus_years(self):
        c = parse_search_criteria("python dev with 5+ years experience")
        self.assertEqual(c.min_years, 5)

    def test_minimum_years_phrasing(self):
        c = parse_search_criteria("minimum 8 years required")
        self.assertEqual(c.min_years, 8)

    def test_at_least_years_phrasing(self):
        c = parse_search_criteria("at least 3 yrs of experience")
        self.assertEqual(c.min_years, 3)

    def test_speaks_two_languages_with_and(self):
        c = parse_search_criteria("data scientist speaks French and Arabic, based in Dubai")
        self.assertEqual(c.required_languages, ["arabic", "french"])

    def test_fluent_in_comma_list(self):
        c = parse_search_criteria("recruiter, fluent in french, german, italian")
        self.assertEqual(c.required_languages, ["french", "german", "italian"])

    def test_languages_colon_list(self):
        c = parse_search_criteria("languages: english, hindi, tamil")
        self.assertEqual(c.required_languages, ["english", "hindi", "tamil"])

    def test_hyphenated_speaking(self):
        c = parse_search_criteria("Arabic-speaking customer support agent")
        self.assertIn("arabic", c.required_languages)

    def test_or_separator(self):
        c = parse_search_criteria("fluent in mandarin or japanese based in Singapore")
        self.assertEqual(sorted(c.required_languages), ["japanese", "mandarin"])
        self.assertEqual(c.location, "singapore")

    def test_unknown_language_filtered_out(self):
        # "Klingon" isn't in the whitelist
        c = parse_search_criteria("speaks Klingon")
        self.assertEqual(c.required_languages, [])

    def test_location_based_in(self):
        c = parse_search_criteria("senior dev based in Mumbai")
        self.assertEqual(c.location, "mumbai")

    def test_location_located_in(self):
        c = parse_search_criteria("manager located in Riyadh, full-time")
        self.assertEqual(c.location, "riyadh")

    def test_location_remote(self):
        c = parse_search_criteria("react engineer, remote")
        self.assertEqual(c.location, "remote")

    def test_location_colon_form(self):
        c = parse_search_criteria("backend role. Location: Bangalore")
        self.assertEqual(c.location, "bangalore")

    def test_combined_query(self):
        c = parse_search_criteria(
            "data scientist with 5+ years experience, speaks French and Arabic, based in Dubai"
        )
        self.assertEqual(c.min_years, 5)
        self.assertEqual(c.required_languages, ["arabic", "french"])
        self.assertEqual(c.location, "dubai")

    def test_is_empty_on_plain_skill_query(self):
        c = parse_search_criteria("python react aws")
        self.assertTrue(c.is_empty())


class EvaluateCriteriaTests(unittest.TestCase):
    def test_no_criteria_marks_not_evaluated(self):
        ev = evaluate_criteria({}, SearchCriteria())
        self.assertFalse(ev["evaluated"])

    def test_all_match(self):
        crit = SearchCriteria(min_years=3, required_languages=["english"], location="dubai")
        cand = _candidate(years=5, location="Dubai, UAE", languages=["English", "Arabic"])
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(ev["misses"], [])
        self.assertEqual(len(ev["matches"]), 3)
        self.assertEqual(ev["penalty_applied"], 0)

    def test_years_below_threshold_is_miss(self):
        crit = SearchCriteria(min_years=5)
        cand = _candidate(years=3)
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(len(ev["misses"]), 1)
        self.assertEqual(ev["misses"][0]["criterion"], "experience_years")
        # Now carries an explicit per-miss penalty field.
        self.assertIn("penalty", ev["misses"][0])

    def test_missing_language_is_miss(self):
        crit = SearchCriteria(required_languages=["french"])
        cand = _candidate(languages=["English"])
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(len(ev["misses"]), 1)
        self.assertEqual(ev["misses"][0]["required"], "french")

    def test_location_token_overlap_matches(self):
        crit = SearchCriteria(location="dubai")
        cand = _candidate(location="Dubai, UAE")
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(ev["misses"], [])

    def test_location_mismatch_is_miss(self):
        crit = SearchCriteria(location="mumbai")
        cand = _candidate(location="Bangalore, India")
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(len(ev["misses"]), 1)

    def test_unknown_years_is_miss(self):
        crit = SearchCriteria(min_years=5)
        cand = {"gemini_analysis": {"match_score": 80, "hr_scorecard": {}}}
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(ev["misses"][0]["candidate"], "unknown")


class ApplyCriteriaTests(unittest.TestCase):
    def test_apply_reduces_score_by_penalty(self):
        crit = parse_search_criteria(
            "5+ years experience, speaks French and Arabic, based in Dubai"
        )
        cand = _candidate(years=3, location="Dubai, UAE", languages=["English"], score=90)
        apply_criteria_to_result(cand, crit)
        ga = cand["gemini_analysis"]
        # 3 misses: years gap 2y (proportional ~16) + french 25 + arabic 25 = 66
        # -> 90 - 66 = 24.
        self.assertEqual(ga["match_score"], 24.0)
        self.assertEqual(ga["match_score_before_criteria"], 90.0)
        self.assertIn("criteria_match", cand)
        self.assertEqual(cand["criteria_match"]["penalty_applied"], 66)

    def test_apply_floors_at_zero(self):
        crit = SearchCriteria(min_years=10, required_languages=["french", "german", "italian", "spanish"])
        cand = _candidate(years=1, languages=[], score=40)
        apply_criteria_to_result(cand, crit)
        self.assertEqual(cand["gemini_analysis"]["match_score"], 0.0)

    def test_apply_no_op_when_empty_criteria(self):
        cand = _candidate(years=3, score=85)
        apply_criteria_to_result(cand, SearchCriteria())
        self.assertEqual(cand["gemini_analysis"]["match_score"], 85)
        self.assertNotIn("criteria_match", cand)

    def test_apply_to_results_resorts_descending(self):
        crit = parse_search_criteria("5+ years experience")
        # A scores 90 but has 2y; B scores 80 with 6y -> B should rise.
        a = _candidate(years=2, score=90)
        b = _candidate(years=6, score=80)
        results = [a, b]
        apply_criteria_to_results(results, crit)
        self.assertIs(results[0], b)
        self.assertIs(results[1], a)

    def test_strict_mode_keeps_only_exact_criteria_matches(self):
        crit = SearchCriteria(
            min_years=5,
            required_languages=["english"],
            location="dubai",
        )
        exact = _candidate(years=6, location="Dubai, UAE", languages=["English"], score=70)
        under_years = _candidate(years=4, location="Dubai, UAE", languages=["English"], score=100)
        wrong_location = _candidate(years=7, location="Bangalore, India", languages=["English"], score=95)

        results = [under_years, wrong_location, exact]
        apply_criteria_to_results(results, crit, strict=True, min_kept=0)

        self.assertEqual(results, [exact])
        self.assertEqual(results[0]["criteria_match"]["misses"], [])

    def test_scorecard_nested_score_also_adjusted(self):
        crit = SearchCriteria(min_years=5)
        cand = _candidate(years=2, score=80)
        apply_criteria_to_result(cand, crit)
        co = cand["gemini_analysis"]["hr_scorecard"]["candidate_overview"]
        # 3y gap -> proportional penalty 24, score 80 -> 56
        self.assertEqual(co["overall_match_score"], 56)
        self.assertEqual(co["overall_match_score_before_criteria"], 80)

    def test_proportional_years_penalty_caps_at_max(self):
        crit = SearchCriteria(min_years=15)
        cand = _candidate(years=1, score=100)
        apply_criteria_to_result(cand, crit)
        # gap is 14y but capped at PENALTY_YEARS_MAX = 30
        self.assertEqual(cand["criteria_match"]["penalty_applied"], 30)
        self.assertEqual(cand["gemini_analysis"]["match_score"], 70.0)

    def test_small_years_gap_still_penalized(self):
        crit = SearchCriteria(min_years=5)
        cand = _candidate(years=4, score=80)
        apply_criteria_to_result(cand, crit)
        # 1y gap * 8 = 8, but floor at PENALTY_PER_MISS//2 = 12 -> 68
        self.assertEqual(cand["gemini_analysis"]["match_score"], 68.0)


class NewPatternsAndSynonymsTests(unittest.TestCase):
    def test_must_speak_phrasing(self):
        c = parse_search_criteria("recruiter who must speak French")
        self.assertIn("french", c.required_languages)

    def test_native_phrasing(self):
        c = parse_search_criteria("customer support agent, Arabic native preferred")
        self.assertIn("arabic", c.required_languages)

    def test_dubai_based_pattern(self):
        c = parse_search_criteria("senior engineer, Dubai-based")
        self.assertEqual(c.location, "dubai")

    def test_in_the_uae_pattern(self):
        c = parse_search_criteria("role in the UAE")
        self.assertIsNotNone(c.location)

    def test_french_ans_phrasing(self):
        c = parse_search_criteria("developpeur avec 7 ans d'experience")
        self.assertEqual(c.min_years, 7)

    def test_over_n_years(self):
        c = parse_search_criteria("over 10 years in HR")
        self.assertEqual(c.min_years, 10)

    def test_three_digit_year_requirement_does_not_parse_as_zero(self):
        c = parse_search_criteria("accountant with 100+ years experience")
        self.assertEqual(c.min_years, 100)

    def test_location_synonym_uae_matches_dubai(self):
        crit = SearchCriteria(location="uae")
        cand = _candidate(location="Dubai")
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(ev["misses"], [])

    def test_location_synonym_ksa_matches_riyadh(self):
        crit = SearchCriteria(location="ksa")
        cand = _candidate(location="Riyadh, Saudi Arabia")
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(ev["misses"], [])

    def test_wfh_matches_remote_intent(self):
        crit = SearchCriteria(location="remote")
        cand = _candidate(location="WFH, India")
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        self.assertEqual(ev["misses"], [])


class RegressionBugs(unittest.TestCase):
    """Regressions for bugs found in audit."""

    def test_short_token_synonyms_dont_false_match(self):
        # "us" used to leak from the U.S. synonym group and false-match
        # any candidate text containing the substring "us" (e.g. "Houston").
        crit = SearchCriteria(location="dubai")
        cand = _candidate(location="Houston, Texas")
        ev = evaluate_criteria(cand["gemini_analysis"], crit)
        # Houston is not Dubai -> must be a miss
        self.assertTrue(any(m["criterion"] == "location" for m in ev["misses"]))

    def test_apply_criteria_is_idempotent(self):
        crit = SearchCriteria(min_years=5)
        cand = _candidate(years=2, score=90)
        apply_criteria_to_result(cand, crit)
        first_score = cand["gemini_analysis"]["match_score"]
        apply_criteria_to_result(cand, crit)
        second_score = cand["gemini_analysis"]["match_score"]
        self.assertEqual(first_score, second_score,
                         "Re-applying same criteria should not compound the penalty")
        # And the recorded pre-criteria score should still be the original 90
        self.assertEqual(cand["gemini_analysis"]["match_score_before_criteria"], 90)


if __name__ == "__main__":
    unittest.main()
