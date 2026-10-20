"""Publisher RSS discovery and optional Gemini summarization (stdlib only)."""
import json
import hashlib
import re
import logging
import os
import urllib.parse
from html.parser import HTMLParser

LOG = logging.getLogger("deka_news")
SITES = [
 ("🇰🇭 Cambodia · Phnom Penh Post", "https://www.phnompenhpost.com"),
 ("🇰🇭 Cambodia · Khmer Times", "https://www.khmertimeskh.com"),
 ("🇰🇭 Cambodia · CamboJA", "https://cambojanews.com"),
 ("🇰🇭 Cambodia · Cambodianess", "https://cambodianess.com"),
 ("🇮🇩 Indonesia · ANTARA", "https://www.antaranews.com"),
 ("🇮🇩 Indonesia · Kompas", "https://www.kompas.com"),
 ("🇮🇩 Indonesia · Tempo", "https://www.tempo.co"),
]

class FeedLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        attrs = dict(attrs)
        if "alternate" in attrs.get("rel", "").split() and attrs.get("type", "").lower() in ("application/rss+xml", "application/atom+xml"):
            if attrs.get("href"):
                self.links.append(attrs["href"])

def publisher_news(keywords, *, request, parse_feed):
    found = {}
    for category, homepage in SITES:
        try:
            parser = FeedLinks()
            parser.feed(request(homepage, timeout=10).decode("utf-8", errors="replace"))
            home_host = urllib.parse.urlparse(homepage).hostname
            for href in parser.links[:2]:
                url = urllib.parse.urljoin(homepage, href)
                if urllib.parse.urlparse(url).hostname != home_host:
                    continue
                for item in parse_feed(request(url, timeout=10))[:20]:
                    if not item["title"] or not item["link"]:
                        continue
                    if urllib.parse.urlparse(item["link"]).hostname != home_host:
                        continue
                    if not any(k in (item["title"] + " " + item["summary"]).casefold() for k in keywords):
                        continue
                    item.update(category=category, source=home_host)
                    item["id"] = hashlib.sha256(re.sub(r"[^\\w]+", " ", item["title"].casefold()).strip().encode("utf-8")).hexdigest()
                    found.setdefault(item["id"], item)
        except Exception as exc:
            LOG.warning("Publisher feed skipped (%s): %s", category, exc)
    return list(found.values())

def ai_summary(item, *, request):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = ("Ringkas netral maksimal dua kalimat dalam bahasa Indonesia, hanya dari judul dan cuplikan. "
              "Jangan mengarang fakta atau mengaku membaca artikel lengkap. Sebutkan bila informasi terbatas.\n"
              f"Judul: {item['title']}\nCuplikan: {item['summary']}")
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + urllib.parse.quote(model, safe="-._") + ":generateContent")
        data = request(url, headers={"x-goog-api-key": key},
                       payload={"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"maxOutputTokens": 220}}, timeout=20)
        response = json.loads(data)
        parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return " ".join(p.get("text", "") for p in parts).strip()[:550]
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        LOG.warning("AI summary skipped: %s", exc)
        return ""
