#!/usr/bin/env python3
"""Regenerate dark_mode.svg (comic-panel theme) with live GitHub stats via the GraphQL API."""
import json, os, sys, textwrap, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from xml.sax.saxutils import escape as esc

USER = "MatiasPinho"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

DISPLAY_FONT = "Impact, Haettenschweiler, 'Arial Black', sans-serif"
BAR_X, BAR_W, BAR_H = 190, 310, 13
LANG_Y0, LANG_STEP = 572, 32
REPO_Y0, REPO_STEP, REPO_COUNT = 548, 18, 3
REPO_NAME_MAX = 30

# --- extended panels (contribution web / pinned cards / activity mix / log) ---
CAL_X0, CAL_Y0, CAL_CELL, CAL_STEP = 88, 810, 13, 16
CAL_RAMP = ["#161a24", "#4a1512", "#8a221c", "#c2332b", "#ff5b52"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PIN_Y0, PIN_STEP, PIN_COUNT, PIN_DESC_W = 1046, 104, 4, 58
MIX_Y0, MIX_STEP, MIX_W = 1058, 40, 315
LOG_Y0, LOG_MAX_Y, LOG_BAR_W = 1558, 1926, 260


def gql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        out = json.loads(r.read())
    if "errors" in out:
        print("GraphQL error:", out["errors"], file=sys.stderr)
        sys.exit(1)
    return out["data"]


PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        description
        pushedAt
        isFork
        isPrivate
        stargazerCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes { ... on Repository {
        name
        description
        isPrivate
        stargazerCount
        primaryLanguage { name color }
      } }
    }
    organizations { totalCount }
    repositoriesContributedTo(
      first: 1
      includeUserRepositories: false
      contributionTypes: [COMMIT, PULL_REQUEST]
    ) { totalCount }
    followers { totalCount }
  }
}
"""

# Everything rendered below the fold: calendar, activity mix and the monthly log.
ACTIVITY_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { firstDay contributionDays { contributionCount weekday } }
      }
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
    month: contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 6) {
        repository { name }
        contributions { totalCount }
      }
      repositoryContributions(first: 5) {
        nodes { occurredAt repository { name isPrivate primaryLanguage { name } } }
      }
      pullRequestContributions(first: 100) {
        nodes { pullRequest { state repository { name } } }
      }
      pullRequestReviewContributions(first: 3) {
        nodes { occurredAt pullRequest { title repository { name } } }
      }
    }
  }
}
"""

# contributionsCollection caps at one year per call, so walk year by year.
COMMITS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""


