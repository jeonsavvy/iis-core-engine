-- IIS Session-First Big-Bang migration
-- WARNING: This migration intentionally drops legacy pipeline tables without backup.

create extension if not exists pgcrypto;

-- ------------------------------------------------------------------
-- New Session-first tables
-- ------------------------------------------------------------------

create table if not exists public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  title text not null,
  genre text not null default '',
  status text not null default 'active' check (status in ('active', 'published', 'cancelled', 'error')),
  current_html text not null default '',
  score int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_sessions_status_updated_at
on public.sessions (status, updated_at desc);

create table if not exists public.conversation_history (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_conversation_history_session_created
on public.conversation_history (session_id, created_at asc);

create table if not exists public.session_events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  event_type text not null,
  agent text,
  action text,
  summary text not null default '',
  score int,
  before_score int,
  after_score int,
  decision_reason text not null default '',
  input_signal text not null default '',
  change_impact text not null default '',
  confidence double precision,
  error_code text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_session_events_session_created
on public.session_events (session_id, created_at desc);

create table if not exists public.session_publish_history (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  game_id uuid references public.games_metadata(id) on delete set null,
  game_slug text not null,
  play_url text not null,
  public_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_session_publish_history_session_created
on public.session_publish_history (session_id, created_at desc);

-- updated_at trigger helper
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_sessions_updated_at on public.sessions;
create trigger trg_sessions_updated_at
before update on public.sessions
for each row execute function public.set_updated_at();

-- ------------------------------------------------------------------
-- Access policies
-- ------------------------------------------------------------------

alter table public.sessions enable row level security;
alter table public.conversation_history enable row level security;
alter table public.session_events enable row level security;
alter table public.session_publish_history enable row level security;

drop policy if exists sessions_master_admin_only on public.sessions;
create policy sessions_master_admin_only
on public.sessions
for all
to authenticated
using (public.is_master_admin())
with check (public.is_master_admin());

drop policy if exists conversation_history_master_admin_only on public.conversation_history;
create policy conversation_history_master_admin_only
on public.conversation_history
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

drop policy if exists session_events_master_admin_only on public.session_events;
create policy session_events_master_admin_only
on public.session_events
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

drop policy if exists session_publish_history_master_admin_only on public.session_publish_history;
create policy session_publish_history_master_admin_only
on public.session_publish_history
for all
to authenticated
using (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
)
with check (
  exists (select 1 from public.sessions s where s.id = session_id and public.is_master_admin())
);

grant select on public.sessions, public.conversation_history, public.session_events, public.session_publish_history to authenticated;
grant all privileges on public.sessions, public.conversation_history, public.session_events, public.session_publish_history to service_role;

-- ------------------------------------------------------------------
-- Big-Bang legacy hard drop (no backup)
-- ------------------------------------------------------------------

drop table if exists public.qa_improvement_queue cascade;
drop table if exists public.asset_registry cascade;
drop table if exists public.pipeline_logs cascade;
drop table if exists public.admin_config cascade;

-- keep enums if shared by legacy readers; can be dropped later after full code cleanup.
