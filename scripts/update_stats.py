"""Refresh the profile's stats from GitHub. Requires Python 3 and authenticated gh."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


USERNAME = "BenceGyurus"
README = Path(__file__).resolve().parents[1] / "README.md"
START = "<!-- github-stats:start -->"
END = "<!-- github-stats:end -->"
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
    }
  }
}
"""


def github_api(*args):
    result = subprocess.run(
        ["gh", "api", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    data = json.loads(result.stdout)
    if isinstance(data, dict) and data.get("errors"):
        raise RuntimeError(f"GitHub API errors: {data['errors']}")
    return data


def render_stats(now):
    since = now - timedelta(days=365)
    profile = github_api(f"users/{USERNAME}")
    pages = github_api(
        f"users/{USERNAME}/repos?type=owner&per_page=100",
        "--paginate",
        "--slurp",
    )
    repos = [
        repo
        for page in pages
        for repo in page
        if not repo["fork"]
        and not repo["private"]
        and repo["owner"]["login"].casefold() == USERNAME.casefold()
    ]
    activity = github_api(
        "graphql",
        "-f", f"query={QUERY}",
        "-f", f"login={USERNAME}",
        "-f", f"from={since.isoformat()}",
        "-f", f"to={now.isoformat()}",
    )
    contributions = activity["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["totalContributions"]
    stars = sum(repo["stargazers_count"] for repo in repos)
    return (
        "| Metric | Count |\n"
        "| --- | ---: |\n"
        f"| Contributions in the past 365 days | {contributions:,} |\n"
        f"| Public repositories I own (excluding forks) | {len(repos):,} |\n"
        f"| Stars on those repositories | {stars:,} |\n"
        f"| Followers | {profile['followers']:,} |\n\n"
        f"Updated {now:%Y-%m-%d %H:%M} UTC from the GitHub API. "
        f"Contribution window: {since:%Y-%m-%d} to {now:%Y-%m-%d}.\n\n"
        "Contributions follow GitHub's calendar rules, including anonymised "
        "private activity where available; they are not a total commit count. "
        "Repository and star counts include archived repositories and exclude "
        "forks, private repositories, and organisation-owned projects.\n\n"
        f"[Contribution history](https://github.com/{USERNAME}?tab=overview) "
        "· [How GitHub counts contributions]"
        "(https://docs.github.com/en/account-and-profile/"
        "how-tos/contribution-settings)"
    )


def update_readme(stats):
    original = README.read_text(encoding="utf-8")
    if original.count(START) != 1 or original.count(END) != 1:
        raise ValueError("README must contain exactly one pair of stats markers")
    before, remainder = original.split(START, 1)
    _, after = remainder.split(END, 1)
    updated = f"{before}{START}\n{stats}\n{END}{after}"
    if updated != original:
        README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    update_readme(render_stats(datetime.now(timezone.utc).replace(microsecond=0)))
