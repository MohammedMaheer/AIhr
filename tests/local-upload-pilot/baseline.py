"""Run only against synthetic fixtures in a network-isolated runtime."""

import base64
from copy import deepcopy
import json
from math import sqrt
import os
from pathlib import Path
from statistics import median
import tempfile
from time import perf_counter

from vps_local import discovery_shim as search


def cosine(left, right):
    return sum(a * b for a, b in zip(left, right, strict=True)) / sqrt(
        sum(v * v for v in left) * sum(v * v for v in right)
    )


def elapsed(start):
    return round((perf_counter() - start) * 1000, 2)


def compare(payload):
    revision = (Path(os.environ['SENTENCE_TRANSFORMERS_HOME']) /
                'models--sentence-transformers--all-MiniLM-L6-v2/refs/main').read_text().strip()
    assert revision == payload['revision'], revision
    files = []
    with tempfile.TemporaryDirectory() as temp:
        for case in payload['files']:
            source = Path(temp) / 'fixture.pdf'
            source.write_bytes(base64.b64decode(case['pdf']))
            start = perf_counter()
            text = search._extract_text_from_file(source)
            extract_ms = elapsed(start)
            vector = search._embed_query(text)
            files.append(dict(case, text=text, vector=vector, vps_ms=elapsed(start), extract_ms=extract_ms))
    model = search.vertexai_shim._get_embedder()
    assert model.max_seq_length == 256
    assert model.get_sentence_embedding_dimension() == 384

    comparisons = []
    for probe in payload['probes']:
        vector = search._embed_query(probe['text'])
        comparisons.append(cosine(vector, probe['vector']))
    same_text = min(comparisons)
    same_bytes = sum(case['text'] == case['browserText'] for case in files)
    rank_report = []
    for query in payload['queries']:
        qvec = search._embed_query(query['text'])

        def ranked(browser):
            rows = []
            for case in files:
                text = case['browserText'] if browser else case['text']
                vec = case['browserVector'] if browser else case['vector']
                rows.append({
                    'id': case['id'], 'text': text, 'score': cosine(qvec, vec),
                    **search.profile_from_text(text, source='text_incremental'),
                })
            # Candidate pool is fixed and exhaustive. SQL/keyword scoring is not exercised.
            rows.sort(key=lambda row: row['score'], reverse=True)
            ranked_rows = search._rank_rows(rows, query['text'], query['limit'])
            return [(row['id'], row.get('criteria_profile_status', 'no_criteria')) for row in ranked_rows]

        vps, browser = ranked(False), ranked(True)
        rank_report.append({
            'case': query['name'], 'ordered_match': browser == vps,
            'same_members_and_statuses': set(browser) == set(vps),
            'vps_count': len(vps), 'browser_count': len(browser),
            'vps_first': vps[0][0] if vps else None,
            'browser_first': browser[0][0] if browser else None,
            'vps_exact': sum(status == 'exact' for _, status in vps),
            'browser_exact': sum(status == 'exact' for _, status in browser),
        })

    warm = files[1:]
    report = {
        'revision': revision,
        'vps_process_cold_ms': files[0]['vps_ms'],
        'vps_warm_median_ms': round(median(case['vps_ms'] for case in warm), 2),
        'vps_warm_extraction_median_ms': round(median(case['extract_ms'] for case in warm), 2),
        'same_input_probes': len(comparisons),
        'same_input_min_cosine': same_text,
        'exact_pdf_text': same_bytes,
        'pdf_count': len(files),
        'end_to_end_min_cosine': min(cosine(case['vector'], case['browserVector']) for case in files),
        'different_text_fixtures': [case['id'] for case in files if case['text'] != case['browserText']],
        'rank_comparisons': rank_report,
    }
    print('PILOT_REPORT:' + json.dumps(report))
