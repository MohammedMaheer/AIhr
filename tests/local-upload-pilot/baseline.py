"""Run only against synthetic fixtures in a network-isolated runtime."""

import base64
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


def check_revision(payload):
    revision = (Path(os.environ['SENTENCE_TRANSFORMERS_HOME']) /
                'models--sentence-transformers--all-MiniLM-L6-v2/refs/main').read_text().strip()
    assert revision == payload['revision'], revision
    return revision


def ranked_rows(files, vectors, query, qvec):
    rows = [dict(id=case['id'], text=case['text'], score=cosine(qvec, vector),
                 **search.profile_from_text(case['text'], source='text_incremental'))
            for case, vector in zip(files, vectors, strict=True)]
    # Fixed exhaustive pool; SQL retrieval and lexical scoring are not exercised.
    rows.sort(key=lambda row: row['score'], reverse=True)
    ranked = search._rank_rows(rows, query['text'], query['limit'])
    return [(r['id'], r.get('criteria_profile_status', 'no_criteria')) for r in ranked]


def compare(payload):
    revision = check_revision(payload)
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

        vps = ranked_rows(files, [case['vector'] for case in files], query, qvec)
        browser = ranked_rows([dict(case, text=case['browserText']) for case in files],
                              [case['browserVector'] for case in files], query, qvec)
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


def embedding_baseline(payload):
    revision = check_revision(payload)
    docs = []
    with tempfile.TemporaryDirectory() as temp:
        for item in payload['files']:
            path = Path(temp) / 'fixture.pdf'
            path.write_bytes(base64.b64decode(item['pdf']))
            text = search._extract_text_from_file(path)
            assert text and len(text) >= 30
            docs.append(dict(id=item['id'], text=text))
    docs.extend(payload['probes'])
    docs.sort(key=lambda item: len(item['text']))
    texts = [item['text'] for item in docs]
    encode = search.vertexai_shim.language_models.TextEmbeddingModel.from_pretrained('all-MiniLM-L6-v2').get_embeddings
    encode(['model warm-up'])
    model = search.vertexai_shim._get_embedder()
    assert model.max_seq_length == 256 and model.get_sentence_embedding_dimension() == 384

    def trials(size):
        batches = [texts[i:i + size] for i in range(0, len(texts), size)]
        latencies, totals = [], []
        for _ in range(3):
            start = perf_counter()
            vectors = []
            for batch in batches:
                t0 = perf_counter()
                vectors.extend(result.values for result in encode(batch))
                latencies.append(elapsed(t0))
            totals.append(elapsed(start))
        return round(median(latencies), 2), round(median(totals), 2), vectors

    single, single_corpus_ms, vectors = trials(1)
    _, batched_corpus_ms, batched_vectors = trials(payload['batchSize'])
    print('PILOT_REPORT:' + json.dumps({
        'revision': revision, 'docs': docs, 'vectors': vectors, 'batchedVectors': batched_vectors,
        'queryVectors': [search._embed_query(query['text']) for query in payload['queries']],
        'single_ms': single, 'single_corpus_ms': single_corpus_ms, 'batched_corpus_ms': batched_corpus_ms,
    }))


def embedding_rank(payload):
    check_revision(payload)
    label, vectors = payload['baseline'], payload['vectors']
    docs = payload['docs']
    assert len(docs) == len(vectors) and len(vectors) >= len(payload['candidateIds'])
    eligible = [i for i, doc in enumerate(docs) if doc['id'] in payload['candidateIds']]
    pool = [docs[i] for i in eligible]

    def ranks(items):
        return [ranked_rows(pool, [items[i] for i in eligible], q, qvec)
                for q, qvec in zip(payload['queries'], payload['queryVectors'], strict=True)]

    reference = ranks(vectors)
    strict = next(i for i, q in enumerate(payload['queries']) if q['name'] == 'ten-full-stack')
    assert len(reference[strict]) == 10 and all(status == 'exact' for _, status in reference[strict])
    report = {}
    for variant, outputs in {label: vectors, **payload['variants']}.items():
        similarities = [cosine(a, b) for a, b in zip(vectors, outputs, strict=True)]
        ordering = ranks(outputs)
        changed = [q['name'] for q, before, after in zip(payload['queries'], reference, ordering, strict=True)
                   if before != after]
        report[variant] = {'minCosine': min(similarities), 'changedQueries': changed,
                           'passesParity': min(similarities) >= 0.9999 and not changed}
    print('PILOT_REPORT:' + json.dumps(report))
