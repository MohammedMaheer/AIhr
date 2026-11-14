from unittest.mock import MagicMock

import pytest

import main
from services import similar_candidates
from vps_local import discovery_shim
from test_integration_workflows import api


@pytest.fixture(autouse=True)
def isolated_request_limits():
    main.limiter.reset()
    yield
    main.limiter.reset()


def row(id, *, years=4, location='Dubai, UAE', skills=None, score=.8, folder='resumes'):
    return {'id': id, 'filename': f'fixture-{id}.pdf', 'storage_bucket': 'qa-bucket',
            'folder': folder, 'candidate_years': years, 'candidate_location': location,
            'candidate_skills': skills if skills is not None else ['Python'], 'score':score}


def test_opt_in_similarity_retains_near_misses_and_scope_without_paid_models(monkeypatch):
    scopes=[{'bucket':'qa-bucket','path':'resumes'}]
    filters={'tags':['Data and AI'],'date_basis':'received','date_from':'2026-01-01'}
    calls=[]
    def search(*args,**kwargs):
        calls.append((args,kwargs))
        return [row(1,score=.7),row(2,years=2,score=.99),row(3,location='Chennai, India'),
                row(4,skills=['JavaScript']),row(5,folder='excluded')]
    monkeypatch.setattr(discovery_shim,'_vector_search',search)
    result=similar_candidates.search('Engineer based in Dubai with 3-5 years. Required skills: Python.',10,
                                     'company_id: ANY("1")',scopes,filters)
    assert len(result)==4 and result[0]['id']=='1'
    assert calls[0][0][2:] == ('company_id: ANY("1")',scopes,filters)
    assert calls[0][1]=={'criteria_query':'','profile_preview':True}
    assert all(r['verification']=='indexed_profile_only' for r in result)
    assert all('match_score' not in r and 'text' not in r and 'gemini_analysis' not in r for r in result)
    assert {m['criterion'] for r in result for m in r['unmet_criteria']} >= {'skill','experience_years','location'}


def test_similar_preview_never_pads_duplicates_or_accepts_invalid_paths(monkeypatch):
    rows=[row(1),row(1),dict(row(2),filename='../invalid.pdf'),dict(row(3),storage_bucket='')]
    monkeypatch.setattr(discovery_shim,'_vector_search',lambda *a,**k:rows)
    assert len(similar_candidates.search('Python developer',10,'',[],{}))==1


def test_equal_gap_counts_prioritize_nearest_experience_before_semantics(monkeypatch):
    monkeypatch.setattr(discovery_shim,'_vector_search',lambda *a,**k:[
        row('far',years=20,score=.99),row('near',years=6,score=.6)])
    result=similar_candidates.search('Engineer with 3-5 years. Required skills: Python.',10,'',[],{})
    assert [r['id'] for r in result]==['near','far']


def test_absent_profile_fields_remain_unverified_not_an_invented_exact_score(monkeypatch):
    monkeypatch.setattr(discovery_shim,'_vector_search',lambda *a,**k:[row(1,years=None,location='',skills=[])])
    result=similar_candidates.search('Developer in Dubai with 5+ years. Required skills: Python',10,'',[],{})
    assert result[0]['experience_years'] is None and result[0]['location']==''
    assert len(result[0]['unmet_criteria'])==3


