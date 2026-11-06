#!/usr/bin/env python3
"""Maintain the publication list using Python's standard library only."""

import argparse
import calendar
from datetime import date
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/publications.json"
INDEX = ROOT / "index.html"
START = "      <!-- PUBLICATIONS:START -->"
END = "      <!-- PUBLICATIONS:END -->"
CATEGORIES = ("journal", "international_conference", "domestic")
STATUSES = ("published", "accepted", "under_review")
FIELDS = {
    "id", "category", "status", "language", "authors", "title", "venue", "date",
    "volume", "issue", "pages", "article_number", "report_number", "location", "doi",
}
GROUPS = (
    ("journal", "Journal Papers", "雑誌論文"),
    ("under_review", "Under Review", "投稿中"),
    ("international_conference", "International Conferences", "国際会議"),
    ("domestic", "Domestic Presentations", "国内研究会"),
)
PREPOSITIONS = frozenset("""
    aboard about above across after against along amid amidst among amongst around
    as at before behind below beneath beside besides between beyond but by
    concerning considering despite down during except excluding following for
    from in including inside into like near notwithstanding of off on onto
    opposite outside over past per regarding round since through throughout
    till to toward towards under underneath unlike until unto up upon versus
    via with within without
""".split())


def format_title(title):
    """Capitalize English titles, retaining prepositions and compound suffixes."""
    # Domestic records can contain fully English titles; do not use record language.
    if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", title):
        return title

    def capitalize_word(word):
        if word.lower() in PREPOSITIONS:
            return word.lower()
        # Preserve scientific abbreviations and names such as IEEE and GraphSAGE.
        if (word.isupper() and len(word) > 1) or any(char.isupper() for char in word[1:]):
            return word
        return word[0].upper() + word[1:].lower()

    def capitalize_compound(match):
        word = match.group()
        parts = re.split(r"([-‑])", word)
        for i in range(0, len(parts), 2):
            # Examples: Time-Varying, Network-based, Non-local.
            if i and (parts[i].lower() == "based" or parts[0].lower() == "non"):
                parts[i] = parts[i].lower()
            else:
                parts[i] = capitalize_word(parts[i])
        return "".join(parts)

    return re.sub(r"[A-Za-z]+(?:['’][A-Za-z]+)*(?:[-‑][A-Za-z]+(?:['’][A-Za-z]+)*)*",
                  capitalize_compound, title)


def normalize_doi(value):
    value = value.strip()
    if value.lower().startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.netloc.lower() not in ("doi.org", "dx.doi.org"):
            raise ValueError("DOI URLには doi.org を指定してください。")
        value = unquote(parsed.path.lstrip("/"))
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    if not re.fullmatch(r"10\.\d{4,9}/[^\s\x00-\x1f]+", value):
        raise ValueError("DOIは 10.xxxx/... または https://doi.org/... で指定してください。")
    return value.lower()


def date_parts(value):
    if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
        raise ValueError(f"日付は YYYY / YYYY-MM / YYYY-MM-DD で指定してください: {value}")
    parts = [int(part) for part in value.split("-")]
    date(*(parts + [1] * (3 - len(parts))))
    return parts


