#!/usr/bin/env python3
"""Regenerate dark_mode.svg with live GitHub stats via the GraphQL API."""
import json, os, sys, urllib.request
from collections import defaultdict

USER = "MatiasPinho"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

PALETTE_ROW1 = ["#101315", "#565d60", "#9fa5a9", "#d9dbdc", "#798186", "#aeaeae", "#707070", "#cbc2be"]
PALETTE_ROW2 = ["#4b4e55", "#de6145", "#343d41", "#c9c2b4", "#5d6367", "#9a9a9a", "#707070", "#a5aeb4"]

COL1_X = 15    # bee
COL2_X = 395   # system info + contact + github stats + top languages
SVG_W   = 990
SVG_H   = 755


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


def lang_tspan(name, pct, y, col, x):
    dots = "." * (col - len(name) + 3)
    bar = make_bar(pct)
    n = len(bar) - len(bar.lstrip("▓"))
    filled, empty = bar[:n], bar[n:]
    return (
        f'<tspan x="{x}" y="{y}">'
        f'<tspan class="dot">. </tspan>'
        f'<tspan class="key">{name}</tspan>'
        f'<tspan class="dot">:{dots} </tspan>'
        f'<tspan class="key">{filled}</tspan>'
        f'<tspan fill="#343d41">{empty}</tspan>'
        f'<tspan class="dot">  </tspan>'
        f'<tspan class="val">{pct}%</tspan>'
        f'</tspan>'
    )


def stat_tspan(label, value, y, x=COL2_X, col=13):
    dots = "." * (col - len(label))
    return (
        f'<tspan x="{x}" y="{y}">'
        f'<tspan class="dot">. </tspan>'
        f'<tspan class="key">{label}</tspan>'
        f'<tspan class="dot">:{dots} </tspan>'
        f'<tspan class="val">{value}</tspan>'
        f'</tspan>'
    )


