"""Optional direct publisher RSS and Gemini summaries; failures never stop news delivery."""
import hashlib
import os
from urllib.parse import urljoin, urlparse
import feedparser
import requests
from bs4 import BeautifulSoup

SITES = [
 ("🇰🇭 Cambodia · Phnom Penh Post", "https://www.phnompenhpost.com"),
 ("🇰🇭 Cambodia · Khmer Times", "https://www.khmertimeskh.com"),
 ("🇰🇭 Cambodia · CamboJA", "https://cambojanews.com"),
 ("🇰🇭 Cambodia · Cambodianess", "https://cambodianess.com"),
 ("🇮🇩 Indonesia · ANTARA", "https://www.antaranews.com"),
 ("🇮🇩 Indonesia · Kompas", "https://www.kompas.com"),
 ("🇮🇩 Indonesia · Tempo", "https://www.tempo.co"),
]

def publisher_news(keywords):
    found = {}
    for category, homepage in SITES:
        try:
            r = requests.get(homepage, timeout=10, headers={"User-Agent": "DekaNewsResearch/1.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            feeds = []
            for tag in soup.find_all("link", href=True):
                if "alternate" in tag.get("rel", []) and tag.get("type", "").lower() in ("application/rss+xml", "application/atom+xml"):
                    url = urljoin(r.url, tag["href"])
                    if urlparse(url).hostname == urlparse(r.url).hostname:
                        feeds.append(url)
            for url in feeds[:2]:
                fr = requests.get(url, timeout=10)
                fr.raise_for_status()
                for entry in feedparser.parse(fr.content).entries[:20]:
                    title = BeautifulSoup(entry.get("title", ""), "html.parser").get_text(" ", strip=True)
                    summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)
                    link = entry.get("link", "")
                    if not title or not link or not any(k in (title + " " + summary).lower() for k in keywords):
                        continue
                    if urlparse(link).hostname != urlparse(r.url).hostname:
                        continue
                    identity = hashlib.sha256((title.lower() + "|" + link).encode()).hexdigest()
                    found[identity] = {"id": identity, "category": category, "source": urlparse(homepage).hostname,
                        "title": title, "link": link, "published": entry.get("published", "Waktu tidak tersedia"),
                        "summary": summary[:300]}
        except Exception as exc:
            print(f"Publisher feed skipped ({category}): {exc}")
    return list(found.values())

def ai_summary(item):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return ""
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = ("Ringkas secara netral dalam bahasa Indonesia maksimal dua kalimat berdasarkan judul dan "
              "cuplikan berikut saja. Jangan mengarang fakta atau mengaku telah membaca artikel lengkap. "
              "Jika informasi terbatas, sebutkan itu.\nJudul: " + item["title"] + "\nCuplikan: " + item["summary"])
    try:
        r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 220}},
            timeout=20)
        r.raise_for_status()
        parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return " ".join(p.get("text", "") for p in parts).strip()[:550]
    except Exception as exc:
        print(f"AI summary skipped: {exc}")
        return ""
