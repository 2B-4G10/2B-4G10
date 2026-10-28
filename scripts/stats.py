"""Builds the profile's live cards from the GitHub API.

Writes to the folder given as the first argument:
  downloads.json            shields.io endpoint: release downloads across all public repos
  languages-{dark,light}.svg  top languages, by bytes of code in my public repos
  overview-{dark,light}.svg   downloads, stars, repos and followers at a glance

Settings come from the environment:
  USER_LOGIN    whose profile this is
  EXTRA_REPOS   other repos whose release downloads count too (comma-separated owner/name)
  SKIP_LANGS    what the language card leaves out, such as upstream code in forks (comma-separated
                repo names, or repo:Language to drop one language of a repo)
  GH_TOKEN      a token for the API (the workflow's own token is enough)
"""

import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

API = "https://api.github.com"
USER = os.environ.get("USER_LOGIN", "2B-4G10")
EXTRA_REPOS = [r.strip() for r in os.environ.get("EXTRA_REPOS", "").split(",") if r.strip()]
SKIP_LANGS = {r.strip().lower() for r in os.environ.get("SKIP_LANGS", "").split(",") if r.strip()}
TOKEN = os.environ.get("GH_TOKEN", "")

# GitHub's own language colours (github-linguist), for the languages these repos are likely to have.
COLOURS = {
    "Java": "#b07219", "Kotlin": "#A97BFF", "Python": "#3572A5", "Swift": "#F05138",
    "Shell": "#89e051", "C": "#555555", "C++": "#f34b7d", "C#": "#178600",
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#663399",
    "Objective-C": "#438eff", "Objective-C++": "#6866fb", "Logos": "#bec7ae", "Makefile": "#427819",
    "Go": "#00ADD8", "Rust": "#dea584", "Dart": "#00B4AB", "PowerShell": "#012456",
    "Batchfile": "#C1F12E", "Dockerfile": "#384d54", "Ruby": "#701516", "PHP": "#4F5D95",
    "Smali": "#ffffff", "AIDL": "#34EB6B", "CMake": "#DA3434", "Groovy": "#4298b8",
    "Inno Setup": "#264b99", "Nix": "#7e7eff", "Lua": "#000080",
}

THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#2AABEE", "text": "#e6edf3",
             "muted": "#8b949e", "track": "#21262d"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "title": "#1d8fcf", "text": "#1f2328",
              "muted": "#59636e", "track": "#eaeef2"},
}

# Both cards share one size so they sit side by side in the README.
WIDTH, HEIGHT = 420, 200

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def get(path):
    """Fetches every page of an API list (or a single object)."""
    url, items = f"{API}/{path}", []
    while url:
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"{USER}-profile-stats",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            link = resp.headers.get("Link", "")
        if not isinstance(data, list):
            return data
        items += data
        url = next((p.split(";")[0].strip()[1:-1] for p in link.split(",") if 'rel="next"' in p), None)
    return items


def short(n):
    for size, suffix in ((1_000_000, "M"), (1_000, "k")):
        if n >= size:
            return f"{n / size:.1f}".removesuffix(".0") + suffix
    return str(n)


def colour(lang):
    if lang in COLOURS:
        return COLOURS[lang]
    h = sum(ord(c) * 31 ** i for i, c in enumerate(lang)) % 360
    return f"hsl({h},55%,55%)"


def card(theme, width, height, title, body):
    t = THEMES[theme]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">\n'
        f'<title>{escape(title)}</title>\n'
        f'<style>text{{font-family:{FONT}}}</style>\n'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{t["bg"]}" stroke="{t["border"]}"/>\n'
        f'<text x="24" y="38" font-size="17" font-weight="600" fill="{t["title"]}">{escape(title)}</text>\n'
        f'{body}</svg>\n'
    )


