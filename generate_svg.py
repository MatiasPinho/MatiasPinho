#!/usr/bin/env python3
"""Regenerate dark_mode.svg with live GitHub stats via the GraphQL API."""
import json, os, sys, urllib.request
from collections import defaultdict

USER = "MatiasPinho"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

PALETTE_ROW1 = ["#101315", "#565d60", "#9fa5a9", "#d9dbdc", "#798186", "#aeaeae", "#707070", "#cbc2be"]
PALETTE_ROW2 = ["#4b4e55", "#de6145", "#343d41", "#c9c2b4", "#5d6367", "#9a9a9a", "#707070", "#a5aeb4"]


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


def fetch_stats():
    u = gql(
        """
        query($login: String!) {
          user(login: $login) {
            repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
              totalCount
              nodes {
                stargazerCount
                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                  edges { size node { name } }
                }
              }
            }
            repositoriesContributedTo(
              first: 1
              includeUserRepositories: false
              contributionTypes: [COMMIT, PULL_REQUEST]
            ) { totalCount }
            followers { totalCount }
            contributionsCollection {
              totalCommitContributions
              restrictedContributionsCount
            }
          }
        }
        """,
        {"login": USER},
    )["user"]

    nodes = u["repositories"]["nodes"]

    # Aggregate language byte sizes across all repos
    lang_sizes = defaultdict(int)
    for repo in nodes:
        for edge in repo.get("languages", {}).get("edges", []):
            lang_sizes[edge["node"]["name"]] += edge["size"]

    total_bytes = sum(lang_sizes.values()) or 1
    top = sorted(lang_sizes.items(), key=lambda x: -x[1])[:4]
    langs = [(name, round(size * 100 / total_bytes)) for name, size in top] or [("N/A", 100)]

    return dict(
        repos=u["repositories"]["totalCount"],
        stars=sum(n["stargazerCount"] for n in nodes),
        followers=u["followers"]["totalCount"],
        commits=(
            u["contributionsCollection"]["totalCommitContributions"]
            + u["contributionsCollection"]["restrictedContributionsCount"]
        ),
        contributed=u["repositoriesContributedTo"]["totalCount"],
        langs=langs,
    )


def make_bar(pct):
    filled = max(0, min(10, round(pct / 10)))
    return "▓" * filled + "░" * (10 - filled)


def lang_tspan(name, pct, y, col):
    """col = fixed column width for the name field (for alignment)."""
    dots = "." * (col - len(name) + 3)
    bar = make_bar(pct)
    n_filled = len(bar) - len(bar.lstrip("▓"))
    filled_part = bar[:n_filled]
    empty_part = bar[n_filled:]
    return (
        f'<tspan x="390" y="{y}">'
        f'<tspan class="dot">. </tspan>'
        f'<tspan class="key">{name}</tspan>'
        f'<tspan class="dot">:{dots} </tspan>'
        f'<tspan class="key">{filled_part}</tspan>'
        f'<tspan fill="#343d41">{empty_part}</tspan>'
        f'<tspan class="dot">  </tspan>'
        f'<tspan class="val">{pct}%</tspan>'
        f'</tspan>'
    )


def palette_rects():
    w, h, gap, rx = 30, 14, 4, 2
    step = w + gap
    lines = []
    for row_y, row in ((632, PALETTE_ROW1), (650, PALETTE_ROW2)):
        for i, color in enumerate(row):
            x = 390 + i * step
            lines.append(
                f'<rect x="{x}" y="{row_y}" width="{w}" height="{h}" '
                f'fill="{color}" stroke="#1e2427" stroke-width="0.5" rx="{rx}"/>'
            )
    return "\n".join(lines)


