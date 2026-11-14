"""Opt-in, local-only suggestions; never substitute them for verified exact results."""
import math
import re

from search_criteria import evaluate_criteria, parse_search_criteria
from services.resume_folders import source_in_folders
from vps_local.profile_extractor import profile_from_row, profile_to_analysis


def search(query, count, tenant_filter, folders, filters):
    from vps_local.discovery_shim import _vector_search

    criteria = parse_search_criteria(query)
    # Only this explicit preview bypasses qualification preselection. SQL still
    # applies the unchanged tenant/folder/tag/date scope before vector ranking.
    pool = _vector_search(query, min(100, max(count * 5, 25)), tenant_filter,
                          folders, filters, criteria_query='')
    suggestions, seen = [], set()
    for row in pool:
        filename, bucket = row.get('filename') or '', row.get('storage_bucket') or ''
        if not filename or any(c in filename for c in '/\\') or filename in ('.', '..') or not bucket:
            continue
        key = '/'.join(part for part in (row.get('folder') or '', filename) if part)
        uri = f'gs://{bucket}/{key}'
        if uri in seen or (folders and not source_in_folders(uri, folders)):
            continue
        profile = profile_from_row(row, required_skills=criteria.required_skills)
        evaluation = evaluate_criteria(profile_to_analysis(profile), criteria)
        misses = evaluation.get('misses') or []
        similarity = float(row.get('score') or 0)
        if not math.isfinite(similarity):
            similarity = 0
        years = profile.get('candidate_years')
        distance = 0
        if criteria.min_years is not None or criteria.max_years is not None:
            if years is None:
                distance = math.inf
            else:
                if criteria.min_years is not None:
                    distance += max(0, criteria.min_years - years)
                if criteria.max_years is not None:
                    distance += max(0, years - criteria.max_years)
        suggestions.append({
            'id': str(row['id']), 'file_path': uri,
            'file_name': re.sub(r'^(?:graph_[a-f0-9]{12,64}_|[a-f0-9]{24,64}_)', '', filename, flags=re.I),
            'experience_years': profile.get('candidate_years'),
            'location': profile.get('candidate_location') or '',
            'skills': (profile.get('candidate_skills') or [])[:30],
            'matched_criteria': evaluation.get('matches') or [],
            'unmet_criteria': misses,
            'verification': 'indexed_profile_only',
            '_rank': (len(misses), distance, -similarity),
        })
        seen.add(uri)
    suggestions.sort(key=lambda row: row['_rank'])
    results = suggestions[:count]
    for result in results:
        result.pop('_rank')
    return results