def validate(records):
    if not isinstance(records, list):
        raise ValueError("業績データの最上位は配列にしてください。")
    ids, dois = set(), set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("各業績はオブジェクトにしてください。")
        label = item.get("id", "(IDなし)")
        unknown = item.keys() - FIELDS
        if unknown:
            raise ValueError(f"{label}: 未対応の項目: {', '.join(sorted(unknown))}")
        for field, value in item.items():
            if field != "authors" and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{label}: {field} は空でない文字列にしてください。")
        for field in ("id", "category", "status", "language", "title"):
            if field not in item:
                raise ValueError(f"{label}: {field} が必要です。")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", item["id"]):
            raise ValueError(f"{label}: IDには英小文字・数字・ハイフンを使用してください。")
        if item["id"] in ids:
            raise ValueError(f"IDが重複しています: {label}")
        ids.add(item["id"])
        if item["category"] not in CATEGORIES or item["status"] not in STATUSES:
            raise ValueError(f"{label}: category または status が未対応です。")
        if item["language"] not in ("ja", "en"):
            raise ValueError(f"{label}: language は ja / en で指定してください。")
        authors = item.get("authors")
        if not isinstance(authors, list) or not authors or any(
            not isinstance(author, str) or not author.strip() for author in authors
        ):
            raise ValueError(f"{label}: authors は空でない著者名の配列にしてください。")
        if item["status"] != "under_review" and not item.get("venue"):
            raise ValueError(f"{label}: venue が必要です。")
        if item["status"] == "published" and not item.get("date"):
            raise ValueError(f"{label}: 出版済みの業績には date が必要です。")
        if "date" in item:
            date_parts(item["date"])
        if "doi" in item:
            doi = normalize_doi(item["doi"])
            if doi in dois:
                raise ValueError(f"DOIが重複しています: {doi}")
            dois.add(doi)
    return records


def load_records(path=DATA):
    return validate(json.loads(path.read_text(encoding="utf-8")))


def format_date(value, language):
    parts = date_parts(value)
    if language == "ja":
        return f"{parts[0]}年" + (f"{parts[1]}月" if len(parts) > 1 else "") + (
            f"{parts[2]}日" if len(parts) > 2 else ""
        )
    if len(parts) == 1:
        return str(parts[0])
    month = calendar.month_abbr[parts[1]] + ("" if parts[1] == 5 else ".")
    return f"{month} {parts[0]}" if len(parts) == 2 else f"{month} {parts[2]}, {parts[0]}"


def render_item(item):
    ja = item["language"] == "ja"
    separator = "，" if ja else ", "
    authors = item["authors"]
    if ja or len(authors) == 1:
        author_text = separator.join(authors)
    elif len(authors) == 2:
        author_text = " and ".join(authors)
    else:
        author_text = ", ".join(authors[:-1]) + ", and " + authors[-1]
    title_end = "”" if ja else ",”"
    introduction = (f'<span class="authors">{escape(author_text)}</span>{separator}'
                    f'<span class="title">“{escape(format_title(item["title"]))}{title_end}</span>')
    pieces = []
    if item.get("venue"):
        venue = item["venue"]
        prefix = ""
        if item["category"] == "international_conference":
            prefix = "in "
            venue = re.sub(r"^in\s+", "", venue, flags=re.IGNORECASE)
        pieces.append(f'{prefix}<span class="venue">{escape(venue)}</span>')
    if item.get("location") and not ja:
        pieces.append(escape(item["location"]))
    for field, prefix in (("volume", "vol. "), ("issue", "no. "),
                          ("report_number", ""), ("pages", "pp. "),
                          ("article_number", "Art. no. ")):
        if field in item:
            pieces.append(prefix + escape(item[field]))
    if item.get("location") and ja:
        pieces.append(escape(item["location"]))
    if item.get("date"):
        pieces.append(format_date(item["date"], item["language"]))
    if item["status"] != "published":
        en, jp = ("accepted", "採択済み") if item["status"] == "accepted" else ("under review", "投稿中")
        pieces.append(f'<span class="en">{en}</span><span class="ja">{jp}</span>')
    citation = introduction + (separator if ja else " ") + separator.join(pieces) + "."
    if item.get("doi"):
        url = "https://doi.org/" + quote(normalize_doi(item["doi"]), safe="/")
        citation += f' <a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">DOI</a>'
    return f'          <li id="{item["id"]}" lang="{item["language"]}">{citation}</li>'


def render(records):
    blocks = []
    for group, en, ja in GROUPS:
        items = [item for item in records if (
            "under_review" if item["status"] == "under_review" else item["category"]
        ) == group]
        if not items:
            continue
        items.sort(key=lambda item: item.get("date", ""), reverse=True)
        list_class = "publication-list ja-list" if group == "domestic" else "publication-list"
        blocks.append("\n".join([
            '      <div class="publication-group">',
            f'        <h3><span class="en">{en}</span><span class="ja">{ja}</span></h3>',
            f'        <ol class="{list_class}">',
            *(render_item(item) for item in items),
            '        </ol>',
            '      </div>',
        ]))
    return "\n\n".join(blocks)


