"""Regression tests for data preservation, rendering, and DOI import failures."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publications", ROOT / "scripts/publications.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)

# Crossref-shaped response, including markup and partial publication dates.
METADATA = {
    "DOI": "10.1234/example.1",
    "type": "journal-article",
    "title": ["Sampling <i>edges</i> &amp; networks"],
    "container-title": ["Example Journal"],
    "author": [{"given": "Kenta", "family": "Yanagiya"}, {"name": "Research Group"}],
    "published-online": {"date-parts": [[2026, 10]]},
    "created": {"date-parts": [[2025, 2, 3]]},
    "volume": "12",
    "issue": "2",
    "page": "1-10",
}


class PublicationsTest(unittest.TestCase):
    def setUp(self):
        self.records = pub.load_records()
        self.source = pub.INDEX.read_text(encoding="utf-8")

    def imported(self, metadata=None):
        return pub.record_from_metadata(deepcopy(metadata or METADATA), "10.1234/example.1")

    def test_build_preserves_content_outside_publication_markers(self):
        generated = pub.build_html(self.records, self.source)
        self.assertEqual(generated.split(pub.START)[0], self.source.split(pub.START)[0])
        self.assertEqual(generated.split(pub.END)[1], self.source.split(pub.END)[1])
        self.assertEqual(generated, pub.build_html(self.records, generated))
        for record in self.records:
            self.assertIn(f'id="{record["id"]}"', generated)

    def test_dates_sort_newest_first_and_empty_groups_are_omitted(self):
        records = [deepcopy(self.records[2]), deepcopy(self.records[3])]
        output = pub.render(records[::-1])
        self.assertLess(output.index(records[0]["id"]), output.index(records[1]["id"]))
        self.assertNotIn("Journal Papers", output)
        self.assertEqual(pub.format_date("2024-03", "ja"), "2024年3月")
        self.assertEqual(pub.format_date("2024", "en"), "2024")

    def test_html_from_bibliographic_fields_cannot_be_executed(self):
        record = deepcopy(self.records[0])
        record["title"] = '<script>alert("title")</script>'
        record["authors"] = ["<img src=x onerror=alert(1)>"]
        record["venue"] = "<iframe src=x>"
        record["doi"] = '10.1234/test"<img>'
        output = pub.render([record])
        self.assertNotIn("<script>", output)
        self.assertNotIn("<img", output)
        self.assertNotIn("<iframe", output)
        self.assertIn("&lt;script&gt;", output.lower())
        self.assertIn("https://doi.org/10.1234/test%22%3Cimg%3E", output)

    def test_invalid_data_does_not_silently_drop_records(self):
        for field, value in (("status", "publishd"), ("date", "2025-02-29"),
                             ("authors", []), ("category", "unknown")):
            with self.subTest(field=field):
                record = deepcopy(self.records[0])
                record[field] = value
                with self.assertRaises(ValueError):
                    pub.validate([record])
        with self.assertRaises(ValueError):
            pub.validate([self.records[0], self.records[0]])

    def test_doi_url_is_normalized_and_arbitrary_urls_are_rejected(self):
        self.assertEqual(pub.normalize_doi("https://doi.org/10.1234/EXAMPLE%2E1"), "10.1234/example.1")
        self.assertEqual(pub.normalize_doi(" DOI:10.1234/Example.1 "), "10.1234/example.1")
        for value in ("https://example.com/10.1234/example.1", "nonsense", "10.1234/has a space"):
            with self.assertRaises(ValueError):
                pub.normalize_doi(value)

    def test_metadata_uses_publication_date_and_cleans_markup(self):
        record = self.imported()
        self.assertEqual(record["date"], "2026-10")
        self.assertEqual(record["title"], "Sampling Edges & Networks")
        self.assertEqual(record["authors"], ["Kenta Yanagiya", "Research Group"])
        self.assertEqual(record["category"], "journal")
        self.assertEqual(record["pages"], "1-10")

    def test_english_titles_follow_the_requested_case_and_hyphenation(self):
        cases = {
            "time-varying edge removal scheduling for network-based epidemic control":
                "Time-Varying Edge Removal Scheduling for Network-based Epidemic Control",
            "Edge sampling of graphs: Graph signal processing approach with edge smoothness":
                "Edge Sampling of Graphs: Graph Signal Processing Approach with Edge Smoothness",
            "lossy compression of adjacency matrices by graph filter banks":
                "Lossy Compression of Adjacency Matrices by Graph Filter Banks",
            "multiscale graph construction using non-local cluster features":
                "Multiscale Graph Construction Using Non-local Cluster Features",
            "On graphs: WITH signals FROM networks": "on Graphs: with Signals from Networks",
            "IEEE methods for GraphSAGE": "IEEE Methods for GraphSAGE",
            "Line グラフ変換とグラフサンプリング定理を用いた辺サンプリング":
                "Line グラフ変換とグラフサンプリング定理を用いた辺サンプリング",
        }
        for original, expected in cases.items():
            with self.subTest(title=original):
                self.assertEqual(pub.format_title(original), expected)
                self.assertEqual(pub.format_title(expected), expected)

    def test_fully_english_domestic_title_is_formatted_without_changing_venue(self):
        record = deepcopy(self.records[9])
        record["title"] = "time-varying edge removal scheduling for network-based epidemic control"
        record["venue"] = "Example conference for graphs"
        output = pub.render([record])
        self.assertIn("Time-Varying Edge Removal Scheduling for Network-based Epidemic Control", output)
        self.assertIn("Example conference for graphs", output)

    def test_incomplete_or_mismatched_metadata_is_rejected(self):
        for field in ("author", "title", "container-title", "published-online"):
            metadata = deepcopy(METADATA)
            del metadata[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.imported(metadata)
        metadata = deepcopy(METADATA)
        metadata["DOI"] = "10.1234/different"
        with self.assertRaises(ValueError):
            self.imported(metadata)

    def test_same_paper_cannot_be_added_twice_with_different_doi_spellings(self):
        record = self.imported()
        existing = dict(record, doi="https://doi.org/10.1234/EXAMPLE.1")
        with self.assertRaises(ValueError):
            pub.merge_record([existing], record)
        # Existing records may not yet have a DOI: match title and category too.
        del existing["doi"]
        existing["title"] = "Sampling edges and networks"  # Different content remains distinct.
        pub.merge_record([existing], dict(record, id="another-id"))
        existing["title"] = "SAMPLING EDGES & NETWORKS."
        with self.assertRaises(ValueError):
            pub.merge_record([existing], record)

    def test_under_review_moves_to_journal_without_duplicate_or_id_change(self):
        existing = deepcopy(self.records[1])
        record = self.imported()
        records, updated = pub.merge_record([existing], record, existing["id"])
        self.assertEqual(len(records), 1)
        self.assertEqual(updated["id"], existing["id"])
        self.assertEqual(updated["status"], "published")
        self.assertNotIn("Under Review", pub.render(records))
        self.assertIn("Journal Papers", pub.render(records))
        with self.assertRaises(ValueError):
            pub.merge_record(records, dict(record, doi="10.1234/different"), existing["id"])

    def test_network_errors_report_an_actionable_error(self):
        errors = (HTTPError("url", 404, "Not Found", None, None),
                  HTTPError("url", 429, "Too Many Requests", None, None),
                  URLError("offline"))
        for error in errors:
            with self.subTest(error=error), patch.object(pub, "urlopen", side_effect=error):
                with self.assertRaises(ValueError):
                    pub.fetch_metadata("10.1234/example.1")

    def test_cli_dry_run_and_failed_import_leave_both_files_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "publications.json"
            index = Path(directory) / "index.html"
            initial_data = json.dumps(self.records, ensure_ascii=False)
            data.write_text(initial_data, encoding="utf-8")
            index.write_text(self.source, encoding="utf-8")
            with patch.object(pub, "DATA", data), patch.object(pub, "INDEX", index), \
                    patch.object(pub, "load_records", lambda: json.loads(data.read_text(encoding="utf-8"))), \
                    patch.object(pub, "fetch_metadata", return_value=deepcopy(METADATA)), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(pub.main(["add-doi", "10.1234/example.1", "--dry-run"]), 0)
                self.assertEqual(data.read_text(encoding="utf-8"), initial_data)
                self.assertEqual(index.read_text(encoding="utf-8"), self.source)
                self.assertEqual(pub.main(["add-doi", "10.1234/example.1", "--id", "INVALID ID"]), 1)
                self.assertEqual(data.read_text(encoding="utf-8"), initial_data)
                self.assertEqual(index.read_text(encoding="utf-8"), self.source)
                self.assertEqual(pub.main(["add-doi", "10.1234/example.1"]), 0)
                saved = json.loads(data.read_text(encoding="utf-8"))
                self.assertEqual(len(saved), len(self.records) + 1)
                self.assertIn("https://doi.org/10.1234/example.1", index.read_text(encoding="utf-8"))
                self.assertEqual(pub.main(["add-doi", "10.1234/example.1"]), 1)
                self.assertEqual(json.loads(data.read_text(encoding="utf-8")), saved)


if __name__ == "__main__":
    unittest.main()
