-- Historical migration kept for schema provenance.
-- Apply only when operating an older environment that still needs this cutover.
-- IIS pipeline v2 breaking migration
-- Apply during maintenance window.

begin;

create extension if not exists pgcrypto;

-- 1) Back up pipeline_logs snapshot (lightweight)
create table if not exists public.pipeline_logs_backup_20260301 as
select *
from public.pipeline_logs;

-- Backup table keeps historical rows only; cast enum columns to text
-- so v1 enum types can be dropped safely without CASCADE side effects.
alter table if exists public.pipeline_logs_backup_20260301
  alter column stage type text using stage::text,
  alter column agent_name type text using agent_name::text;

-- 2) Convert enum columns to text temporarily
alter table public.pipeline_logs
  alter column stage type text using stage::text,
  alter column agent_name type text using agent_name::text;

-- 3) Recreate pipeline_stage enum
alter type public.pipeline_stage rename to pipeline_stage_v1;
create type public.pipeline_stage as enum (
  'analyze',
  'plan',
  'design',
  'build',
  'qa_runtime',
  'qa_quality',
  'release',
  'report',
  'done'
);

-- 4) Recreate pipeline_agent_name enum
alter type public.pipeline_agent_name rename to pipeline_agent_name_v1;
create type public.pipeline_agent_name as enum (
  'analyzer',
  'planner',
  'designer',
  'developer',
  'qa_runtime',
  'qa_quality',
  'releaser',
  'reporter'
);

-- 5) Map existing log data to v2 values
update public.pipeline_logs
set stage = case stage
  when 'trigger' then 'analyze'
  when 'plan' then 'plan'
  when 'style' then 'design'
  when 'build' then 'build'
  when 'qa' then 'qa_runtime'
  when 'publish' then 'release'
  when 'echo' then 'report'
  when 'done' then 'done'
  else stage
end;

update public.pipeline_logs
set agent_name = case agent_name
  when 'Trigger' then 'analyzer'
  when 'Architect' then 'planner'
  when 'Stylist' then 'designer'
  when 'Builder' then 'developer'
  when 'Sentinel' then 'qa_runtime'
  when 'Publisher' then 'releaser'
  when 'Echo' then 'reporter'
  else agent_name
end;

-- 6) Cast text columns back to enum
alter table public.pipeline_logs
  alter column stage type public.pipeline_stage using stage::public.pipeline_stage,
  alter column agent_name type public.pipeline_agent_name using agent_name::public.pipeline_agent_name;

drop type public.pipeline_stage_v1;
drop type public.pipeline_agent_name_v1;

-- 7) Improvement queue table
create table if not exists public.qa_improvement_queue (
  id uuid primary key default gen_random_uuid(),
  pipeline_id uuid not null references public.admin_config(id) on delete cascade,
  game_slug text not null,
  core_loop_type text not null,
  keyword text not null default '',
  stage public.pipeline_stage not null,
  reason text not null,
  severity text not null default 'low',
  tokens text[] not null default '{}'::text[],
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_qa_improvement_core_created
on public.qa_improvement_queue (core_loop_type, created_at desc);

create index if not exists idx_qa_improvement_slug_created
on public.qa_improvement_queue (game_slug, created_at desc);

alter table public.qa_improvement_queue enable row level security;

grant select on public.qa_improvement_queue to authenticated;
grant all privileges on public.qa_improvement_queue to service_role;

drop policy if exists qa_improvement_queue_select_creator_or_admin on public.qa_improvement_queue;
create policy qa_improvement_queue_select_creator_or_admin
on public.qa_improvement_queue
for select
to authenticated
using (public.is_creator_or_admin());

drop policy if exists qa_improvement_queue_service_role_all on public.qa_improvement_queue;
create policy qa_improvement_queue_service_role_all
on public.qa_improvement_queue
for all
to service_role
using (true)
with check (true);

do $$
begin
  alter publication supabase_realtime add table public.qa_improvement_queue;
exception
  when duplicate_object then null;
end
$$;

commit;
