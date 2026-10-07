-- Железный круг, обновление 3: лайки, комментарии, время подписки (для уведомлений).
-- Запускать в SQL Editor после schema.sql и schema_v2.sql. Скрипт можно запускать повторно.

-- 1. Лайки
create table if not exists likes (
  post_id bigint not null references posts(id) on delete cascade,
  user_id uuid not null references profiles(id) on delete cascade,
  created_at timestamptz default now(),
  primary key (post_id, user_id)
);
alter table likes enable row level security;
drop policy if exists "likes read" on likes;
drop policy if exists "likes insert own" on likes;
drop policy if exists "likes delete own" on likes;
create policy "likes read" on likes for select to authenticated using (true);
create policy "likes insert own" on likes for insert to authenticated with check (auth.uid() = user_id);
create policy "likes delete own" on likes for delete to authenticated using (auth.uid() = user_id);

-- 2. Комментарии (до 300 знаков; удалить может автор комментария или автор поста)
create table if not exists comments (
  id bigint generated always as identity primary key,
  post_id bigint not null references posts(id) on delete cascade,
  user_id uuid not null references profiles(id) on delete cascade,
  body text not null check (char_length(body) between 1 and 300),
  created_at timestamptz default now()
);
alter table comments enable row level security;
drop policy if exists "comments read" on comments;
drop policy if exists "comments insert own" on comments;
drop policy if exists "comments delete own" on comments;
create policy "comments read" on comments for select to authenticated using (true);
create policy "comments insert own" on comments for insert to authenticated with check (auth.uid() = user_id);
create policy "comments delete own" on comments for delete to authenticated
  using (auth.uid() = user_id or exists (select 1 from posts p where p.id = post_id and p.user_id = auth.uid()));

-- 3. Время подписки: нужно, чтобы показывать «на вас подписались»
alter table follows add column if not exists created_at timestamptz default now();

-- 4. Защита от спама комментариями: не больше 60 в час на пользователя
create or replace function throttle_comments() returns trigger language plpgsql as $$
begin
  if (select count(*) from comments where user_id = new.user_id and created_at > now() - interval '1 hour') >= 60
  then raise exception 'Слишком много комментариев, попробуйте позже'; end if;
  return new;
end $$;
drop trigger if exists comments_throttle on comments;
create trigger comments_throttle before insert on comments for each row execute function throttle_comments();
