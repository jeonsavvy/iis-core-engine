from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.orchestration.runner import PipelineRunner
from app.services.pipeline_repository import PipelineRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _run_job(runner: PipelineRunner, job_id: str, job) -> None:
    try:
        await asyncio.to_thread(runner.run, job)
    except Exception as exc:  # pragma: no cover - runtime safeguard
        logger.exception("Pipeline job crashed: %s (%s)", job_id, exc)


async def run_worker_forever() -> None:
    settings = get_settings()
    repository = PipelineRepository.from_settings(settings)
    runner = PipelineRunner(repository=repository, settings=settings)
    running_tasks: set[asyncio.Task[None]] = set()
    concurrency = max(1, settings.pipeline_worker_concurrency)

    logger.info(
        "ForgeFlow worker started. poll_interval=%s concurrency=%s",
        settings.pipeline_poll_interval_seconds,
        concurrency,
    )

    while True:
        requeued = repository.requeue_stale_running_pipelines(settings.pipeline_stale_after_seconds)
        if requeued:
            logger.warning("Requeued stale running pipelines: %s", requeued)

        done_tasks = {task for task in running_tasks if task.done()}
        for task in done_tasks:
            running_tasks.discard(task)
            if task.cancelled():
                continue
            task.exception()

        while len(running_tasks) < concurrency:
            job = repository.claim_next_queued_pipeline()
            if not job:
                break

            logger.info("Processing pipeline %s", job.pipeline_id)
            task = asyncio.create_task(_run_job(runner, str(job.pipeline_id), job))
            running_tasks.add(task)

        if not running_tasks:
            await asyncio.sleep(settings.pipeline_poll_interval_seconds)
            continue

        done, pending = await asyncio.wait(
            running_tasks,
            timeout=settings.pipeline_poll_interval_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        running_tasks = done | pending


if __name__ == "__main__":
    asyncio.run(run_worker_forever())
