"""Regresiones puras de la frontera GitHub REST de Factory #1104."""
from __future__ import annotations

import copy
import json
import unittest

from scripts.salud_cola_github import (
    GitHubPageError, parse_github_issue_page, parse_github_issue_sequence,
    require_stable_github_sweeps,
)


def url(page=1, repo="Factory"):
    return (f"https://api.github.com/repos/pl0n3r/{repo}/issues"
            f"?state=open&per_page=100&page={page}")


def link(page, relation, repo="Factory"):
    return f'<{url(page, repo)}>; rel="{relation}"'


def full_items(count=100):
    return [{"number": n + 1, "state": "open", "labels": []}
            for n in range(count)]


def parse(*, repo="Factory", page=1, request=None, status=200,
          header=None, items=None):
    return parse_github_issue_page(
        repo, page, request if request is not None else url(page, repo),
        status, header, items if items is not None else [],
    )


class GitHubPageTests(unittest.TestCase):
    def test_only_canonical_rest_issue_request_is_accepted(self):
        self.assertEqual(parse()["page_number"], 1)
        self.assertEqual(parse(repo="brvtal", request=url(1, "brvtal"))["issues"], [])
        bad_urls = (
            "http://api.github.com/repos/pl0n3r/Factory/issues?state=open&per_page=100&page=1",
            "https://evil.example/repos/pl0n3r/Factory/issues?state=open&per_page=100&page=1",
            "https://pl0n3r@api.github.com/repos/pl0n3r/Factory/issues?state=open&per_page=100&page=1",
            "https://api.github.com:443/repos/pl0n3r/Factory/issues?state=open&per_page=100&page=1",
            url(1, "Condor"),
            url(1).replace("state=open", "state=all"),
            url(1).replace("per_page=100", "per_page=50"),
            url(1) + "&extra=1",
            url(1) + "#fragment",
            url(1).replace("page=1", "page=01"),
            url(1).replace("page=1", "page=%31"),
            url(1).replace("state=open", "state=%6fpen"),
            url(1).replace("state=open", "st%61te=open"),
            url(1).replace("per_page=100", "per_page=%3100"),
            url(1).replace("page=1", "page=+1"),
            "\n" + url(1),
            url(1).replace("/repos", "/re\npos"),
            url(1) + "\r",
            url(1).replace("api.github.com", "api.github.com\t"),
            "\x00" + url(1),
            url(1) + "\x7f",
        )
        for request in bad_urls:
            with self.subTest(request=request), self.assertRaises(GitHubPageError):
                parse(request=request)
        for p in (True, 0, 101, "1"):
            with self.subTest(page=p), self.assertRaises(GitHubPageError):
                parse(page=p)
        for status in (True, 201, 204, 301, 401, 403, 404, 429, 500, "200"):
            with self.subTest(status=status), self.assertRaises(GitHubPageError):
                parse(status=status)

    def test_link_headers_are_consistent_and_closed(self):
        first = ", ".join([link(2, "next"), link(3, "last")])
        middle = ", ".join([link(1, "first"), link(1, "prev"),
                            link(3, "next"), link(3, "last")])
        final = ", ".join([link(1, "first"), link(2, "prev"),
                           link(3, "last")])
        self.assertTrue(parse(header=first, items=full_items())["has_next"])
        self.assertTrue(parse(page=2, header=middle, items=full_items())["has_next"])
        for count in (0, 1, 99):
            with self.subTest(underfilled=count):
                with self.assertRaisesRegex(GitHubPageError, "nonterminal_page_underfilled"):
                    parse(header=first, items=full_items(count))
        # Underfilled terminal pages are unambiguous; 100 without a
        # definitive end marker could omit a page containing Issue 101.
        for count in (0, 1, 99):
            self.assertFalse(parse(items=full_items(count))["has_next"])
        with self.assertRaisesRegex(GitHubPageError, "ambiguous_terminal_full_page"):
            parse(items=full_items(100))
        with self.assertRaisesRegex(GitHubPageError, "ambiguous_terminal_full_page"):
            parse(page=2, header=link(1, "prev"), items=full_items(100))
        self.assertFalse(parse(page=3, header=final)["has_next"])
        self.assertFalse(parse()["has_next"])
        bad = (
            (1, link(3, "next")),
            (1, link(2, "next") + ", " + link(2, "next")),
            (1, link(2, "next") + ", " + link(1, "last")),
            (1, link(1, "prev")),
            (1, link(1, "next")),
            (1, link(2, "next", repo="Condor")),
            (1, link(2, "next").replace("page=2", "page=%32")),
            (1, link(2, "next").replace("state=open", "st%61te=open")),
            (1, '<https://evil.example/path?page=2>; rel="next"'),
            (1, link(2, "weird")),
            (1, link(2, "next").replace("/repos", "/re\npos")),
            (1, link(2, "next").replace("api.github.com", "api.github.com\t")),
            (1, link(2, "next") + "\r"),
            (1, "junk"),
            (2, None),
            (2, link(3, "next")),
            (2, link(1, "prev") + ", " + link(4, "next")),
            (2, link(1, "prev") + ", " + link(3, "last")),
            (3, link(2, "prev") + ", " + link(4, "last")),
        )
        for page, header in bad:
            with self.subTest(page=page, header=header), self.assertRaises(GitHubPageError):
                parse(page=page, header=header)


    def test_page_sequence_reconciles_last_and_duplicate_issues(self):
        def capture(n, items, header):
            return {"request_url": url(n), "status_code": 200,
                    "link_header": header, "payload": items}

        first = capture(1, full_items(),
                        ", ".join((link(2, "next"), link(2, "last"))))
        second = capture(2, [{"number": 101, "state": "open", "labels": []}],
                         ", ".join((link(1, "first"), link(1, "prev"))))
        batch = parse_github_issue_sequence("Factory", [first, second])
        self.assertEqual(set(batch), {"name", "pages"})
        self.assertEqual([p["page_number"] for p in batch["pages"]], [1, 2])
        self.assertEqual([p["has_next"] for p in batch["pages"]], [True, False])
        self.assertEqual(sum(len(p["issues"]) for p in batch["pages"]), 101)
        self.assertEqual(parse_github_issue_sequence("Factory", [
            capture(1, [], None)])["pages"][0]["has_next"], False)

        # A caller cannot declare the snapshot complete if the first
        # authenticated Link announced four pages but only two were read.
        mismatched_first = capture(1, full_items(),
                                    ", ".join((link(2, "next"), link(4, "last"))))
        changed_last = capture(2, second["payload"],
                               ", ".join((link(1, "prev"), link(3, "last"))))
        missing_last = capture(1, full_items(), link(2, "next"))
        duplicated_issue = capture(2, [{"number": 1, "state": "open", "labels": []}],
                                   link(1, "prev"))
        cases = (
            [mismatched_first, second],
            [first, changed_last],
            [missing_last, second],
            [first],  # Missing a page announced by next.
            [first, duplicated_issue],
            [capture(1, full_items(), None)],  # Missing Link on full page.
            [second],  # Requesting page 2 as the first capture.
            [first, second, second],
            [{"request_url": url(1), "status_code": 200,
              "link_header": None}],  # Missing payload.
        )
        for case in cases:
            with self.subTest(case=str(case)[:100]):
                with self.assertRaises(GitHubPageError):
                    parse_github_issue_sequence("Factory", case)

        for incomplete in ([], {}, [True]):
            with self.subTest(incomplete=incomplete):
                with self.assertRaises(GitHubPageError):
                    parse_github_issue_sequence("Factory", incomplete)


    def test_two_stable_sweeps_reject_issue_drift(self):
        def capture(n, items, header):
            return {"request_url": url(n), "status_code": 200,
                    "link_header": header, "payload": items}
        first = capture(1, full_items(),
                        ", ".join((link(2, "next"), link(2, "last"))))
        second = capture(2, [{"number": 101, "state": "open",
                               "labels": [{"name": "estado: reservado"}]}],
                         link(1, "prev"))
        initial = [first, second]
        stable = copy.deepcopy(initial)
        result = require_stable_github_sweeps("Factory", initial, stable)
        self.assertEqual(set(result), {"name", "pages"})
        self.assertEqual(sum(len(p["issues"]) for p in result["pages"]), 101)

        # Same count but a different Issue, status, label, PR type or order
        # must be treated as drift instead of a complete actionable snapshot.
        mutations = (
            lambda pages: pages[0]["payload"][0].update(number=300),
            lambda pages: pages[0]["payload"][0].update(
                labels=[{"name": "estado: disponible"}]),
            lambda pages: pages[1]["payload"][0].update(
                labels=[{"name": "estado: disponible"}]),
            lambda pages: pages[0]["payload"][0].update(
                pull_request={"url": "https://example.invalid/pr"}),
            lambda pages: pages[0]["payload"].reverse(),
            lambda pages: pages[1]["payload"].append(
                {"number": 102, "state": "open", "labels": []}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(initial)
                mutation(changed)
                with self.assertRaisesRegex(GitHubPageError, "unstable_issue_sweeps"):
                    require_stable_github_sweeps("Factory", initial, changed)

        # The helper must never accept an incomplete second sweep or
        # an impossible data source even if the first sweep is complete.
        partial = copy.deepcopy(initial)[:1]
        with self.assertRaises(GitHubPageError):
            require_stable_github_sweeps("Factory", initial, partial)
        with self.assertRaises(GitHubPageError):
            require_stable_github_sweeps("UnknownRepo", initial, stable)
        ambiguous = [capture(1, full_items(), None)]
        with self.assertRaisesRegex(GitHubPageError, "ambiguous_terminal_full_page"):
            require_stable_github_sweeps("Factory", ambiguous, copy.deepcopy(ambiguous))
        # Source-only free text is intentionally excluded from comparisons.
        texts_only = copy.deepcopy(initial)
        texts_only[0]["payload"][0]["title"] = "private changed title"
        self.assertEqual(require_stable_github_sweeps(
            "Factory", initial, texts_only), result)

    def test_projection_excludes_pr_and_private_text(self):
        payload = [
            {"number": 17, "state": "open",
             "labels": [{"name": "estado: disponible", "color": "123456"},
                        {"name": "contact_email=alice@example.invalid"}],
             "title": "password=SECRET", "body": "TOKEN:SECRET",
             "user": {"login": "private-user"}, "html_url": "https://private.example"},
            {"number": 18, "state": "open",
             "labels": [{"name": "tracking=private-user"}],
             "pull_request": {"url": "https://private.example"},
             "body": "api_key=SECRET", "user": {"login": "private-user"}},
        ]
        result = parse(items=payload)
        self.assertEqual(set(result), {"page_number", "has_next", "issues"})
        self.assertEqual(result["issues"], [
            {"number": 17, "labels": ["estado: disponible"],
             "pull_request": False, "blocker": None},
            {"number": 18, "labels": [], "pull_request": True, "blocker": None},
        ])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("private-user", json.dumps(result))
        self.assertNotIn("private.example", json.dumps(result))
        self.assertNotIn("alice@example.invalid", json.dumps(result))
        self.assertNotIn("contact_email=", json.dumps(result))
        # The recovery status is canonical but remains non-dispatchable until
        # sibling contracts add the sixth category in Factory #1102.
        recovered = parse(items=[{"number": 19, "state": "open",
            "labels": [{"name": "status: recovery required"}]}])
        self.assertEqual(recovered["issues"][0]["labels"],
                         ["status: recovery required"])
        # The sibling snapshot normalizer excludes records flagged pull_request.
        self.assertEqual(sum(not row["pull_request"] for row in result["issues"]), 1)

    def test_invalid_payload_fails_closed(self):
        baseline = {"number": 1, "state": "open",
                    "labels": [{"name": "status: blocked"}]}
        bad_payloads = (
            {},
            "not an array",
            [None],
            [42],
            [{"labels": []}],
            [{"number": True, "labels": []}],
            [{"number": -1, "labels": []}],
            [baseline, baseline.copy()],
            [{"number": 42, "state": "closed", "labels": [{"name": "estado: disponible"}]}],
            [{"number": 42, "labels": [{"name": "estado: disponible"}]}],
            [{"number": 42, "state": True, "labels": [{"name": "estado: disponible"}]}],
            [{"number": 42, "state": "open",
              "labels": [{"name": "estado: disponible"},
                         {"name": "estado: etiqueta inventada"}]}],
            [{"number": 42, "state": "open",
              "labels": [{"name": "status: available"},
                         {"name": "status: unauthorized"}]}],
            [{"number": 42, "state": "open",
              "labels": [{"name": "estado: disponible"},
                         {"name": "Estado: bloqueado"}]}],
            [{"number": 42, "state": "open",
              "labels": [{"name": "status: available"},
                         {"name": "STATUS: BLOCKED"}]}],
            [{"number": 1, "state": "open", "labels": {}}],
            [{"number": 1, "labels": [42]}],
            [{"number": 1, "labels": [{"color": "fff"}]}],
            [{"number": 1, "labels": [{"name": 3}]}],
            [{"number": 1, "labels": [], "pull_request": None}],
            [{"number": 1, "labels": [], "pull_request": False}],
            [{"number": 1, "labels": [], "pull_request": {}}],
            [{"number": i+1, "labels": []} for i in range(101)],
        )
        for items in bad_payloads:
            with self.subTest(items=str(items)[:70]), self.assertRaises(GitHubPageError):
                parse(items=items)
        non_workflow = parse(items=[{"number": 42, "state": "open",
                                     "labels": [{"name": "estado_de_prueba"}]}])
        self.assertEqual(non_workflow["issues"][0]["labels"], [])


if __name__ == "__main__":
    unittest.main()