def all_time_commits(created_at):
    """Sum commit contributions across every year since the account was created."""
    start = int(created_at[:4])
    end = datetime.now(timezone.utc).year
    total = 0
    for year in range(start, end + 1):
        c = gql(
            COMMITS_QUERY,
            {
                "login": USER,
                "from": f"{year}-01-01T00:00:00Z",
                "to": f"{year}-12-31T23:59:59Z",
            },
        )["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
    return total


def fetch_stats():
    u = gql(PROFILE_QUERY, {"login": USER})["user"]
    nodes = u["repositories"]["nodes"]

    lang_sizes = defaultdict(int)
    for repo in nodes:
        for edge in repo.get("languages", {}).get("edges", []):
            lang_sizes[edge["node"]["name"]] += edge["size"]

    total_bytes = sum(lang_sizes.values()) or 1
    top = sorted(lang_sizes.items(), key=lambda x: -x[1])[:4]
    langs = [(name, round(size * 100 / total_bytes)) for name, size in top] or [("N/A", 100)]

    pinned_nodes = [n for n in u["pinnedItems"]["nodes"] if n]
    by_name = {n["name"]: n for n in nodes}
    pinned = [n["name"] for n in pinned_nodes]
    if len(pinned) < REPO_COUNT:  # fall back to the most recently pushed own repos
        own = sorted(
            (n for n in nodes if not n.get("isFork")),
            key=lambda n: n["pushedAt"] or "",
            reverse=True,
        )
        for n in own:
            if n["name"] not in pinned:
                pinned.append(n["name"])
            if len(pinned) == REPO_COUNT:
                break

    cards = []
    for name in pinned[:PIN_COUNT]:
        src = next((p for p in pinned_nodes if p["name"] == name), None) or by_name.get(name) or {}
        cards.append(
            dict(
                name=name,
                description=src.get("description") or "",
                private=bool(src.get("isPrivate")),
                stars=src.get("stargazerCount") or 0,
                lang=(src.get("primaryLanguage") or {}).get("name") or "",
                color=(src.get("primaryLanguage") or {}).get("color") or "#6f7a90",
            )
        )

    now = datetime.now(timezone.utc)
    act = gql(
        ACTIVITY_QUERY,
        {
            "login": USER,
            "from": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z"),
            "to": now.isoformat().replace("+00:00", "Z"),
        },
    )["user"]
    coll, month = act["contributionsCollection"], act["month"]
    cal = coll["contributionCalendar"]

    return dict(
        repos=u["repositories"]["totalCount"],
        stars=sum(n["stargazerCount"] for n in nodes),
        followers=u["followers"]["totalCount"],
        commits=all_time_commits(u["createdAt"]),
        contributed=u["repositoriesContributedTo"]["totalCount"],
        langs=langs,
        pinned=pinned,
        cards=cards,
        orgs=u["organizations"]["totalCount"],
        weeks=cal["weeks"],
        total_contributions=cal["totalContributions"],
        mix=[
            ("Commits", coll["totalCommitContributions"]),
            ("Pull requests", coll["totalPullRequestContributions"]),
            ("Issues", coll["totalIssueContributions"]),
            ("Code review", coll["totalPullRequestReviewContributions"]),
        ],
        month=month,
        month_label=f"{MONTHS[now.month - 1].upper()} {now.year}",
    )


def lang_rows(langs):
    """One row per language: label, track, animated fill, percentage."""
    parts = []
    for i, (name, pct) in enumerate(langs[:4]):
        y = LANG_Y0 + i * LANG_STEP
        top = y - 11
        width = round(max(0, min(100, pct)) * BAR_W / 100, 1)
        delay = f"{0.5 + i * 0.15:.2f}".rstrip("0")
        parts.append(
            f'<text x="36" y="{y}" font-size="14px" fill="#e4e1d8">{name}</text>\n'
            f'<rect x="{BAR_X}" y="{top}" width="{BAR_W}" height="{BAR_H}" fill="#171b26" stroke="#2a3242" stroke-width="1"></rect>\n'
            f'<rect x="{BAR_X}" y="{top}" width="{width}" height="{BAR_H}" fill="#e0403a" '
            f'style="transform-box:fill-box;transform-origin:0% 50%;animation:sw-bar 1s cubic-bezier(.2,.9,.3,1) {delay}s both"></rect>\n'
            f'<text x="572" y="{y + 1}" text-anchor="end" font-family="{DISPLAY_FONT}" font-size="17px" fill="#efe6d5">{pct}%</text>'
        )
    return "\n".join(parts)


def repo_rows(names):
    """PINNED REPOS panel: a web-bullet diamond plus the repo name."""
    parts = []
    for i, name in enumerate(names[:REPO_COUNT]):
        y = REPO_Y0 + i * REPO_STEP
        cy = y - 4
        label = name if len(name) <= REPO_NAME_MAX else name[: REPO_NAME_MAX - 1] + "\u2026"
        parts.append(
            f'<path d="M642 {cy - 4} L646 {cy} L642 {cy + 4} L638 {cy} Z" fill="#e0403a"></path>\n'
            f'<text x="654" y="{y}" font-size="13px" fill="#e4e1d8">{label}</text>'
        )
    return "\n".join(parts)


def calendar_cells(weeks):
    """53 columns of day cells inside the comic vignette, plus month labels."""
    cells, labels, seen = [], [], set()
    for w, week in enumerate(weeks[-53:]):
        x = CAL_X0 + w * CAL_STEP
        key = week["firstDay"][:7]
        if key not in seen and w < 51:
            seen.add(key)
            labels.append(f'<text x="{x}" y="800">{MONTHS[int(week["firstDay"][5:7]) - 1]}</text>')
        for day in week["contributionDays"]:
            c = day["contributionCount"]
            lvl = 0 if c == 0 else 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4
            y = CAL_Y0 + day["weekday"] * CAL_STEP
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CAL_CELL}" height="{CAL_CELL}" rx="1.5" fill="{CAL_RAMP[lvl]}"></rect>'
            )
    return '<g font-size="11px" fill="#8a93a6">' + "".join(labels) + "</g>\n" + "\n".join(cells)


def streak_stats(weeks):
    """Current / longest streak, best single day and active days — all from the calendar."""
    counts = [d["contributionCount"] for week in weeks for d in week["contributionDays"]]
    run = longest = current = active = 0
    for c in counts:
        if c:
            run += 1
            active += 1
            longest = max(longest, run)
        else:
            run = 0
    for c in reversed(counts):
        if not c:
            break
        current += 1
    return dict(current=current, longest=longest, best=max(counts or [0]), active=active)


def streak_panel(stats):
    """WEB-SLINGING STREAK: four Impact numbers in the GITHUB STATS rhythm."""
    cells = (
        (638, 1314, 1332, stats["current"], "CURRENT STREAK", 0.3),
        (806, 1314, 1332, stats["longest"], "LONGEST STREAK", 0.45),
        (638, 1380, 1398, stats["best"], "BEST DAY", 0.6),
        (806, 1380, 1398, stats["active"], "ACTIVE DAYS", 0.75),
    )
    parts = []
    for x, y, ly, value, label, delay in cells:
        parts.append(
            f'<g style="transform-box:fill-box;transform-origin:0% 100%;animation:sw-pop .5s ease-out {delay}s both">\n'
            f'<text x="{x}" y="{y}" font-family="{DISPLAY_FONT}" font-size="32px" fill="#e0403a">{value}</text>\n'
            f'</g>\n'
            f'<text x="{x}" y="{ly}" font-size="10.5px" fill="#8a93a6" letter-spacing="1.8">{label}</text>'
        )
    return "\n".join(parts)


