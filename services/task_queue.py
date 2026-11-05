"""PostgreSQL-backed search workers; no provider calls while the queue is idle."""
import asyncio
from contextlib import suppress
import logging
import os

from services.task_lease import PermanentTaskError, TaskLeaseLost, current_lease

logger = logging.getLogger(__name__)


def local_queue_enabled():
    return os.getenv("USE_CLOUD_TASKS", "true").strip().lower() in {"false", "0", "no"}


class SearchWorker:
    def __init__(self, get_database, execute, *, poll_seconds=2, heartbeat_seconds=20,
                 lease_seconds=120, max_attempts=3, max_active=2, timeout_seconds=900):
        if heartbeat_seconds <= 0 or lease_seconds < heartbeat_seconds * 3:
            raise ValueError("The task lease must cover at least three heartbeats")
        self.get_database = get_database
        self.execute = execute
        self.poll_seconds = poll_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.lease_seconds = lease_seconds
        self.max_attempts = max(1, min(int(max_attempts), 3))
        self.max_active = max(1, min(int(max_active), 4))
        if timeout_seconds <= 0:
            raise ValueError("Search execution timeout must be positive")
        self.timeout_seconds = timeout_seconds
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.run(), name="durable-search-worker")

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def _heartbeat(self, database, job):
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            owned = await asyncio.to_thread(database.renew_hr_task_lease,
                                            job["task_id"], job["lease_token"], self.lease_seconds)
            if not owned:
                raise TaskLeaseLost("Search ownership expired")

    async def process(self, database, job):
        context = current_lease.set((job["task_id"], job["lease_token"]))
        work = heartbeat = None
        try:
            work = asyncio.create_task(self.execute(job["task_payload"]))
            heartbeat = asyncio.create_task(self._heartbeat(database, job))
            done, _ = await asyncio.wait((work, heartbeat), timeout=self.timeout_seconds,
                                         return_when=asyncio.FIRST_COMPLETED)
            if not done:
                raise PermanentTaskError("Search exceeded its execution window")
            if work in done:
                outcome = await work
                if not outcome or not outcome.get("success"):
                    raise PermanentTaskError("Search could not be completed with the supplied input")
            else:
                await heartbeat
        except asyncio.CancelledError:
            # Leave the lease in place: an in-flight provider thread may still be finishing.
            # Another process can recover it after expiry without accepting stale writes.
            raise
        except TaskLeaseLost:
            logger.warning("Search lease lost for task %s", job["task_id"])
        except Exception as exc:
            if work:
                work.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await work
            permanent = isinstance(exc, PermanentTaskError) or getattr(exc, "status_code", 500) in (400, 403, 404, 422)
            error = "Search failed. Please retry or contact support with the task ID."
            logger.warning("Search attempt failed: task=%s attempt=%s type=%s",
                           job["task_id"], job["attempt_count"], type(exc).__name__)
            await asyncio.to_thread(database.release_hr_task, job["task_id"], job["lease_token"],
                                    error, self.max_attempts, permanent)
        finally:
            for task in (work, heartbeat):
                if task:
                    task.cancel()
            for task in (work, heartbeat):
                if task:
                    with suppress(asyncio.CancelledError, Exception):
                        await task
            current_lease.reset(context)

    async def run(self):
        while True:
            try:
                database = await asyncio.to_thread(self.get_database)
                if database is None:
                    raise RuntimeError("Search database unavailable")
                job = await asyncio.to_thread(database.claim_next_hr_task,
                                              self.lease_seconds, self.max_attempts, self.max_active)
                if job:
                    await self.process(database, job)
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Search queue poll failed: %s", type(exc).__name__)
            await asyncio.sleep(self.poll_seconds)


async def gather_candidates(awaitables):
    """Do not leave sibling provider tasks running after a failed/cancelled batch."""
    tasks = [asyncio.create_task(item) for item in awaitables]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
