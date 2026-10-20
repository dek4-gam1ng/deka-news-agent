# DEKA News Agent 📰

Python 3.12+ news monitor for Indonesia and Cambodia. **No pip dependencies**. Searches Google News RSS and publisher RSS, filters headlines, deduplicates, sends Telegram reports, and optionally summarizes headline/snippet with Gemini.

## Run locally

```bash
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
# Optional:
export GEMINI_API_KEY="your-key"
python news_agent.py
```

GitHub Actions runs every four hours or manually. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID under repository Settings → Secrets and variables → Actions. Optionally add GEMINI_API_KEY. Enable Actions workflow write permissions for committing seen_news.json.

## Files

- news_agent.py: stdlib HTTP, RSS/Atom parsing, filtering, Telegram, state.
- sources_ai.py: publisher feed discovery and optional Gemini REST summaries.
- seen_news.json: fingerprints of delivered stories.
- .github/workflows/news.yml: scheduled execution.
- requirements.txt: empty; no third-party packages.

## Limitations

Not a conversational JARVIS yet: GitHub Actions runs on a schedule, not a persistent Telegram listener. AI summaries only use headline and RSS snippet, not full article verification. Google News may return publisher redirects. Never commit tokens or private conversations. News classification is keyword-based; validate important claims at their original sources.
