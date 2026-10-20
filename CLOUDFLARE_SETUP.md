# Cloudflare Workers webhook (DEKA JARVIS)

The Worker runs real-time Telegram chat; GitHub Actions continues scheduled news reporting.

## Setup (do not put tokens in repository files)

1. Cloudflare Workers project → Settings → Variables and Secrets: add encrypted secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_ID`, `GROQ_API_KEY`, and `WEBHOOK_SECRET` (a new long random string; letters, numbers, underscores, and hyphens). Optional: `GROQ_MODEL`.
2. Ensure Git deployment uses `wrangler.toml` and the production URL serves JSON at `/`.
3. **Before setting Telegram webhook**, disable the `Poll Telegram and respond` step in `.github/workflows/news.yml`. Keep the news-monitoring steps. Telegram getUpdates polling and webhook must not run together.
4. Register the webhook using Telegram Bot API `setWebhook` with URL `https://YOUR-WORKER.workers.dev/telegram` and `secret_token` equal to `WEBHOOK_SECRET`. Do this only after secrets and polling change are ready. Never paste bot tokens into chat, screenshots, or a public repository.
5. Test `/start`, `/status`, and an AI question in your private chat.

**Current limitation:** `/news` in the Worker is informational; the scheduled news channel report remains handled by GitHub Actions. The Worker responds only to the private chat whose numeric ID matches `TELEGRAM_ADMIN_ID`.

**Important:** Deploying this code does not automatically register a webhook or disable GitHub polling. Until migration is completed, the old bot continues working through GitHub Actions.