def pinned_cards(cards):
    """One comic card per pinned repo: name, visibility pill, 2 description lines, language."""
    parts = []
    for i, r in enumerate(cards[:PIN_COUNT]):
        y = PIN_Y0 + i * PIN_STEP
        wrapped = textwrap.wrap(r["description"], PIN_DESC_W)
        lines = wrapped[:2] or [""]
        if len(wrapped) > 2:
            lines[1] = lines[1][: PIN_DESC_W - 1] + "\u2026"
        pill = "PRIVATE" if r["private"] else "PUBLIC"
        p = [
            f'<rect x="36" y="{y}" width="548" height="94" fill="#0f1219" stroke="#2a3242" stroke-width="1.2" rx="2"></rect>',
            f'<rect x="36" y="{y}" width="3" height="94" fill="#e0403a"></rect>',
            f'<text x="56" y="{y + 28}" font-family="{DISPLAY_FONT}" font-size="17px" fill="#efe6d5" letter-spacing="0.8">{esc(r["name"])}</text>',
            f'<rect x="508" y="{y + 12}" width="62" height="18" fill="none" stroke="#3b4557" stroke-width="1" rx="9"></rect>',
            f'<text x="539" y="{y + 25}" text-anchor="middle" font-size="9.5px" fill="#8a93a6" letter-spacing="1.2">{pill}</text>',
        ]
        for j, line in enumerate(lines):
            p.append(f'<text x="56" y="{y + 52 + j * 18}" font-size="12px" fill="#8a93a6">{esc(line)}</text>')
        if r["lang"]:
            p.append(f'<circle cx="60" cy="{y + 82}" r="4.5" fill="{r["color"]}"></circle>')
            p.append(f'<text x="72" y="{y + 86}" font-size="12px" fill="#e4e1d8">{esc(r["lang"])}</text>')
        if r["stars"]:
            cy = y + 78
            p.append(
                f'<path d="M552 {cy} L554 {cy + 4.5} L559 {cy + 5} L555.2 {cy + 8.2} L556.4 {cy + 13} '
                f'L552 {cy + 10.4} L547.6 {cy + 13} L548.8 {cy + 8.2} L545 {cy + 5} L550 {cy + 4.5} Z" fill="#e0403a"></path>'
            )
            p.append(f'<text x="540" y="{y + 86}" text-anchor="end" font-size="12px" fill="#e4e1d8">{r["stars"]}</text>')
        parts.append("\n".join(p))
    return "\n".join(parts)


def mix_rows(mix):
    """Commits / PRs / issues / reviews as percentages of the year's contributions."""
    total = sum(v for _, v in mix) or 1
    parts = []
    for i, (label, value) in enumerate(mix):
        y = MIX_Y0 + i * MIX_STEP
        pct = round(value * 100 / total)
        parts.append(
            f'<text x="638" y="{y}" font-size="12.5px" fill="#e4e1d8">{label}</text>\n'
            f'<text x="953" y="{y}" text-anchor="end" font-family="{DISPLAY_FONT}" font-size="15px" fill="#efe6d5">{pct}%</text>\n'
            f'<rect x="638" y="{y + 8}" width="{MIX_W}" height="10" fill="#171b26" stroke="#2a3242" stroke-width="1"></rect>'
            + (
                f'\n<rect x="638" y="{y + 8}" width="{round(pct * MIX_W / 100, 1)}" height="10" fill="#e0403a" '
                f'style="transform-box:fill-box;transform-origin:0% 50%;animation:sw-bar 1s cubic-bezier(.2,.9,.3,1) {0.5 + i * 0.15:.2f}s both"></rect>'
                if pct
                else ""
            )
        )
    return "\n".join(parts)


def _log_head(y, title):
    return (
        f'<path d="M48 {y - 6} L54 {y} L48 {y + 6} L42 {y} Z" fill="#e0403a"></path>\n'
        f'<text x="72" y="{y + 6}" font-family="{DISPLAY_FONT}" font-size="16px" fill="#efe6d5" letter-spacing="0.8">{esc(title)}</text>'
    )


