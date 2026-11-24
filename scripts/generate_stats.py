#!/usr/bin/env python3
"""Generate assets/stats.svg (themed GitHub activity card) from the GitHub GraphQL API.

Usage:
    LOGIN=MarcusVinicius44 GITHUB_TOKEN=... python scripts/generate_stats.py --out assets/stats.svg
    python scripts/generate_stats.py --fixture fixture.json --out assets/stats.svg   (offline preview)

Token: STATS_TOKEN (optional personal token, read:user + repo) is preferred over GITHUB_TOKEN.
With a personal token the card also counts private repos; with the default GITHUB_TOKEN it sees
what the public profile shows (enable "Include private contributions on my profile" in settings).
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape

G = "#0BD400"
BG = "#050505"
TXT = "#F0F0F0"
DIM = "#aaaaaa"
MONO = "'JetBrains Mono','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
LEVELS = ["#111a11", "#0b4f08", "#0a7d06", "#09b000", "#0BD400"]
LANG_COLORS = ["#0BD400", "#09a800", "#078000", "#056000", "#034200"]

QUERY = """
query($login:String!){
  user(login:$login){
    repositories(ownerAffiliations:OWNER,isFork:false,first:100){
      totalCount
      nodes{ languages(first:6,orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name } } } }
    }
    contributionsCollection{
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ contributionCount date } }
      }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {payload.get('errors') or payload}")
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    sizes = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    tot = sum(sizes.values()) or 1
    langs = sorted(((n, s * 100 / tot) for n, s in sizes.items()), key=lambda x: -x[1])[:5]
    return {
        "total": cal["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "issues": cc["totalIssueContributions"],
        "weeks": [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]]
                  for w in cal["weeks"]],
        "langs": langs,
    }


def level(count, mx):
    if count <= 0:
        return 0
    r = count / mx
    return 1 if r <= .25 else 2 if r <= .5 else 3 if r <= .75 else 4


def fmt(v):
    return "--" if v is None else f"{v:,}"


def render(d, out):
    W, H = 1100, 384
    weeks = d["weeks"]
    mx = max((c for w in weeks for _, c in w), default=1) or 1
    X0, Y0, P, C = 330, 92, 13.6, 11

    cells, months, prev = [], [], None
    for i, w in enumerate(weeks):
        for j, (date, cnt) in enumerate(w):
            cells.append(f'<rect x="{X0 + i * P:.1f}" y="{Y0 + j * P:.1f}" width="{C}" height="{C}" '
                         f'rx="2" fill="{LEVELS[level(cnt, mx)]}"/>')
        m = dt.date.fromisoformat(w[0][0]).strftime("%b")
        if m != prev and i < len(weeks) - 2:
            months.append(f'<text x="{X0 + i * P:.1f}" y="{Y0 - 10}" font-family="{MONO}" '
                          f'font-size="11" fill="{DIM}">{m}</text>')
        prev = m

    tiles = [("commits", d.get("commits")), ("pull requests", d.get("prs")),
             ("code reviews", d.get("reviews")), ("issues", d.get("issues"))]
    tile_svg = []
    for k, (lab, val) in enumerate(tiles):
        tx, ty = 48 + (k % 2) * 160, 206 + (k // 2) * 52
        tile_svg.append(
            f'<text x="{tx}" y="{ty}" font-family="{MONO}" font-size="22" font-weight="700" fill="{TXT}">{fmt(val)}</text>'
            f'<text x="{tx}" y="{ty + 18}" font-family="{MONO}" font-size="12" fill="{DIM}">{lab}</text>')

    legend_y = Y0 + 7 * P + 16
    lx = X0 + 53 * P - 5 * 15 - 70
    legend = [f'<text x="{lx}" y="{legend_y + 9}" font-family="{MONO}" font-size="11" fill="{DIM}">less</text>']
    for k, col in enumerate(LEVELS):
        legend.append(f'<rect x="{lx + 34 + k * 15}" y="{legend_y}" width="11" height="11" rx="2" fill="{col}"/>')
    legend.append(f'<text x="{lx + 34 + 5 * 15 + 4}" y="{legend_y + 9}" font-family="{MONO}" font-size="11" fill="{DIM}">more</text>')

    # languages
    BX, BW = 48, 1004
    langs = d.get("langs") or []
    bar, lab = [], []
    tot = sum(p for _, p in langs) or 1
    x = BX
    for k, (name, pct) in enumerate(langs):
        w = max(4, BW * pct / tot - 2)
        bar.append(f'<rect x="{x:.1f}" y="322" width="{w:.1f}" height="10" rx="3" fill="{LANG_COLORS[k]}"/>')
        x += w + 2
        lx2 = 48 + k * 200
        lab.append(f'<rect x="{lx2}" y="348" width="9" height="9" rx="2" fill="{LANG_COLORS[k]}"/>'
                   f'<text x="{lx2 + 16}" y="357" font-family="{MONO}" font-size="13" fill="{TXT}">'
                   f'{escape(name)} <tspan fill="{DIM}">{pct:.1f}%</tspan></text>')

    updated = d.get("updated") or dt.date.today().isoformat()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub activity: {d['total']} contributions in the last year">
  <defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="{G}" stroke-opacity=".05"/></pattern></defs>
  <rect width="{W}" height="{H}" rx="14" fill="{BG}"/>
  <rect width="{W}" height="{H}" rx="14" fill="url(#grid)"/>
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{G}" stroke-opacity=".25"/>

  <text x="48" y="44" font-family="{MONO}" font-size="14" fill="{G}">$ gh activity --last-year</text>
  <text x="48" y="122" font-family="{MONO}" font-size="64" font-weight="700" fill="{G}">{d['total']:,}</text>
  <text x="48" y="150" font-family="{MONO}" font-size="14" fill="{DIM}">contributions in the last year</text>
  {''.join(tile_svg)}

  {''.join(months)}
  {''.join(cells)}
  {''.join(legend)}

  <text x="48" y="304" font-family="{MONO}" font-size="12" fill="{DIM}">top languages · public repositories</text>
  {''.join(bar)}
  {''.join(lab)}
  <text x="{W - 48}" y="44" text-anchor="end" font-family="{MONO}" font-size="11" fill="#666">updated {updated}</text>
</svg>
"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/stats.svg")
    ap.add_argument("--fixture")
    a = ap.parse_args()
    if a.fixture:
        d = json.load(open(a.fixture))
        d["weeks"] = [[tuple(x) for x in w] for w in d["weeks"]]
        d["langs"] = [tuple(x) for x in d["langs"]]
    else:
        login = os.environ.get("LOGIN") or sys.exit("set LOGIN")
        token = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN") or sys.exit("set GITHUB_TOKEN")
        d = fetch(login, token)
    render(d, a.out)


if __name__ == "__main__":
    main()
