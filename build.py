"""Render the neofetch-style profile card (dark_mode.svg, light_mode.svg).

Static facts live in CARD below; GitHub stats are fetched with the GraphQL API.
Runs daily in GitHub Actions. Locally: GITHUB_TOKEN=$(gh auth token) python3 build.py
Standard library only.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = "vanalex"
HEADER = "alex@pajaron"
WIDTH = 60  # characters in the right-hand column

# (key, value) rows; None draws a blank line, a str draws a section header.
CARD: list = [
    ("OS", "macOS, Linux containers"),
    ("Uptime", "{uptime}"),
    ("Host", "Berlin, Germany"),
    ("Kernel", "Senior Software Engineer"),
    ("Shell", "zsh"),
    None,
    ("Languages.Programming", "Python, Rust, Scala, Java"),
    ("Languages.Real", "Spanish, English, German"),
    None,
    ("Stack.Data", "Kafka, Redpanda, Flink, Spark, Iceberg"),
    ("Stack.Storage", "ClickHouse, Postgres, MySQL"),
    ("Stack.AI", "LangGraph, Qdrant, Weaviate"),
    None,
    ("Hobbies", "Reading, Basketball"),
    ("Hobbies.Main", "Family (most of the uptime)"),
    "Contact",
    ("Email.Personal", "apjorquera@gmail.com"),
    ("LinkedIn", "alex-pajaron"),
    "GitHub Stats",
    ("Repos", "{repos} {{Contributed: {contributed}}}"),
    ("Stars", "{stars}"),
    ("Commits", "{commits}"),
    ("Followers", "{followers}"),
]

THEMES = {
    "dark_mode.svg": {
        "bg": "#161b22", "text": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
        "dots": "#616e7f", "border": "#30363d",
    },
    "light_mode.svg": {
        "bg": "#f6f8fa", "text": "#24292f", "key": "#953800", "value": "#0a3069",
        "dots": "#c2cfde", "border": "#d0d7de",
    },
}

FONT_SIZE, LINE, CHAR_W = 16, 20, 9.6
ART_X, TEXT_X, TOP = 15, 430, 30
ART_FONT, ART_LINE = 9.6, 11.2  # smaller font so the portrait has more detail


# --------------------------------------------------------------------------- stats


def graphql(query: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_stats(token: str) -> dict:
    base = graphql(
        f"""{{ user(login: "{LOGIN}") {{
              createdAt
              followers {{ totalCount }}
              repositoriesContributedTo(
                contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {{ totalCount }}
            }} }}""",
        token,
    )["user"]

    repos = stars = 0
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ""
        page = graphql(
            f"""{{ user(login: "{LOGIN}") {{
                  repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC,
                               isFork: false{after}) {{
                    totalCount
                    nodes {{ stargazerCount }}
                    pageInfo {{ hasNextPage endCursor }}
                  }} }} }}""",
            token,
        )["user"]["repositories"]
        repos = page["totalCount"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    # contributionsCollection spans at most one year, so ask once per year since signup.
    created = datetime.fromisoformat(base["createdAt"])
    now = datetime.now(UTC)
    years = range(created.year, now.year + 1)
    parts = " ".join(
        f'y{y}: contributionsCollection(from: "{max(created, datetime(y, 1, 1, tzinfo=UTC)).isoformat()}", '
        f'to: "{min(now, datetime(y, 12, 31, 23, 59, 59, tzinfo=UTC)).isoformat()}") '
        "{ totalCommitContributions }"
        for y in years
    )
    yearly = graphql(f'{{ user(login: "{LOGIN}") {{ {parts} }} }}', token)["user"]
    commits = sum(v["totalCommitContributions"] for v in yearly.values())

    return {
        "created": created.date(),
        "repos": repos,
        "contributed": base["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "commits": commits,
        "followers": base["followers"]["totalCount"],
    }


def uptime(start: date, today: date) -> str:
    years = today.year - start.year
    months = today.month - start.month
    days = today.day - start.day
    if days < 0:
        months -= 1
        prev_month_end = date(today.year, today.month, 1).toordinal() - 1
        days += date.fromordinal(prev_month_end).day
    if months < 0:
        years -= 1
        months += 12

    def unit(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    return f"{unit(years, 'year')}, {unit(months, 'month')}, {unit(days, 'day')}"


# --------------------------------------------------------------------------- render


def row_spans(key: str, value: str) -> str:
    """'. Key: ....... value' padded so every value ends at WIDTH."""
    dots = max(1, WIDTH - len(". ") - len(key) - len(": ") - len(value) - 1)
    key_html = ".".join(f'<tspan class="key">{escape(k)}</tspan>' for k in key.split("."))
    return (
        f'<tspan class="dots">. </tspan>{key_html}:'
        f'<tspan class="dots"> {"." * dots} </tspan>'
        f'<tspan class="value">{escape(value)}</tspan>'
    )


def header_spans(title: str) -> str:
    return f'{escape(title)} <tspan class="dots">-{"—" * (WIDTH - len(title) - 2)}</tspan>'


def render(theme: dict, art: list[str], rows: list) -> str:
    lines = [header_spans(HEADER)]
    for row in rows:
        if row is None:
            lines.append('<tspan class="dots">. </tspan>')
        elif isinstance(row, str):
            lines.append("")
            lines.append("- " + header_spans(row))
        else:
            lines.append(row_spans(*row))

    height = int(max(TOP + len(lines) * LINE, TOP + 4 + len(art) * ART_LINE))
    width = int(TEXT_X + (WIDTH + 2) * CHAR_W)
    art_tspans = "".join(
        f'<tspan x="{ART_X}" y="{TOP + 4 + i * ART_LINE:.1f}">{escape(line)}</tspan>'
        for i, line in enumerate(art)
    )
    text_tspans = "".join(
        f'<tspan x="{TEXT_X}" y="{TOP + i * LINE}">{line}</tspan>' for i, line in enumerate(lines)
    )
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-size="{FONT_SIZE}px">
<style>
text {{ font-family: Consolas, "DejaVu Sans Mono", Menlo, "Courier New", monospace;
        fill: {theme["text"]}; white-space: pre; }}
.key {{ fill: {theme["key"]}; }}
.value {{ fill: {theme["value"]}; }}
.dots {{ fill: {theme["dots"]}; }}
</style>
<rect width="{width}" height="{height}" rx="15" fill="{theme["bg"]}" stroke="{theme["border"]}"/>
<text xml:space="preserve" font-size="{ART_FONT}px">{art_tspans}</text>
<text xml:space="preserve">{text_tspans}</text>
</svg>
"""


def main() -> None:
    here = Path(__file__).parent
    token = os.environ["GITHUB_TOKEN"]
    stats = fetch_stats(token)
    values = {
        "uptime": uptime(stats["created"], datetime.now(UTC).date()),
        **{k: f"{v:,}" for k, v in stats.items() if k != "created"},
    }
    rows = [r if not isinstance(r, tuple) else (r[0], r[1].format(**values)) for r in CARD]
    art = (here / "ascii.txt").read_text().splitlines()
    for name, theme in THEMES.items():
        (here / name).write_text(render(theme, art, rows))
    print(json.dumps(values))


if __name__ == "__main__":
    main()