def palette_rects(cx=SVG_W // 2):
    w, h, gap, rx = 30, 14, 4, 2
    step = w + gap
    n = len(PALETTE_ROW1)
    total = (n - 1) * step + w
    x0 = cx - total // 2
    lines = []
    for row_y, row in ((690, PALETTE_ROW1), (708, PALETTE_ROW2)):
        for i, color in enumerate(row):
            x = x0 + i * step
            lines.append(
                f'<rect x="{x}" y="{row_y}" width="{w}" height="{h}" '
                f'fill="{color}" stroke="#1e2427" stroke-width="0.5" rx="{rx}"/>'
            )
    return "\n".join(lines)


def build_svg(repos, stars, followers, commits, contributed, langs):
    col = max((len(name) for name, _ in langs), default=8)
    col = max(col, 8)

    # Stats tspans (y=450–530)
    stat_block = "\n".join([
        stat_tspan("Repos",       repos,       450),
        stat_tspan("Stars",       stars,       470),
        stat_tspan("Commits",     commits,     490),
        stat_tspan("Followers",   followers,   510),
        stat_tspan("Contributed", contributed, 530),
    ])

    # Language bar tspans (y=590–650)
    lang_lines = []
    for idx, (name, pct) in enumerate(langs):
        lang_lines.append(lang_tspan(name, pct, 590 + idx * 20, col, COL2_X))
    for idx in range(len(langs), 4):
        lang_lines.append(
            f'<tspan x="{COL2_X}" y="{590 + idx * 20}">'
            f'<tspan class="dot">. </tspan></tspan>'
        )
    lang_block = "\n".join(lang_lines)

    pal = palette_rects()

    return f"""\
<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     font-family="ConsolasFallback,Consolas,monospace" width="{SVG_W}px" height="{SVG_H}px" font-size="16px">
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
text, tspan {{ white-space: pre; }}
</style>

<rect width="{SVG_W}px" height="{SVG_H}px" fill="#101315" rx="12"/>

<!-- Column 1 — bee -->
<text x="{COL1_X}" y="30" fill="#de6145">
<tspan x="{COL1_X}" y="30" >                                             </tspan>
<tspan x="{COL1_X}" y="50" >                  o   ^   o                  </tspan>
<tspan x="{COL1_X}" y="70" >                (%%%%%%%%%%%)                </tspan>
<tspan x="{COL1_X}" y="90" >           ( / )(%%%%%%%%%%%)( \\ )           </tspan>
<tspan x="{COL1_X}" y="110">         ( / / )(%%%%%%%%%%%)( \\ \\ )         </tspan>
<tspan x="{COL1_X}" y="130">       ( / / / )(%%%%%%%%%%%)( \\ \\ \\ )       </tspan>
<tspan x="{COL1_X}" y="150">     ( / / / / )(%%%%%%%%%%%)( \\ \\ \\ \\ )     </tspan>
<tspan x="{COL1_X}" y="170">   ( / / / / / )(%%%%%%%%%%%)( \\ \\ \\ \\ \\ )  </tspan>
<tspan x="{COL1_X}" y="190">     ( / / / / )(%%%%%%%%%%%)( \\ \\ \\ \\ )     </tspan>
<tspan x="{COL1_X}" y="210">       ( / / / )(%%%%%%%%%%%)( \\ \\ \\ )       </tspan>
<tspan x="{COL1_X}" y="230">         ( / / )(%%%%%%%%%%%)( \\ \\ )         </tspan>
<tspan x="{COL1_X}" y="250">           ( / )(%%%%%%%%%%%)( \\ )           </tspan>
<tspan x="{COL1_X}" y="270">                (%%%%%%%%%%%)                </tspan>
<tspan x="{COL1_X}" y="290">                (%%%%%%%%%%%)                </tspan>
<tspan x="{COL1_X}" y="310">                 (%%%%%%%%%%)                </tspan>
<tspan x="{COL1_X}" y="330">                  (%%%%%%%%%)                </tspan>
<tspan x="{COL1_X}" y="350">                   (%%%%%%%)                 </tspan>
<tspan x="{COL1_X}" y="370">                    (%%%%%)                  </tspan>
<tspan x="{COL1_X}" y="390">                     (%%%)                   </tspan>
<tspan x="{COL1_X}" y="410">                      (%)                    </tspan>
<tspan x="{COL1_X}" y="430">                       !                     </tspan>
<tspan x="{COL1_X}" y="450">                                             </tspan>
<tspan x="{COL1_X}" y="470">                                             </tspan>
</text>

<!-- Column 2 — system info -->
<text x="{COL2_X}" y="30" fill="#cacccc">

<tspan x="{COL2_X}" y="30" font-weight="bold">matias@pinho</tspan><tspan fill="#565d60"> -———————————————————————————————————————————————————————————————————————-—-</tspan>

<tspan x="{COL2_X}" y="50" ><tspan class="dot">. </tspan><tspan class="key">OS</tspan><tspan class="dot">:........................ </tspan><tspan class="val">Linux, Android</tspan></tspan>
<tspan x="{COL2_X}" y="70" ><tspan class="dot">. </tspan><tspan class="key">Location</tspan><tspan class="dot">:.................. </tspan><tspan class="val">Buenos Aires, Argentina</tspan></tspan>
<tspan x="{COL2_X}" y="90" ><tspan class="dot">. </tspan><tspan class="key">Host</tspan><tspan class="dot">:...................... </tspan><tspan class="val">G&amp;L Group</tspan></tspan>
<tspan x="{COL2_X}" y="110"><tspan class="dot">. </tspan><tspan class="key">Role</tspan><tspan class="dot">:...................... </tspan><tspan class="val">Frontend Developer</tspan></tspan>
<tspan x="{COL2_X}" y="130"><tspan class="dot">. </tspan><tspan class="key">Experience</tspan><tspan class="dot">:................ </tspan><tspan class="val">+2 years</tspan></tspan>
<tspan x="{COL2_X}" y="150"><tspan class="dot">. </tspan><tspan class="key">IDE</tspan><tspan class="dot">:....................... </tspan><tspan class="val">VSCode</tspan></tspan>
<tspan x="{COL2_X}" y="170"><tspan class="dot">. </tspan></tspan>

<tspan x="{COL2_X}" y="190"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Programming</tspan><tspan class="dot">:..... </tspan><tspan class="val">JavaScript, TypeScript, Java</tspan></tspan>
<tspan x="{COL2_X}" y="210"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Markup</tspan><tspan class="dot">:.......... </tspan><tspan class="val">HTML, CSS, SASS</tspan></tspan>
<tspan x="{COL2_X}" y="230"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Real</tspan><tspan class="dot">:............ </tspan><tspan class="val">Spanish, English</tspan></tspan>
<tspan x="{COL2_X}" y="250"><tspan class="dot">. </tspan></tspan>

<tspan x="{COL2_X}" y="270"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">Frontend</tspan><tspan class="dot">:............ </tspan><tspan class="val">React, Angular, Astro, Tailwind</tspan></tspan>
<tspan x="{COL2_X}" y="290"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">Backend</tspan><tspan class="dot">:............. </tspan><tspan class="val">Node.js, Express, Jest</tspan></tspan>
<tspan x="{COL2_X}" y="310"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">DB</tspan><tspan class="dot">:.................. </tspan><tspan class="val">MySQL, MongoDB</tspan></tspan>

<tspan x="{COL2_X}" y="330" fill="#565d60">- Contact -——————————————————————————————————————————————-—-</tspan>

</text>

<!-- Column 2 — clickable contact links -->
<text x="{COL2_X}" font-size="16px">
  <a xlink:href="mailto:matiaspinho.dev@gmail.com" target="_blank">
    <tspan x="{COL2_X}" y="350"><tspan class="dot">. </tspan><tspan class="key">Email</tspan><tspan class="dot">:..................... </tspan><tspan class="val">matiaspinho.dev@gmail.com</tspan></tspan>
  </a>
  <a xlink:href="https://linkedin.com/in/matias-pinho" target="_blank">
    <tspan x="{COL2_X}" y="370"><tspan class="dot">. </tspan><tspan class="key">LinkedIn</tspan><tspan class="dot">:.................. </tspan><tspan class="val">matias-pinho</tspan></tspan>
  </a>
  <a xlink:href="https://matiaspinho-portfolio.vercel.app" target="_blank">
    <tspan x="{COL2_X}" y="390"><tspan class="dot">. </tspan><tspan class="key">Portfolio</tspan><tspan class="dot">:................. </tspan><tspan class="val">matiaspinho-portfolio.vercel.app</tspan></tspan>
  </a>
</text>

<!-- Column 2 — GitHub stats -->
<text x="{COL2_X}" font-size="16px" fill="#cacccc">
<tspan x="{COL2_X}" y="430" fill="#565d60">- GitHub Stats -————————————</tspan>
{stat_block}
<tspan x="{COL2_X}" y="550"><tspan class="dot">. </tspan></tspan>
<tspan x="{COL2_X}" y="570" fill="#565d60">- Top Languages -———————————</tspan>
{lang_block}
<tspan x="{COL2_X}" y="670"><tspan class="dot">. </tspan></tspan>
</text>

<!-- Theme palette -->
{pal}

<!-- Quote -->
<text x="{SVG_W // 2}" y="730" text-anchor="middle" font-size="14px" style="white-space:normal"><tspan fill="#de6145">&gt;</tspan><tspan fill="#565d60"> You will be what you must be, or you will be nothing.</tspan></text>

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
