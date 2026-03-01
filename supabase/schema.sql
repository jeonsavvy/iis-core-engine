-- IIS MVP schema for Supabase SQL Editor
-- Includes: profiles(auth linkage), users compatibility view, admin_config, leaderboard, pipeline_logs, games_metadata, asset_registry

create extension if not exists pgcrypto;

-- =========================
-- Enums
-- =========================
do $$
begin
  if not exists (select 1 from pg_type where typname = 'app_role') then
    create type public.app_role as enum ('master_admin', 'reviewer');
  end if;

  if not exists (select 1 from pg_type where typname = 'pipeline_stage') then
    create type public.pipeline_stage as enum ('trigger', 'plan', 'style', 'build', 'qa', 'publish', 'echo', 'done');
  end if;

  if not exists (select 1 from pg_type where typname = 'pipeline_status') then
    create type public.pipeline_status as enum ('queued', 'running', 'success', 'error', 'retry', 'skipped');
  end if;

  if not exists (select 1 from pg_type where typname = 'pipeline_agent_name') then
    create type public.pipeline_agent_name as enum ('Trigger', 'Architect', 'Stylist', 'Builder', 'Sentinel', 'Publisher', 'Echo');
  end if;

  if not exists (select 1 from pg_type where typname = 'game_status') then
    create type public.game_status as enum ('active', 'inactive', 'archived');
  end if;
end
$$;

-- =========================
-- Shared utility functions
-- =========================
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- =========================
-- users(auth linkage) via profiles + compatibility view
-- =========================
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  role public.app_role not null default 'reviewer',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create or replace function public.handle_auth_user_created()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, role)
  values (new.id, coalesce(new.email, ''), 'reviewer')
  on conflict (id) do update
    set email = excluded.email,
        updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_auth_user_created();

create or replace view public.users as
select
  p.id,
  p.email,
  p.role,
  p.created_at,
  p.updated_at
from public.profiles p;

create or replace function public.current_user_role()
returns public.app_role
language sql
stable
security definer
set search_path = public
as $$
  select p.role
  from public.profiles p
  where p.id = auth.uid()
  limit 1;
$$;

create or replace function public.is_master_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(public.current_user_role() = 'master_admin'::public.app_role, false);
$$;

create or replace function public.is_reviewer_or_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  -- Single-operator mode:
  -- reviewer role is deprecated for this MVP rollout.
  select coalesce(public.current_user_role() = 'master_admin'::public.app_role, false);
$$;

