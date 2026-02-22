from __future__ import annotations

from supabase import Client, create_client

from app.core.config import Settings


def create_supabase_admin_client(settings: Settings) -> Client | None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