def _log_row(y, left, mid="", right="", frac=None, pills=()):
    p = [f'<text x="72" y="{y}" font-size="13px" fill="#e4e1d8">{esc(left)}</text>']
    if mid:
        p.append(f'<text x="380" y="{y}" font-size="12px" fill="#6f7a90">{esc(mid)}</text>')
    if right:
        p.append(f'<text x="949" y="{y}" text-anchor="end" font-size="12px" fill="#6f7a90">{esc(right)}</text>')
    if frac is not None:
        p.append(f'<rect x="500" y="{y - 9}" width="{max(3, round(LOG_BAR_W * frac, 1))}" height="9" fill="#e0403a"></rect>')
    x = 380
    for label, kind in pills:
        w = 12 + 7 * len(label)
        fill, stroke, color = {
            "open": ("none", "#e0403a", "#e0403a"),
            "merged": ("#e0403a", "none", "#efe6d5"),
            "closed": ("none", "#3b4557", "#8a93a6"),
        }[kind]
        p.append(
            f'<rect x="{x}" y="{y - 11}" width="{w}" height="17" fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"></rect>\n'
            f'<text x="{x + w / 2}" y="{y + 2}" text-anchor="middle" font-size="11px" fill="{color}" letter-spacing="0.6">{esc(label)}</text>'
        )
        x += w + 8
    return "\n".join(p)


def _shorten(value, limit):
    value = value or ""
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


def _activity_date(value):
    if not value:
        return ""
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return f"{MONTHS[stamp.month - 1].upper()} {stamp.day}"


def activity_log(month):
    """Build the compact monthly timeline rendered at the bottom of the SVG."""
    sections = []

    commit_items = []
    for item in month.get("commitContributionsByRepository", []):
        repository = item.get("repository") or {}
        count = (item.get("contributions") or {}).get("totalCount") or 0
        if count:
            commit_items.append((repository.get("name") or "Private repository", count))
    if commit_items:
        maximum = max(count for _, count in commit_items) or 1
        total = sum(count for _, count in commit_items)
        rows = [
            dict(
                left=name,
                mid=f"{count} {'commit' if count == 1 else 'commits'}",
                frac=count / maximum,
            )
            for name, count in commit_items[:4]
        ]
        repo_word = "REPOSITORY" if len(commit_items) == 1 else "REPOSITORIES"
        sections.append((f"CREATED {total} COMMITS IN {len(commit_items)} {repo_word}", rows))

    repository_nodes = (month.get("repositoryContributions") or {}).get("nodes") or []
    if repository_nodes:
        rows = []
        for node in repository_nodes[:2]:
            repository = node.get("repository") or {}
            visibility = "private" if repository.get("isPrivate") else "public"
            language = (repository.get("primaryLanguage") or {}).get("name") or ""
            detail = visibility + (f" // {language}" if language else "")
            rows.append(
                dict(
                    left=repository.get("name") or "Private repository",
                    mid=detail,
                    right=_activity_date(node.get("occurredAt")),
                )
            )
        repo_word = "REPOSITORY" if len(repository_nodes) == 1 else "REPOSITORIES"
        sections.append((f"CREATED {len(repository_nodes)} {repo_word}", rows))

    pull_requests = [
        node.get("pullRequest") or {}
        for node in (month.get("pullRequestContributions") or {}).get("nodes") or []
    ]
    if pull_requests:
        by_repository = {}
        for pull_request in pull_requests:
            repository = (pull_request.get("repository") or {}).get("name") or "Private repository"
            state = (pull_request.get("state") or "CLOSED").lower()
            if state not in {"open", "merged", "closed"}:
                state = "closed"
            counts = by_repository.setdefault(repository, {"open": 0, "merged": 0, "closed": 0})
            counts[state] += 1
        rows = []
        for repository, counts in list(by_repository.items())[:2]:
            pills = tuple(
                (f"{counts[state]} {state.upper()}", state)
                for state in ("open", "merged", "closed")
                if counts[state]
            )
            rows.append(dict(left=repository, pills=pills))
        pr_word = "PULL REQUEST" if len(pull_requests) == 1 else "PULL REQUESTS"
        repo_word = "REPOSITORY" if len(by_repository) == 1 else "REPOSITORIES"
        sections.append(
            (f"OPENED {len(pull_requests)} {pr_word} IN {len(by_repository)} {repo_word}", rows)
        )

    reviews = (month.get("pullRequestReviewContributions") or {}).get("nodes") or []
    if reviews:
        rows = []
        review_repositories = set()
        for node in reviews[:1]:
            pull_request = node.get("pullRequest") or {}
            repository = (pull_request.get("repository") or {}).get("name") or "Private repository"
            review_repositories.add(repository)
            rows.append(
                dict(
                    left=repository,
                    mid=_shorten(pull_request.get("title"), 44),
                    right=_activity_date(node.get("occurredAt")),
                )
            )
        review_word = "PULL REQUEST" if len(reviews) == 1 else "PULL REQUESTS"
        repo_word = "REPOSITORY" if len(review_repositories) == 1 else "REPOSITORIES"
        sections.append(
            (f"REVIEWED {len(reviews)} {review_word} IN {len(review_repositories)} {repo_word}", rows)
        )

    if not sections:
        return '<text x="72" y="1584" font-size="13px" fill="#8a93a6">No public activity this month.</text>'

    parts = []
    y = LOG_Y0
    for index, (title, rows) in enumerate(sections):
        if index:
            y += 14
        if y + 32 > LOG_MAX_Y:
            break
        parts.append(_log_head(y, title))
        y += 32
        for row in rows:
            if y > LOG_MAX_Y:
                break
            parts.append(_log_row(y, **row))
            y += 22
    return "\n".join(parts)


