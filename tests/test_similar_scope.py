"""Real SQL and private fictional files, with deterministic local query vectors."""
import json

import pytest

from test_durable_search import queue_db  # noqa: F401
from test_folder_tag_e2e import flow,seed,FOLDER,BUCKET  # noqa: F401
from vps_local import discovery_shim


@pytest.mark.parametrize('advanced',[True,False])
def test_similar_preview_keeps_every_ingestion_scope_before_relaxing_qualifications(flow,monkeypatch,advanced):
    rows=seed(flow)
    monkeypatch.setattr(discovery_shim,'ADVANCED_SEARCH_ENABLED',advanced)
    cases=[
        ([FOLDER],{'tags':['UI design'],'date_basis':'received','date_from':'2026-04-01','date_to':'2026-04-30'},
         lambda r:r['original_filename']=='within.docx'),
        ([FOLDER],{'tags':['UI design'],'date_basis':'uploaded','date_from':'2026-04-01','date_to':'2026-04-30'},
         lambda r:r['folder']==FOLDER and r['original_filename']=='same-name.docx'),
        ([FOLDER,FOLDER+'-old'],{'tags':['UI design','Web design']},
         lambda r:r['folder'] in (FOLDER,FOLDER+'/sub',FOLDER+'-old') and bool(set(r['search_tags'])&{'UI design','Web design'})),
        ([FOLDER],{'tags':['Finance and accounting'],'date_basis':'received','date_from':'2026-04-01','date_to':'2026-04-30'},
         lambda r:False),
    ]
    for folders,filters,predicate in cases:
        form={'query':'Designer based in Dubai with 20-25 years. Required skills: Figma.', 'result_count':'10',
              'folders':json.dumps([{'bucket':BUCKET,'path':f} for f in folders]),'filters':json.dumps(filters)}
        strict=flow.client.post('/api/search-vector',data=form)
        assert strict.status_code==200 and strict.json()['results']==[],strict.text
        response=flow.client.post('/api/similar-candidates',data=form)
        assert response.status_code==200,response.text
        result=response.json()
        expected={str(r['id']) for r in rows if r['company_id']==1 and predicate(r)}
        assert {r['id'] for r in result['results']}==expected
        assert result['paid_ai_calls']==0
        assert all(r['verification']=='indexed_profile_only' for r in result['results'])


def test_empty_similar_scope_never_embeds_or_looks_outside_selection(flow,monkeypatch):
    seed(flow)
    def no_embedding(*a):raise AssertionError('An empty selected scope must not trigger model inference')
    monkeypatch.setattr(discovery_shim,'_embed_query',no_embedding)
    response=flow.client.post('/api/similar-candidates',data={'query':'Designer in Dubai',
        'folders':json.dumps([{'bucket':BUCKET,'path':'Missing folder'}]),'result_count':'10'})
    assert response.status_code==200 and response.json()['results']==[]


def test_profile_preview_keeps_indexed_details_with_advanced_ranking_disabled(flow,monkeypatch):
    seed(flow)
    with flow.db.get_cursor() as (cur,_):
        cur.execute("UPDATE resume_embeddings SET candidate_years=7,candidate_location='Sharjah' WHERE company_id=1")
        cur.execute("CREATE INDEX fixture_hnsw ON resume_embeddings USING hnsw (embedding vector_cosine_ops)")
    from services.similar_candidates import search
    results=[]
    for advanced in (True,False):
        monkeypatch.setattr(discovery_shim,'ADVANCED_SEARCH_ENABLED',advanced)
        rows=search('Designer in Dubai with 3-5 years. Required skills: Figma',10,'company_id: ANY("1")',[],{})
        assert rows and all(r['experience_years']==7 and r['location']=='sharjah' for r in rows)
        results.append(rows)
    assert results[0]==results[1]
    assert all(r['unmet_criteria'] for r in results[0])
