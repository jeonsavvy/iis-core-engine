from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "IIS Core Engine"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    internal_api_token: str | None = None

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "games"

    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"

    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_webhook_secret: str | None = None
    telegram_control_enabled: bool = False
    telegram_allow_dangerous_commands: bool = False
    telegram_confirm_ttl_seconds: int = Field(default=120, ge=30, le=600)
    telegram_confirm_secret: str | None = None

    x_api_base_url: str = "https://api.x.com"
    x_bearer_token: str | None = None
    x_auto_post_enabled: bool = False
    x_posts_per_game_per_day: int = Field(default=1, ge=1, le=10)
    x_daily_stop_on_error: bool = True
    x_quota_state_file: str = ".x_quota_state.json"

    github_token: str | None = None
    github_archive_repo: str | None = None
    github_archive_branch: str = "main"
    github_api_base_url: str = "https://api.github.com"

    public_games_base_url: str = "https://cdn.example.com/games"
    public_portal_base_url: str | None = None

    playwright_required: bool = False
    qa_smoke_timeout_seconds: float = Field(default=8.0, ge=2.0, le=60.0)
    qa_min_quality_score: int = Field(default=40, ge=0, le=100)
    qa_min_gameplay_score: int = Field(default=55, ge=0, le=100)
    qa_min_visual_score: int = Field(default=45, ge=0, le=100)
    qa_min_artifact_contract_score: int = Field(default=70, ge=0, le=100)
    qa_hard_gate: bool = False
    builder_candidate_count: int = Field(default=1, ge=1, le=5)
    builder_codegen_enabled: bool = True
    builder_codegen_passes: int = Field(default=1, ge=0, le=2)
    builder_codegen_max_output_tokens: int = Field(default=12_000, ge=512, le=65_536)
    builder_force_pro_model: bool = True
    builder_scope_guard_enabled: bool = True
    builder_asset_memory_enabled: bool = True
    builder_quality_floor_enforced: bool = True
    builder_quality_floor_score: int = Field(default=72, ge=0, le=100)
    builder_runtime_signature_guard: bool = True
    builder_playability_hard_gate: bool = True
    builder_playability_refinement_rounds: int = Field(default=2, ge=0, le=4)
    pipeline_contract_enforcement: str = Field(default="warn_only", pattern=r"^(strict|warn_only)$")
    qa_retry_source: str = Field(default="builder_only", pattern=r"^(builder_only|qa_or_builder)$")
    pipeline_default_version: str = Field(default="forgeflow-v1", min_length=1, max_length=40)

    pipeline_poll_interval_seconds: float = Field(default=3.0, ge=0.5, le=30.0)
    pipeline_stale_after_seconds: int = Field(default=900, ge=60, le=86400)
    pipeline_worker_concurrency: int = Field(default=1, ge=1, le=8)
    trigger_min_keyword_length: int = Field(default=1, ge=1, le=32)
    trigger_forbidden_keywords: str = ""
    http_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    http_max_retries: int = Field(default=3, ge=1, le=5)

    def telegram_allowed_chat_id_set(self) -> set[str]:
        return {chat_id.strip() for chat_id in self.telegram_allowed_chat_ids.split(",") if chat_id.strip()}

    def telegram_allowed_user_id_set(self) -> set[str]:
        return {user_id.strip() for user_id in self.telegram_allowed_user_ids.split(",") if user_id.strip()}

    def trigger_forbidden_keyword_set(self) -> set[str]:
        return {
            keyword.strip().casefold()
            for keyword in self.trigger_forbidden_keywords.split(",")
            if keyword.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
