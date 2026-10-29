// Telegram bot for the lessons. Telegram posts every message here (webhook); only the owner is answered.
//  - a text message is the topic of the coming lesson: the bot replies with a link to the announcement image
//  - an audio file is a new recording: the bot asks for its title, one sentence, podcast and season, then
//    stores it in R2 and adds it to the catalog, the site and the podcast feed
import { PODCASTS, CATALOG_PATH, lessonId, seasonOf, parseCsv, csvLine, feedItem, hms, MIME, Repo } from './lib.js';

const SITE = 'https://wulkane.github.io/shiurim/';
const MAX_BYTES = 20 * 1024 * 1024;   // the most a bot can download from Telegram

const tg = (env, method, body) => fetch(`https://api.telegram.org/bot${env.BOT_TOKEN.trim()}/${method}`, {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
});
const say = (env, chat, text, markup) => tg(env, 'sendMessage', { chat_id: chat, text, ...(markup ? { reply_markup: markup } : {}) });
const buttons = rows => ({ inline_keyboard: rows.map(r => r.map(([text, data]) => ({ text, callback_data: data }))) });

async function getState(env, chat) {
  const r = await env.DB.prepare('SELECT data FROM bot_state WHERE chat = ?').bind(String(chat)).first();
  return r ? JSON.parse(r.data) : null;
}
async function setState(env, chat, st) {
  if (!st) await env.DB.prepare('DELETE FROM bot_state WHERE chat = ?').bind(String(chat)).run();
  else await env.DB.prepare('INSERT OR REPLACE INTO bot_state (chat, data, updated) VALUES (?, ?, datetime(\'now\'))')
    .bind(String(chat), JSON.stringify(st)).run();
}

// ---- announcement for the coming lesson ----
async function announce(env, chat, topic) {
  const link = `${SITE}modaa.html?topic=${encodeURIComponent(topic.trim())}&date=`;
  await say(env, chat, 'המודעה מוכנה. בדף שייפתח לוחצים „שיתוף” ובוחרים וואטסאפ:',
    { inline_keyboard: [[{ text: 'פתיחת המודעה לשיתוף', url: link }]] });
}