def test_similar_api_auth_csrf_and_validation(api,monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    backend=MagicMock();monkeypatch.setattr(similar_candidates,'search',backend)
    assert client.post('/api/similar-candidates',data={'query':''}).status_code in (400,422)
    assert client.post('/api/similar-candidates',data={'query':'   '}).status_code==400
    assert client.post('/api/similar-candidates',data={'query':'Python','filters':'{"date_from":"2026-12-31","date_to":"2026-01-01"}'}).status_code==422
    assert client.post('/api/similar-candidates',data={'query':'Python','filters':'{"tags":["invalid"]}'}).status_code==422
    backend.assert_not_called()
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/similar-candidates',data={'query':'Python'}).status_code==403
    client.cookies.clear()
    assert client.post('/api/similar-candidates',data={'query':'Python'}).status_code in (401,403)


def test_similar_api_preserves_tenant_and_explicit_scope(api,monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    monkeypatch.setattr(main,'get_company_resources',lambda u:('qa-bucket','qa-store'))
    from services import resume_folders
    monkeypatch.setattr(resume_folders,'searchable_count',lambda *a,**k:3)
    called=MagicMock(return_value=[{'verification':'indexed_profile_only'}])
    monkeypatch.setattr(similar_candidates,'search',called)
    response=client.post('/api/similar-candidates',data={'query':'Engineer in Dubai with 3-5 years',
        'result_count':'10','folders':'[{"bucket":"qa-bucket","path":"resumes"}]',
        'filters':'{"tags":["Data and AI"],"date_basis":"received","date_from":"2026-01-01"}'})
    assert response.status_code==200,response.text
    assert response.json()['paid_ai_calls']==0 and response.json()['match_mode']=='similar'
    assert called.call_args.args[1:4]==(10,'company_id: ANY("1")',[{'bucket':'qa-bucket','path':'resumes'}])
    assert called.call_args.args[4]['date_basis']=='received'
    db.check_search_limit.assert_called_once_with(1)


def test_empty_scope_skips_even_local_embedding(api,monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    from services import resume_folders
    monkeypatch.setattr(resume_folders,'searchable_count',lambda *a,**k:0)
    called=MagicMock();monkeypatch.setattr(similar_candidates,'search',called)
    response=client.post('/api/similar-candidates',data={'query':'Engineer','result_count':'10'})
    assert response.status_code==200 and response.json()['results']==[]
    called.assert_not_called()


def test_all_authorized_folders_preserve_other_filters_but_explicit_empty_is_invalid(api,monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    from services import resume_folders
    monkeypatch.setattr(resume_folders,'searchable_count',lambda *a,**k:2)
    called=MagicMock(return_value=[])
    monkeypatch.setattr(similar_candidates,'search',called)
    data={'query':'Python developer','filters':'{"tags":["Data and AI"],"date_from":"2026-01-01"}'}
    response=client.post('/api/similar-candidates',data=data)
    assert response.status_code==200,response.text
    assert called.call_args.args[3] == []
    assert called.call_args.args[4]['tags']==['Data and AI']
    assert called.call_args.args[4]['date_from']=='2026-01-01'
    called.reset_mock()
    assert client.post('/api/similar-candidates',data={**data,'folders':'[]'}).status_code==422
    called.assert_not_called()


def test_similar_unavailable_outside_local_mode_fails_closed(api,monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','0')
    assert client.post('/api/similar-candidates',data={'query':'Engineer'}).status_code==501


def test_similar_errors_are_sanitized_and_company_limits_respected(api,monkeypatch):
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    db.check_search_limit.side_effect=RuntimeError('private-database-marker')
    r=client.post('/api/similar-candidates',data={'query':'Engineer'})
    assert r.status_code==503 and 'private-database-marker' not in r.text
    db.check_search_limit.side_effect=RuntimeError('maximum search limit')
    assert client.post('/api/similar-candidates',data={'query':'Engineer'}).status_code==400


def test_similar_api_rate_limit_prevents_unbounded_local_inference(api,monkeypatch):
    client,db=api
    monkeypatch.setattr(main.limiter,'enabled',True)
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    from services import resume_folders
    monkeypatch.setattr(resume_folders,'searchable_count',lambda *a,**k:0)
    for _ in range(10):
        assert client.post('/api/similar-candidates',data={'query':'Engineer'}).status_code==200
    assert client.post('/api/similar-candidates',data={'query':'Engineer'}).status_code==429


def test_busy_preview_does_not_queue_more_embedding_work(monkeypatch):
    import threading
    slots=threading.BoundedSemaphore(1)
    monkeypatch.setattr(similar_candidates,'_slots',slots)
    called=MagicMock()
    monkeypatch.setattr(similar_candidates,'_search',called)
    assert slots.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError,match='busy'):
            similar_candidates.search('Engineer',10,'',[],{})
        called.assert_not_called()
    finally:
        slots.release()
    called.side_effect=ValueError('Test failure')
    with pytest.raises(ValueError):
        similar_candidates.search('Engineer',10,'',[],{})
    assert slots.acquire(blocking=False),'Failed searches must release their worker slot'
    slots.release()


@pytest.mark.parametrize('disconnected',[True,False])
def test_disconnected_client_skips_new_embedding_work(api,monkeypatch,disconnected):
    from unittest.mock import AsyncMock
    from starlette.requests import Request
    from services import resume_folders
    client,db=api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    calls=AsyncMock(side_effect=[True] if disconnected else [False,True])
    monkeypatch.setattr(Request,'is_disconnected',calls)
    count=MagicMock(return_value=3)
    monkeypatch.setattr(resume_folders,'searchable_count',count)
    search=MagicMock()
    monkeypatch.setattr(similar_candidates,'search',search)
    assert client.post('/api/similar-candidates',data={'query':'Engineer'}).status_code==499
    search.assert_not_called()
    assert count.call_count==(0 if disconnected else 1)
    if not disconnected:
        assert count.call_args.kwargs=={'timeout_ms':5000}
