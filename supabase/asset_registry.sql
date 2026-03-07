-- IIS asset registry additive migration
-- Run in Supabase SQL Editor before enabling production rollout that relies on asset_registry.

create extension if not exists pgcrypto;

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

grant select on public.asset_registry to authenticated;
grant all privileges on public.asset_registry to service_role;

alter table public.asset_registry enable row level security;

drop policy if exists asset_registry_select_creator_or_admin on public.asset_registry;
create policy asset_registry_select_creator_or_admin
on public.asset_registry
for select
to authenticated
using (public.is_creator_or_admin());

drop policy if exists asset_registry_service_role_all on public.asset_registry;
create policy asset_registry_service_role_all
on public.asset_registry
for all
to service_role
using (true)
with check (true);