// ---- receiving a recording ----
function audioOf(msg) {
  const a = msg.audio || msg.document;
  if (!a) return null;
  const name = (a.file_name || '').toLowerCase(), mime = a.mime_type || '';
  if (!msg.audio && !/^audio\//.test(mime) && !/\.(mp3|m4a)$/.test(name)) return null;
  let ext = (name.match(/\.(mp3|m4a)$/) || [])[0];
  if (!ext) ext = mime === 'audio/mpeg' ? '.mp3' : /^audio\/(mp4|x-m4a|m4a)$/.test(mime) ? '.m4a' : null;
  return { id: a.file_id, ext, size: a.file_size || 0, seconds: a.duration || 0 };
}

async function receive(env, chat, file) {
  if (!file.ext) return say(env, chat, 'אני מקבל רק קובצי mp3 או m4a. אפשר להמיר ולשלוח שוב.');
  if (file.size > MAX_BYTES) return say(env, chat, 'הקובץ גדול מ־20 מגה, וטלגרם לא מאפשרת לבוט להוריד אותו. אפשר לשלוח גרסה קטנה יותר, או להגיד לי ואעלה אותו ידנית.');
  const st = { stage: file.seconds ? 'title' : 'dur', file };
  await setState(env, chat, st);
  if (st.stage === 'dur') return say(env, chat, 'קיבלתי את ההקלטה. כמה זמן היא נמשכת? למשל 14:30');
  await say(env, chat, `קיבלתי את ההקלטה (${hms(file.seconds)}).\nמה השם של ההקלטה שיופיע בפודקאסט?\nלסדרה כותבים כך: תפילה (2)- שם השיעור`);
}

function parseDuration(text) {
  const p = text.trim().split(':').map(Number);
  if (!p.length || p.length > 3 || p.some(v => !Number.isInteger(v) || v < 0)) return 0;
  return p.length === 1 ? p[0] * 60 : p.reduce((s, v) => s * 60 + v, 0);
}

async function loadSeasons(podKey) {
  const r = await fetch(SITE + 'data.js', { cf: { cacheTtl: 0 } });
  const data = JSON.parse((await r.text()).replace(/^window\.DATA = /, '').replace(/;\s*$/, ''));
  const pod = data.find(p => p.name === PODCASTS[podKey]);
  return [...new Set(pod.seasons.map(s => s.name))];
}

async function confirmation(env, chat, st) {
  st.stage = 'confirm';
  await setState(env, chat, st);
  await say(env, chat,
    `לפרסם?\n\nשם: ${st.title}\nתיאור: ${st.desc}\nפודקאסט: ${PODCASTS[st.pod]}\n` +
    (st.season ? `עונה: ${st.season}\n` : '') + `אורך: ${hms(st.file.seconds)}`,
    buttons([[['✅ פרסום', 'ok'], ['✖ ביטול', 'no']]]));
}

async function text(env, chat, msgText) {
  const st = await getState(env, chat);
  const t = msgText.trim();
  if (!st) return announce(env, chat, t);
  if (st.stage === 'dur') {
    const s = parseDuration(t);
    if (!s) return say(env, chat, 'לא הבנתי. כתוב את האורך כך: 14:30');
    st.file.seconds = s; st.stage = 'title';
    await setState(env, chat, st);
    return say(env, chat, 'מה השם של ההקלטה שיופיע בפודקאסט?\nלסדרה כותבים כך: תפילה (2)- שם השיעור');
  }
  if (st.stage === 'title') {
    st.title = t; st.stage = 'desc';
    await setState(env, chat, st);
    return say(env, chat, 'ומה המשפט שמתאר את השיעור, שיופיע מתחת לשם?');
  }
  if (st.stage === 'desc') {
    st.desc = t; st.stage = 'pod';
    await setState(env, chat, st);
    return say(env, chat, 'באיזה פודקאסט לפרסם?',
      buttons(Object.entries(PODCASTS).map(([k, name]) => [[name, 'pod:' + k]])));
  }
  if (st.stage === 'newseason') { st.season = t; return confirmation(env, chat, st); }
  return say(env, chat, 'אני מחכה ללחיצה על אחד הכפתורים למעלה. לביטול כתוב /cancel');
}

async function press(env, chat, data) {
  const st = await getState(env, chat);
  if (!st) return;
  if (data === 'no') { await setState(env, chat, null); return say(env, chat, 'בוטל. ההקלטה לא פורסמה.'); }
  if (data === 'ok' && st.stage === 'confirm') return publish(env, chat, st);
  if (data.startsWith('pod:') && st.stage === 'pod') {
    st.pod = data.slice(4);
    st.seasons = (await loadSeasons(st.pod)).filter(Boolean);
    if (!st.seasons.length) { st.season = ''; return confirmation(env, chat, st); }
    st.stage = 'season';
    await setState(env, chat, st);
    return say(env, chat, 'לאיזו עונה?', buttons([
      ...st.seasons.map((s, i) => [[s, 'sea:' + i]]),
      [['➕ עונה חדשה', 'sea:new']],
    ]));
  }
  if (data.startsWith('sea:') && st.stage === 'season') {
    if (data === 'sea:new') {
      st.stage = 'newseason';
      await setState(env, chat, st);
      return say(env, chat, 'מה שם העונה החדשה?');
    }
    st.season = st.seasons[Number(data.slice(4))];
    return confirmation(env, chat, st);
  }
}

// ---- publishing ----
const ilDate = d => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jerusalem', day: '2-digit', month: '2-digit', year: 'numeric' }).format(d);
const pad = n => String(n).padStart(2, '0');

async function publish(env, chat, st) {
  st.stage = 'publishing';
  await setState(env, chat, st);
  await say(env, chat, 'מעלה את ההקלטה ומעדכן את הפיד והאתר, זה לוקח כחצי דקה...');
  const site = SITE, media = env.MEDIA_URL;
  const title = st.title.trim(), desc = st.desc.trim();
  const lid = lessonId(title), ext = st.file.ext;
  let step = 'הורדה מטלגרם';
  try {
    // 1. the recording: Telegram -> R2
    const info = await (await tg(env, 'getFile', { file_id: st.file.id })).json();
    if (!info.ok) throw new Error('getFile ' + JSON.stringify(info));
    const dl = await fetch(`https://api.telegram.org/file/bot${env.BOT_TOKEN.trim()}/${info.result.file_path}`);
    if (!dl.ok) throw new Error('download ' + dl.status);
    step = 'העלאה לענן';
    const stored = await env.MEDIA.put(`audio/${lid}${ext}`, await dl.arrayBuffer(), { httpMetadata: { contentType: MIME[ext] } });

    // 2. the catalog decides the season number, the episode number and where the row goes
    step = 'קריאת הקטלוג';
    const repo = new Repo(env);
    const cat = await repo.read(CATALOG_PATH);
    const rows = parseCsv(cat.text), head = rows[0].fields, col = n => head.indexOf(n);
    const eol = cat.text.includes('\r\n') ? '\r\n' : '\n';
    const body = rows.slice(1);
    if (body.some(r => lessonId(r.fields[col('כותרת מקורית')]) === lid)) throw new Error('כבר יש שיעור עם השם הזה');
    const podName = PODCASTS[st.pod];
    const podRows = body.filter(r => r.fields[col('פודקאסט')].trim() === podName);
    const seasonName = r => seasonOf(r.fields[col('כותרת חדשה')], r.fields[col('עונה')]);
    const season = seasonOf(title, st.season || '');
    const seasons = [...new Set(podRows.map(seasonName))];
    const sameSeason = podRows.filter(r => seasonName(r) === season);
    const isNew = !seasons.includes(season);
    const allSeasons = isNew ? [...seasons, season] : seasons;
    const numbered = allSeasons.length > 1 || allSeasons[0] !== '';
    const seasonIndex = allSeasons.indexOf(season) + 1, episode = sameSeason.length + 1;

    // 3. dates: the feed date has the time of day (UTC), the catalog date is the Israeli day
    const now = new Date(Date.now() - 60000);
    const feedDate = `${pad(now.getUTCDate())}/${pad(now.getUTCMonth() + 1)}/${now.getUTCFullYear()} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}`;
    const pubDate = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), now.getUTCHours(), now.getUTCMinutes())).toUTCString();
    const fields = head.map(() => '');
    Object.entries({
      'פודקאסט': podName, 'עונה': season, 'כותרת חדשה': title, 'כותרת מקורית': title, 'תיאור': desc,
      'תאריך': ilDate(now), 'אורך': hms(st.file.seconds), 'תאריך בפיד': feedDate,
    }).forEach(([k, v]) => { fields[col(k)] = v; });

    // 4. commits: audio list, catalog, site, and the feed last (so apps only see a lesson the site already has)
    step = 'עדכון הרשימה';
    const cloud = await repo.read('data/cloud_audio.json');
    const cloudAudio = cloud ? JSON.parse(cloud.text) : {};
    cloudAudio[lid] = { ext, size: stored.size };
    await repo.write('data/cloud_audio.json', JSON.stringify(cloudAudio, null, 1) + '\n', cloud?.sha, `Add recording ${lid}`);

    step = 'עדכון הקטלוג';
    const anchor = sameSeason.at(-1) || podRows.at(-1) || body.at(-1);
    const before = cat.text.slice(0, anchor.end), after = cat.text.slice(anchor.end);
    const sep = /[\r\n]$/.test(before) ? '' : eol;
    await repo.write(CATALOG_PATH, before + sep + csvLine(fields, eol) + after, cat.sha, `Add lesson: ${title}`);

    step = 'עדכון האתר';
    const dataJs = await repo.read('docs/data.js');
    const data = JSON.parse(dataJs.text.replace(/^window\.DATA = /, '').replace(/;\s*$/, ''));
    const pod = data.find(p => p.name === podName);
    let block = [...pod.seasons].reverse().find(s => s.name === season);
    if (!block) pod.seasons.push(block = { name: season, about: '', lessons: [] });
    block.lessons.push({ id: lid, title, desc, date: ilDate(now), dur: hms(st.file.seconds), audio: `${media}audio/${lid}${ext}` });
    await repo.write('docs/data.js', 'window.DATA = ' + JSON.stringify(data, null, 1) + ';\n', dataJs.sha, `Site: add lesson ${title}`);

    step = 'עדכון הפיד';
    const feedPath = `docs/feeds/${st.pod}.xml`;
    const feed = await repo.read(feedPath);
    const item = feedItem({
      lesson: { id: lid, title, desc, pubDate, ext, size: stored.size, seconds: st.file.seconds, season },
      site, media, seasonIndex, episode, numbered,
    });
    const at = feed.text.indexOf('    <item>');
    await repo.write(feedPath, feed.text.slice(0, at) + item + feed.text.slice(at), feed.sha, `Feed: add lesson ${title}`);

    await setState(env, chat, null);
    await say(env, chat, '✅ פורסם! ההקלטה בענן, בפיד ובאתר. אפליקציות הפודקאסטים יקלטו אותה בדרך כלל תוך דקות עד כמה שעות, והאתר יתעדכן בתוך דקה או שתיים.');
    await say(env, chat, `🎧 שיעור חדש: ${title}\n${desc}\n${site}#${lid}`);
  } catch (e) {
    // before anything was committed the recording can simply be published again
    const safe = ['הורדה מטלגרם', 'העלאה לענן', 'קריאת הקטלוג'].includes(step);
    st.stage = safe ? 'confirm' : 'failed';
    await setState(env, chat, st);
    await say(env, chat, `❌ התקלה בשלב „${step}”: ${String(e.message || e).slice(0, 300)}` +
      (safe ? '\nאפשר ללחוץ שוב על פרסום.' : '\nחלק מהעדכונים כבר נשמרו, אל תנסה שוב, ותגיד לי ואבדוק.'),
      safe ? buttons([[['✅ פרסום', 'ok'], ['✖ ביטול', 'no']]]) : undefined);
  }
}

