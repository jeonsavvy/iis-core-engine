from __future__ import annotations

from app.core.config import Settings
from app.services.session_publisher import SessionPublisher


def test_session_publisher_initializes_without_archive_repo_local_path_setting() -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    assert publisher is not None
