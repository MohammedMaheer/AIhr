import unittest
from decimal import Decimal

from search_criteria import SearchCriteria
from vps_local.profile_extractor import (
    clean_location,
    evaluate_profile,
    profile_from_analysis,
    profile_from_row,
    profile_from_text,
)
from vps_local.discovery_shim import _rank_rows


class ProfileExtractorTests(unittest.TestCase):
    def test_profile_from_scorecard_extracts_core_fields(self):
        analysis = {
            "hr_scorecard": {
                "candidate_overview": {
                    "experience_years": "3 years 9 months",
                    "location": "Dubai, UAE",
                },
                "detailed_analysis": {
                    "languages": ["English", "Arabic"],
                    "technical_skills": ["Accounts Payable", "SAP FICO"],
                },
                "keyword_coverage": {
                    "matched_keywords": ["VAT", "Bank Reconciliation"],
                },
            }
        }

        profile = profile_from_analysis(analysis)

        self.assertEqual(profile["candidate_years"], 3.75)
        self.assertEqual(profile["candidate_location"], "dubai, uae")
        self.assertIn("english", profile["candidate_languages"])
        self.assertIn("accounts payable", profile["candidate_skills"])
        self.assertIn("vat", profile["candidate_skills"])

    def test_uncertain_languages_do_not_count_as_exact(self):
        analysis = {
            "hr_scorecard": {
                "detailed_analysis": {
                    "languages": [
                        "English (implied)",
                        "Arabic (inferred)",
                        "Hindi",
                    ]
                }
            }
        }

        profile = profile_from_analysis(analysis)

        self.assertNotIn("english", profile["candidate_languages"])
        self.assertNotIn("arabic", profile["candidate_languages"])
        self.assertIn("hindi", profile["candidate_languages"])

    def test_uncertain_languages_from_text_do_not_count_as_exact(self):
        text = "Languages: English (implied), Arabic (assumed), Hindi"

        profile = profile_from_text(text)

        self.assertNotIn("english", profile["candidate_languages"])
        self.assertNotIn("arabic", profile["candidate_languages"])
        self.assertIn("hindi", profile["candidate_languages"])

    def test_contact_words_are_trimmed_from_locations(self):
        self.assertEqual(clean_location("Dubai U.A.E Phone Number"), "dubai u.a.e")
        self.assertEqual(clean_location("India (implied by phone number and company locations)"), "india")
        self.assertEqual(clean_location("email"), "")

    def test_timeline_does_not_pollute_skills_with_company_or_dates(self):
        analysis = {
            "hr_scorecard": {
                "career_timeline": [
                    {
                        "role": "Accountant",
                        "company": "V Care Waterproofing LLC",
                        "year_range": "May 2018 to June 2024",
                        "key_skills": ["Accounts Payable", "VAT"],
                    }
                ]
            }
        }

        profile = profile_from_analysis(analysis)

        self.assertIn("accounts payable", profile["candidate_skills"])
        self.assertIn("vat", profile["candidate_skills"])
        self.assertNotIn("v care waterproofing llc", profile["candidate_skills"])
        self.assertNotIn("may 2018 to june 2024", profile["candidate_skills"])

    def test_profile_from_text_extracts_fallback_signals(self):
        text = """
        Current Location: Abu Dhabi, UAE
        Professional summary: Accountant with 6+ years of experience.
        Languages: English, Hindi
        Skills: accounts payable, bank reconciliation, SAP, VAT, Excel
        """

        profile = profile_from_text(text)

        self.assertEqual(profile["candidate_years"], 6.0)
        self.assertIn("abu dhabi", profile["candidate_location"])
        self.assertIn("hindi", profile["candidate_languages"])
        self.assertIn("accounts payable", profile["candidate_skills"])

    def test_evaluate_profile_marks_exact_match(self):
        profile = {
            "candidate_years": 6,
            "candidate_location": "dubai uae",
            "candidate_languages": ["english"],
            "candidate_skills": ["accounts payable", "sap"],
        }
        criteria = SearchCriteria(
            min_years=5,
            location="uae",
            required_languages=["english"],
            required_skills=["accounts payable"],
        )

        ev, status = evaluate_profile(profile, criteria)

        self.assertEqual(status, "exact")
        self.assertEqual(ev["misses"], [])

    def test_profile_from_row_normalizes_postgres_decimal_years(self):
        profile = profile_from_row({
            "candidate_years": Decimal("3.50"),
            "candidate_location": "Dubai, UAE",
            "candidate_languages": ["English"],
            "candidate_skills": ["Python"],
            "profile_source": "test",
        })

        self.assertEqual(profile["candidate_years"], 3.5)

    def test_evaluate_profile_marks_known_fail(self):
        profile = {
            "candidate_years": 2,
            "candidate_location": "bangalore india",
            "candidate_languages": ["english"],
            "candidate_skills": ["accounts payable"],
        }
        criteria = SearchCriteria(min_years=5, location="dubai")

        ev, status = evaluate_profile(profile, criteria)

        self.assertEqual(status, "known_fail")
        self.assertTrue(ev["misses"])

    def test_rank_rows_excludes_known_fail_when_criteria_present(self):
        rows = [
            {
                "id": "known-fail",
                "score": 0.99,
                "lexical_score": 1,
                "candidate_years": 1,
                "candidate_location": "bangalore india",
                "candidate_languages": [],
                "candidate_skills": ["python"],
                "profile_source": "test",
                "text": "",
            },
            {
                "id": "exact",
                "score": 0.70,
                "lexical_score": 0.2,
                "candidate_years": 5,
                "candidate_location": "dubai uae",
                "candidate_languages": [],
                "candidate_skills": ["python"],
                "profile_source": "test",
                "text": "",
            },
        ]

        ranked = _rank_rows(rows, "python developer with 3+ years based in Dubai", 10)

        self.assertEqual([r["id"] for r in ranked], ["exact"])


if __name__ == "__main__":
    unittest.main()