def languages_svg(theme, langs):
    t = THEMES[theme]
    width, height, top = WIDTH, HEIGHT, 6
    total = sum(langs.values()) or 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    shown = ranked[:top]
    rest = sum(v for _, v in ranked[top:])
    if rest:
        shown.append(("Other", rest))

    # One rounded bar split into each language's share.
    bar, x, bar_w = [], 24.0, width - 48
    bar.append(f'<clipPath id="bar"><rect x="24" y="56" width="{bar_w}" height="10" rx="5"/></clipPath>')
    bar.append(f'<rect x="24" y="56" width="{bar_w}" height="10" rx="5" fill="{t["track"]}"/>')
    bar.append('<g clip-path="url(#bar)">')
    for lang, v in shown:
        w = bar_w * v / total
        fill = t["muted"] if lang == "Other" else colour(lang)
        bar.append(f'<rect x="{x:.2f}" y="56" width="{w + 0.5:.2f}" height="10" fill="{fill}"/>')
        x += w
    bar.append("</g>")

    legend = []
    for i, (lang, v) in enumerate(shown):
        lx = 24 + (i % 2) * 196
        ly = 100 + (i // 2) * 28
        fill = t["muted"] if lang == "Other" else colour(lang)
        pct = f"{100 * v / total:.1f}%"
        legend.append(f'<circle cx="{lx + 6}" cy="{ly - 5}" r="6" fill="{fill}"/>')
        legend.append(f'<text x="{lx + 20}" y="{ly}" font-size="14" fill="{t["text"]}">{escape(lang)} '
                      f'<tspan fill="{t["muted"]}">{pct}</tspan></text>')
    return card(theme, width, height, "Most used languages", "\n".join(bar + legend) + "\n")


def overview_svg(theme, facts):
    t = THEMES[theme]
    width, height = WIDTH, HEIGHT
    body = []
    for i, (icon, label, value) in enumerate(facts):
        y = 80 + i * 30
        body.append(f'<text x="24" y="{y}" font-size="14" fill="{t["text"]}">{icon}  {escape(label)}</text>')
        body.append(f'<text x="{width - 24}" y="{y}" font-size="14" font-weight="600" text-anchor="end" '
                    f'fill="{t["text"]}">{escape(value)}</text>')
    return card(theme, width, height, "At a glance", "\n".join(body) + "\n")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
    out.mkdir(parents=True, exist_ok=True)

    user = get(f"users/{USER}")
    repos = [r for r in get(f"users/{USER}/repos?type=owner&per_page=100")
             if not r["private"] and not r["archived"]]

    downloads = 0
    for name in [r["full_name"] for r in repos] + EXTRA_REPOS:
        n = sum(a["download_count"] for rel in get(f"repos/{name}/releases?per_page=100")
                for a in rel["assets"])
        print(f"{name}: {n} downloads")
        downloads += n

    langs = {}
    for r in repos:
        name = r["name"].lower()
        if name in SKIP_LANGS:
            continue
        for lang, size in get(f"repos/{r['full_name']}/languages").items():
            if f"{name}:{lang.lower()}" not in SKIP_LANGS:
                langs[lang] = langs.get(lang, 0) + size
    print("languages:", langs)

    stars = sum(r["stargazers_count"] for r in repos)
    facts = [
        ("⬇️", "Total downloads", f"{downloads:,}"),
        ("⭐", "Stars earned", f"{stars:,}"),
        ("📦", "Public projects", str(len(repos))),
        ("👥", "Followers", f"{user['followers']:,}"),
    ]

    (out / "downloads.json").write_text(json.dumps({
        "schemaVersion": 1, "label": "downloads", "message": short(downloads),
        "color": "2AABEE", "cacheSeconds": 3600,
    }, indent=2) + "\n")
    for theme in THEMES:
        (out / f"languages-{theme}.svg").write_text(languages_svg(theme, langs))
        (out / f"overview-{theme}.svg").write_text(overview_svg(theme, facts))


if __name__ == "__main__":
    main()