def build_html(records, source):
    validate(records)
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("index.html の PUBLICATIONS マーカーが見つからないか重複しています。")
    before, rest = source.split(START)
    _, after = rest.split(END)
    return before + START + "\n" + render(records) + "\n" + END + after


def atomic_write(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []

    def handle_data(self, data):
        self.chunks.append(data)


def plain_text(value):
    parser = PlainText()
    parser.feed(str(value))
    return " ".join("".join(parser.chunks).split())


def first_text(value):
    if isinstance(value, list):
        value = value[0] if value else ""
    return plain_text(value) if value else ""


def fetch_metadata(doi, email=None):
    agent = "KentaYanagiya-publications/1.0"
    if email:
        agent += f" (mailto:{email})"
    request = Request("https://api.crossref.org/works/" + quote(doi, safe=""), headers={
        "Accept": "application/json", "User-Agent": agent,
    })
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise ValueError("CrossrefにDOIが見つかりません。未登録の業績はJSONへ手動で追加できます。") from error
        raise ValueError(f"Crossrefへの接続に失敗しました (HTTP {error.code})。再試行してください。") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(f"Crossrefに接続できません: {error}") from error
    if not isinstance(result, dict) or result.get("status") != "ok" or not isinstance(result.get("message"), dict):
        raise ValueError("Crossrefから有効な書誌情報を取得できませんでした。")
    return result["message"]


def record_from_metadata(metadata, doi, category=None, record_id=None):
    inferred = {"journal-article": "journal", "proceedings-article": "international_conference"}
    category = category or inferred.get(metadata.get("type"))
    if not category:
        raise ValueError("業績区分を判定できません。--category を指定してください。")
    returned_doi = normalize_doi(metadata.get("DOI", ""))
    if returned_doi != doi:
        raise ValueError("取得結果のDOIが指定されたDOIと一致しません。")
    authors = []
    for author in metadata.get("author", []):
        name = " ".join(filter(None, [plain_text(author.get("given", "")),
                                      plain_text(author.get("family", ""))]))
        authors.append(name or plain_text(author.get("name", "")))
    record = {
        "id": record_id or "doi-" + re.sub(r"[^a-z0-9]+", "-", doi).strip("-"),
        "category": category,
        "status": "published",
        "language": "ja" if metadata.get("language", "").startswith("ja") else "en",
        "authors": authors,
        "title": format_title(first_text(metadata.get("title"))),
        "venue": first_text(metadata.get("container-title")),
        "doi": doi,
    }
    for key in ("published-print", "published-online", "published", "issued"):
        parts = metadata.get(key, {}).get("date-parts", [[]])[0]
        if parts:
            candidate = "-".join(f"{part:04d}" if i == 0 else f"{part:02d}"
                                 for i, part in enumerate(parts))
            date_parts(candidate)
            record["date"] = candidate
            break
    for source, target in (("volume", "volume"), ("issue", "issue"),
                           ("page", "pages"), ("article-number", "article_number")):
        if metadata.get(source):
            record[target] = plain_text(metadata[source])
    validate([record])
    return record


def merge_record(records, record, update_id=None):
    target = next((item for item in records if item["id"] == update_id), None)
    if update_id and target is None:
        raise ValueError(f"更新対象のIDが見つかりません: {update_id}")
    title_key = lambda value: re.sub(r"[\W_]+", "", value.casefold())
    for item in records:
        if item is target:
            continue
        same_doi = "doi" in item and normalize_doi(item["doi"]) == record["doi"]
        same_title = item["category"] == record["category"] and title_key(item["title"]) == title_key(record["title"])
        if same_doi or same_title:
            raise ValueError(f"登録済みの業績です: {item['id']}。更新する場合は --update {item['id']} を指定してください。")
    if target is not None:
        if "doi" in target and normalize_doi(target["doi"]) != record["doi"]:
            raise ValueError("既存項目とは異なるDOIです。別の業績として追加してください。")
        # Retain local presentation details; bibliographic fields come from Crossref.
        merged = {key: value for key, value in target.items() if key in ("location", "report_number", "language")}
        merged.update(record)
        merged["language"] = target["language"]
        merged["id"] = target["id"]
        result = [merged if item is target else item for item in records]
        record = merged
    else:
        result = records + [record]
    validate(result)
    return result, record


def main(argv=None):
    parser = argparse.ArgumentParser(description="業績データの検証・HTML生成・DOIからの追加")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="業績欄を生成する")
    build.add_argument("--output", type=Path, help="公開用サイト一式を別のディレクトリに生成する")
    commands.add_parser("check", help="業績データと生成済みHTMLの一致を確認する")
    add = commands.add_parser("add-doi", help="Crossrefから書誌情報を取得して追加し、HTMLも更新する")
    add.add_argument("doi", help="DOIまたはdoi.orgのURL")
    add.add_argument("--category", choices=CATEGORIES)
    add.add_argument("--id", help="新規項目のID（省略時はDOIから生成）")
    add.add_argument("--update", metavar="ID", help="既存項目を出版済みに更新する")
    add.add_argument("--dry-run", action="store_true", help="保存せず、取り込む内容を表示する")
    add.add_argument("--email", help="Crossrefへの問い合わせ元メールアドレス（任意）")
    args = parser.parse_args(argv)
    try:
        records = load_records()
        source = INDEX.read_text(encoding="utf-8")
        if args.command == "add-doi":
            if args.id and args.update:
                raise ValueError("--id と --update は同時に指定できません。")
            doi = normalize_doi(args.doi)
            target = next((item for item in records if item["id"] == args.update), None)
            if args.update and target is None:
                raise ValueError(f"更新対象のIDが見つかりません: {args.update}")
            if not args.update and any(normalize_doi(item["doi"]) == doi for item in records if "doi" in item):
                raise ValueError("このDOIは登録済みです。更新する場合は --update ID を指定してください。")
            category = args.category or (target["category"] if target else None)
            record = record_from_metadata(fetch_metadata(doi, args.email), doi, category, args.id)
            records, record = merge_record(records, record, args.update)
            generated = build_html(records, source)
            print(json.dumps(record, ensure_ascii=False, indent=2))
            if args.dry_run:
                print("プレビューのみ。ファイルは変更していません。", file=sys.stderr)
                return 0
            atomic_write(DATA, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
            atomic_write(INDEX, generated)
            print("業績データと index.html を更新しました。", file=sys.stderr)
            return 0
        generated = build_html(records, source)
        if args.command == "check":
            if source != generated:
                raise ValueError("HTMLが最新ではありません。python3 scripts/publications.py build を実行してください。")
            print(f"OK: {len(records)}件の業績データとHTMLが一致しています。")
        elif args.output is None:
            atomic_write(INDEX, generated)
            print(f"index.html の業績欄を生成しました（{len(records)}件）。")
        else:
            output = args.output.resolve()
            if output == ROOT or ROOT.is_relative_to(output):
                raise ValueError("--output にはプロジェクトとは別の出力ディレクトリを指定してください。")
            output.mkdir(parents=True, exist_ok=True)
            atomic_write(output / "index.html", generated)
            for name in ("style.css", "script.js"):
                shutil.copy2(ROOT / name, output / name)
            shutil.copytree(ROOT / "assets", output / "assets", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".*"))
            cname = ROOT / "CNAME"
            if cname.exists():
                shutil.copy2(cname, output / "CNAME")
            (output / ".nojekyll").touch()
            print(f"公開用サイトを生成しました: {output}")
        return 0
    except (ValueError, OSError, TypeError, KeyError, IndexError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
