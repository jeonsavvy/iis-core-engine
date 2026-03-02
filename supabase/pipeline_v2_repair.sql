-- IIS pipeline v2 repair migration (additive, non-dropping)
-- Safe to rerun during maintenance window.

begin;

create extension if not exists pgcrypto;

-- Ensure backup table does not depend on enum types.
create table if not exists public.pipeline_logs_backup_20260301 as
select *
from public.pipeline_logs;

alter table if exists public.pipeline_logs_backup_20260301
  alter column stage type text using stage::text,
  alter column agent_name type text using agent_name::text;

do $$
begin
  if exists (
    select 1 from pg_type t where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_stage'
  ) then
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_stage' and e.enumlabel = 'analyze'
    ) then
      alter type public.pipeline_stage add value 'analyze';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_stage' and e.enumlabel = 'qa_runtime'
    ) then
      alter type public.pipeline_stage add value 'qa_runtime';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_stage' and e.enumlabel = 'qa_quality'
    ) then
      alter type public.pipeline_stage add value 'qa_quality';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_stage' and e.enumlabel = 'release'
    ) then
      alter type public.pipeline_stage add value 'release';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_stage' and e.enumlabel = 'report'
    ) then
      alter type public.pipeline_stage add value 'report';
    end if;
  end if;
end
$$;

do $$
begin
  if exists (
    select 1 from pg_type t where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name'
  ) then
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'analyzer'
    ) then
      alter type public.pipeline_agent_name add value 'analyzer';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'planner'
    ) then
      alter type public.pipeline_agent_name add value 'planner';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'designer'
    ) then
      alter type public.pipeline_agent_name add value 'designer';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'developer'
    ) then
      alter type public.pipeline_agent_name add value 'developer';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'qa_runtime'
    ) then
      alter type public.pipeline_agent_name add value 'qa_runtime';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'qa_quality'
    ) then
      alter type public.pipeline_agent_name add value 'qa_quality';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'releaser'
    ) then
      alter type public.pipeline_agent_name add value 'releaser';
    end if;
    if not exists (
      select 1
      from pg_enum e
      join pg_type t on t.oid = e.enumtypid
      where t.typnamespace = 'public'::regnamespace and t.typname = 'pipeline_agent_name' and e.enumlabel = 'reporter'
    ) then
      alter type public.pipeline_agent_name add value 'reporter';
    end if;
  end if;
end
$$;

-- Normalize legacy enum/text values in pipeline_logs.
alter table public.pipeline_logs
  alter column stage type text using stage::text,
  alter column agent_name type text using agent_name::text;

update public.pipeline_logs
set stage = case stage
  when 'trigger' then 'analyze'
  when 'style' then 'design'
  when 'qa' then 'qa_runtime'
  when 'publish' then 'release'
  when 'echo' then 'report'
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
  else lower(agent_name)
end;

alter table public.pipeline_logs
  alter column stage type public.pipeline_stage using stage::public.pipeline_stage,
  alter column agent_name type public.pipeline_agent_name using agent_name::public.pipeline_agent_name;

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

drop policy if exists qa_improvement_queue_select_reviewer_or_admin on public.qa_improvement_queue;
create policy qa_improvement_queue_select_reviewer_or_admin
on public.qa_improvement_queue
for select
to authenticated
using (public.is_reviewer_or_admin());

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
