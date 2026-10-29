// Telegram bot for the lessons. Telegram posts every message here (webhook); only the owner is answered.
const API = t => `https://api.telegram.org/bot${t}/`;

const SITE = 'https://wulkane.github.io/shiurim/';

async function send(env, chat, text, extra = {}) {
  await fetch(API(env.BOT_TOKEN.trim()) + 'sendMessage', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: chat, text, ...extra }),
  });
}

// a text message is the lesson topic; the day and place stay fixed
async function announce(env, chat, text) {
  const topic = text.trim(), date = '';
  const link = `${SITE}modaa.html?topic=${encodeURIComponent(topic)}&date=${encodeURIComponent(date)}`;
  await send(env, chat, 'המודעה מוכנה. בדף שייפתח לוחצים „שיתוף” ובוחרים וואטסאפ:', {
    reply_markup: { inline_keyboard: [[{ text: 'פתיחת המודעה לשיתוף', url: link }]] },
  });
}

async function handle(env, msg) {
  const from = String(msg.from.id);
  const owner = (env.OWNER_ID || '').trim();
  if (!owner) return send(env, msg.chat.id, `המזהה שלך בטלגרם: ${from}`);
  if (from !== owner) return;
  const text = (msg.text || '').trim();
  if (!text || text.startsWith('/')) {
    return send(env, msg.chat.id, 'שלח לי את נושא השיעור ואכין את המודעה.');
  }
  await announce(env, msg.chat.id, text);
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
