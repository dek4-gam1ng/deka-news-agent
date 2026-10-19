"""Free Indonesia–Cambodia gambling-policy news monitor (no AI API needed)."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

STATE = Path("seen_news.json")
SEARCHES = [
    ("🇮🇩 Indonesia", "judi online penindakan OR pemblokiran OR PPATK OR Komdigi when:7d", "id", "ID"),
    ("🇰🇭 Cambodia", "Cambodia online gambling crackdown arrests cyber scam when:7d", "en", "KH"),
    ("🇮🇩🇰🇭 Lintas negara", "Indonesia Cambodia online gambling WNI deportasi when:7d", "id", "ID"),
]
KEYWORDS = ("judi", "judol", "gambling", "casino", "betting", "scam", "penipuan", "wni", "deportasi", "pemblokiran", "ppatk")
USER_AGENT = "DekaNewsResearch/1.0 (public RSS monitoring)"
MAX_ITEMS = 7


def get_entries():
    found = {}
    for label, query, lang, country in SEARCHES:
        url = "https://news.google.com/rss/search?q=" + quote(query) + f"&hl={lang}&gl={country}&ceid={country}:{lang}"
        try:
            response = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:25]:
                title = BeautifulSoup(entry.get("title", ""), "html.parser").get_text(" ", strip=True)
                summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)
                if not any(k in (title + " " + summary).lower() for k in KEYWORDS):
                    continue
                link = entry.get("link", "")
                if not link or not title:
                    continue
                identity = hashlib.sha256((title.lower() + "|" + link).encode()).hexdigest()
                found[identity] = {
                    "id": identity, "category": label, "title": title,
                    "link": link, "published": entry.get("published", "Waktu tidak tersedia"),
                    "summary": summary[:300]
                }
        except Exception as exc:
            print(f"Feed failed ({label}): {exc}", file=sys.stderr)
    return list(found.values())


def send_message(token, chat_id, text):
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             json={"chat_id": chat_id, "text": text,
                                   "disable_web_page_preview": True},
                             timeout=25)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError("Telegram rejected message")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in GitHub Actions secrets")
    previous = json.loads(STATE.read_text()) if STATE.exists() else {"seen": []}
    seen = set(previous.get("seen", []))
    entries = get_entries()
    new = [e for e in entries if e["id"] not in seen][:MAX_ITEMS]
    if not new:
        print("No new relevant news; no Telegram message sent.")
        return
    header = "📰 DEKA NEWS | RISET INDONESIA–KAMBOJA\n"
    header += datetime.now(timezone.utc).strftime("UTC %d/%m/%Y %H:%M") + "\n"
    header += "Berita baru dari RSS, bukan analisis AI atau verifikasi independen.\n"
    chunks = [header]
    for idx, item in enumerate(new, 1):
        title = re.sub(r"[\x00-\x1f]", " ", item["title"])[:220]
        chunks.append(f"\n{idx}. {item['category']}\n{title}\n📅 {item['published']}\n🔗 {item['link']}\n")
    # Split under Telegram's 4096-character text limit.
    messages, buf = [], ""
    for chunk in chunks:
        if len(buf) + len(chunk) > 3800 and buf:
            messages.append(buf)
            buf = ""
        buf += chunk
    if buf:
        messages.append(buf)
    for message in messages:
        send_message(token, chat_id, message)
    seen.update(e["id"] for e in new)
    STATE.write_text(json.dumps({"seen": list(seen)[-1000:]}, ensure_ascii=False, indent=2) + "\n")
    print(f"Sent {len(new)} new stories.")


if __name__ == "__main__":
    main()
