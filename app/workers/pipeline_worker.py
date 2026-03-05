"""Legacy pipeline worker — kept as a stub for backward compatibility.

The batch pipeline has been replaced by the interactive session API.
This module exists only to prevent import errors from existing deployment
scripts. The actual game generation now happens via:
  POST /api/v1/sessions/{id}/prompt
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_worker_forever() -> None:
    """Stub — the batch pipeline worker is no longer active."""
    logger.warning(
        "Legacy pipeline worker is deprecated. "
        "Game generation now uses the interactive session API. "
        "Remove this worker from your deployment."
    )
    # Sleep forever to prevent systemd restart loops
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_worker_forever())
