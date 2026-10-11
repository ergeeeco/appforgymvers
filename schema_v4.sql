-- Железный круг, обновление 4: размеры фото (чтобы рамка поста сразу была нужной пропорции).
-- Запускать после schema_v3.sql. Можно запускать повторно. Без него приложение работает, но рамка
-- подстраивается под фото уже после загрузки картинки.

alter table posts add column if not exists media_w int, add column if not exists media_h int;
alter table form_posts add column if not exists media_w int, add column if not exists media_h int;

alter table posts drop constraint if exists po_dims;
alter table posts add constraint po_dims check (
  (media_w is null and media_h is null) or (media_w between 1 and 20000 and media_h between 1 and 20000));
alter table form_posts drop constraint if exists f_dims;
alter table form_posts add constraint f_dims check (
  (media_w is null and media_h is null) or (media_w between 1 and 20000 and media_h between 1 and 20000));
