-- IIS publish copy metadata upgrade
-- Apply after session_first_big_bang.sql and session_async_collab_upgrade.sql

alter table public.games_metadata
  add column if not exists marketing_summary text;

alter table public.games_metadata
  add column if not exists play_overview jsonb not null default '[]'::jsonb;

alter table public.games_metadata
  add column if not exists controls_guide jsonb not null default '[]'::jsonb;

alter table public.games_metadata
  add column if not exists publish_copy_version text not null default 'v1';