SVG_TEMPLATE = r"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="985" height="1962" viewBox="0 0 985 1962" font-family="ConsolasFallback,Consolas,monospace" font-size="16px">
<style>
@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback'; font-display: swap; size-adjust: 109%; }
text, tspan { white-space: pre; }
@keyframes sw-drop { 0% { transform: translateY(-96px); } 100% { transform: translateY(0); } }
@keyframes sw-swing { 0% { transform: rotate(-7deg); } 100% { transform: rotate(7deg); } }
@keyframes sw-strand { 0% { stroke-dashoffset: 12; } 100% { stroke-dashoffset: 0; } }
@keyframes sw-thwip { 0% { transform: scale(.2) rotate(-10deg); opacity: 0; } 6% { transform: scale(1.18) rotate(-10deg); opacity: 1; } 10% { transform: scale(.96) rotate(-10deg); } 14%, 74% { transform: scale(1) rotate(-10deg); opacity: 1; } 88%, 100% { transform: scale(.9) rotate(-10deg); opacity: 0; } }
@keyframes sw-bar { 0% { transform: scaleX(0); } 100% { transform: scaleX(1); } }
@keyframes sw-pop { 0% { transform: translateY(10px) scale(.7); opacity: 0; } 100% { transform: translateY(0) scale(1); opacity: 1; } }
@keyframes sw-blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
@keyframes sw-shimmer { 0%, 100% { opacity: .5; } 50% { opacity: 1; } }
</style>
<defs>
<pattern id="net" width="26" height="26" patternUnits="userSpaceOnUse">
<path d="M0 13 L13 0 L26 13 L13 26 Z" fill="none" stroke="#1d2433" stroke-width="0.7"></path>
</pattern>
<pattern id="dots" width="7" height="7" patternUnits="userSpaceOnUse">
<circle cx="1.6" cy="1.6" r="1.1" fill="#e0403a" opacity="0.16"></circle>
</pattern>
<pattern id="netLite" width="26" height="26" patternUnits="userSpaceOnUse">
<path d="M0 13 L13 0 L26 13 L13 26 Z" fill="none" stroke="#ffd9d4" stroke-width="0.8" opacity="0.32"></path>
</pattern>
<clipPath id="clipTitle"><rect x="12" y="12" width="961" height="126" rx="2"></rect></clipPath>
</defs>

<rect width="985" height="1962" fill="#0b0d14" rx="10"></rect>

<rect x="15" y="15" width="961" height="126" fill="#e0403a" opacity="0.35" rx="2"></rect>
<rect x="12" y="12" width="961" height="126" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<g clip-path="url(#clipTitle)">
<rect x="12" y="12" width="961" height="126" fill="url(#dots)"></rect>
<g style="animation:sw-shimmer 5s ease-in-out infinite">
<g stroke="#242c3d" stroke-width="1" fill="none">
<path d="M12 12 L182 12"></path>
<path d="M12 12 L169 77"></path>
<path d="M12 12 L132 132"></path>
<path d="M12 12 L77 169"></path>
<path d="M12 12 L12 182"></path>
<path d="M57 12 A45 45 0 0 1 12 57"></path>
<path d="M92 12 A80 80 0 0 1 12 92"></path>
<path d="M127 12 A115 115 0 0 1 12 127"></path>
<path d="M162 12 A150 150 0 0 1 12 162"></path>
</g>
</g>
</g>

<text x="39" y="79" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="58px" fill="#e0403a" opacity="0.55" letter-spacing="1">MATIAS PINHO</text>
<text x="36" y="76" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="58px" fill="#efe6d5" letter-spacing="1">MATIAS PINHO</text>
<text x="38" y="106" font-size="13px" fill="#8a93a6" letter-spacing="2.4">FRONTEND DEVELOPER // BUENOS AIRES, ARGENTINA</text>
<rect x="504" y="95" width="8" height="13" fill="#e0403a" style="animation:sw-blink 1.1s steps(1) infinite"></rect>

