// Edge-функция «push»: получает событие от базы и отправляет уведомление на телефоны через Firebase (HTTP v1).
// Секреты (Dashboard -> Edge Functions -> Secrets):
//   FCM_SERVICE_ACCOUNT  - содержимое JSON-ключа сервисного аккаунта Firebase целиком
//   PUSH_WEBHOOK_SECRET  - та же строка, что push_secret в таблице app_config
// В настройках функции отключите "Enforce JWT Verification": базу мы проверяем по секрету, а не по JWT.
import { createClient } from 'npm:@supabase/supabase-js@2'

const SECRET = Deno.env.get('PUSH_WEBHOOK_SECRET') ?? ''
const SA = JSON.parse(Deno.env.get('FCM_SERVICE_ACCOUNT') ?? '{}')
const db = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)

const b64url = (data: ArrayBuffer | string) => {
  const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : new Uint8Array(data)
  let s = ''
  bytes.forEach((b) => (s += String.fromCharCode(b)))
  return btoa(s).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
}

let cached: { token: string; exp: number } | null = null
async function accessToken(): Promise<string> {
  if (cached && cached.exp > Date.now() + 60_000) return cached.token
  const now = Math.floor(Date.now() / 1000)
  const unsigned =
    b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' })) + '.' +
    b64url(JSON.stringify({
      iss: SA.client_email,
      scope: 'https://www.googleapis.com/auth/firebase.messaging',
      aud: 'https://oauth2.googleapis.com/token',
      iat: now,
      exp: now + 3600,
    }))
  const pem = String(SA.private_key).replace(/-----[^-]+-----/g, '').replace(/\s+/g, '')
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0))
  const key = await crypto.subtle.importKey('pkcs8', der, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign'])
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(unsigned))
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: unsigned + '.' + b64url(sig),
    }),
  })
  const j = await r.json()
  if (!j.access_token) throw new Error('FCM auth failed: ' + JSON.stringify(j))
  cached = { token: j.access_token, exp: Date.now() + (j.expires_in ?? 3600) * 1000 }
  return cached.token
}

async function send(token: string, title: string, body: string, at: string) {
  const r = await fetch(`https://fcm.googleapis.com/v1/projects/${SA.project_id}/messages:send`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${at}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: { token, notification: { title, body }, android: { priority: 'HIGH' } } }),
  })
  if (!r.ok) {
    const t = await r.text()
    console.log('FCM error', r.status, t)
    if (t.includes('UNREGISTERED') || t.includes('NOT_FOUND')) await db.from('push_tokens').delete().eq('token', token)
  }
}

Deno.serve(async (req) => {
  if (!SECRET || req.headers.get('x-webhook-secret') !== SECRET) return new Response('forbidden', { status: 403 })
  const { table, record: r } = await req.json()
  let actor = ''
  let text = ''
  let to: string[] = []

  if (table === 'posts') {
    actor = r.user_id
    text = 'опубликовал(а) тренировку: ' + r.ex + (r.kg ? `, ${r.kg} кг` : '')
    const { data } = await db.from('follows').select('follower').eq('following', actor)
    to = (data ?? []).map((x: { follower: string }) => x.follower)
  } else if (table === 'likes' || table === 'comments') {
    actor = r.user_id
    const { data: post } = await db.from('posts').select('user_id, ex').eq('id', r.post_id).single()
    if (!post) return new Response('no post')
    text = table === 'likes'
      ? 'оценил(а) вашу тренировку: ' + post.ex
      : 'прокомментировал(а): ' + String(r.body).slice(0, 80)
    to = [post.user_id]
  } else if (table === 'follows') {
    actor = r.follower
    text = 'подписался(ась) на вас'
    to = [r.following]
  } else {
    return new Response('skip')
  }

  to = to.filter((id) => id !== actor)
  if (!to.length) return new Response('nobody')
  const { data: prof } = await db.from('profiles').select('username').eq('id', actor).single()
  const { data: toks } = await db.from('push_tokens').select('token').in('user_id', to)
  if (!toks?.length) return new Response('no tokens')
  const at = await accessToken()
  await Promise.all(toks.map((t: { token: string }) => send(t.token, prof?.username ?? 'Атлет', text, at)))
  return new Response('ok')
})
