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


def graphql_request(
    token: str, query: str, variables: dict | None = None
) -> dict:
    payload = {"query": query, "variables": variables or {}}
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

    return result["data"]


def get_current_github_status(token: str) -> dict | None:
    query = """
    query {
      viewer {
        status {
          emoji
          message
          indicatesLimitedAvailability
        }
      }
    }
    """
    data = graphql_request(token, query)
    return data["viewer"]["status"]


def update_github_status(token: str, message: str, emoji: str) -> dict:
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
    data = graphql_request(
        token,
        query,
        {
            "input": {
                "emoji": emoji,
                "message": message,
                "limitedAvailability": False,
            }
        },
    )
    return data["changeUserStatus"]["status"]


def format_status(status: dict | None) -> str:
    if not status:
        return "(none)"

    emoji = status.get("emoji") or ""
    message = status.get("message") or ""
    label = f"{emoji} {message}".strip()
    return label or "(empty)"


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_step_summary(
    *,
    result: str,
    previous_status: dict | None,
    new_status: dict,
    status_date: dt.date,
    population: int,
) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    previous_limited = (
        previous_status.get("indicatesLimitedAvailability")
        if previous_status
        else "(none)"
    )
    source_url = POPULATION_API_URL.format(date=status_date.isoformat())
    summary = f"""## GitHub Status Update

**Result:** {result}

| Field | Previous | New |
| --- | --- | --- |
| Status | {markdown_cell(format_status(previous_status))} | {markdown_cell(format_status(new_status))} |
| Limited availability | {markdown_cell(previous_limited)} | {markdown_cell(new_status.get("indicatesLimitedAvailability"))} |

**Population date:** `{status_date.isoformat()}`

**Population value:** `{population:,}`

**Source:** `{source_url}`
"""
    with open(summary_path, "a", encoding="utf-8") as summary_file:
        summary_file.write(summary)


def escape_workflow_command(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit_notice(title: str, message: str) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    print(
        f"::notice title={escape_workflow_command(title)}::"
        f"{escape_workflow_command(message)}"
    )


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

    previous_status = get_current_github_status(token)
    new_status = update_github_status(token, message, emoji)
    changed = format_status(previous_status) != format_status(new_status)
    result = "Updated" if changed else "No change"

    print(f"Population date: {status_date.isoformat()}")
    print(f"Population value: {population:,}")
    print(f"Previous GitHub status: {format_status(previous_status)}")
    print(f"New GitHub status: {format_status(new_status)}")
    print(f"Result: {result}")
    emit_notice(
        "GitHub status update",
        f"{result}: {format_status(previous_status)} -> {format_status(new_status)}",
    )
    write_step_summary(
        result=result,
        previous_status=previous_status,
        new_status=new_status,
        status_date=status_date,
        population=population,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
