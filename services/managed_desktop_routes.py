"""Small, HTTPS-only API for enrolled managed desktop agents."""
import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from services.managed_desktop import RESULT_LIMIT


def route_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, 'Not available') from None


async def json_body(request, limit=2048):
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        value = json.loads(body)
    except (ValueError, RecursionError):
        raise HTTPException(400, 'Invalid request') from None
    if not isinstance(value, dict):
        raise HTTPException(400, 'Invalid request')
    return value


def reply(data, status=200):
    return JSONResponse(data, status_code=status, headers={'Cache-Control': 'no-store'})


def create_managed_desktop_router(require_admin, company_for, secure_request, run_upload_worker, limiter):
    router = APIRouter(prefix='/api/managed-desktop')

    def get_pool(request):
        scheduler = getattr(request.app.state, 'managed_desktop_scheduler', None)
        if not scheduler or not scheduler.pool.companies or not secure_request(request):
            raise HTTPException(404, 'Not available')
        return scheduler.pool

    def admin_pool(request, user):
        pool = get_pool(request)
        company = company_for(user)
        if company not in pool.companies:
            raise HTTPException(404, 'Not available')
        return pool, company

    def agent(request):
        kind, _, credential = request.headers.get('authorization', '').partition(' ')
        if kind.lower() != 'bearer':
            raise HTTPException(401, 'Worker authentication required')
        return route_id(request.headers.get('x-smarthr-worker-id')), credential

    @router.post('/admin/invites')
    @limiter.limit('6/minute')
    async def invite(request: Request, user=Depends(require_admin)):
        pool, company = admin_pool(request, user)
        code = await asyncio.to_thread(pool.invite, company)
        return reply({'enrollmentCode': code, 'expiresIn': 600}, 201)

    @router.get('/admin/workers')
    async def workers(request: Request, user=Depends(require_admin)):
        pool, company = admin_pool(request, user)
        records = await asyncio.to_thread(pool.workers, company)
        return reply({'workers': [{**row, 'last_seen': row['last_seen'].isoformat() if row['last_seen'] else None} for row in records]})

    @router.delete('/admin/workers/{worker_id}')
    async def revoke(request: Request, worker_id: str, user=Depends(require_admin)):
        pool, company = admin_pool(request, user)
        if not await asyncio.to_thread(pool.revoke, company, route_id(worker_id)):
            raise HTTPException(404, 'Not available')
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    @router.post('/enroll')
    @limiter.limit('12/minute')
    async def enroll(request: Request):
        pool = get_pool(request)
        body = await json_body(request)
        result = await asyncio.to_thread(pool.enroll, body.get('enrollmentCode'), body.get('name'), body.get('publicKey'))
        if not result:
            raise HTTPException(400, 'Enrollment could not be completed')
        return reply(result, 201)

    @router.post('/claim')
    async def claim(request: Request):
        pool = get_pool(request)
        worker, credential = agent(request)
        body = await json_body(request)
        job, authenticated = await asyncio.to_thread(pool.reserve, worker, credential, body.get('model'), body.get('ready'))
        if not authenticated:
            raise HTTPException(401, 'Worker authorization expired')
        if job:
            lease = await run_upload_worker(pool.materialize, job)
            if lease:
                return reply(lease)
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    @router.post('/jobs/{job_id}/complete')
    async def complete(request: Request, job_id: str):
        pool = get_pool(request)
        worker, credential = agent(request)
        body = await json_body(request, RESULT_LIMIT + 1024)
        result = await asyncio.to_thread(pool.complete, worker, credential, route_id(job_id), route_id(body.get('leaseId')),
                                         body.get('vectors'), body.get('signature'))
        if result is None:
            raise HTTPException(401, 'Worker authorization expired')
        if not result:
            raise HTTPException(409, 'Lease or result unavailable')
        return reply({'state': 'accepted'}, 202)

    return router
