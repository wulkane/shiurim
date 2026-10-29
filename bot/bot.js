// Telegram bot for the lessons. Telegram posts every message here (webhook); only the owner is answered.
const API = t => `https://api.telegram.org/bot${t}/`;

async function send(env, chat, text) {
  await fetch(API(env.BOT_TOKEN.trim()) + 'sendMessage', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: chat, text }),
  });
}

async function handle(env, msg) {
  const from = String(msg.from.id);
  const owner = (env.OWNER_ID || '').trim();
  if (!owner) return send(env, msg.chat.id, `המזהה שלך בטלגרם: ${from}`);
  if (from !== owner) return;
  await send(env, msg.chat.id, 'שלום אלעד, הבוט מחובר. בקרוב: מודעות והעלאת הקלטות.');
}

export default {
  async fetch(req, env, ctx) {
    if (req.method !== 'POST' || req.headers.get('x-telegram-bot-api-secret-token') !== (env.WEBHOOK_SECRET || '').trim())
      return new Response('ok');
    const update = await req.json();
    if (update.message) ctx.waitUntil(handle(env, update.message));
    return new Response('ok');
  },
};
