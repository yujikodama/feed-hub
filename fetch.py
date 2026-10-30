#!/usr/bin/env python3
"""feeds.yaml に書かれたRSS/Atomを取得し、data/items.json に新着を蓄積する。

保存するのはタイトル・リンク・短い概要のみ(記事本文は保存しない)。
取得に失敗したフィードがあっても、他のフィードの処理は続行する。
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import yaml

ROOT = Path(__file__).parent
FEEDS_FILE = ROOT / "feeds.yaml"
DATA_FILE = ROOT / "data" / "items.json"
USER_AGENT = "feed-hub/1.0 (personal feed aggregator)"
SUMMARY_MAX = 200

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean_summary(raw: str) -> str:
    """HTMLタグを除去し、短く切り詰める。"""
    text = html.unescape(TAG_RE.sub(" ", raw or ""))
    text = SPACE_RE.sub(" ", text).strip()
    if len(text) > SUMMARY_MAX:
        text = text[: SUMMARY_MAX - 1].rstrip() + "…"
    return text


def entry_time(entry) -> datetime:
    """記事の日時(UTC)。取得できなければ現在時刻。"""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return datetime.now(timezone.utc)


def item_id(feed_name: str, link: str, title: str) -> str:
    return hashlib.sha1(f"{feed_name}|{link or title}".encode("utf-8")).hexdigest()


def load_items() -> dict[str, dict]:
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return {it["id"]: it for it in data.get("items", [])}
    return {}


def main() -> int:
    config = yaml.safe_load(FEEDS_FILE.read_text(encoding="utf-8"))
    settings = config.get("settings", {})
    keep_days = int(settings.get("keep_days", 30))
    per_feed = int(settings.get("max_items_per_feed", 30))

    items = load_items()
    now = datetime.now(timezone.utc)
    new_count = 0
    errors: list[str] = []
    status: dict[str, dict] = {}

    for feed in config.get("feeds", []):
        name, url = feed["name"], feed["url"]
        category = feed.get("category", "その他")
        parsed = feedparser.parse(url, agent=USER_AGENT)

        # 取得できなかった(エントリ0件かつ例外あり)場合は記録して次へ
        if not parsed.entries and parsed.get("bozo"):
            msg = f"{name}: {parsed.get('bozo_exception', '取得失敗')}"
            errors.append(msg)
            status[name] = {"ok": False, "error": str(parsed.get("bozo_exception", ""))}
            print(f"[NG] {msg}", file=sys.stderr)
            continue

        added = 0
        for entry in parsed.entries[:per_feed]:
            link = entry.get("link", "")
            title = SPACE_RE.sub(" ", entry.get("title", "")).strip() or "(タイトルなし)"
            iid = item_id(name, link, title)
            if iid in items:
                continue
            items[iid] = {
                "id": iid,
                "feed": name,
                "category": category,
                "title": title,
                "link": link,
                "summary": clean_summary(entry.get("summary", "")),
                "published": entry_time(entry).isoformat(),
                "fetched": now.isoformat(),
            }
            added += 1
        new_count += added
        status[name] = {"ok": True, "added": added}
        print(f"[OK] {name}: +{added}")

    # 古い記事を削除
    cutoff = now - timedelta(days=keep_days)
    items = {
        k: v for k, v in items.items()
        if datetime.fromisoformat(v["published"]) >= cutoff
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "updated": now.isoformat(),
        "status": status,
        "items": sorted(items.values(), key=lambda x: x["published"], reverse=True),
    }
    DATA_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n新着 {new_count} 件 / 保持 {len(items)} 件 / 失敗 {len(errors)} フィード")
    return 0


if __name__ == "__main__":
    sys.exit(main())
