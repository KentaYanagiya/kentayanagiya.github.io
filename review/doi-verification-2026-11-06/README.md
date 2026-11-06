# DOIからの業績追加の実証確認

確認日: 2026-11-06（日本時間）

## 結果

国際会議5件のうち、ICASSP 2022・ICASSP 2024・MLSP 2024の3件は区分指定なしで追加に成功しました。SSSも取得できますが、国際会議として扱うには区分指定が必要です。ASPIRE WorkshopはDOIが存在する一方、現行のCrossref取得処理では追加できませんでした。参考として、掲載済みのTSIPN雑誌論文も実際の追加に成功しました。

| 対象 | 論文DOI | 現行コマンドの結果 |
| --- | --- | --- |
| SSS（2025年11月開催） | `10.5687/sss.2026.96` | 取得・保存・HTML生成に成功。ただし自動判定は `journal`。`--category international_conference` による区分指定もプレビューで確認済み |
| ICASSP 2022 | `10.1109/ICASSP43922.2022.9747724` | 国際会議として取得・保存・HTML生成に成功 |
| ICASSP 2024 | `10.1109/ICASSP48485.2024.10448045` | 国際会議として取得・保存・HTML生成に成功 |
| ASPIRE Workshop 2024 | `10.34385/proc.80.P-16` | CrossrefからHTTP 404。現行処理では追加不可 |
| MLSP 2024 | `10.1109/MLSP58920.2024.10734767` | 国際会議として取得・保存・HTML生成に成功 |
| IEEE TSIPN 2025（雑誌論文） | `10.1109/TSIPN.2025.3639969` | 雑誌論文として取得・保存・HTML生成に成功 |

ASPIREについては、DOIがないという意味ではありません。[IEICEの公式掲載ページ](https://www.ieice.org/publications/proceedings/summary.php?expandable=4&iconf=ASPIRE_WS&number=P-16&session_num=P&year=2024) にDOIが明記されています。対応するにはCrossref以外からの取得処理を追加するか、公式ページの情報をJSONへ手動入力する必要があります。

## 検証方法と保存した記録

- リポジトリのスクリプトとHTMLを一時ディレクトリへコピーし、業績データを空配列にした上で、実際の `add-doi DOI` コマンドを実行しました。
- 成功した5件はJSONへの保存、HTMLへの反映、`check` コマンドの成功まで確認しました。
- SSSについては、追加した項目に `--category international_conference --update ID --dry-run` を指定し、区分が国際会議になることも確認しました。
- 元の `data/publications.json`、`index.html`、`scripts/publications.py`、`style.css` はハッシュで変更がないことを確認しました。実サイトへの追加・更新・公開は行っていません。
- 実行結果と取得した書誌項目は [results.json](results.json) に記録しています。
- 検証中、Crossrefから一部HTTP 429（アクセス制限）が返りました。ASPIREは再試行でHTTP 404と判明しました。ICASSP 2024は最初の追加・生成には成功していますが、その後の重複検出テストはHTTP 429のため未確認です。

## 既存項目を更新する場合のコマンド

現在の業績一覧にはすでに同じ論文があるため、新規追加ではなく `--update ID` を使用します。以下は内容確認だけを行い、保存しないコマンドです。この確認作業では、これらのコマンドによる元データの更新は実施していません。

```sh
python3 scripts/publications.py add-doi '10.5687/sss.2026.96' --update yanagiya-2025-sssa --category international_conference --dry-run
python3 scripts/publications.py add-doi '10.1109/ICASSP43922.2022.9747724' --update yanagiya-2022-icassp --dry-run
python3 scripts/publications.py add-doi '10.1109/ICASSP48485.2024.10448045' --update yanagiya-2024-icassp --dry-run
python3 scripts/publications.py add-doi '10.1109/MLSP58920.2024.10734767' --update kaneko-2024-mlsp --dry-run
python3 scripts/publications.py add-doi '10.1109/TSIPN.2025.3639969' --update yanagiya-2025-edge-sampling --dry-run
```

プレビューを確認して `--dry-run` を外すと保存されます。`--update` の対象に既存の区分がある場合、その区分が引き継がれるため、SSSの上記コマンドでの `--category` は明示用です。SSSを空のデータへ新規追加する場合は、必ず `--category international_conference` を指定します。区分が違うと、現在の「同一区分・同一題名」の重複検出では既存項目を見逃すことが実証確認されました。

## 取り込み時の表記の違い

- 著者名は `K. Yanagiya` のような略記から `Kenta Yanagiya` のようなフルネームになります。フルネームも下線の対象です。
- 会議名はCrossrefの正式名称で取得されます。現在手入力されている `Proc. IEEE International Conference ...` という略記への変換は行いません。国際会議の欄では生成時に `in` が付与されます。
- 新規追加では開催地を取得しません。既存項目の更新では登録済みの開催地が引き継がれます。
- SSSはDOIと巻番号が `2026` ですが、取得された出版日は `2025-11-05` です。既存の `2025-11` と年・月は一致しています。[J-STAGEの公式掲載ページ](https://www.jstage.jst.go.jp/article/sss/2026/0/2026_96/_article/-char/en)
- 取得されたページはICASSP 2022が `5932-5936`、ICASSP 2024が `9386-9390`、MLSP 2024が `1-6` でした。

## DOIの照合先

- SSS: [J-STAGE公式掲載ページ](https://www.jstage.jst.go.jp/article/sss/2026/0/2026_96/_article/-char/en)
- ICASSP 2022: [著者の研究室の業績一覧](https://www.msp-lab.org/publications)、Crossrefから取得した題名・著者・会議名・ページ
- ICASSP 2024: [著者が公開したarXiv論文](https://arxiv.org/abs/2402.02884) の題名・著者、Crossrefから取得した対応する会議論文DOI・題名・著者・ページ
- ASPIRE: [IEICE公式掲載ページ](https://www.ieice.org/publications/proceedings/summary.php?expandable=4&iconf=ASPIRE_WS&number=P-16&session_num=P&year=2024)
- MLSP 2024: [著者が公開したarXiv論文](https://arxiv.org/abs/2411.08371) の関連DOI、Crossrefから取得した題名・著者・会議名・ページ
- IEEE TSIPN: [大阪大学の機関リポジトリ](https://ir.library.osaka-u.ac.jp/repo/ouka/all/104057/)、Crossrefから取得した題名・著者・掲載誌・ページ