<g clip-path="url(#clipTitle)">
<g fill="none" stroke="#5b6478" stroke-width="1" stroke-linecap="round">
<path d="M600 13 L636 13"></path>
<path d="M600 13 L631.2 31"></path>
<path d="M600 13 L618 44.2"></path>
<path d="M600 13 L600 49"></path>
<path d="M600 13 L582 44.2"></path>
<path d="M600 13 L568.8 31"></path>
<path d="M600 13 L564 13"></path>
<path d="M614 13 Q611.5 16.1 612.1 20 Q608.4 21.4 607 25.1 Q603.1 24.5 600 27 Q596.9 24.5 593 25.1 Q591.6 21.4 587.9 20 Q588.5 16.1 586 13"></path>
<path d="M625 13 Q620.5 18.5 621.7 25.5 Q615 28 612.5 34.7 Q605.5 33.5 600 38 Q594.5 33.5 587.5 34.7 Q585 28 578.3 25.5 Q579.5 18.5 575 13"></path>
<path d="M636 13 Q629.6 20.9 631.2 31 Q621.6 34.6 618 44.2 Q607.9 42.6 600 49 Q592.1 42.6 582 44.2 Q578.4 34.6 568.8 31 Q570.4 20.9 564 13"></path>
</g>
<g style="animation:sw-drop 1.6s cubic-bezier(.3,1.2,.5,1) both">
<g style="transform-box:fill-box;transform-origin:50% 0;animation:sw-swing 3.4s ease-in-out 1.6s infinite alternate">
<line x1="600" y1="49" x2="600" y2="61" stroke="#5b6478" stroke-width="1" stroke-dasharray="12" style="animation:sw-strand 1.6s ease-out both"></line>
<text x="545" y="63" fill="#e0403a" font-size="13px" style="white-space:pre"><tspan x="545" y="63">     _ ___</tspan><tspan x="545" y="78">     \.\'.\</tspan><tspan x="545" y="93">      \'\'.\</tspan><tspan x="545" y="108">     __\.\:/_//</tspan><tspan x="545" y="123">    {{{{{(__(")</tspan></text>
</g>
</g>
</g>

<g style="transform-box:fill-box;transform-origin:50% 60%;animation:sw-thwip 5s cubic-bezier(.2,1.5,.4,1) 1.4s infinite">
<text x="948" y="96" text-anchor="end" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="46px" fill="#e0403a" stroke="#efe6d5" stroke-width="3.5" paint-order="stroke" letter-spacing="1">THWIP!</text>
</g>

<rect x="12" y="148" width="596" height="344" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="14" y="150" width="592" height="340" fill="url(#net)" opacity="0.5"></rect>
<rect x="36" y="172" width="10" height="10" fill="#e0403a"></rect>
<text x="54" y="182" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">SYSTEM</text>
<text x="36" y="212" font-size="15px" style="white-space:pre">
<tspan x="36" y="212"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">OS</tspan><tspan fill="#6f7a90">:........................ </tspan><tspan fill="#e4e1d8">Linux, Android</tspan></tspan>
<tspan x="36" y="233"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Location</tspan><tspan fill="#6f7a90">:.................. </tspan><tspan fill="#e4e1d8">Buenos Aires, Argentina</tspan></tspan>
<tspan x="36" y="254"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Host</tspan><tspan fill="#6f7a90">:...................... </tspan><tspan fill="#e4e1d8">G&amp;L Group</tspan></tspan>
<tspan x="36" y="275"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Role</tspan><tspan fill="#6f7a90">:...................... </tspan><tspan fill="#e4e1d8">Frontend Developer</tspan></tspan>
<tspan x="36" y="296"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Experience</tspan><tspan fill="#6f7a90">:................ </tspan><tspan fill="#e4e1d8">+2 years</tspan></tspan>
<tspan x="36" y="317"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">IDE</tspan><tspan fill="#6f7a90">:....................... </tspan><tspan fill="#e4e1d8">VSCode</tspan></tspan>
<tspan x="36" y="350"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Languages</tspan><tspan fill="#6f7a90">.</tspan><tspan fill="#e0403a">Programming</tspan><tspan fill="#6f7a90">:..... </tspan><tspan fill="#e4e1d8">JavaScript, TypeScript, Java</tspan></tspan>
<tspan x="36" y="371"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Languages</tspan><tspan fill="#6f7a90">.</tspan><tspan fill="#e0403a">Markup</tspan><tspan fill="#6f7a90">:.......... </tspan><tspan fill="#e4e1d8">HTML, CSS, SASS</tspan></tspan>
<tspan x="36" y="392"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Languages</tspan><tspan fill="#6f7a90">.</tspan><tspan fill="#e0403a">Real</tspan><tspan fill="#6f7a90">:............ </tspan><tspan fill="#e4e1d8">Spanish, English</tspan></tspan>
<tspan x="36" y="425"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Stack</tspan><tspan fill="#6f7a90">.</tspan><tspan fill="#e0403a">Frontend</tspan><tspan fill="#6f7a90">:............ </tspan><tspan fill="#e4e1d8">React, Angular, Astro, Tailwind</tspan></tspan>
<tspan x="36" y="446"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Stack</tspan><tspan fill="#6f7a90">.</tspan><tspan fill="#e0403a">Backend</tspan><tspan fill="#6f7a90">:............. </tspan><tspan fill="#e4e1d8">Node.js, Express, Jest</tspan></tspan>
<tspan x="36" y="467"><tspan fill="#6f7a90">. </tspan><tspan fill="#e0403a">Stack</tspan><tspan fill="#6f7a90">.</tspan><tspan fill="#e0403a">DB</tspan><tspan fill="#6f7a90">:.................. </tspan><tspan fill="#e4e1d8">MySQL, MongoDB</tspan></tspan>
</text>

