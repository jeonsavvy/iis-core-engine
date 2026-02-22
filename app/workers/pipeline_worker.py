from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.orchestration.runner import PipelineRunner
from app.services.pipeline_repository import PipelineRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_worker_forever() -> None:
    settings = get_settings()
    repository = PipelineRepository.from_settings(settings)
    runner = PipelineRunner(repository=repository, settings=settings)

    logger.info("ForgeFlow worker started. poll_interval=%s", settings.pipeline_poll_interval_seconds)

    while True:
        requeued = repository.requeue_stale_running_pipelines(settings.pipeline_stale_after_seconds)
        if requeued:
            logger.warning("Requeued stale running pipelines: %s", requeued)

        job = repository.claim_next_queued_pipeline()
        if not job:
            await asyncio.sleep(settings.pipeline_poll_interval_seconds)
            continue

        logger.info("Processing pipeline %s", job.pipeline_id)
        await asyncio.to_thread(runner.run, job)


if __name__ == "__main__":
    asyncio.run(run_worker_forever())
