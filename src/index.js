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
      return `Groq gagal (HTTP ${response.status}). Beri tahu admin kode ini, tanpa mengirim API key.`;
    }
    const data = await response.json();
    return data?.choices?.[0]?.message?.content?.trim() || "AI belum menghasilkan jawaban. Coba lagi sebentar ya.";
  } catch (error) {
    console.error("Groq request error", error?.name || "unknown");
    return "AI belum bisa menjawab sekarang. Coba lagi nanti.";
  }
}


// Private activation page. Password is sent in an HTTPS POST body, never a URL.
// The webhook secret must be a strong random value configured in Worker Secrets.
const setupPage = `<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>Aktifkan DEKA JARVIS</title>
<style>body{font:16px system-ui;max-width:440px;margin:60px auto;padding:20px;line-height:1.5}
input,button{box-sizing:border-box;width:100%;padding:13px;margin:8px 0;font:inherit}
button{background:#202bdf;color:white;border:0;border-radius:8px}
input{border:1px solid #aaa;border-radius:8px}</style></head><body>
<h2>🤖 Aktifkan DEKA JARVIS</h2><p>Masukkan WEBHOOK_SECRET yang sudah disimpan di Cloudflare.
Jangan masukkan token bot atau API key di sini.</p>
<form action="/setup" method="POST"><label>WEBHOOK_SECRET
<input type="password" name="secret" required autocomplete="off"></label>
<button type="submit">Aktifkan Telegram Webhook</button></form>
<p>Setelah berhasil, coba kirim /start ke bot Telegram.</p></body></html>`;
const privateHeaders = { "cache-control": "no-store", "referrer-policy": "no-referrer",
  "x-content-type-options": "nosniff" };
async function activateWebhook(request, env, url) {
  const missing = [
    !env.TELEGRAM_BOT_TOKEN && "TELEGRAM_BOT_TOKEN",
    !env.WEBHOOK_SECRET && "WEBHOOK_SECRET"
  ].filter(Boolean);
  if (missing.length) {
    const details = missing.map(name => `<li><code>${name}</code> belum terbaca</li>`).join("");
    const diagnostics = ["TELEGRAM_BOT_TOKEN", "WEBHOOK_SECRET", "TELEGRAM_ADMIN_ID", "GROQ_API_KEY"].map(name => {
      const bound = Object.prototype.hasOwnProperty.call(env, name);
      const type = typeof env[name];
      return `<li><code>${name}</code>: ${bound ? "bound" : "absent"} (type: ${type})</li>`;
    }).join("");
    return new Response(`<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font:16px system-ui;max-width:480px;margin:40px auto;padding:16px">
<h2>⚠️ Secrets Cloudflare belum lengkap</h2>
<p>Worker Production belum bisa membaca:</p><ul>${details}</ul>
<p>Cek <b>Settings → Variables and Secrets</b> pada Worker yang sama, lalu pastikan nama dan nilainya terisi. Simpan dan deploy ulang jika perlu.</p>
<h3>Binding diagnostics</h3><ul>${diagnostics}</ul>
<p>Hanya nama Secret yang ditampilkan. Nilai rahasia tidak ditampilkan.</p></body></html>`, {
      status: 503, headers: { ...privateHeaders, "content-type": "text/html; charset=utf-8" }
    });
  }
  if (request.method === "GET") {
    return new Response(setupPage, { headers: { ...privateHeaders, "content-type": "text/html; charset=utf-8" } });
  }
  if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
  // Activation is authorized by the strong WEBHOOK_SECRET in the POST body.
  // Do not depend on Origin/Referer headers, which may be modified by proxies.
  if (Number(request.headers.get("content-length") || 0) > 4096) {
    return new Response("Request too large", { status: 413, headers: privateHeaders });
  }
  const form = await request.formData();
  const supplied = form.get("secret");
  if (typeof supplied !== "string" || supplied.length > 256 || supplied !== env.WEBHOOK_SECRET) {
    return new Response("Secret salah. Kembali dan coba lagi.", { status: 403, headers: privateHeaders });
  }
  const response = await fetch(`${TG}${env.TELEGRAM_BOT_TOKEN}/setWebhook`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      url: `${url.origin}/telegram`,
      secret_token: env.WEBHOOK_SECRET,
      allowed_updates: ["message"],
      drop_pending_updates: false
    })
  });
  if (!response.ok) {
    console.error("Telegram setWebhook HTTP", response.status);
    return new Response("Aktivasi gagal. Cek token bot di Cloudflare.", { status: 502, headers: privateHeaders });
  }
  const result = await response.json();
  if (!result.ok) return new Response("Telegram menolak aktivasi webhook.", { status: 502, headers: privateHeaders });
  return new Response("✅ Webhook berhasil aktif! Sekarang coba kirim /start ke JARVIS di Telegram.", {
    headers: { ...privateHeaders, "content-type": "text/plain; charset=utf-8" }
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/setup") return activateWebhook(request, env, url);
    if (request.method === "GET" && url.pathname === "/") {
      return json({ service: "DEKA JARVIS", status: "ready", webhook: "setup at /setup", deployment: "verify-github-deploy-20261020-c" });
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
