"""Thin client for the GitHub GraphQL API used by the project."""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from . import queries

REST_URL = "https://api.github.com"
GRAPHQL_URL = f"{REST_URL}/graphql"


class GitHubClient:
    """Encapsulates the session, headers, and queries needed for the stats."""

    def __init__(self, token: str, timeout: int = 15):
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        response = requests.post(
            GRAPHQL_URL,
            headers=self._headers,
            json={"query": query, "variables": variables or {}},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"Error de GraphQL: {payload['errors']}")
        return payload["data"]

    def get_user_overview(self, username: str) -> dict:
        data = self._graphql(queries.USER_QUERY, {"login": username})
        return data["user"]

    def get_all_repositories(self, username: str) -> list[dict]:
        """Fetches ALL public owned repos, paginating 100 at a time."""
        repos: list[dict] = []
        after = None
        while True:
            data = self._graphql(queries.REPOS_QUERY, {"login": username, "after": after})
            block = data["user"]["repositories"]
            repos.extend(block["nodes"])
            if not block["pageInfo"]["hasNextPage"]:
                break
            after = block["pageInfo"]["endCursor"]
        return repos

    def get_contributions_by_year(self, username: str, start_year: int) -> dict[int, dict]:
        """One query per year (GraphQL limit is one year per query)."""
        current_year = datetime.now(timezone.utc).year
        results: dict[int, dict] = {}

        for year in range(start_year, current_year + 1):
            date_from = f"{year}-01-01T00:00:00Z"
            date_to = (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if year == current_year
                else f"{year}-12-31T23:59:59Z"
            )
            data = self._graphql(
                queries.CONTRIBUTIONS_QUERY,
                {"login": username, "from": date_from, "to": date_to},
            )
            results[year] = data["user"]["contributionsCollection"]

        return results
