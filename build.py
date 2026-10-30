#!/usr/bin/env python3
"""data/items.json から静的HTML(site/index.html)を生成する。

- カテゴリ別のタブ、日付順
- キーワードに一致した記事を強調表示
- ダークモード(OS設定に追従 + 手動切替、選択はブラウザに保存)
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "items.json"
FEEDS_FILE = ROOT / "feeds.yaml"
OUT_DIR = ROOT / "site"
JST = timezone(timedelta(hours=9))

PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Feed Hub</title>
<script>
  // 描画前にテーマを適用してチラつきを防ぐ
  try {{
    var t = localStorage.getItem("theme");
    if (t) document.documentElement.setAttribute("data-theme", t);
  }} catch (e) {{}}
</script>
<style>
  :root {{
    --bg: #f7f7f5; --card: #ffffff; --text: #1f2328; --muted: #656d76;
    --border: #d8dee4; --accent: #0969da; --hl-bg: #fff3cd; --hl-bd: #e0a800;
    --new: #1a7f37;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #0d1117; --card: #161b22; --text: #e6edf3; --muted: #8b949e;
      --border: #30363d; --accent: #58a6ff; --hl-bg: #3a2f0b; --hl-bd: #bb8009;
      --new: #3fb950;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0d1117; --card: #161b22; --text: #e6edf3; --muted: #8b949e;
    --border: #30363d; --accent: #58a6ff; --hl-bg: #3a2f0b; --hl-bd: #bb8009;
    --new: #3fb950;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", "Segoe UI", sans-serif;
    line-height: 1.6;
  }}
  header, main {{ max-width: 860px; margin: 0 auto; padding: 0 16px; }}
  header {{ padding-top: 20px; }}
  .top {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; }}
  h1 {{ font-size: 1.3rem; margin: 0; }}
  .meta {{ color: var(--muted); font-size: .8rem; }}
  button {{
    background: var(--card); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 12px; cursor: pointer; font: inherit; font-size: .85rem;
  }}
  button:hover {{ border-color: var(--accent); }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 6px; }}
  .tabs button[aria-pressed="true"] {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .tools {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin: 8px 0 12px; }}
  .tools input[type=search] {{
    flex: 1; min-width: 160px; padding: 6px 10px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--card); color: var(--text); font: inherit; font-size: .9rem;
  }}
  .tools label {{ font-size: .85rem; color: var(--muted); display: flex; gap: 4px; align-items: center; }}
  h2 {{ font-size: .95rem; margin: 22px 0 8px; color: var(--muted); border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
  ul {{ list-style: none; margin: 0; padding: 0; }}
  li.item {{
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 14px; margin-bottom: 8px;
  }}
  li.item.hl {{ background: var(--hl-bg); border-color: var(--hl-bd); }}
  li.item a.title {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
  li.item a.title:hover {{ text-decoration: underline; }}
  li.item a.title:visited {{ color: var(--muted); }}
  .info {{ font-size: .75rem; color: var(--muted); margin-top: 2px; }}
  .badge {{ color: var(--new); font-weight: 700; margin-right: 4px; }}
  .sum {{ font-size: .85rem; margin-top: 4px; color: var(--muted); }}
  .hidden {{ display: none !important; }}
  details.err {{ margin: 28px 0; font-size: .8rem; color: var(--muted); }}
  footer {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 40px; color: var(--muted); font-size: .75rem; }}
</style>
</head>
<body>
<header>
  <div class="top">
    <h1>📡 Feed Hub</h1>
    <button id="theme" type="button" aria-label="テーマ切替">🌓 テーマ</button>
  </div>
  <div class="meta">最終更新: {updated} / 表示 {total} 件</div>
  <div class="tabs" id="tabs">{tabs}</div>
  <div class="tools">
    <input type="search" id="q" placeholder="タイトル・概要で絞り込み">
    <label><input type="checkbox" id="onlyhl"> 注目キーワードのみ</label>
  </div>
</header>
<main id="list">
{body}
{errors}
</main>
<footer>タイトル・リンク・概要のみを表示しています。詳細は各記事のリンク先をご覧ください。</footer>
<script>
(function () {{
  var root = document.documentElement;
  var btn = document.getElementById("theme");
  function current() {{
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }}
  btn.addEventListener("click", function () {{
    var next = current() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {{ localStorage.setItem("theme", next); }} catch (e) {{}}
  }});

  var cat = "all";
  var tabs = document.querySelectorAll("#tabs button");
  var q = document.getElementById("q");
  var onlyhl = document.getElementById("onlyhl");
  var items = document.querySelectorAll("li.item");
  var groups = document.querySelectorAll("section.day");

  function apply() {{
    var kw = q.value.trim().toLowerCase();
    items.forEach(function (li) {{
      var ok = (cat === "all" || li.dataset.cat === cat)
        && (!onlyhl.checked || li.classList.contains("hl"))
        && (!kw || li.dataset.text.indexOf(kw) !== -1);
      li.classList.toggle("hidden", !ok);
    }});
    groups.forEach(function (g) {{
      g.classList.toggle("hidden", !g.querySelector("li.item:not(.hidden)"));
    }});
  }}
  tabs.forEach(function (b) {{
    b.addEventListener("click", function () {{
      cat = b.dataset.cat;
      tabs.forEach(function (x) {{ x.setAttribute("aria-pressed", x === b ? "true" : "false"); }});
      apply();
    }});
  }});
  q.addEventListener("input", apply);
  onlyhl.addEventListener("change", apply);
}})();
</script>
</body>
</html>
"""


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def main() -> None:
    settings = yaml.safe_load(FEEDS_FILE.read_text(encoding="utf-8")).get("settings", {})
    keywords = [k for k in settings.get("highlight_keywords", []) if k]
    kw_re = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE) if keywords else None

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    items = data.get("items", [])
    now = datetime.now(JST)
    fetched_recent = now - timedelta(hours=24)

    # カテゴリ一覧(feeds.yaml の順序を優先)
    cats: list[str] = []
    for it in items:
        if it["category"] not in cats:
            cats.append(it["category"])

    tabs = ['<button type="button" data-cat="all" aria-pressed="true">すべて</button>']
    for c in cats:
        tabs.append(f'<button type="button" data-cat="{esc(c)}" aria-pressed="false">{esc(c)}</button>')

    # 日付ごとにグルーピング(JST)
    by_day: dict[str, list[dict]] = {}
    for it in items:
        day = datetime.fromisoformat(it["published"]).astimezone(JST).strftime("%Y-%m-%d (%a)")
        by_day.setdefault(day, []).append(it)

    parts: list[str] = []
    for day, day_items in by_day.items():
        parts.append(f'<section class="day"><h2>{esc(day)}</h2><ul>')
        for it in day_items:
            text = f'{it["title"]} {it["summary"]} {it["feed"]}'
            hl = bool(kw_re and kw_re.search(f'{it["title"]} {it["summary"]}'))
            is_new = datetime.fromisoformat(it["fetched"]) >= fetched_recent
            pub = datetime.fromisoformat(it["published"]).astimezone(JST).strftime("%H:%M")
            cls = "item hl" if hl else "item"
            badge = '<span class="badge">NEW</span>' if is_new else ""
            link = esc(it["link"]) if it["link"].startswith(("http://", "https://")) else "#"
            summary = f'<div class="sum">{esc(it["summary"])}</div>' if it["summary"] else ""
            parts.append(
                f'<li class="{cls}" data-cat="{esc(it["category"])}" data-text="{esc(text.lower())}">'
                f'<a class="title" href="{link}" target="_blank" rel="noopener noreferrer">{esc(it["title"])}</a>'
                f'<div class="info">{badge}{esc(it["feed"])} · {pub}</div>{summary}</li>'
            )
        parts.append("</ul></section>")

    failed = {n: s for n, s in data.get("status", {}).items() if not s.get("ok")}
    errors = ""
    if failed:
        rows = "".join(f"<li>{esc(n)}: {esc(s.get('error', ''))}</li>" for n, s in failed.items())
        errors = (
            f'<details class="err"><summary>取得に失敗したフィード ({len(failed)})</summary>'
            f"<ul>{rows}</ul><p>URLが変わった可能性があります。feeds.yaml を確認してください。</p></details>"
        )

    updated = datetime.fromisoformat(data["updated"]).astimezone(JST).strftime("%Y-%m-%d %H:%M JST")
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "index.html").write_text(
        PAGE.format(updated=updated, total=len(items), tabs="".join(tabs), body="\n".join(parts), errors=errors),
        encoding="utf-8",
    )
    print(f"生成: {OUT_DIR / 'index.html'} ({len(items)} 件)")


if __name__ == "__main__":
    main()
