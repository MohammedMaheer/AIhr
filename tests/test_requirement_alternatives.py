"""Deterministic eligibility and safe Boolean parsing, without paid AI calls."""
import pytest

from search_criteria import _extract_candidate_years, _parse_years_string, evaluate_criteria, parse_search_criteria
from services import requirements_logic as logic
from vps_local.profile_extractor import parse_years, profile_from_analysis


@pytest.mark.parametrize('query,skills,languages,expected', [
    ('Developer who speaks English or Arabic', [], ['English'], True),
    ('Developer who speaks English or Arabic', [], ['French'], False),
    ('Developer who speaks English and Arabic', [], ['English'], False),
    ('Developer proficient in English', [], ['English'], True),
    ('Required skills: Python or Java', ['Java'], [], True),
    ('Required skills: Python or Java', ['JavaScript'], [], False),
    ('Required skills: Python and .NET', ['Python'], [], False),
    ('Required skills: Python and .NET', ['Python', 'ASP.NET Core'], [], True),
    ('Required skills: Python and (Java or SQL)', ['Python', 'SQL Server'], [], True),
    ('Required skills: Python and (Java or SQL)', ['SQL Server'], [], False),
    ('Required skills: (Python or Java) and SQL', ['Java', 'MySQL'], [], True),
    ('Required skills: (Python or Java) and SQL', ['Java'], [], False),
    ('Required skills: Python or Java and SQL', ['Python'], [], True),
    ('Required skills: Python or Java and SQL', ['Java'], [], False),
    ('Required skills: Python or Java. Must have SQL', ['Python'], [], False),
    ('Required skills: Python or Java. Must have SQL', ['Python', 'SQL'], [], True),
    ('Required skills: Node.js or .NET', ['.NET 8'], [], True),
    ('Required skills: Node.js or .NET', ['Python'], [], False),
    ('Required skills: Python or Java. Languages: English or Arabic', ['Java'], ['Arabic'], True),
    ('Required skills: Python or Java. Languages: English or Arabic', ['Java'], ['French'], False),
])
def test_explicit_alternatives_and_conjunctions(query, skills, languages, expected):
    criteria = parse_search_criteria(query)
    result = evaluate_criteria({'candidate_overview': {'skills': skills},
                                'detailed_analysis': {'languages': languages}}, criteria)
    assert (not result['misses']) is expected


@pytest.mark.parametrize('raw,expected', [
    ('9 months', .75), ('3-5 Years', 3), ('3 yrs 9 months', 3.75),
    ('0.5 Years + 0.5 Years', 1), ('5+ years', 5), ('2021-2024', None),
    (True, None), (float('inf'), None), (float('nan'), None),
    ('3 months', .25), ('no experience', 0), ('5 to 3 years', None),
    ('1000 years', None), ('-3 years', None), ('unknown', None),
])
def test_shortlist_and_final_experience_conversion_are_identical(raw, expected):
    assert _parse_years_string(raw) == expected
    assert parse_years(raw) == expected


@pytest.mark.parametrize('scorecard,expected', [
    ({'candidate_overview': {'experience_years': 0}}, 0),
    ({'candidate_overview': {'experience_years': 'not specified', 'total_experience': '5 years'}}, 5),
    ({'candidate_overview': {'experience_years': '2 years', 'total_experience': '5 years'}}, 5),
    ({'experience_fit_analysis': {'candidate_total_experience': '9 months'}}, .75),
])
def test_profile_and_final_filter_select_the_same_experience_fields(scorecard, expected):
    source = {'hr_scorecard': scorecard}
    assert profile_from_analysis(source)['candidate_years'] == expected
    assert _extract_candidate_years(source) == expected


def test_boolean_compiler_preserves_precedence_parentheses_and_parameters():
    expression = logic.compile_clause('(Python or Java) and SQL', str.lower)
    assert logic.evaluate(expression, {'java', 'sql'}.__contains__)
    assert not logic.evaluate(expression, {'java'}.__contains__)
    sql, params = logic.sql(expression, lambda term: ('%s = ANY(skills)', [term]))
    assert sql == '((%s = ANY(skills) OR %s = ANY(skills)) AND %s = ANY(skills))'
    assert params == ['python', 'java', 'sql']
    assert logic.label(expression) == '((python or java) and sql)'


@pytest.mark.parametrize('text', [
    'a or', '(a or b', 'a or or b', 'a or '*65+'b',
    '('*25+'a or b'+')'*25, 'a'*4097+' or b',
])
def test_malformed_or_oversized_clauses_are_rejected(text):
    assert logic.compile_clause(text, str.lower) is None


def test_text_is_never_executed_or_interpolated_into_sql():
    payload = '__import__("os").system("false")'
    assert logic.compile_clause('a or '+payload, str.lower) is None
    expression = logic.compile_clause("x' 1=1 -- or java", str.lower)
    sql, params = logic.sql(expression, lambda term: ('skill = %s', [term]))
    assert '1=1' not in sql and '__import__' not in sql
    assert params and any('1=1' in term for term in params)


@pytest.mark.parametrize('expression', [None, [], {}, {'op':'all', 'items':[]},
    {'op':'not', 'items':[{'term':'a'}]}, {'op':'any', 'items':'a'}])
def test_invalid_trees_fail_closed(expression):
    assert not logic.evaluate(expression, lambda term: True)
    assert logic.sql(expression, lambda term: ('TRUE', [])) == ('FALSE', [])
