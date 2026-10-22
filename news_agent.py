"""Free Indonesia–Cambodia gambling-policy news monitor (no AI API needed)."""
import hashlib
from html import escape
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import feedparser
import requests
from sources_ai import publisher_news
from bs4 import BeautifulSoup

STATE = Path("seen_news.json")
# News discovery restricted to identifiable publishers; verify stories at source.
SEARCHES = [
    [
        "🇰🇭 Cambodia · Phnom Penh Post",
        "site:phnompenhpost.com Cambodia gambling OR scam OR crackdown when:14d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · Khmer Times",
        "site:khmertimeskh.com Cambodia gambling OR scam OR crackdown when:14d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · CamboJA",
        "site:cambojanews.com Cambodia gambling OR scam OR cybercrime when:14d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · Cambodianess",
        "site:cambodianess.com Cambodia gambling OR scam OR crackdown when:14d",
        "en",
        "KH"
    ],
    [
        "🇮🇩 Indonesia · ANTARA",
        "site:antaranews.com judi online Kamboja penindakan when:14d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · Kompas",
        "site:kompas.com judi online Kamboja penindakan when:14d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · Tempo",
        "site:tempo.co judi online Kamboja penindakan when:14d",
        "id",
        "ID"
    ],
    [
        "🌏 Lintas negara · Reuters",
        "site:reuters.com Cambodia Indonesia online gambling scam when:14d",
        "en",
        "KH"
    ]
]

KEYWORDS = ("judol", "judi online", "casino", "scam online", "deportasi")
USER_AGENT = "DekaNewsResearch/1.0 (public RSS monitoring)"
MAX_ITEMS = 7


def published_at(item):
    """Return a timezone-aware publication time, or None if unavailable."""
    try:
        value = parsedate_to_datetime(item.get("published", ""))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None



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
                    "id": identity, "category": label, "source": entry.get("source", {}).get("title", label), "title": title,
                    "link": link, "published": entry.get("published", "Waktu tidak tersedia"),
                    "summary": summary[:300]
                }
        except Exception as exc:
            print(f"Feed failed ({label}): {exc}", file=sys.stderr)
    for item in publisher_news(KEYWORDS):
        found.setdefault(item['id'], item)
    return list(found.values())


def send_message(token, chat_id, text):
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             json={"chat_id": chat_id, "text": text,
                                   "disable_web_page_preview": True, "parse_mode": "HTML"},
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
    now = datetime.now(timezone.utc)
    dated = [(e, published_at(e)) for e in entries if e["id"] not in seen]
    recent = [(e, dt) for e, dt in dated if dt is not None and now - timedelta(hours=24) <= dt <= now + timedelta(minutes=10)]
    fallback = [(e, dt) for e, dt in dated if dt is not None and now - timedelta(days=3) <= dt < now - timedelta(hours=24)]
    recent.sort(key=lambda pair: pair[1], reverse=True)
    fallback.sort(key=lambda pair: pair[1], reverse=True)
    new = [e for e, _ in (recent + fallback)[:MAX_ITEMS]]
    if not new:
        print("No new relevant news; no Telegram message sent.")
        return
    header = "📰 DEKA NEWS | RISET INDONESIA–KAMBOJA\n"
    header += datetime.now(timezone.utc).strftime("UTC %d/%m/%Y %H:%M") + "\n"
    header += "Berita dikumpulkan dari RSS; selalu verifikasi melalui tautan sumber.\n"
    chunks = [header]
    for idx, item in enumerate(new, 1):
        source = escape(str(item.get("source", item["category"])))
        category = escape(item["category"])
        title = escape(re.sub(r"[\x00-\x1f]", " ", item["title"])[:220])
        published = escape(item["published"])
        link = escape(item["link"], quote=True)
        chunks.append(
            f"\n<b>{idx}. {category}</b>\n"
            f"<b>{title}</b>\n"
            f"🗞 Sumber: {source}\n"
            f"📅 {published}\n"
            f'🔗 <a href="{link}">Baca Berita</a>\n'
        )
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
