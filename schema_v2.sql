-- Железный круг, обновление базы. Выполните в SQL Editor ПОСЛЕ schema.sql (один раз).

-- 1. Новые поля профиля
alter table profiles
  add column if not exists height numeric, add column if not exists years numeric,
  add column if not exists category text, add column if not exists federation text,
  add column if not exists coach text, add column if not exists gym text,
  add column if not exists goal text, add column if not exists city text, add column if not exists bio text;

-- 2. Актуальная форма (фото и короткие видео)
create table if not exists form_posts (
  id bigint generated always as identity primary key,
  user_id uuid not null references profiles(id) on delete cascade,
  caption text, media_path text not null, media_type text not null,
  created_at timestamptz default now()
);
alter table form_posts enable row level security;
create policy "form read" on form_posts for select to authenticated using (true);
create policy "form insert own" on form_posts for insert to authenticated with check (auth.uid() = user_id);
create policy "form delete own" on form_posts for delete to authenticated using (auth.uid() = user_id);

-- 3. Чтение данных только для вошедших пользователей
drop policy if exists "profiles read" on profiles;
drop policy if exists "posts read" on posts;
drop policy if exists "follows read" on follows;
create policy "profiles read" on profiles for select to authenticated using (true);
create policy "posts read" on posts for select to authenticated using (true);
create policy "follows read" on follows for select to authenticated using (true);

-- 4. Проверки значений на стороне сервера: модифицированное приложение не сможет записать мусор
alter table profiles drop constraint if exists p_chk;
alter table profiles add constraint p_chk check (
  char_length(username) between 2 and 24 and (sex in ('m','f') or sex is null)
  and (bw is null or bw between 30 and 300) and (height is null or height between 100 and 250)
  and (years is null or years between 0 and 80)
  and (sq is null or sq between 0 and 600) and (bp is null or bp between 0 and 600) and (dl is null or dl between 0 and 600)
  and char_length(coalesce(category,'')) <= 60 and char_length(coalesce(federation,'')) <= 60
  and char_length(coalesce(coach,'')) <= 60 and char_length(coalesce(gym,'')) <= 60
  and char_length(coalesce(goal,'')) <= 120 and char_length(coalesce(city,'')) <= 60
  and char_length(coalesce(bio,'')) <= 300);
alter table posts drop constraint if exists po_chk;
alter table posts add constraint po_chk check (
  kg between 0 and 600 and reps between 0 and 100 and sets between 0 and 50
  and char_length(ex) between 1 and 40 and char_length(coalesce(note,'')) <= 120
  and (media_type in ('i','v') or media_type is null));
alter table form_posts drop constraint if exists f_chk;
alter table form_posts add constraint f_chk check (media_type in ('i','v') and char_length(coalesce(caption,'')) <= 120);

-- 5. Хранилище: только jpeg, mp4, mov и не больше 20 МБ
update storage.buckets set file_size_limit = 20971520,
  allowed_mime_types = array['image/jpeg','video/mp4','video/quicktime'] where id = 'media';

-- 6. Защита от спама: не больше 30 публикаций в час на пользователя
create or replace function throttle() returns trigger language plpgsql as $$
begin
  if (select count(*) from posts where user_id = new.user_id and created_at > now() - interval '1 hour')
   + (select count(*) from form_posts where user_id = new.user_id and created_at > now() - interval '1 hour') >= 30
  then raise exception 'Слишком много публикаций, попробуйте позже'; end if;
  return new;
end $$;
drop trigger if exists posts_throttle on posts;
create trigger posts_throttle before insert on posts for each row execute function throttle();
drop trigger if exists form_throttle on form_posts;
create trigger form_throttle before insert on form_posts for each row execute function throttle();
