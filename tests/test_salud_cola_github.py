"""Regresiones puras de la frontera GitHub REST de Factory #1104."""
from __future__ import annotations

import json
import unittest

from scripts.salud_cola_github import GitHubPageError, parse_github_issue_page


def url(page=1, repo="Factory"):
    return (f"https://api.github.com/repos/pl0n3r/{repo}/issues"
            f"?state=open&per_page=100&page={page}")


def link(page, relation, repo="Factory"):
    return f'<{url(page, repo)}>; rel="{relation}"'


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
        self.assertTrue(parse(header=first)["has_next"])
        self.assertTrue(parse(page=2, header=middle)["has_next"])
        self.assertFalse(parse(page=3, header=final)["has_next"])
        self.assertFalse(parse()["has_next"])
        bad = (
            (1, link(3, "next")),
            (1, link(2, "next") + ", " + link(2, "next")),
            (1, link(2, "next") + ", " + link(1, "last")),
            (1, link(1, "prev")),
            (1, link(1, "next")),
            (1, link(2, "next", repo="Condor")),
            (1, '<https://evil.example/path?page=2>; rel="next"'),
            (1, link(2, "weird")),
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

    def test_projection_excludes_pr_and_private_text(self):
        payload = [
            {"number": 17, "labels": [{"name": "estado: disponible", "color": "123456"}],
             "title": "password=SECRET", "body": "TOKEN:SECRET",
             "user": {"login": "private-user"}, "html_url": "https://private.example"},
            {"number": 18, "labels": [], "pull_request": {"url": "https://private.example"},
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
        # The sibling snapshot normalizer excludes records flagged pull_request.
        self.assertEqual(sum(not row["pull_request"] for row in result["issues"]), 1)

    def test_invalid_payload_fails_closed(self):
        baseline = {"number": 1, "labels": [{"name": "status: blocked"}]}
        bad_payloads = (
            {},
            "not an array",
            [None],
            [42],
            [{"labels": []}],
            [{"number": True, "labels": []}],
            [{"number": -1, "labels": []}],
            [baseline, baseline.copy()],
            [{"number": 1, "labels": {}}],
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


if __name__ == "__main__":
    unittest.main()
