"""Scheduled Telegram command/chat poller. State contains only update offsets."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.telegram.org/bot"
STATE_FILE = "telegram_offset.json"
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def request_json(url, payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)


def github_state(method="GET", state=None, sha=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    url = f"https://api.github.com/repos/{repo}/contents/{STATE_FILE}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}
    if method == "GET":
        try:
            result = request_json(url, headers=headers)
            import base64
            return json.loads(base64.b64decode(result["content"])), result["sha"]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"offset": 0}, None
            raise
    import base64
    payload = {"message": "Update Telegram polling offset",
               "content": base64.b64encode((json.dumps(state) + "\n").encode()).decode()}
    if sha:
        payload["sha"] = sha
    return request_json(url, payload, headers)


def telegram(token, method, payload):
    return request_json(f"{API}{token}/{method}", payload)


def latest_news():
    from news_agent import get_entries
    entries = get_entries()[:5]
    if not entries:
        return "Belum ada berita yang cocok saat ini."
    return "📰 Berita terbaru:\n" + "\n\n".join(
        f"• {item['title'][:150]}\n{item['link']}" for item in entries
    )


def groq_reply(text):
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return "AI chat belum aktif. Tambahkan GROQ_API_KEY di GitHub Actions Secrets. Perintah /news dan /status tetap bisa."
    prompt = ("Kamu DEKA JARVIS, asisten berita berbahasa Indonesia santai. "
              "Jawab singkat, akurat, dan jangan mengaku mengetahui berita terbaru tanpa sumber. "
              "Jangan mengarang fakta atau tautan.\n\nPengguna: " + text[:3000])
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                         "max_tokens": 500, "temperature": 0.3}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.load(response)
        return result["choices"][0]["message"]["content"][:3500]
    except urllib.error.HTTPError as exc:
        print(f"Groq HTTP error: {exc.code}")
        return "AI sedang tidak tersedia atau kuotanya habis. Coba lagi nanti; /news tetap bisa."
    except (TimeoutError, KeyError, IndexError, ValueError) as exc:
        print(f"Groq error: {type(exc).__name__}")
        return "AI belum bisa menjawab sekarang. Coba lagi nanti."


def answer(text):
    cmd = text.strip().split(maxsplit=1)[0].split("@")[0].lower() if text.strip() else ""
    if cmd in ("/start", "/help"):
        return "🤖 DEKA JARVIS\n/news — berita terbaru\n/status — status bot\n/help — bantuan\nAtau kirim pertanyaan bebas untuk Groq AI."
    if cmd in ("/news", "/latest"):
        return latest_news()
    if cmd == "/status":
        return f"🟢 DEKA JARVIS aktif via GitHub Actions. UTC {datetime.now(timezone.utc):%d/%m %H:%M}. Chat tidak real-time."
    return groq_reply(text)


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    allowed = str(os.environ["TELEGRAM_CHAT_ID"]).strip()
    state, sha = github_state()
    offset = int(state.get("offset", 0))
    result = telegram(token, "getUpdates", {"offset": offset, "timeout": 0, "limit": 50,
                                            "allowed_updates": ["message"]})
    if not result.get("ok"):
        raise RuntimeError("Telegram getUpdates failed")
    for update in result.get("result", []):
        uid = int(update["update_id"])
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        content = message.get("text", "")
        if chat_id == allowed and content:
            try:
                response = answer(content)
                for pos in range(0, len(response), 3500):
                    sent = telegram(token, "sendMessage", {"chat_id": allowed,
                                                           "text": response[pos:pos+3500],
                                                           "disable_web_page_preview": True})
                    if not sent.get("ok"):
                        raise RuntimeError("Telegram sendMessage failed")
            except Exception:
                # Retry this update on the next run instead of silently losing it.
                if offset != int(state.get("offset", 0)):
                    github_state("PUT", {"offset": offset}, sha)
                raise
        offset = uid + 1
    if offset != int(state.get("offset", 0)):
        github_state("PUT", {"offset": offset}, sha)
    print(f"Telegram updates processed; offset={offset}")


if __name__ == "__main__":
    main()