// ---- entry point ----
async function handle(env, msg) {
  const from = String(msg.from.id);
  const owner = (env.OWNER_ID || '').trim();
  if (!owner) return say(env, msg.chat.id, `המזהה שלך בטלגרם: ${from}`);
  if (from !== owner) return;
  const chat = msg.chat.id;
  if (msg.voice) return say(env, chat, 'הודעה קולית נשמרת בפורמט שאפליקציות הפודקאסטים לא מכירות. שלח את ההקלטה כקובץ mp3 או m4a.');
  const file = audioOf(msg);
  if (file) return receive(env, chat, file);
  const t = (msg.text || '').trim();
  if (t === '/cancel') { await setState(env, chat, null); return say(env, chat, 'בוטל.'); }
  if (!t || t.startsWith('/')) {
    return say(env, chat, 'שלח לי נושא שיעור ואכין את המודעה, או שלח הקלטה ואפרסם אותה בכל האפליקציות.');
  }
  return text(env, chat, t);
}

export default {
  async fetch(req, env, ctx) {
    if (req.method !== 'POST' || req.headers.get('x-telegram-bot-api-secret-token') !== (env.WEBHOOK_SECRET || '').trim())
      return new Response('ok');
    const update = await req.json();
    const owner = (env.OWNER_ID || '').trim();
    if (update.message) ctx.waitUntil(handle(env, update.message));
    else if (update.callback_query) {
      const cb = update.callback_query;
      if (owner && String(cb.from.id) === owner) {
        ctx.waitUntil(tg(env, 'answerCallbackQuery', { callback_query_id: cb.id })
          .then(() => press(env, cb.message.chat.id, cb.data)));
      }
    }
    return new Response('ok');
  },
};
