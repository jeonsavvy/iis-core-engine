from dataclasses import dataclass

from app.services.github_service import GitHubArchiveService
from app.services.pipeline_repository import PipelineRepository
from app.services.publisher_service import PublisherService
from app.services.quality_service import QualityService
from app.services.telegram_service import TelegramService
from app.services.vertex_service import VertexService


@dataclass(frozen=True)
class NodeDependencies:
    repository: PipelineRepository
    telegram_service: TelegramService
    quality_service: QualityService
    publisher_service: PublisherService
    github_archive_service: GitHubArchiveService
    vertex_service: VertexService