-- =========================
-- Games catalog
-- =========================
create table if not exists public.games_metadata (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  genre text not null,
  url text not null,
  thumbnail_url text,
  ai_review text,
  screenshot_url text,
  status public.game_status not null default 'active',
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_games_metadata_updated_at on public.games_metadata;
create trigger trg_games_metadata_updated_at
before update on public.games_metadata
for each row execute function public.set_updated_at();

create index if not exists idx_games_metadata_status_created_at
on public.games_metadata (status, created_at desc);

-- =========================
-- Pipeline queue + logs
-- =========================
create table if not exists public.admin_config (
  id uuid primary key default gen_random_uuid(),
  requested_by uuid references public.profiles(id),
  trigger_source text not null check (trigger_source in ('telegram', 'console')),
  keyword text not null,
  payload jsonb not null default '{}'::jsonb,
  status public.pipeline_status not null default 'queued',
  error_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_admin_config_updated_at on public.admin_config;
create trigger trg_admin_config_updated_at
before update on public.admin_config
for each row execute function public.set_updated_at();

create index if not exists idx_admin_config_status_created_at
on public.admin_config (status, created_at asc);

create table if not exists public.pipeline_logs (
  id bigserial primary key,
  pipeline_id uuid not null references public.admin_config(id) on delete cascade,
  stage public.pipeline_stage not null,
  status public.pipeline_status not null,
  agent_name public.pipeline_agent_name not null,
  message text not null,
  reason text,
  attempt int not null default 1 check (attempt >= 1 and attempt <= 3),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_pipeline_logs_pipeline_created_at
on public.pipeline_logs (pipeline_id, created_at desc);

create table if not exists public.asset_registry (
  id uuid primary key default gen_random_uuid(),
  pipeline_id uuid not null unique references public.admin_config(id) on delete cascade,
  game_slug text not null,
  game_name text not null default '',
  keyword text not null default '',
  core_loop_type text not null,
  asset_pack text not null default '',
  variant_id text not null default '',
  variant_theme text not null default '',
  final_composite_score numeric,
  final_quality_score numeric,
  final_gameplay_score numeric,
  qa_status public.pipeline_status,
  qa_reason text,
  failure_reasons text[] not null default '{}'::text[],
  failure_tokens text[] not null default '{}'::text[],
  artifact_manifest jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_asset_registry_updated_at on public.asset_registry;
create trigger trg_asset_registry_updated_at
before update on public.asset_registry
for each row execute function public.set_updated_at();

create index if not exists idx_asset_registry_engine_created_at
on public.asset_registry (core_loop_type, created_at desc);

create index if not exists idx_asset_registry_engine_pack
on public.asset_registry (core_loop_type, asset_pack, created_at desc);

-- =========================
-- Leaderboard
-- =========================
create table if not exists public.leaderboard (
  id bigserial primary key,
  game_id uuid not null references public.games_metadata(id) on delete cascade,
  player_name text not null check (char_length(player_name) between 1 and 24),
  score int not null check (score >= 0 and score <= 1000000000),
  player_fingerprint text not null check (char_length(player_fingerprint) between 16 and 128),
  created_at timestamptz not null default now()
);

create index if not exists idx_leaderboard_game_score_created
on public.leaderboard (game_id, score desc, created_at asc);

create index if not exists idx_leaderboard_game_fingerprint_created
on public.leaderboard (game_id, player_fingerprint, created_at desc);

create or replace function public.can_submit_score(p_game_id uuid, p_player_fingerprint text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select count(*) < 5
  from public.leaderboard l
  where l.game_id = p_game_id
    and l.player_fingerprint = p_player_fingerprint
    and l.created_at > now() - interval '1 minute';
$$;

-- =========================
-- Grants
-- =========================
grant usage on schema public to anon, authenticated, service_role;

grant select on public.users to anon, authenticated;

grant select on public.games_metadata to anon, authenticated;
grant select on public.leaderboard to anon, authenticated;
grant insert on public.leaderboard to anon, authenticated;

grant select on public.profiles to authenticated;
grant select, insert on public.admin_config to authenticated;
grant select on public.pipeline_logs to authenticated;
grant select on public.asset_registry to authenticated;

grant all privileges on public.profiles, public.admin_config, public.pipeline_logs, public.asset_registry, public.games_metadata, public.leaderboard to service_role;
grant usage, select on sequence public.pipeline_logs_id_seq to service_role;
grant usage, select on sequence public.leaderboard_id_seq to anon, authenticated, service_role;

-- =========================
-- RLS
-- =========================
alter table public.profiles enable row level security;
alter table public.admin_config enable row level security;
alter table public.leaderboard enable row level security;
alter table public.pipeline_logs enable row level security;
alter table public.asset_registry enable row level security;
alter table public.games_metadata enable row level security;

drop policy if exists profiles_select_own_or_admin on public.profiles;
create policy profiles_select_own_or_admin
on public.profiles
for select
to authenticated
using (id = auth.uid() or public.is_master_admin());

drop policy if exists profiles_update_own_or_admin on public.profiles;
create policy profiles_update_own_or_admin
on public.profiles
for update
to authenticated
using (id = auth.uid() or public.is_master_admin())
with check (id = auth.uid() or public.is_master_admin());

drop policy if exists admin_config_select_reviewer_or_admin on public.admin_config;
create policy admin_config_select_reviewer_or_admin
on public.admin_config
for select
to authenticated
using (public.is_reviewer_or_admin());

drop policy if exists admin_config_insert_reviewer_or_admin on public.admin_config;
create policy admin_config_insert_reviewer_or_admin
on public.admin_config
for insert
to authenticated
with check (
  public.is_reviewer_or_admin()
  and (requested_by is null or requested_by = auth.uid())
);

drop policy if exists admin_config_update_master_admin on public.admin_config;
create policy admin_config_update_master_admin
on public.admin_config
for update
to authenticated
using (public.is_master_admin())
with check (public.is_master_admin());

drop policy if exists admin_config_delete_master_admin on public.admin_config;
create policy admin_config_delete_master_admin
on public.admin_config
for delete
to authenticated
using (public.is_master_admin());

drop policy if exists admin_config_service_role_all on public.admin_config;
create policy admin_config_service_role_all
on public.admin_config
for all
to service_role
using (true)
with check (true);

drop policy if exists pipeline_logs_select_reviewer_or_admin on public.pipeline_logs;
create policy pipeline_logs_select_reviewer_or_admin
on public.pipeline_logs
for select
to authenticated
using (public.is_reviewer_or_admin());

drop policy if exists pipeline_logs_insert_service_role on public.pipeline_logs;
create policy pipeline_logs_insert_service_role
on public.pipeline_logs
for insert
to service_role
with check (true);

drop policy if exists pipeline_logs_service_role_all on public.pipeline_logs;
create policy pipeline_logs_service_role_all
on public.pipeline_logs
for all
to service_role
using (true)
with check (true);

drop policy if exists asset_registry_select_reviewer_or_admin on public.asset_registry;
create policy asset_registry_select_reviewer_or_admin
on public.asset_registry
for select
to authenticated
using (public.is_reviewer_or_admin());

drop policy if exists asset_registry_service_role_all on public.asset_registry;
create policy asset_registry_service_role_all
on public.asset_registry
for all
to service_role
using (true)
with check (true);

drop policy if exists leaderboard_select_public on public.leaderboard;
create policy leaderboard_select_public
on public.leaderboard
for select
to anon, authenticated
using (true);

drop policy if exists leaderboard_insert_public_with_guardrail on public.leaderboard;
create policy leaderboard_insert_public_with_guardrail
on public.leaderboard
for insert
to anon, authenticated
with check (
  public.can_submit_score(game_id, player_fingerprint)
);

drop policy if exists leaderboard_service_role_all on public.leaderboard;
create policy leaderboard_service_role_all
on public.leaderboard
for all
to service_role
using (true)
with check (true);

drop policy if exists games_metadata_select_active_or_staff on public.games_metadata;
create policy games_metadata_select_active_or_staff
on public.games_metadata
for select
to anon, authenticated
using (status = 'active'::public.game_status or public.is_reviewer_or_admin());

drop policy if exists games_metadata_insert_master_admin on public.games_metadata;
create policy games_metadata_insert_master_admin
on public.games_metadata
for insert
to authenticated
with check (public.is_master_admin());

drop policy if exists games_metadata_update_master_admin on public.games_metadata;
create policy games_metadata_update_master_admin
on public.games_metadata
for update
to authenticated
using (public.is_master_admin())
with check (public.is_master_admin());

drop policy if exists games_metadata_delete_master_admin on public.games_metadata;
create policy games_metadata_delete_master_admin
on public.games_metadata
for delete
to authenticated
using (public.is_master_admin());

drop policy if exists games_metadata_service_role_all on public.games_metadata;
create policy games_metadata_service_role_all
on public.games_metadata
for all
to service_role
using (true)
with check (true);

-- =========================
-- Realtime publication
-- =========================
do $$
begin
  alter publication supabase_realtime add table public.pipeline_logs;
exception
  when duplicate_object then null;
end
$$;
