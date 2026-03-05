-- IIS Session-First async run + human-agent collaboration upgrade
-- Apply after session_first_big_bang.sql

create extension if not exists pgcrypto;

create table if not exists public.session_runs (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  prompt text not null,
  auto_qa boolean not null default true,
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  error_code text,
  error_detail text not null default '',
  final_score int not null default 0,
  activities jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.session_issues (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  title text not null,
  details text not null default '',
  category text not null default 'gameplay',
  status text not null default 'open' check (status in ('open', 'proposed', 'resolved', 'discarded')),
  created_by text not null default 'master_admin',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.session_issue_proposals (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  issue_id uuid not null references public.session_issues(id) on delete cascade,
  summary text not null default '',
  proposal_prompt text not null default '',
  preview_html text not null default '',
  status text not null default 'proposed' check (status in ('proposed', 'applied', 'rejected')),
  proposed_by text not null default 'codegen',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.session_publish_approvals (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  approved_by text not null default 'master_admin',
  note text not null default '',
  approved_at timestamptz not null default now()
);

create index if not exists idx_session_runs_session_created
on public.session_runs (session_id, created_at desc);

create index if not exists idx_session_runs_status_created
on public.session_runs (status, created_at desc);

create index if not exists idx_session_issues_session_created
on public.session_issues (session_id, created_at desc);

create index if not exists idx_session_publish_approvals_session_approved
on public.session_publish_approvals (session_id, approved_at desc);

drop trigger if exists trg_session_runs_updated_at on public.session_runs;
create trigger trg_session_runs_updated_at
before update on public.session_runs
for each row execute function public.set_updated_at();

drop trigger if exists trg_session_issues_updated_at on public.session_issues;
create trigger trg_session_issues_updated_at
before update on public.session_issues
for each row execute function public.set_updated_at();

drop trigger if exists trg_session_issue_proposals_updated_at on public.session_issue_proposals;
create trigger trg_session_issue_proposals_updated_at
before update on public.session_issue_proposals
for each row execute function public.set_updated_at();

alter table public.session_runs enable row level security;
alter table public.session_issues enable row level security;
alter table public.session_issue_proposals enable row level security;
alter table public.session_publish_approvals enable row level security;

drop policy if exists session_runs_master_admin_only on public.session_runs;
create policy session_runs_master_admin_only
on public.session_runs
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

drop policy if exists session_issues_master_admin_only on public.session_issues;
create policy session_issues_master_admin_only
on public.session_issues
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

drop policy if exists session_issue_proposals_master_admin_only on public.session_issue_proposals;
create policy session_issue_proposals_master_admin_only
on public.session_issue_proposals
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

drop policy if exists session_publish_approvals_master_admin_only on public.session_publish_approvals;
create policy session_publish_approvals_master_admin_only
on public.session_publish_approvals
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

grant select on public.session_runs, public.session_issues, public.session_issue_proposals, public.session_publish_approvals to authenticated;
grant all privileges on public.session_runs, public.session_issues, public.session_issue_proposals, public.session_publish_approvals to service_role;
