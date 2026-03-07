-- IIS public catalog / discovery upgrade
-- Additive only: extends games_metadata and introduces game_play_events

alter table if exists public.games_metadata
  add column if not exists short_description text;

alter table if exists public.games_metadata
  add column if not exists description text;

alter table if exists public.games_metadata
  add column if not exists genre_primary text;

alter table if exists public.games_metadata
  add column if not exists genre_tags jsonb not null default '[]'::jsonb;

alter table if exists public.games_metadata
  add column if not exists hero_image_url text;

alter table if exists public.games_metadata
  add column if not exists featured_rank int;

alter table if exists public.games_metadata
  add column if not exists released_at timestamptz;

alter table if exists public.games_metadata
  add column if not exists visibility text not null default 'public';

alter table if exists public.games_metadata
  add column if not exists play_count_cached int not null default 0;

alter table if exists public.games_metadata
  drop constraint if exists games_metadata_visibility_check;

alter table if exists public.games_metadata
  add constraint games_metadata_visibility_check
  check (visibility in ('public', 'hidden', 'unlisted'));

create index if not exists idx_games_metadata_public_discovery
on public.games_metadata (status, visibility, play_count_cached desc, created_at desc);

create table if not exists public.game_play_events (
  id uuid primary key default gen_random_uuid(),
  game_id uuid not null references public.games_metadata(id) on delete cascade,
  fingerprint_hash text not null check (char_length(fingerprint_hash) between 32 and 128),
  source text not null default 'portal',
  created_at timestamptz not null default now()
);

create index if not exists idx_game_play_events_game_created
on public.game_play_events (game_id, created_at desc);

create index if not exists idx_game_play_events_game_fingerprint
on public.game_play_events (game_id, fingerprint_hash, created_at desc);

grant select on public.game_play_events to authenticated;
grant all privileges on public.game_play_events to service_role;

alter table public.game_play_events enable row level security;

drop policy if exists game_play_events_master_admin_only on public.game_play_events;
create policy game_play_events_master_admin_only
on public.game_play_events
for select
to authenticated
using (public.is_master_admin());

drop policy if exists game_play_events_service_role_all on public.game_play_events;
create policy game_play_events_service_role_all
on public.game_play_events
for all
to service_role
using (true)
with check (true);
