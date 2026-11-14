"""Free Indonesia–Cambodia gambling-policy news monitor (no AI API needed)."""
import hashlib
from difflib import SequenceMatcher
from html import escape
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

STATE = Path("seen_news.json")
# News discovery restricted to identifiable publishers; verify stories at source.
SEARCHES = [
    [
        "🇰🇭 Cambodia · Phnom Penh Post",
        "site:phnompenhpost.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · Khmer Times",
        "site:khmertimeskh.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · CamboJA",
        "site:cambojanews.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · Cambodianess",
        "site:cambodianess.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · VOA Khmer",
        "site:khmer.voanews.com (casino OR scam OR \"scam center\" OR \"scam centre\" OR trafficking OR deportation) when:1d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · RFA Cambodia",
        "site:rfa.org/english/cambodia (casino OR scam OR \"scam center\" OR \"scam centre\" OR trafficking OR deportation) when:1d",
        "en",
        "KH"
    ],
    [
        "🇰🇭 Cambodia · AKP (sumber resmi)",
        "site:akp.gov.kh (casino OR scam OR \"online fraud\" OR trafficking OR deportation) when:1d",
        "en",
        "KH"
    ],
    [
        "🇮🇩 Indonesia · ANTARA",
        "site:antaranews.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · Kompas",
        "site:kompas.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · Tempo",
        "site:tempo.co (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · CNN Indonesia",
        "site:cnnindonesia.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · Detik",
        "site:detik.com (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · Tirto",
        "site:tirto.id (casino OR scam OR \"scam online\" OR trafficking) when:1d",
        "id",
        "ID"
    ],
    [
        "🇮🇩 Indonesia · The Jakarta Post",
        "site:thejakartapost.com (\"online gambling\" OR casino OR scam OR \"online fraud\" OR trafficking OR deportation) when:1d",
        "en",
        "ID"
    ],
    [
        "🌏 Lintas negara · Reuters",
        "site:reuters.com (\"online gambling\" OR casino OR scam OR \"online fraud\" OR trafficking OR deportation) when:1d",
        "en",
        "KH"
    ]
]

KEYWORDS = (
    "online gambling", "casino", "scam online", "scam",
    "scam center", "scam centre", "online fraud", "cyberfraud",
    "deportation", "trafficking"
)
USER_AGENT = "DekaNewsResearch/1.0 (public RSS monitoring)"
WIB = ZoneInfo("Asia/Jakarta")

SOURCE_SUFFIXES = (
    "kompas.com", "antara news", "antara news mataram", "tempo.co", "cnn indonesia",
    "detikcom", "detik.com", "tirto.id", "the jakarta post", "phnom penh post",
    "khmer times", "camboja news", "cambodianess", "voa khmer", "radio free asia",
    "reuters"
)
GENERIC_STORY_WORDS = {
    "berita", "foto", "video", "halaman", "indonesia", "kamboja", "cambodia",
    "online", "scam", "casino", "judi", "judol", "kasus", "terkait", "diduga",
    "ungkap", "sebut", "terbaru", "hari", "news"
}


def clean_title(title):
    """Remove RSS/publisher boilerplate while preserving display casing."""
    value = title.strip()
    value = re.sub(r"^(?:foto|video)\s*:\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+halaman\s+\d+\b", "", value, flags=re.IGNORECASE)
    suffixes = "|".join(re.escape(name) for name in SOURCE_SUFFIXES)
    return re.sub(rf"(?:\s*-\s*(?:{suffixes}))+\s*$", "", value,
                  flags=re.IGNORECASE).strip()


def normalize_title(title):
    """Normalize a cleaned headline before duplicate comparison."""
    return re.sub(r"[^\w]+", " ", clean_title(title).casefold()).strip()


def same_story(left, right):
    """Detect headline variants for one event from the same publisher."""
    if left == right:
        return True
    left_words = set(left.split())
    right_words = set(right.split())
    common = left_words & right_words
    smallest = max(1, min(len(left_words), len(right_words)))
    if SequenceMatcher(None, left, right).ratio() >= 0.72:
        return True
    if len(common) / smallest >= 0.65:
        return True
    distinctive = common - GENERIC_STORY_WORDS
    return len(common) >= 2 and bool(distinctive)


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
            for entry in feed.entries:
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
    previous = json.loads(STATE.read_text()) if STATE.exists() else {"seen": [], "titles": []}
    seen = set(previous.get("seen", []))
    seen_titles = previous.get("titles", [])
    entries = get_entries()
    now = datetime.now(timezone.utc)
    # Match by normalized title across RSS sources and changing article URLs.
    # Keep checking legacy title+URL hashes so previously sent stories stay excluded.
    def legacy_title_key(item):
        normalized = re.sub(r"[^\w]+", " ", item["title"].casefold()).strip()
        return "TITLE:v2:" + hashlib.sha256(normalized.encode()).hexdigest()

    def title_key(item):
        return "TITLE:v3:" + hashlib.sha256(normalize_title(item["title"]).encode()).hexdigest()

    def duplicate_of_stored(item):
        normalized = normalize_title(item["title"])
        source = str(item.get("source", item["category"])).casefold()
        return any(
            record.get("source") == source and same_story(normalized, record.get("title", ""))
            for record in seen_titles
        )

    recent = []
    for item in entries:
        dt = published_at(item)
        if dt is None or not (now - timedelta(hours=24) <= dt <= now + timedelta(minutes=10)):
            continue
        key = title_key(item)
        if key in seen or legacy_title_key(item) in seen or item["id"] in seen or duplicate_of_stored(item):
            continue
        recent.append((item, dt, key))
    recent.sort(key=lambda pair: pair[1], reverse=True)
    new = []
    batch_titles = []
    for item, _, key in recent:
        normalized = normalize_title(item["title"])
        source = str(item.get("source", item["category"])).casefold()
        if any(old_source == source and same_story(normalized, old_title)
               for old_source, old_title in batch_titles):
            continue
        batch_titles.append((source, normalized))
        new.append(item)
    if not new:
        print("No new relevant news; no Telegram message sent.")
        return
    header = "📰 <b>D3ka News</b>\n"
    header += datetime.now(WIB).strftime("Update %d/%m/%Y · %H.%M WIB\n")
    chunks = [header]
    for idx, item in enumerate(new, 1):
        category = escape(item["category"])
        title = escape(re.sub(r"[\x00-\x1f]", " ", clean_title(item["title"]))[:220])
        published = published_at(item).astimezone(WIB).strftime("%d %b %Y · %H.%M WIB")
        link = escape(item["link"], quote=True)
        chunks.append(
            f"\n<b>{idx}. {category}</b>\n"
            f"<b>{title}</b>\n"
            f"🕒 {published}\n"
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
    seen.update(title_key(e) for e in new)
    seen_titles.extend({
        "source": str(e.get("source", e["category"])).casefold(),
        "title": normalize_title(e["title"])
    } for e in new)
    STATE.write_text(json.dumps({
        "seen": sorted(seen),
        "titles": seen_titles[-500:]
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"Sent {len(new)} new stories.")


if __name__ == "__main__":
    main()
