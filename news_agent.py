"""DEKA News: standard-library-only RSS monitor with optional Gemini summaries."""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from sources_ai import ai_summary, publisher_news

LOG = logging.getLogger("deka_news")
STATE = Path(os.getenv("NEWS_STATE_FILE", "seen_news.json"))
MAX_ITEMS = int(os.getenv("MAX_NEWS_ITEMS", "7"))
KEYWORDS = ("judi", "judol", "gambling", "casino", "betting", "scam", "penipuan",
            "wni", "deportasi", "pemblokiran", "ppatk", "cybercrime")
SEARCHES = [
    ("🇰🇭 Cambodia · Phnom Penh Post", "site:phnompenhpost.com Cambodia gambling OR scam OR crackdown when:14d", "en", "KH"),
    ("🇰🇭 Cambodia · Khmer Times", "site:khmertimeskh.com Cambodia gambling OR scam OR crackdown when:14d", "en", "KH"),
    ("🇰🇭 Cambodia · CamboJA", "site:cambojanews.com Cambodia gambling OR scam OR cybercrime when:14d", "en", "KH"),
    ("🇰🇭 Cambodia · Cambodianess", "site:cambodianess.com Cambodia gambling OR scam OR crackdown when:14d", "en", "KH"),
    ("🇮🇩 Indonesia · ANTARA", "site:antaranews.com judi online Kamboja penindakan when:14d", "id", "ID"),
    ("🇮🇩 Indonesia · Kompas", "site:kompas.com judi online Kamboja penindakan when:14d", "id", "ID"),
    ("🇮🇩 Indonesia · Tempo", "site:tempo.co judi online Kamboja penindakan when:14d", "id", "ID"),
    ("🌏 Lintas negara · Reuters", "site:reuters.com Cambodia Indonesia online gambling scam when:14d", "en", "KH"),
]


def request(url, *, payload=None, headers=None, timeout=20):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    h = {"User-Agent": "DekaNewsResearch/2.0 (+public RSS research)"}
    if data is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def child_text(node, name):
    child = node.find(name)
    return "".join(child.itertext()).strip() if child is not None else ""


def parse_feed(data):
    """Read RSS 2.0 or Atom; no third-party parser required."""
    root = ET.fromstring(data)
    entries = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: child for child in node}
        def field(*names):
            for name in names:
                el = fields.get(name)
                if el is not None:
                    return "".join(el.itertext()).strip()
            return ""
        link = field("link")
        link_node = fields.get("link")
        if link_node is not None and link_node.get("href"):
            link = link_node.get("href", link)
        entries.append({"title": clean(field("title")), "summary": clean(field("description", "summary", "content")),
                        "link": link, "published": field("pubDate", "published", "updated") or "Waktu tidak tersedia",
                        "source": field("source")})
    return entries


def fingerprint(item):
    # Prefer normalized title: Google News and direct feeds often use different URLs.
    title = re.sub(r"[^\w]+", " ", item["title"].casefold()).strip()
    return hashlib.sha256(title.encode("utf-8")).hexdigest()


def collect():
    found = {}
    for category, query, lang, country in SEARCHES:
        params = urllib.parse.urlencode({"q": query, "hl": lang, "gl": country, "ceid": f"{country}:{lang}"})
        try:
            entries = parse_feed(request("https://news.google.com/rss/search?" + params))
            for item in entries[:25]:
                if not item["title"] or not item["link"]:
                    continue
                if not any(k in (item["title"] + " " + item["summary"]).casefold() for k in KEYWORDS):
                    continue
                item.update(category=category, source=item["source"] or category)
                item["id"] = fingerprint(item)
                found.setdefault(item["id"], item)
        except (OSError, ET.ParseError, ValueError) as exc:
            LOG.warning("Feed failed (%s): %s", category, exc)
    for item in publisher_news(KEYWORDS, request=request, parse_feed=parse_feed):
        found.setdefault(item["id"], item)
    return list(found.values())


def load_seen():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError) as exc:
        LOG.warning("State missing or invalid; starting empty: %s", exc)
        return set()


def save_seen(seen):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(STATE.suffix + ".tmp")
    tmp.write_text(json.dumps({"seen": sorted(seen)}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def telegram_send(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    for attempt in range(3):
        try:
            response = json.loads(request(url, payload=payload, timeout=25))
            if not response.get("ok"):
                raise RuntimeError("Telegram rejected message")
            return
        except (OSError, ValueError, RuntimeError) as exc:
            if attempt == 2:
                raise RuntimeError("Telegram delivery failed") from exc
            LOG.warning("Telegram retry %d: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)


def format_item(item, index):
    e = html.escape
    title = e(item["title"][:220])
    source = e(str(item["source"]))
    category = e(str(item["category"]))
    published = e(str(item["published"]))
    link = e(item["link"], quote=True)
    summary = ai_summary(item, request=request)
    ai_line = f"🧠 AI (judul/cuplikannya): {e(summary)}\n" if summary else ""
    return (f"\n<b>{index}. {category}</b>\n<b>{title}</b>\n"
            f"🗞 Sumber: {source}\n📅 {published}\n{ai_line}"
            f'🔗 <a href="{link}">Baca Berita</a>\n')


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    seen = load_seen()
    unseen = [item for item in collect() if item["id"] not in seen]
    kh = [item for item in unseen if item["category"].startswith("🇰🇭")]
    other = [item for item in unseen if not item["category"].startswith("🇰🇭")]
    selected = (kh[:4] + other)[:max(0, MAX_ITEMS)]
    if not selected:
        LOG.info("No new news")
        return
    header = ("📰 DEKA NEWS | RISET INDONESIA–KAMBOJA\n"
              + datetime.now(timezone.utc).strftime("UTC %d/%m/%Y %H:%M")
              + "\nAI hanya merangkum judul/cuplikannya, bukan verifikasi.\n")
    # Send one item per message to keep Telegram HTML well-formed.
    # Save after each successful send to prevent resending on partial failures.
    telegram_send(token, chat_id, header)
    for index, item in enumerate(selected, 1):
        telegram_send(token, chat_id, format_item(item, index))
        seen.add(item["id"])
        save_seen(seen)
    LOG.info("Sent %d stories", len(selected))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        main()
    except Exception:
        LOG.exception("News run failed")
        sys.exit(1)