def build_svg(repos, stars, followers, commits, contributed, langs):
    col = max((len(name) for name, _ in langs), default=8)
    col = max(col, 8)

    lang_lines = []
    for idx, (name, pct) in enumerate(langs):
        lang_lines.append(lang_tspan(name, pct, 550 + idx * 20, col))

    lang_block = "\n".join(lang_lines)
    pal = palette_rects()

    return f"""\
<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     font-family="ConsolasFallback,Consolas,monospace" width="985px" height="710px" font-size="16px">
<style>
@font-face {{
  src: local('Consolas'), local('Consolas Bold');
  font-family: 'ConsolasFallback';
  font-display: swap;
  -webkit-size-adjust: 109%;
  size-adjust: 109%;
}}
.key {{ fill: #de6145; }}
.val {{ fill: #cacccc; }}
.dot {{ fill: #798186; }}
.info-panel text > tspan[fill="#565d60"] {{ display: none; }}
text, tspan {{ white-space: pre; }}
</style>

<rect width="985px" height="710px" fill="#101315" rx="12"/>

<!-- ASCII art -->
<text x="95" y="250" fill="#de6145" font-size="22px">
<tspan x="95" y="250">     _ ___</tspan>
<tspan x="95" y="278">     \\.\\'.\\</tspan>
<tspan x="95" y="306">      \\'\\'.\\</tspan>
<tspan x="95" y="334">     __\\.\\:/_//</tspan>
<tspan x="95" y="362">    {{{{{{{{{{(__(")</tspan>
<tspan x="95" y="390">jgs `~~~~ &gt;&gt;&gt;^</tspan>
</text>

<g class="info-panel" transform="translate(-55 0)">
<g fill="#565d60" stroke="#565d60" stroke-width="1">
  <line x1="500" y1="25" x2="950" y2="25"/>
  <text x="390" y="350" stroke="none">- Contact</text><line x1="535" y1="345" x2="950" y2="345"/>
  <text x="390" y="450" stroke="none">- GitHub Stats</text><line x1="535" y1="445" x2="950" y2="445"/>
  <text x="390" y="530" stroke="none">- Top Languages</text><line x1="535" y1="525" x2="950" y2="525"/>
</g>
<!-- Info panel -->
<text x="390" y="30" fill="#cacccc">

<tspan x="390" y="30" font-weight="bold">matias@pinho</tspan><tspan fill="#565d60"> -———————————————————————————————————————————-—-</tspan>

<tspan x="390" y="50" ><tspan class="dot">. </tspan><tspan class="key">OS</tspan><tspan class="dot">:........................ </tspan><tspan class="val">Linux, Android</tspan></tspan>
<tspan x="390" y="70" ><tspan class="dot">. </tspan><tspan class="key">Location</tspan><tspan class="dot">:.................. </tspan><tspan class="val">Buenos Aires, Argentina</tspan></tspan>
<tspan x="390" y="90" ><tspan class="dot">. </tspan><tspan class="key">Host</tspan><tspan class="dot">:...................... </tspan><tspan class="val">G&amp;L Group</tspan></tspan>
<tspan x="390" y="110"><tspan class="dot">. </tspan><tspan class="key">Role</tspan><tspan class="dot">:...................... </tspan><tspan class="val">Frontend Developer</tspan></tspan>
<tspan x="390" y="130"><tspan class="dot">. </tspan><tspan class="key">Experience</tspan><tspan class="dot">:................ </tspan><tspan class="val">+2 years</tspan></tspan>
<tspan x="390" y="150"><tspan class="dot">. </tspan><tspan class="key">IDE</tspan><tspan class="dot">:....................... </tspan><tspan class="val">VSCode</tspan></tspan>
<tspan x="390" y="190"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Programming</tspan><tspan class="dot">:..... </tspan><tspan class="val">JavaScript, TypeScript, Java</tspan></tspan>
<tspan x="390" y="210"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Markup</tspan><tspan class="dot">:.......... </tspan><tspan class="val">HTML, CSS, SASS</tspan></tspan>
<tspan x="390" y="230"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Real</tspan><tspan class="dot">:............ </tspan><tspan class="val">Spanish, English</tspan></tspan>
<tspan x="390" y="270"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">Frontend</tspan><tspan class="dot">:............ </tspan><tspan class="val">React, Angular, Astro, Tailwind</tspan></tspan>
<tspan x="390" y="290"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">Backend</tspan><tspan class="dot">:............. </tspan><tspan class="val">Node.js, Express, Jest</tspan></tspan>
<tspan x="390" y="310"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">DB</tspan><tspan class="dot">:.................. </tspan><tspan class="val">MySQL, MongoDB</tspan></tspan>

<tspan x="390" y="330" fill="#565d60">- Contact -——————————————————————————————————————————————-—-</tspan>

</text>

<!-- Clickable contact links -->
<text x="390" font-size="16px">
  <a xlink:href="mailto:matiaspinho.dev@gmail.com" target="_blank">
    <tspan x="390" y="370"><tspan class="dot">. </tspan><tspan class="key">Email</tspan><tspan class="dot">:..................... </tspan><tspan class="val">matiaspinho.dev@gmail.com</tspan></tspan>
  </a>
  <a xlink:href="https://linkedin.com/in/matias-pinho" target="_blank">
    <tspan x="390" y="390"><tspan class="dot">. </tspan><tspan class="key">LinkedIn</tspan><tspan class="dot">:.................. </tspan><tspan class="val">matias-pinho</tspan></tspan>
  </a>
  <a xlink:href="https://matiaspinho-portfolio.vercel.app" target="_blank">
    <tspan x="390" y="410"><tspan class="dot">. </tspan><tspan class="key">Portfolio</tspan><tspan class="dot">:................. </tspan><tspan class="val">matiaspinho-portfolio.vercel.app</tspan></tspan>
  </a>
</text>

<!-- GitHub Stats -->
<text x="390" font-size="16px" fill="#cacccc">
<tspan x="390" y="410" fill="#565d60">- GitHub Stats -—————————————————————————————————————————-—-</tspan>
<tspan x="390" y="470"><tspan class="dot">. </tspan><tspan class="key">Repos</tspan><tspan class="dot">:..... </tspan><tspan class="val">{repos}</tspan><tspan class="dot"> {{</tspan><tspan class="key">Contributed</tspan><tspan class="dot">: </tspan><tspan class="val">{contributed}</tspan><tspan class="dot">}} | </tspan><tspan class="key">Followers</tspan><tspan class="dot">:......... </tspan><tspan class="val">{followers}</tspan></tspan>
<tspan x="390" y="490"><tspan class="dot">. </tspan><tspan class="key">Commits</tspan><tspan class="dot">:................. </tspan><tspan class="val">{commits}</tspan><tspan class="dot"> | </tspan><tspan class="key">Stars</tspan><tspan class="dot">:............. </tspan><tspan class="val">{stars}</tspan></tspan>
</text>

<!-- Top Languages -->
<text x="390" font-size="16px" fill="#cacccc">
<tspan x="390" y="490" fill="#565d60">- Top Languages -—————————————————————————————————————————-—-</tspan>
{lang_block}
</text>

<!-- Theme palette -->
{pal}
</g>

<!-- Quote -->
<text x="492" y="690" text-anchor="middle" font-size="14px" style="white-space:normal"><tspan fill="#de6145">&gt;</tspan><tspan fill="#565d60"> You will be what you must be, or you will be nothing.</tspan></text>

</svg>
"""


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
