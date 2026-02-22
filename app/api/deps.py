from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.pipeline_repository import PipelineRepository


@lru_cache(maxsize=1)
def get_pipeline_repository() -> PipelineRepository:
    settings: Settings = get_settings()
    return PipelineRepository.from_settings(settings)
