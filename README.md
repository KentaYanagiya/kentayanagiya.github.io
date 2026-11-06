# kentayanagiya.github.io

個人Webサイト。研究業績は [`data/publications.json`](data/publications.json) で一元管理し、PythonでHTMLを生成します。Python 3.10以上を使用します。追加ライブラリやAPIキーは不要です。

## 普段の更新

### DOIから論文を追加する

`10.xxxx/xxxxx` を実際のDOIに置き換えます。最初に、保存せず取得内容を確認できます。

```sh
python3 scripts/publications.py add-doi 'https://doi.org/10.xxxx/xxxxx' --dry-run
```

確認後、`--dry-run` を外すと業績データと `index.html` の両方を更新します。

```sh
python3 scripts/publications.py add-doi '10.xxxx/xxxxx'
```

- Crossrefから著者、題名、掲載先、出版年月、巻号、ページ、DOIを取得します。取得項目は登録状況に依存します。
- 雑誌論文と会議論文は区分を自動判定します。国内会議などは `--category domestic`、国際会議は `--category international_conference`、雑誌論文は `--category journal` で指定できます。
- 著者順は取得した内容を使用します。英語タイトルは取り込み時とHTML生成時に各単語の先頭を大文字にし、前置詞は位置によらず小文字に統一します。著者名の略記、開催地、発表年月などは必要に応じてデータを修正してください。
- 出版年月は冊子版、オンライン版、その他の出版日の順に採用します。会議の開催日とは異なる場合があります。年のみ判明している場合は年のみ保存します。
- 同じDOI、または同じ区分・題名の登録を検出して停止します。CrossrefにないDOIや必須情報が欠ける場合は、データを手動で追加してください。
- IDを指定する場合は `--id yanagiya-2026-example`、問い合わせ元を示す場合は `--email your-address@example.com` を付けます。

取得元: [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)

### 投稿中の論文を出版済みに更新する

既存項目の `id` を指定します。項目を増やさず、同じIDのまま書誌情報を更新して雑誌論文などの欄へ移動します。

```sh
python3 scripts/publications.py add-doi '10.xxxx/xxxxx' --update yanagiya-transform-coding --dry-run
python3 scripts/publications.py add-doi '10.xxxx/xxxxx' --update yanagiya-transform-coding
```

採択時点でDOIがなければ、JSONの `status` を `accepted` に変え、`venue` を追加します。掲載誌の欄に「採択済み / accepted」と表示されます。年月が未定なら `date` は省略できます。

### DOIのない発表を追加する／既存業績を修正する

`data/publications.json` の配列に、次のような項目を追加・編集します。最後の項目以外には項目間のカンマが必要です。

```json
{
  "id": "yanagiya-2026-example",
  "category": "domestic",
  "status": "published",
  "language": "ja",
  "authors": ["栁谷健太", "共著者名"],
  "title": "発表題目",
  "venue": "研究会名",
  "date": "2026-11",
  "location": "開催地"
}
```

| 項目 | 指定する内容 |
| --- | --- |
| `id` | 重複しない英小文字・数字・ハイフン。掲載状況が変わっても維持する |
| `category` | `journal` / `international_conference` / `domestic` |
| `status` | `under_review`（投稿中）/ `accepted`（採択済み）/ `published`（出版・発表済み） |
| `language` | 書誌情報の日付・著者区切りの表記: `ja` / `en`。サイトの表示言語とは独立 |
| `authors` | 掲載順の著者名の配列 |
| `title` | 題名。引用符や末尾の句読点は不要 |
| `venue` | 雑誌・会議・研究会名。投稿中のみ省略可能 |
| `date` | `2026` / `2026-11` / `2026-11-06`。投稿中・採択済みは省略可能 |
| 任意項目 | `volume`, `issue`, `pages`, `article_number`, `report_number`, `location`, `doi` |

数値の巻号も `"volume": "11"` のように文字列で指定します。不明な任意項目は省略します。投稿中は業績区分によらず投稿中欄へまとめ、それ以外は区分別・年月の新しい順に表示します。年月が同じ項目はデータ内の順序を維持します。

英語タイトルは `Time-Varying Edge Removal Scheduling for Network-based Epidemic Control` のように表示します。`of`・`on`・`for`・`with`・`by` などの前置詞は小文字、`Time-Varying` は両語の先頭を大文字、`-based` と `Non-local` の後半は小文字にします。略語や固有の綴り（`IEEE`、`GraphSAGE` など）を保持します。日本語を含むタイトル、著者名、雑誌・会議名はこの変換の対象外です。国内発表でもタイトル全体が英語なら適用します。

国際会議論文は `“Title,” in Proc. Conference Name, ...` の形式で表示します。`venue` には `Proc. ...` などの掲載先名だけを入力し、`in` は生成処理で補います。英語の書誌情報では題名の直後のカンマを閉じ引用符の内側に置きます。

書誌情報のフォント、サイズ、太さ、色、行間は全項目で統一し、題名の太字や掲載先の斜体は使用しません。著者名の `K. Yanagiya`、`栁谷健太`、`柳谷健太` にだけ下線を付けます。DOIから取得するフルネームの `Kenta Yanagiya` も同じ対象です。下線はHTML生成時に付けるため、JSONの著者名に装飾を入力する必要はありません。

ローカルでJSONを編集した後は、次のコマンドでHTMLを更新・確認します。

```sh
python3 scripts/publications.py build
python3 scripts/publications.py check
```

`index.html` の `PUBLICATIONS:START` と `PUBLICATIONS:END` の間は生成領域です。業績の修正はJSONで行ってください。その他のプロフィール・受賞・特許などは引き続きHTMLで編集できます。既存の12件は元の掲載情報を移行しており、新しいDOIや掲載状況を推測で補完していません。

## GitHub Pagesで自動生成・公開する

`.github/workflows/pages.yml` は、`main` へのpush時にテストとサイト生成を行い、GitHub Pagesへ公開します。プルリクエストではテストと生成だけを実行します。

初回のみ、変更をGitHubへpushした後、リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** に設定します。必要なら **Actions → Build and deploy website → Run workflow** で実行します。公開元がまだブランチ設定の場合は、この設定切り替えが必要です。

以後はGitHub上でJSONだけを編集しても、公開時にHTMLを再生成します。Actionsで生成したHTMLは公開用成果物に入り、リポジトリには書き戻しません。ローカルの `index.html` を最新にしたい場合は `build` を実行してください。

GitHubへ反映するときは、変更した `data/publications.json` と、ローカルで生成した場合は `index.html` をコミットしてpushします。初回はスクリプトとワークフローなどの追加ファイルも含めてください。

参考: [GitHub Pagesのカスタムワークフロー](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## 動作確認とプレビュー

```sh
python3 -m unittest discover -s tests -v
python3 scripts/publications.py build --output _site
python3 -m http.server 8000 --directory _site
```

ブラウザで `http://localhost:8000` を開きます。`_site` には公開に必要なHTML・CSS・JavaScript・画像だけを出力します。閲覧時にCrossrefへの通信やPythonの実行は発生しません。生成済みHTMLなのでJavaScriptを無効にしても業績本文を読めます。
