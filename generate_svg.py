#!/usr/bin/env python3
"""Regenerate dark_mode.svg (comic-panel theme) with live GitHub stats via the GraphQL API."""
import json, os, sys, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

USER = "MatiasPinho"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

DISPLAY_FONT = "Impact, Haettenschweiler, 'Arial Black', sans-serif"
BAR_X, BAR_W, BAR_H = 190, 310, 13
LANG_Y0, LANG_STEP = 572, 32
REPO_Y0, REPO_STEP, REPO_COUNT = 548, 18, 3
REPO_NAME_MAX = 30


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
        pushedAt
        isFork
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes { ... on Repository { name } }
    }
    repositoriesContributedTo(
      first: 1
      includeUserRepositories: false
      contributionTypes: [COMMIT, PULL_REQUEST]
    ) { totalCount }
    followers { totalCount }
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

    pinned = [n["name"] for n in u["pinnedItems"]["nodes"] if n]
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

    return dict(
        repos=u["repositories"]["totalCount"],
        stars=sum(n["stargazerCount"] for n in nodes),
        followers=u["followers"]["totalCount"],
        commits=all_time_commits(u["createdAt"]),
        contributed=u["repositoriesContributedTo"]["totalCount"],
        langs=langs,
        pinned=pinned,
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


SVG_TEMPLATE = r"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="985" height="710" viewBox="0 0 985 710" font-family="ConsolasFallback,Consolas,monospace" font-size="16px">
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

<rect width="985" height="710" fill="#0b0d14" rx="10"></rect>

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
</svg>
"""


def build_svg(repos, stars, followers, commits, contributed, langs, pinned):
    svg = SVG_TEMPLATE
    for token, value in (
        ("@@REPOS@@", repos),
        ("@@COMMITS@@", commits),
        ("@@FOLLOWERS@@", followers),
        ("@@STARS@@", stars),
        ("@@CONTRIB@@", contributed),
        ("@@LANGS@@", lang_rows(langs)),
        ("@@REPOLIST@@", repo_rows(pinned)),
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
    print(f"dark_mode.svg written — {stats}")
