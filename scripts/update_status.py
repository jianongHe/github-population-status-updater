#!/usr/bin/env python3
"""Update GitHub user status to the current estimated world population."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request


POPULATION_API_URL = (
    "https://d6wn6bmjj722w.population.io/1.0/population/World/{date}/"
)
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def request_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to request {url}: {exc.reason}") from exc


def get_population(date: dt.date) -> int:
    data = request_json(
        POPULATION_API_URL.format(date=date.isoformat()),
        headers={"User-Agent": "github-population-status-updater"},
    )
    try:
        population = data["total_population"]["population"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Population.io response: {data!r}") from exc

    if not isinstance(population, int) or population <= 0:
        raise RuntimeError(f"Invalid population value: {population!r}")

    return population


def update_github_status(token: str, message: str, emoji: str) -> None:
    query = """
    mutation($input: ChangeUserStatusInput!) {
      changeUserStatus(input: $input) {
        status {
          emoji
          message
          indicatesLimitedAvailability
        }
      }
    }
    """
    payload = {
        "query": query,
        "variables": {
            "input": {
                "emoji": emoji,
                "message": message,
                "limitedAvailability": False,
            }
        },
    }
    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-population-status-updater",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to call GitHub GraphQL: {exc.reason}") from exc

    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {result['errors']!r}")


def parse_date(value: str | None) -> dt.date:
    if not value:
        return dt.datetime.now(dt.timezone.utc).date()
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"STATUS_DATE must be YYYY-MM-DD, got {value!r}") from exc


def main() -> int:
    token = os.environ.get("GH_STATUS_TOKEN")
    if not token:
        print("GH_STATUS_TOKEN is required.", file=sys.stderr)
        return 2

    status_date = parse_date(os.environ.get("STATUS_DATE"))
    emoji = os.environ.get("STATUS_EMOJI", ":sunflower:")
    dry_run = os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}

    population = get_population(status_date)
    message = f"1 / {population:,}"

    if dry_run:
        print(f"DRY_RUN: would set GitHub status to {emoji} {message}")
        return 0

    update_github_status(token, message, emoji)
    print(f"Updated GitHub status to {emoji} {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
