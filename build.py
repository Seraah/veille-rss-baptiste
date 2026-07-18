#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=int(CONFIG["days_back"]))
PARIS = ZoneInfo("Europe/Paris")

USER_AGENT = (
    "Mozilla/5.0 (compatible; BaptisteRSSDashboard/1.0; "
    "+https://github.com/)"
)

def clean_text(value: Any, limit: int | None = None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(str(value), "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text

def canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        clean_query = "&".join(
            part for part in parts.query.split("&")
            if part and not part.lower().startswith(
                ("utm_", "fbclid=", "gclid=", "mc_cid=", "mc_eid=")
            )
        )
        return urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), parts.path, clean_query, "")
        )
    except Exception:
        return url.strip()

def parsed_datetime(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(attr)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    for attr in ("published", "updated", "created"):
        value = entry.get(attr)
        if value:
            try:
                parsed = date_parser.parse(str(value))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except Exception:
                pass
    return None

def make_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml, application/atom+xml, application/xml, "
                "text/xml, application/json, text/html;q=0.8, */*;q=0.5"
            ),
        }
    )
    return session

def fetch_feed(row: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    category = row["category"].strip()
    source = row["source"].strip()
    url = row["url"].strip()
    started = time.monotonic()
    status: dict[str, Any] = {
        "category": category,
        "source": source,
        "url": url,
        "ok": False,
        "http_status": None,
        "entries_kept": 0,
        "error": "",
        "seconds": 0,
    }

    try:
        session = make_session()
        response = session.get(
            url,
            timeout=int(CONFIG["request_timeout_seconds"]),
            allow_redirects=True,
        )
        status["http_status"] = response.status_code
        response.raise_for_status()

        # Avoid accidentally downloading a huge response.
        if len(response.content) > 8_000_000:
            raise ValueError("Flux supérieur à 8 Mo")

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError(str(getattr(parsed, "bozo_exception", "Flux invalide")))

        articles: list[dict[str, Any]] = []
        for entry in parsed.entries[: int(CONFIG["max_entries_per_feed"])]:
            title = clean_text(entry.get("title"))
            link = canonical_url(entry.get("link", ""))
            if not title or not link:
                continue

            published_dt = parsed_datetime(entry)
            if published_dt and published_dt < CUTOFF:
                continue

            summary = (
                entry.get("summary")
                or entry.get("description")
                or entry.get("content", [{}])[0].get("value", "")
            )
            summary = clean_text(summary, int(CONFIG["summary_max_chars"]))
            author = clean_text(entry.get("author"))
            unique = hashlib.sha256(
                (link or f"{source}|{title}").encode("utf-8")
            ).hexdigest()[:20]

            articles.append(
                {
                    "id": unique,
                    "category": category,
                    "source": source,
                    "feed_url": url,
                    "title": title,
                    "link": link,
                    "author": author,
                    "summary": summary,
                    "published": published_dt.isoformat() if published_dt else None,
                    "published_paris": (
                        published_dt.astimezone(PARIS).strftime("%d/%m/%Y %H:%M")
                        if published_dt
                        else "Date inconnue"
                    ),
                }
            )

        status["ok"] = True
        status["entries_kept"] = len(articles)
        return articles, status
    except Exception as exc:
        status["error"] = clean_text(str(exc), 300)
        return [], status
    finally:
        status["seconds"] = round(time.monotonic() - started, 2)

def write_opml(rows: list[dict[str, str]]) -> None:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["category"], []).append(row)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "  <head>",
        "    <title>La Veille RSS de Baptiste</title>",
        "  </head>",
        "  <body>",
    ]
    for category, category_rows in grouped.items():
        lines.append(f'    <outline text="{html.escape(category, quote=True)}">')
        for row in category_rows:
            lines.append(
                '      <outline type="rss" '
                f'text="{html.escape(row["source"], quote=True)}" '
                f'title="{html.escape(row["source"], quote=True)}" '
                f'xmlUrl="{html.escape(row["url"], quote=True)}" />'
            )
        lines.append("    </outline>")
    lines.extend(["  </body>", "</opml>"])
    (SITE / "feeds.opml").write_text("\n".join(lines), encoding="utf-8")

def main() -> None:
    with (ROOT / "feeds.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    all_articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=int(CONFIG["max_workers"])) as executor:
        futures = {executor.submit(fetch_feed, row): row for row in rows}
        for future in as_completed(futures):
            articles, status = future.result()
            all_articles.extend(articles)
            statuses.append(status)

    # Deduplicate articles by canonical URL, keeping the article with the best metadata.
    deduped: dict[str, dict[str, Any]] = {}
    for article in all_articles:
        key = article["link"] or f'{article["source"]}|{article["title"]}'
        previous = deduped.get(key)
        if previous is None or len(article.get("summary", "")) > len(previous.get("summary", "")):
            deduped[key] = article

    articles = list(deduped.values())
    articles.sort(
        key=lambda item: item["published"] or "0000-00-00T00:00:00+00:00",
        reverse=True,
    )
    articles = articles[: int(CONFIG["max_total_articles"])]

    statuses.sort(key=lambda item: (not item["ok"], item["category"], item["source"]))
    build_paris = NOW.astimezone(PARIS)

    payload = {
        "generated_at": NOW.isoformat(),
        "generated_at_paris": build_paris.strftime("%d/%m/%Y à %H:%M"),
        "article_count": len(articles),
        "feed_count": len(rows),
        "articles": articles,
    }
    health = {
        "generated_at": NOW.isoformat(),
        "generated_at_paris": build_paris.strftime("%d/%m/%Y à %H:%M"),
        "feeds_total": len(statuses),
        "feeds_ok": sum(1 for item in statuses if item["ok"]),
        "feeds_failed": sum(1 for item in statuses if not item["ok"]),
        "statuses": statuses,
    }

    (SITE / "articles.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (SITE / "status.json").write_text(
        json.dumps(health, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_opml(rows)

    template = (ROOT / "index.template.html").read_text(encoding="utf-8")
    template = template.replace("__SITE_TITLE__", html.escape(CONFIG["site_title"]))
    (SITE / "index.html").write_text(template, encoding="utf-8")
    (SITE / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n",
        encoding="utf-8",
    )
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    print(
        f"Generated {len(articles)} articles from "
        f"{health['feeds_ok']}/{health['feeds_total']} working feeds."
    )

if __name__ == "__main__":
    main()