<rect x="618" y="148" width="355" height="166" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="638" y="170" width="10" height="10" fill="#e0403a"></rect>
<text x="656" y="180" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">GITHUB STATS</text>
<text x="953" y="180" text-anchor="end" font-size="10.5px" fill="#6f7a90" letter-spacing="1.2">CONTRIBUTED: @@CONTRIB@@</text>
<g style="transform-box:fill-box;transform-origin:0% 100%;animation:sw-pop .5s ease-out .3s both">
<text x="638" y="228" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="36px" fill="#e0403a">@@REPOS@@</text>
</g>
<text x="638" y="244" font-size="10.5px" fill="#8a93a6" letter-spacing="1.8">REPOS</text>
<g style="transform-box:fill-box;transform-origin:0% 100%;animation:sw-pop .5s ease-out .45s both">
<text x="806" y="228" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="36px" fill="#e0403a">@@COMMITS@@</text>
</g>
<text x="806" y="244" font-size="10.5px" fill="#8a93a6" letter-spacing="1.8">COMMITS</text>
<g style="transform-box:fill-box;transform-origin:0% 100%;animation:sw-pop .5s ease-out .6s both">
<text x="638" y="282" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="36px" fill="#e0403a">@@FOLLOWERS@@</text>
</g>
<text x="638" y="298" font-size="10.5px" fill="#8a93a6" letter-spacing="1.8">FOLLOWERS</text>
<g style="transform-box:fill-box;transform-origin:0% 100%;animation:sw-pop .5s ease-out .75s both">
<text x="806" y="282" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="36px" fill="#e0403a">@@STARS@@</text>
</g>
<text x="806" y="298" font-size="10.5px" fill="#8a93a6" letter-spacing="1.8">STARS</text>

<rect x="618" y="324" width="355" height="168" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="638" y="342" width="10" height="10" fill="#e0403a"></rect>
<text x="656" y="352" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">CONTACT</text>
<a href="mailto:matiaspinho.dev@gmail.com" target="_blank">
<text x="638" y="374" font-size="10.5px" fill="#e0403a" letter-spacing="1.8">EMAIL</text>
<text x="638" y="391" font-size="13px" fill="#e4e1d8">matiaspinho.dev@gmail.com</text>
</a>
<a href="https://linkedin.com/in/matias-pinho" target="_blank">
<text x="638" y="415" font-size="10.5px" fill="#e0403a" letter-spacing="1.8">LINKEDIN</text>
<text x="638" y="432" font-size="13px" fill="#e4e1d8">matias-pinho</text>
</a>
<a href="https://matiaspinho-portfolio.vercel.app" target="_blank">
<text x="638" y="456" font-size="10.5px" fill="#e0403a" letter-spacing="1.8">PORTFOLIO</text>
<text x="638" y="473" font-size="13px" fill="#e4e1d8">matiaspinho-portfolio.vercel.app</text>
</a>

<rect x="12" y="502" width="596" height="196" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="14" y="504" width="592" height="192" fill="url(#net)" opacity="0.5"></rect>
<rect x="36" y="524" width="10" height="10" fill="#e0403a"></rect>
<text x="54" y="534" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">TOP LANGUAGES</text>
@@LANGS@@

<rect x="618" y="502" width="355" height="94" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="620" y="504" width="351" height="90" fill="url(#net)" opacity="0.5"></rect>
<rect x="638" y="518" width="10" height="10" fill="#e0403a"></rect>
<text x="656" y="528" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">PINNED REPOS</text>
@@REPOLIST@@

<rect x="621" y="609" width="355" height="92" fill="#7d1a15" rx="2"></rect>
<rect x="618" y="606" width="355" height="92" fill="#c9302a" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="620.5" y="608.5" width="350" height="87" fill="url(#netLite)"></rect>
<text x="795" y="646" text-anchor="middle" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="20px" fill="#efe6d5" stroke="#5c1310" stroke-width="3" paint-order="stroke" letter-spacing="0.6">YOU WILL BE WHAT YOU MUST BE,</text>
<text x="795" y="674" text-anchor="middle" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="20px" fill="#efe6d5" stroke="#5c1310" stroke-width="3" paint-order="stroke" letter-spacing="0.6">OR YOU WILL BE NOTHING.</text>
<rect x="12" y="712" width="961" height="266" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="14" y="714" width="957" height="262" fill="url(#net)" opacity="0.5"></rect>
<rect x="36" y="738" width="10" height="10" fill="#e0403a"></rect>
<text x="54" y="748" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">CONTRIBUTIONS</text>
<text x="949" y="748" text-anchor="end" font-size="10.5px" fill="#6f7a90" letter-spacing="1.2">@@TOTALCONTRIB@@ CONTRIBUTIONS // LAST 12 MONTHS</text>
<rect x="36" y="772" width="913" height="182" fill="#0b0d14" stroke="#efe6d5" stroke-width="1.5" rx="2"></rect>
<path d="M36 772 L64 772 L36 800 Z" fill="#e0403a" opacity="0.5"></path>
<path d="M949 954 L921 954 L949 926 Z" fill="#e0403a" opacity="0.5"></path>
@@CALENDAR@@
<g font-size="10.5px" fill="#6f7a90">
<text x="48" y="837">Mon</text><text x="48" y="869">Wed</text><text x="48" y="901">Fri</text>
</g>
<text x="770" y="942" text-anchor="end" font-size="10.5px" fill="#6f7a90" letter-spacing="1.2">LESS</text>
<rect x="780" y="931" width="13" height="13" rx="1.5" fill="#161a24"></rect>
<rect x="797" y="931" width="13" height="13" rx="1.5" fill="#4a1512"></rect>
<rect x="814" y="931" width="13" height="13" rx="1.5" fill="#8a221c"></rect>
<rect x="831" y="931" width="13" height="13" rx="1.5" fill="#c2332b"></rect>
<rect x="848" y="931" width="13" height="13" rx="1.5" fill="#ff5b52"></rect>
<text x="872" y="942" font-size="10.5px" fill="#6f7a90" letter-spacing="1.2">MORE</text>

