# Feed Hub

セキュリティ・ブラウザ・開発ニュースを1ページに集約する、自分用の情報集積所です。
RSS/Atomを毎朝自動取得し、静的HTMLにして GitHub Pages で公開します。

```
feeds.yaml ──> fetch.py ──> data/items.json ──> build.py ──> site/index.html ──> GitHub Pages
 (購読リスト)   (取得・重複除外)   (蓄積データ)      (HTML生成)
```

## サイトを追加する

`feeds.yaml` の `feeds:` に1ブロック足すだけです。

```yaml
  - name: 表示名
    url: https://example.com/feed.xml
    category: セキュリティ(国内)   # 好きなグループ名でOK
```

- GitHubリポジトリの新リリースは `https://github.com/<owner>/<repo>/releases.atom` で購読できます。
- サイトのRSSのURLが分からない場合は、ページのソースで `rel="alternate"` を探すか、`/feed` `/rss` `/atom.xml` を試してください。
- 注目キーワードは `settings.highlight_keywords` で変更できます(一致した記事が黄色系で強調されます)。

## ローカルで試す

```bash
pip install -r requirements.txt
python fetch.py     # data/items.json を更新
python build.py     # site/index.html を生成
open site/index.html   # Windowsは start、Linuxは xdg-open
```

## GitHubで自動更新する(初回のみ)

1. このフォルダをGitHubの新しいリポジトリにpushします(ブランチ名は `main`)。
2. リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にします。
3. **Actions タブ → Update feeds → Run workflow** で初回実行します。
4. 以後は毎朝 7:00(JST)に自動更新されます。公開URLは Settings → Pages に表示されます。

> 無料プランのリポジトリでPagesを使う場合、公開リポジトリだとページも誰でも見られます。
> 非公開にしたい場合は、Pagesのアクセス制御が使えるプランか、ローカル実行+手元でHTMLを開く運用にしてください。

## 仕様メモ

- 保存するのはタイトル・リンク・短い概要(200字まで)だけで、記事本文は保存しません。
- 取得に失敗したフィードは画面下部に表示されます(URL変更の検知用)。他のフィードは止まりません。
- 記事は `keep_days`(既定30日)を過ぎると自動で削除されます。
- テーマはOSの設定に追従し、右上のボタンで手動切替もできます。
