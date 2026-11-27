#!/usr/bin/env python3
"""Sync ISSUES.md to GitHub issues. ISSUES.md is the source of truth.

Line format:  - [ ][#12][bug, help wanted] Title

Each line's checkbox, tags and title are applied to its issue, overwriting
changes made on GitHub. Two things are written back to the file: the number of a
newly created issue, and open issues that were added on GitHub.
"""

import json
import os
import re
import urllib.request
from pathlib import Path

ISSUES = Path("ISSUES.md")
LINE = re.compile(r"^\s*[-*] \[([ xX]?)\](?:\[\s*#?(\d*)\s*\])?(?:\[([^\]]*)\])?(?!\()\s*(.+?)\s*$")


def api(method, path, data=None):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}",
        data=None if data is None else json.dumps(data).encode(),
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "issues-sync",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_issues():
    issues, page = {}, 1
    while batch := api("GET", f"/issues?state=all&per_page=100&page={page}"):
        issues.update({item["number"]: item for item in batch})
        page += 1
    return issues


def fields(issue):
    return {
        "done": issue["state"] == "closed",
        "title": " ".join(issue["title"].split()),
        "tags": [label["name"] for label in issue["labels"]],
    }


def differs(key, a, b):
    if key == "tags":
        return {t.lower() for t in a} != {t.lower() for t in b}
    return a != b


def main():
    lines = ISSUES.read_text().splitlines()
    issues = fetch_issues()
    listed = {int(m[2]) for line in lines if (m := LINE.match(line)) and m[2]}
    used = set()

    for index, line in enumerate(lines):
        match = LINE.match(line)
        if not match:
            continue
        box, number, tags, title = match.groups()
        local = {
            "done": box.lower() == "x",
            "title": " ".join(title.split()),
            "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
        }
        number = int(number) if number else None
        issue = issues.get(number)

        if issue is None:
            # Reuse an unlisted issue with this title, so a run that failed
            # after creating it does not create a duplicate.
            issue = next(
                (i for n, i in issues.items()
                 if n not in listed and n not in used and "pull_request" not in i
                 and fields(i)["title"] == local["title"]),
                None,
            )
            if issue is None:
                issue = api("POST", "/issues", {"title": local["title"], "labels": local["tags"]})
                print(f"Created #{issue['number']}: {local['title']}")
        elif "pull_request" in issue:
            print(f"::warning::#{number} is a pull request, line skipped")
            continue

        if issue["number"] != number:
            number = issue["number"]
            lines[index] = f"- [{box or ' '}][#{number}][{', '.join(local['tags'])}] {local['title']}"
            # Saved right away so the number survives a later failure.
            ISSUES.write_text("".join(f"{x}\n" for x in lines))
        used.add(number)

        remote = fields(issue)
        changes = {k: v for k, v in local.items() if differs(k, v, remote[k])}
        if changes:
            payload = {}
            if "done" in changes:
                payload["state"] = "closed" if changes["done"] else "open"
            if "title" in changes:
                payload["title"] = changes["title"]
            if "tags" in changes:
                payload["labels"] = changes["tags"]
            api("PATCH", f"/issues/{number}", payload)
            print(f"Updated #{number}: {', '.join(changes)}")

    # Add open issues that are not in the file yet.
    for number, issue in sorted(issues.items()):
        if number not in used | listed and "pull_request" not in issue and issue["state"] == "open":
            item = fields(issue)
            lines.append(f"- [ ][#{number}][{', '.join(item['tags'])}] {item['title']}")
            print(f"Added #{number} to {ISSUES}")
    ISSUES.write_text("".join(f"{x}\n" for x in lines))


if __name__ == "__main__":
    main()
