#!/usr/bin/env python3
"""Regenerate dark_mode.svg with live GitHub stats via the GraphQL API."""
import json, os, sys, urllib.request

USER = "MatiasPinho"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


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
              nodes { stargazerCount }
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

    return dict(
        repos=u["repositories"]["totalCount"],
        stars=sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        followers=u["followers"]["totalCount"],
        commits=(
            u["contributionsCollection"]["totalCommitContributions"]
            + u["contributionsCollection"]["restrictedContributionsCount"]
        ),
        contributed=u["repositoriesContributedTo"]["totalCount"],
    )


def build_svg(repos, stars, followers, commits, contributed):
    return f"""\
<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     font-family="ConsolasFallback,Consolas,monospace" width="985px" height="530px" font-size="16px">
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

<rect width="985px" height="530px" fill="#101315" rx="12"/>

<!-- ASCII art — bee -->
<text x="15" y="30" fill="#de6145">
<tspan x="15" y="30" >                                             </tspan>
<tspan x="15" y="50" >                  o   ^   o                  </tspan>
<tspan x="15" y="70" >                (%%%%%%%%%%%)                </tspan>
<tspan x="15" y="90" >           ( / )(%%%%%%%%%%%)( \\ )           </tspan>
<tspan x="15" y="110">         ( / / )(%%%%%%%%%%%)( \\ \\ )         </tspan>
<tspan x="15" y="130">       ( / / / )(%%%%%%%%%%%)( \\ \\ \\ )       </tspan>
<tspan x="15" y="150">     ( / / / / )(%%%%%%%%%%%)( \\ \\ \\ \\ )     </tspan>
<tspan x="15" y="170">   ( / / / / / )(%%%%%%%%%%%)( \\ \\ \\ \\ \\ )  </tspan>
<tspan x="15" y="190">     ( / / / / )(%%%%%%%%%%%)( \\ \\ \\ \\ )     </tspan>
<tspan x="15" y="210">       ( / / / )(%%%%%%%%%%%)( \\ \\ \\ )       </tspan>
<tspan x="15" y="230">         ( / / )(%%%%%%%%%%%)( \\ \\ )         </tspan>
<tspan x="15" y="250">           ( / )(%%%%%%%%%%%)( \\ )           </tspan>
<tspan x="15" y="270">                (%%%%%%%%%%%)                </tspan>
<tspan x="15" y="290">                (%%%%%%%%%%%)                </tspan>
<tspan x="15" y="310">                 (%%%%%%%%%%)                </tspan>
<tspan x="15" y="330">                  (%%%%%%%%%)                </tspan>
<tspan x="15" y="350">                   (%%%%%%%)                 </tspan>
<tspan x="15" y="370">                    (%%%%%)                  </tspan>
<tspan x="15" y="390">                     (%%%)                   </tspan>
<tspan x="15" y="410">                      (%)                    </tspan>
<tspan x="15" y="430">                       !                     </tspan>
<tspan x="15" y="450">                                             </tspan>
<tspan x="15" y="470">                                             </tspan>
<tspan x="15" y="490">                                             </tspan>
<tspan x="15" y="510">                                             </tspan>
</text>

<!-- Info panel — static lines -->
<text x="390" y="30" fill="#cacccc">

<tspan x="390" y="30" font-weight="bold">matias@pinho</tspan><tspan fill="#565d60"> -———————————————————————————————————————————-—-</tspan>

<tspan x="390" y="50" ><tspan class="dot">. </tspan><tspan class="key">OS</tspan><tspan class="dot">:........................ </tspan><tspan class="val">Linux, Android</tspan></tspan>
<tspan x="390" y="70" ><tspan class="dot">. </tspan><tspan class="key">Location</tspan><tspan class="dot">:.................. </tspan><tspan class="val">Buenos Aires, Argentina</tspan></tspan>
<tspan x="390" y="90" ><tspan class="dot">. </tspan><tspan class="key">Host</tspan><tspan class="dot">:...................... </tspan><tspan class="val">G&amp;L Group</tspan></tspan>
<tspan x="390" y="110"><tspan class="dot">. </tspan><tspan class="key">Role</tspan><tspan class="dot">:...................... </tspan><tspan class="val">Frontend Developer</tspan></tspan>
<tspan x="390" y="130"><tspan class="dot">. </tspan><tspan class="key">Experience</tspan><tspan class="dot">:................ </tspan><tspan class="val">+2 years</tspan></tspan>
<tspan x="390" y="150"><tspan class="dot">. </tspan><tspan class="key">IDE</tspan><tspan class="dot">:....................... </tspan><tspan class="val">VSCode</tspan></tspan>
<tspan x="390" y="170"><tspan class="dot">. </tspan></tspan>

<tspan x="390" y="190"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Programming</tspan><tspan class="dot">:..... </tspan><tspan class="val">JavaScript, TypeScript, Java</tspan></tspan>
<tspan x="390" y="210"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Markup</tspan><tspan class="dot">:.......... </tspan><tspan class="val">HTML, CSS, SASS</tspan></tspan>
<tspan x="390" y="230"><tspan class="dot">. </tspan><tspan class="key">Languages</tspan><tspan class="dot">.</tspan><tspan class="key">Real</tspan><tspan class="dot">:............ </tspan><tspan class="val">Spanish, English</tspan></tspan>
<tspan x="390" y="250"><tspan class="dot">. </tspan></tspan>

<tspan x="390" y="270"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">Frontend</tspan><tspan class="dot">:............ </tspan><tspan class="val">React, Angular, Astro, Tailwind</tspan></tspan>
<tspan x="390" y="290"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">Backend</tspan><tspan class="dot">:............. </tspan><tspan class="val">Node.js, Express, Jest</tspan></tspan>
<tspan x="390" y="310"><tspan class="dot">. </tspan><tspan class="key">Stack</tspan><tspan class="dot">.</tspan><tspan class="key">DB</tspan><tspan class="dot">:.................. </tspan><tspan class="val">MySQL, MongoDB</tspan></tspan>

<tspan x="390" y="330" fill="#565d60">- Contact -——————————————————————————————————————————————-—-</tspan>

</text>

<!-- Clickable contact links -->
<text x="390" font-size="16px">
  <a xlink:href="mailto:matiaspinho.dev@gmail.com" target="_blank">
    <tspan x="390" y="350"><tspan class="dot">. </tspan><tspan class="key">Email</tspan><tspan class="dot">:..................... </tspan><tspan class="val">matiaspinho.dev@gmail.com</tspan></tspan>
  </a>
  <a xlink:href="https://linkedin.com/in/matias-pinho" target="_blank">
    <tspan x="390" y="370"><tspan class="dot">. </tspan><tspan class="key">LinkedIn</tspan><tspan class="dot">:.................. </tspan><tspan class="val">matias-pinho</tspan></tspan>
  </a>
  <a xlink:href="https://matiaspinho-portfolio.vercel.app" target="_blank">
    <tspan x="390" y="390"><tspan class="dot">. </tspan><tspan class="key">Portfolio</tspan><tspan class="dot">:................. </tspan><tspan class="val">matiaspinho-portfolio.vercel.app</tspan></tspan>
  </a>
</text>

<!-- GitHub Stats — regenerated by generate_svg.py -->
<text x="390" font-size="16px" fill="#cacccc">
<tspan x="390" y="410" fill="#565d60">- GitHub Stats -—————————————————————————————————————————-—-</tspan>
<tspan x="390" y="430"><tspan class="dot">. </tspan><tspan class="key">Repos</tspan><tspan class="dot">:..... </tspan><tspan class="val">{repos}</tspan><tspan class="dot"> {{</tspan><tspan class="key">Contributed</tspan><tspan class="dot">: </tspan><tspan class="val">{contributed}</tspan><tspan class="dot">}} | </tspan><tspan class="key">Followers</tspan><tspan class="dot">:......... </tspan><tspan class="val">{followers}</tspan></tspan>
<tspan x="390" y="450"><tspan class="dot">. </tspan><tspan class="key">Commits</tspan><tspan class="dot">:................. </tspan><tspan class="val">{commits}</tspan><tspan class="dot"> | </tspan><tspan class="key">Stars</tspan><tspan class="dot">:............. </tspan><tspan class="val">{stars}</tspan></tspan>
<tspan x="390" y="470"><tspan class="dot">. </tspan></tspan>
</text>

</svg>
"""


if __name__ == "__main__":
    if not TOKEN:
        print("GITHUB_TOKEN not set — aborting", file=sys.stderr)
        sys.exit(1)
    stats = fetch_stats()
    svg = build_svg(**stats)
    out = os.path.join(os.path.dirname(__file__), "dark_mode.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"dark_mode.svg written — {stats}")