<rect x="12" y="990" width="596" height="486" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="14" y="992" width="592" height="482" fill="url(#net)" opacity="0.5"></rect>
<rect x="36" y="1012" width="10" height="10" fill="#e0403a"></rect>
<text x="54" y="1022" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">PINNED REPOS</text>
<text x="584" y="1022" text-anchor="end" font-size="10.5px" fill="#6f7a90" letter-spacing="1.2">@@PINCOUNT@@ SELECTED</text>

@@PINNEDCARDS@@

<rect x="618" y="990" width="355" height="230" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="638" y="1012" width="10" height="10" fill="#e0403a"></rect>
<text x="656" y="1022" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">ACTIVITY MIX</text>
@@MIX@@

<rect x="618" y="1232" width="355" height="244" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="620" y="1234" width="351" height="240" fill="url(#net)" opacity="0.5"></rect>
<rect x="638" y="1254" width="10" height="10" fill="#e0403a"></rect>
<text x="656" y="1264" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">WEB-SLINGING STREAK</text>
@@STREAK@@
<line x1="638" y1="1422" x2="953" y2="1422" stroke="#2a3242" stroke-width="1"></line>
<text x="638" y="1444" font-size="10.5px" fill="#e0403a" letter-spacing="1.8">ORGANIZATIONS</text>
<text x="638" y="1464" font-size="13px" fill="#e4e1d8">Member of @@ORGS@@ organization(s)</text>

<rect x="12" y="1488" width="961" height="462" fill="#10131b" stroke="#efe6d5" stroke-width="2.5" rx="2"></rect>
<rect x="14" y="1490" width="957" height="458" fill="url(#net)" opacity="0.5"></rect>
<rect x="36" y="1510" width="10" height="10" fill="#e0403a"></rect>
<text x="54" y="1520" font-family="Impact, Haettenschweiler, 'Arial Black', sans-serif" font-size="19px" fill="#efe6d5" letter-spacing="1.6">ACTIVITY LOG</text>
<text x="949" y="1520" text-anchor="end" font-size="10.5px" fill="#6f7a90" letter-spacing="1.2">@@LOGMONTH@@</text>
<line x1="48" y1="1544" x2="48" y2="1930" stroke="#2a3242" stroke-width="1" stroke-dasharray="4 4"></line>

@@LOG@@
</svg>
"""


def build_svg(
    repos,
    stars,
    followers,
    commits,
    contributed,
    langs,
    pinned,
    cards,
    orgs,
    weeks,
    total_contributions,
    mix,
    month,
    month_label,
):
    svg = SVG_TEMPLATE
    for token, value in (
        ("@@REPOS@@", repos),
        ("@@COMMITS@@", commits),
        ("@@FOLLOWERS@@", followers),
        ("@@STARS@@", stars),
        ("@@CONTRIB@@", contributed),
        ("@@LANGS@@", lang_rows(langs)),
        ("@@REPOLIST@@", repo_rows(pinned)),
        ("@@TOTALCONTRIB@@", total_contributions),
        ("@@CALENDAR@@", calendar_cells(weeks)),
        ("@@PINCOUNT@@", len(cards)),
        ("@@PINNEDCARDS@@", pinned_cards(cards)),
        ("@@MIX@@", mix_rows(mix)),
        ("@@STREAK@@", streak_panel(streak_stats(weeks))),
        ("@@ORGS@@", orgs),
        ("@@LOGMONTH@@", month_label),
        ("@@LOG@@", activity_log(month)),
    ):
        svg = svg.replace(token, str(value))
    return svg


if __name__ == "__main__":
    if not TOKEN:
        print("GITHUB_TOKEN not set — aborting", file=sys.stderr)
        sys.exit(1)
    stats = fetch_stats()
    svg = build_svg(**stats)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dark_mode.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(
        "dark_mode.svg written — "
        f"{stats['repos']} repos, {stats['commits']} commits, "
        f"{stats['total_contributions']} contributions"
    )
