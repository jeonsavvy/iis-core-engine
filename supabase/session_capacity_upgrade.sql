-- IIS session run capacity / retry upgrade
-- Apply after session_async_collab_upgrade.sql

alter table if exists public.session_runs
  drop constraint if exists session_runs_status_check;

alter table if exists public.session_runs
  add constraint session_runs_status_check
  check (status in ('queued', 'retrying', 'running', 'succeeded', 'failed', 'cancelled'));

alter table if exists public.session_runs
  add column if not exists attempt_count int not null default 0;

alter table if exists public.session_runs
  add column if not exists retry_after_seconds int;

alter table if exists public.session_runs
  add column if not exists model_name text;

alter table if exists public.session_runs
  add column if not exists model_location text;

alter table if exists public.session_runs
  add column if not exists fallback_used boolean not null default false;

alter table if exists public.session_runs
  add column if not exists capacity_error text;
