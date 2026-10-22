"""Collect public scam write-ups from the Canadian Anti-Fraud Centre website.

Sources: the A-Z scam pages, plus the fraud features and news bulletins.
Each page is saved as one JSON document in data/docs/ with its URL, title,
date (when the URL has one) and plain text.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://antifraudcentre-centreantifraude.ca/"
INDEX_PAGES = [
    "scams-fraudes/azindex-eng.htm",
    "scams-fraudes/fraud-features-rubrique-fraude-eng.htm",
    "news-nouvelles/index-eng.htm",
]
SKIP = re.compile(r"index-eng|terms-avis|report-signalez|protect-protegez|about-ausujet|directory-annuaire|victim-victime")
HEADERS = {"User-Agent": "canadian-scam-intelligence/0.1 (student research project)"}

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"


def _get(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def find_page_urls() -> list[str]:
    urls = set()
    for page in INDEX_PAGES:
        page_url = urljoin(BASE, page)
        soup = BeautifulSoup(_get(page_url), "html.parser")
        for a in soup.select("main a[href]"):
            href = a["href"].split("#")[0]
            if href.endswith("-eng.htm") and not SKIP.search(href):
                urls.add(urljoin(page_url, href))
    return sorted(urls)


def _date_from_url(url: str) -> str | None:
    m = re.search(r"/(\d{4})-(\d{2})-(\d{2})-eng", url)
    if m:
        return "-".join(m.groups())
    m = re.search(r"/(\d{4})/(\d{2})/", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    m = re.search(r"/(\d{4})/", url)
    return f"{m.group(1)}-01-01" if m else None


def parse_page(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.body
    for tag in main.select("script, style, nav, .pagedetails, #wb-dtmd"):
        tag.decompose()
    title = (main.find("h1") or soup.title).get_text(" ", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    return {
        "id": re.sub(r"[^a-z0-9]+", "-", url.replace(BASE, "").lower()).strip("-"),
        "url": url,
        "title": title,
        "date": _date_from_url(url),
        "source": "Canadian Anti-Fraud Centre",
        "text": text,
    }


def collect(limit: int | None = None) -> list[Path]:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    urls = find_page_urls()[:limit]
    saved = []
    for url in urls:
        doc = parse_page(url, _get(url))
        path = DOCS_DIR / f"{doc['id']}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        saved.append(path)
        print(f"  saved {doc['title'][:70]}  ({len(doc['text'])} chars)")
        time.sleep(0.5)  # be polite to a government site
    return saved


def load_docs() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DOCS_DIR.glob("*.json"))]
