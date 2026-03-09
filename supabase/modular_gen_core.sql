-- Historical migration kept for schema provenance.
-- Not part of the default bootstrap path for the current repository state.
-- IIS modular generation core additive schema
-- Safe to apply multiple times.

begin;

create extension if not exists pgcrypto;

create table if not exists public.runtime_module_registry (
  module_id text primary key,
  capability_tags text[] not null default '{}'::text[],
  version text not null default '1.0.0',
  stability_score double precision not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.builder_contract_reports (
  id uuid primary key default gen_random_uuid(),
  pipeline_id uuid not null references public.admin_config(id) on delete cascade,
  rqc_version text not null default 'rqc-1',
  checks jsonb not null default '{}'::jsonb,
  failed_reasons text[] not null default '{}'::text[],
  module_signature text not null default 'unknown',
  score integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_builder_contract_reports_pipeline_created
on public.builder_contract_reports (pipeline_id, created_at desc);

create table if not exists public.capability_profiles (
  pipeline_id uuid primary key references public.admin_config(id) on delete cascade,
  game_slug text not null,
  keyword text not null default '',
  core_loop_type text not null default '',
  profile_id text not null,
  capability_profile jsonb not null default '{}'::jsonb,
  module_plan jsonb not null default '{}'::jsonb,
  module_signature text not null default 'unknown',
  updated_at timestamptz not null default now()
);

create index if not exists idx_capability_profiles_slug_updated
on public.capability_profiles (game_slug, updated_at desc);

alter table public.runtime_module_registry enable row level security;
alter table public.builder_contract_reports enable row level security;
alter table public.capability_profiles enable row level security;

grant select on public.runtime_module_registry to authenticated;
grant select on public.builder_contract_reports to authenticated;
grant select on public.capability_profiles to authenticated;
grant all privileges on public.runtime_module_registry to service_role;
grant all privileges on public.builder_contract_reports to service_role;
grant all privileges on public.capability_profiles to service_role;

drop policy if exists runtime_module_registry_select_authenticated on public.runtime_module_registry;
create policy runtime_module_registry_select_authenticated
on public.runtime_module_registry
for select
to authenticated
using (true);

drop policy if exists runtime_module_registry_service_role_all on public.runtime_module_registry;
create policy runtime_module_registry_service_role_all
on public.runtime_module_registry
for all
to service_role
using (true)
with check (true);

drop policy if exists builder_contract_reports_select_creator_or_admin on public.builder_contract_reports;
create policy builder_contract_reports_select_creator_or_admin
on public.builder_contract_reports
for select
to authenticated
using (public.is_creator_or_admin());

drop policy if exists builder_contract_reports_service_role_all on public.builder_contract_reports;
create policy builder_contract_reports_service_role_all
on public.builder_contract_reports
for all
to service_role
using (true)
with check (true);

drop policy if exists capability_profiles_select_creator_or_admin on public.capability_profiles;
create policy capability_profiles_select_creator_or_admin
on public.capability_profiles
for select
to authenticated
using (public.is_creator_or_admin());

drop policy if exists capability_profiles_service_role_all on public.capability_profiles;
create policy capability_profiles_service_role_all
on public.capability_profiles
for all
to service_role
using (true)
with check (true);

commit;
