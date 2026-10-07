-- Железный круг: схема базы для Supabase. Вставьте целиком в SQL Editor и нажмите Run.

create table profiles (
  id uuid primary key references auth.users on delete cascade,
  username text not null,
  sex text default 'm',
  bw numeric, sq numeric, bp numeric, dl numeric,
  created_at timestamptz default now()
);
create table posts (
  id bigint generated always as identity primary key,
  user_id uuid not null references profiles(id) on delete cascade,
  ex text not null,
  kg numeric default 0, reps int default 0, sets int default 0,
  note text, media_path text, media_type text,
  created_at timestamptz default now()
);
create table follows (
  follower uuid references profiles(id) on delete cascade,
  following uuid references profiles(id) on delete cascade,
  primary key (follower, following),
  check (follower <> following)
);

alter table profiles enable row level security;
alter table posts enable row level security;
alter table follows enable row level security;

create policy "profiles read" on profiles for select using (true);
create policy "profiles update own" on profiles for update using (auth.uid() = id);
create policy "posts read" on posts for select using (true);
create policy "posts insert own" on posts for insert to authenticated with check (auth.uid() = user_id);
create policy "posts delete own" on posts for delete to authenticated using (auth.uid() = user_id);
create policy "follows read" on follows for select using (true);
create policy "follows insert own" on follows for insert to authenticated with check (auth.uid() = follower);
create policy "follows delete own" on follows for delete to authenticated using (auth.uid() = follower);

-- профиль создаётся автоматически при регистрации
create function handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, username)
  values (new.id, coalesce(nullif(new.raw_user_meta_data->>'username',''), 'athlete_' || substr(new.id::text,1,4)));
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function handle_new_user();

-- хранилище фото и видео (до 20 МБ на файл)
insert into storage.buckets (id, name, public, file_size_limit) values ('media', 'media', true, 20971520) on conflict (id) do nothing;
create policy "media read" on storage.objects for select using (bucket_id = 'media');
create policy "media upload own" on storage.objects for insert to authenticated
  with check (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "media delete own" on storage.objects for delete to authenticated
  using (bucket_id = 'media' and (storage.foldername(name))[1] = auth.uid()::text);
