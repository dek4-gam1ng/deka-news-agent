// DEKA JARVIS — Telegram webhook for Cloudflare Workers.
// Set TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, GROQ_API_KEY, and WEBHOOK_SECRET
// as encrypted Worker secrets. Do not commit credentials.
const TG = "https://api.telegram.org/bot";
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json; charset=utf-8" }
});

async function sendMessage(env, chatId, message) {
  const text = typeof message === "string" && message.trim()
    ? message.trim() : "Maaf brek, AI belum menghasilkan jawaban. Coba lagi ya.";
  for (let i = 0; i < text.length; i += 3500) {
    const response = await fetch(`${TG}${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: text.slice(i, i + 3500),
        disable_web_page_preview: true })
    });
    if (!response.ok) throw new Error(`Telegram sendMessage HTTP ${response.status}`);
  }
}

async function answer(text, env) {
  const cmd = text.trim().split(/\s+/)[0].split("@")[0].toLowerCase();
  if (cmd === "/start" || cmd === "/help") {
    return "🤖 DEKA JARVIS aktif!\n/status — status bot\n/news — info berita\n/help — bantuan\nAtau langsung tanya apa saja.";
  }
  if (cmd === "/status") return "🟢 DEKA JARVIS aktif via Cloudflare Workers. Chat real-time.";
  if (cmd === "/news" || cmd === "/latest") {
    return "📰 Laporan berita tetap dikirim otomatis ke channel Telegram oleh GitHub Actions. Fitur /news langsung sedang disiapkan.";
  }
  if (!env.GROQ_API_KEY) return "AI belum dikonfigurasi. Hubungi admin JARVIS.";
  try {
    const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "authorization": `Bearer ${env.GROQ_API_KEY}`, "content-type": "application/json" },
      body: JSON.stringify({
        model: env.GROQ_MODEL || "llama-3.1-8b-instant",
        messages: [{ role: "system", content: "Kamu DEKA JARVIS, asisten berbahasa Indonesia santai. Jawab singkat, akurat, dan jangan mengarang fakta atau tautan." },
          { role: "user", content: text.slice(0, 3000) }],
        max_tokens: 500, temperature: 0.3
      })
    });
    if (!response.ok) {
      console.error("Groq HTTP", response.status);
      return "AI sedang tidak tersedia atau kuotanya habis. Coba lagi nanti.";
    }
    const data = await response.json();
    return data?.choices?.[0]?.message?.content?.trim() || "AI belum menghasilkan jawaban. Coba lagi sebentar ya.";
  } catch (error) {
    console.error("Groq request error", error?.name || "unknown");
    return "AI belum bisa menjawab sekarang. Coba lagi nanti.";
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return json({ service: "DEKA JARVIS", status: "ready", webhook: "not automatically configured" });
    }
    if (url.pathname !== "/telegram" || request.method !== "POST") {
      return new Response("Not found", { status: 404 });
    }
    if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_ADMIN_ID || !env.WEBHOOK_SECRET) {
      return json({ error: "Worker secrets not configured" }, 503);
    }
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
      return json({ error: "Unauthorized" }, 401);
    }
    let update;
    try { update = await request.json(); } catch { return json({ error: "Invalid JSON" }, 400); }
    const message = update?.message;
    const chatId = message?.chat?.id;
    const text = message?.text;
    // Only respond to the authorized user's private chat.
    if (message?.chat?.type !== "private" || String(chatId) !== String(env.TELEGRAM_ADMIN_ID) || typeof text !== "string" || !text.trim()) {
      return json({ ok: true, ignored: true });
    }
    try {
      await sendMessage(env, chatId, await answer(text, env));
      return json({ ok: true });
    } catch (error) {
      console.error("Telegram delivery error", error?.message || "unknown");
      return json({ error: "Delivery failed" }, 500);
    }
  }
};
