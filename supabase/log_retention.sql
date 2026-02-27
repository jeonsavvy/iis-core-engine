-- IIS pipeline logs retention / aggregation helpers
-- Apply manually in Supabase SQL editor after reviewing retention policy:
--   ../ops/log-retention-policy.md

-- Daily aggregation materialized view (operations dashboard baseline)
create materialized view if not exists public.pipeline_logs_daily_metrics as
select
  date_trunc('day', created_at)::date as day,
  status,
  stage,
  count(*)::bigint as total_count,
  count(*) filter (where status = 'error')::bigint as error_count,
  case
    when count(*) = 0 then 0
    else round((count(*) filter (where status = 'error'))::numeric / count(*)::numeric, 6)
  end as error_rate
from public.pipeline_logs
group by 1, 2, 3
with no data;

create unique index if not exists idx_pipeline_logs_daily_metrics_pk
on public.pipeline_logs_daily_metrics (day, status, stage);

create or replace function public.refresh_pipeline_logs_daily_metrics()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  refresh materialized view concurrently public.pipeline_logs_daily_metrics;
end;
$$;

-- Purge logs with incident-aware retention windows.
-- incident tag convention:
--   metadata->>'incident' = 'true'
create or replace function public.purge_pipeline_logs(
  retention_days integer default 90,
  incident_retention_days integer default 180
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  deleted_count bigint := 0;
begin
  if retention_days < 1 then
    raise exception 'retention_days must be >= 1';
  end if;
  if incident_retention_days < retention_days then
    raise exception 'incident_retention_days must be >= retention_days';
  end if;

  with deleted as (
    delete from public.pipeline_logs
    where (
      coalesce(metadata->>'incident', 'false') = 'true'
      and created_at < now() - make_interval(days => incident_retention_days)
    ) or (
      coalesce(metadata->>'incident', 'false') <> 'true'
      and created_at < now() - make_interval(days => retention_days)
    )
    returning 1
  )
  select count(*) into deleted_count from deleted;

  return deleted_count;
end;
$$;
