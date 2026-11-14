"""Explicit positive/negative fixtures for strict eligibility, not LLM accuracy."""
import pytest

from search_criteria import (
    SearchCriteria, _location_match, apply_criteria_to_results,
    evaluate_criteria, parse_search_criteria,
)
from vps_local.discovery_shim import _rank_rows
from vps_local.profile_extractor import merge_profiles, parse_years, profile_from_analysis, profile_to_analysis


@pytest.mark.parametrize('role',['HR Recruiter','Designer','Consultant','Nurse'])
def test_location_followed_by_experience_is_not_the_job_title(role):
    criteria=parse_search_criteria(role+' based in Dubai with 3-5 years of experience. Required skills: Python.')
    assert criteria.location=='dubai'
    assert (criteria.min_years,criteria.max_years)==(3,5)
    assert criteria.required_skills==['python']
    assert evaluate_criteria(analysis(location='Chennai',skills=['Python']),criteria)['hard_fail']


@pytest.mark.parametrize('clause',['location: Dubai','must be in Dubai','located in Dubai','in the Dubai'])
def test_explicit_location_ends_before_numeric_qualification(clause):
    assert parse_search_criteria('Recruiter '+clause+' with 3-5 years.').location=='dubai'


def analysis(location='', skills=None, languages=None):
    return {'hr_scorecard': {
        'candidate_overview': {'location': location, 'skills': skills or []},
        'detailed_analysis': {'languages': languages or []},
    }}


@pytest.mark.parametrize('wanted,have,expected', [
    ('Dubai', 'Sharjah, UAE', False),
    ('Dubai, UAE', 'Abu Dhabi, UAE', False),
    ('Abu Dhabi', 'Abu', False),
    ('United States', 'London, United Kingdom', False),
    ('United Kingdom', 'Boston, United States', False),
    ('USA', 'Paris, France', False),
    ('France', 'Paris, USA', False),
    ('India', 'Sharjah, UAE (India market experience)', False),
    ('Dubai', '(Willing to relocate to Dubai)', False),
    ('India', '(India market experience)', False),
    ('Dubai', 'UAE', False),
    ('Dubai', 'Dubai, UAE', True),
    ('UAE', 'Dubai', True),
    ('United Arab Emirates', 'Abu Dhabi', True),
    ('Kingdom of Saudi Arabia', 'Riyadh', True),
    ('United Kingdom', 'London', True),
    ('U.S.A.', 'New York', True),
    ('India', 'Mumbai', True),
    ('Bangalore, India', 'Bengaluru, India', True),
    ('Mumbai', 'Bombay, Maharashtra', True),
    ('Remote', 'WFH, India', True),
])
def test_location_names_are_not_partial_country_or_city_matches(wanted, have, expected):
    assert _location_match(wanted, have) is expected


@pytest.mark.parametrize('query,location,expected', [
    ('Developer based in Dubai, UAE', 'Sharjah, UAE', False),
    ('Developer based in Dubai/UAE', 'Sharjah, UAE', False),
    ('Developer based in Dubai/UAE', 'Dubai, UAE', True),
    ('Developer based in Dubai, not Abu Dhabi', 'Abu Dhabi', False),
    ('Developer based in Dubai with clients in London', 'London', False),
    ('Developer based in Dubai with clients in London or Paris', 'Paris', False),
    ('Developer based in Dubai or Abu Dhabi', 'Abu Dhabi, UAE', True),
    ('Developer based in Dubai or Abu Dhabi', 'Sharjah, UAE', False),
    ('Developer based in Dubai, UAE or Abu Dhabi, UAE', 'Sharjah, UAE', False),
    ('Developer based in Dubai, UAE or Abu Dhabi, UAE', 'Abu Dhabi, UAE', True),
    ('Developer in Pune, Hyderabad or Chennai', 'Hyderabad, India', True),
    ('Developer in Mumbai/Bangalore', 'Bengaluru, India', True),
    ('Developer in USA or UK', 'London, UK', True),
    ('Developer based in Dubai or UAE', 'Sharjah, UAE', True),
])
def test_only_explicit_location_alternatives_expand_the_query(query, location, expected):
    criteria = parse_search_criteria(query)
    result = evaluate_criteria(analysis(location=location), criteria)
    assert not result['misses'] if expected else result['misses']


