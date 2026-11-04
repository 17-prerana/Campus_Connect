-- CampusConnect schema. Events are public; registrations are private to their
-- authenticated owner. Run this in the Supabase SQL Editor before deployment.

create table if not exists public.events (
  id uuid primary key default gen_random_uuid(),
  title text not null check (char_length(title) between 1 and 200),
  capacity integer check (capacity is null or capacity > 0),
  timestamp timestamptz not null,
  organiser_id uuid
);

create table if not exists public.registrations (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null,
  "createdAt" timestamptz not null default now(),
  unique (event_id, user_id)
);

create index if not exists registrations_event_id_created_at_idx
  on public.registrations (event_id, "createdAt");
create index if not exists registrations_user_id_created_at_idx
  on public.registrations (user_id, "createdAt" desc);

alter table public.events enable row level security;
alter table public.registrations enable row level security;

revoke all on public.events from anon, authenticated;
revoke all on public.registrations from anon, authenticated;
grant select on public.events to anon, authenticated;
grant select, insert on public.registrations to authenticated;

drop policy if exists "Anyone can view events" on public.events;
create policy "Anyone can view events"
  on public.events for select
  to anon, authenticated
  using (true);

drop policy if exists "Users can view their registrations" on public.registrations;
create policy "Users can view their registrations"
  on public.registrations for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Users can create their registrations" on public.registrations;
create policy "Users can create their registrations"
  on public.registrations for insert
  to authenticated
  with check ((select auth.uid()) = user_id);
