-- Железный круг, обновление 5: push-уведомления через Firebase.
-- Запускать после schema_v4.sql. Можно запускать повторно.

-- 1. Токены телефонов: приложение само сохраняет и удаляет только свой токен
create table if not exists push_tokens (
  token text primary key,
  user_id uuid not null references profiles(id) on delete cascade,
  updated_at timestamptz default now()
);
alter table push_tokens enable row level security;
drop policy if exists "tokens read own" on push_tokens;
drop policy if exists "tokens insert own" on push_tokens;
drop policy if exists "tokens update own" on push_tokens;
drop policy if exists "tokens delete own" on push_tokens;
create policy "tokens read own" on push_tokens for select to authenticated using (auth.uid() = user_id);
create policy "tokens insert own" on push_tokens for insert to authenticated with check (auth.uid() = user_id);
create policy "tokens update own" on push_tokens for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "tokens delete own" on push_tokens for delete to authenticated using (auth.uid() = user_id);

-- 2. Настройки сервера (адрес функции и секрет). Политик нет: через приложение они недоступны.
create table if not exists app_config (key text primary key, value text not null);
alter table app_config enable row level security;

-- 3. При новом посте, лайке, комментарии или подписке база вызывает функцию push
create extension if not exists pg_net with schema extensions;

create or replace function notify_push() returns trigger
language plpgsql security definer set search_path = public, extensions as $$
declare u text; s text;
begin
  select value into u from app_config where key = 'push_url';
  select value into s from app_config where key = 'push_secret';
  if u is null or s is null then return new; end if;
  perform net.http_post(
    url := u,
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-webhook-secret', s),
    body := jsonb_build_object('table', TG_TABLE_NAME, 'record', to_jsonb(new)));
  return new;
exception when others then
  return new;  -- уведомления никогда не должны ломать публикацию
end $$;

drop trigger if exists push_posts on posts;
create trigger push_posts after insert on posts for each row execute function notify_push();
drop trigger if exists push_likes on likes;
create trigger push_likes after insert on likes for each row execute function notify_push();
drop trigger if exists push_comments on comments;
create trigger push_comments after insert on comments for each row execute function notify_push();
drop trigger if exists push_follows on follows;
create trigger push_follows after insert on follows for each row execute function notify_push();

-- 4. Потом (после деплоя функции) выполните, подставив свои значения:
-- insert into app_config (key, value) values
--   ('push_url', 'https://ВАШ-ПРОЕКТ.supabase.co/functions/v1/push'),
--   ('push_secret', 'ПРИДУМАЙТЕ-ДЛИННУЮ-СЛУЧАЙНУЮ-СТРОКУ')
-- on conflict (key) do update set value = excluded.value;