@pytest.mark.parametrize('wanted,have,expected', [
    ('Java', 'JavaScript', False), ('Java', 'Java', True),
    ('Java', 'Java 17', True), ('Java', 'Java17', True),
    ('SQL', 'NoSQL', False), ('SQL', 'SQL Server', True),
    ('SQL', 'PostgreSQL', True), ('SQL', 'MySQL 8', True),
    ('SQL', 'SQLAlchemy', False), ('SQL', 'MongoDB', False),
    ('C', 'C++', False), ('C', 'C#', False), ('C', 'C', True),
    ('C++', 'C++17', True), ('C#', 'C# / .NET', True),
    ('.NET', 'ASP.NET Core', True), ('.NET', '.NET 8', True),
    ('AWS', 'AWS Lambda', True), ('R', 'CRM', False), ('R', 'R', True),
    ('React', 'Reactive programming', False), ('React', 'React.js', True),
    ('Node.js', 'Node', True), ('Node.js', 'NodeJS 20', True),
    ('NodeJS', 'Node.js', True), ('Node', 'Node JS', True),
    ('Node.js', 'multi-node SDN networks', False), ('Node', 'node_modules', False),
    ('React.js', 'React', True), ('ReactJS', 'React.js 18', True),
    ('React', 'ReactJS', True), ('React.js', 'Reactive programming', False),
    ('Node.js', 'Node.jsOther', False), ('React.js', 'React.jsOther', False),
    ('Node.js', 'Node.js.', True), ('React.js', 'React.js.', True),
    ('Machine Learning', 'Machine Learning / Python', True),
])
def test_required_skill_tokens_are_bounded_without_losing_versions(wanted, have, expected):
    criteria = parse_search_criteria('Required skills: '+wanted)
    assert criteria.required_skills, 'An explicit C/R requirement must not disappear'
    result = evaluate_criteria(analysis(skills=[have]), criteria)
    assert not result['misses'] if expected else result['misses']


@pytest.mark.parametrize('label,expected', [
    ('English (native)', True), ('English (professional)', True),
    ('English (implied)', False), ('English (not provided)', False),
    ('English (assumed)', False), ('English (inferred)', False),
    ('English (unknown)', False), ('English (N/A)', False),
])
def test_preselection_and_final_language_checks_agree(label, expected):
    source = analysis(languages=[label])
    criteria = SearchCriteria(required_languages=['english'])
    final = evaluate_criteria(source, criteria)
    profile = profile_from_analysis(source)
    preselected = evaluate_criteria(profile_to_analysis(profile), criteria)
    assert bool(not final['misses']) is expected
    assert bool(not preselected['misses']) is expected


def test_strict_search_never_pads_with_wrong_city_or_similarly_named_skill():
    query = 'Developer based in Dubai, UAE. Required skills: Java'
    criteria = parse_search_criteria(query)
    rows = [
        {'id':'exact','gemini_analysis': analysis('Dubai, UAE', ['Java'])},
        {'id':'wrong-city','gemini_analysis': analysis('Sharjah, UAE', ['Java'])},
        {'id':'wrong-skill','gemini_analysis': analysis('Dubai, UAE', ['JavaScript'])},
    ]
    apply_criteria_to_results(rows, criteria, strict=True, min_kept=10)
    assert [row['id'] for row in rows] == ['exact']
    pooled = [
        {'id':'exact','candidate_location':'Dubai, UAE','candidate_skills':['Java'],'score':.7},
        {'id':'wrong-city','candidate_location':'Sharjah, UAE','candidate_skills':['Java'],'score':.99},
        {'id':'wrong-skill','candidate_location':'Dubai, UAE','candidate_skills':['JavaScript'],'score':.99},
    ]
    assert [row['id'] for row in _rank_rows(pooled, query, 10)] == ['exact']


@pytest.mark.parametrize('source', [
    None, [], {'hr_scorecard':['invalid']},
    {'candidate_overview':['invalid'],'detailed_analysis':['invalid']},
    {'candidate_overview':{'location':['Dubai'],'experience_years':{'years':5},'skills':[{'name':'Java'}]},
     'detailed_analysis':{'languages':[{'name':'English'}]}},
])
def test_malformed_candidate_fields_fail_closed_without_aborting_search(source):
    criteria = SearchCriteria(min_years=5,location='dubai',required_skills=['java'],required_languages=['english'])
    result = evaluate_criteria(source, criteria)
    assert {miss['criterion'] for miss in result['misses']} == {'experience_years','location','skill','language'}
    rows = [{'gemini_analysis':source}]
    apply_criteria_to_results(rows, criteria, strict=True)
    assert rows == []


@pytest.mark.parametrize('raw,expected',[('9 months',.75),('6 mos',.5),('0 Years',0),('3 years 9 months',3.75)])
def test_months_are_not_treated_as_years_in_preselection(raw, expected):
    assert parse_years(raw) == expected


def test_known_zero_experience_is_not_replaced_by_fallback():
    assert merge_profiles({'candidate_years':0},{'candidate_years':10})['candidate_years'] == 0


