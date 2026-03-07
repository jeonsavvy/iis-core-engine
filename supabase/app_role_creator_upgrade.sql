-- IIS role upgrade: legacy role value -> creator
-- Apply after existing schema migrations

do $$
begin
  begin
    alter type public.app_role rename value 'reviewer' to 'creator';
  exception
    when invalid_parameter_value then
      -- legacy role value already renamed
      null;
    when undefined_object then
      null;
  end;
end
$$;

alter table if exists public.profiles
  alter column role set default 'creator';

create or replace function public.handle_auth_user_created()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, role)
  values (new.id, coalesce(new.email, ''), 'creator')
  on conflict (id) do update
    set email = excluded.email,
        updated_at = now();
  return new;
end;
$$;
