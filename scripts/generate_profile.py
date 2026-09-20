#!/usr/bin/env python3
"""
Generate dark_mode.svg and light_mode.svg for GitHub profile.
Fetches real statistics from GitHub API for Piercies3sc.
"""

import os
import re
import html
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

USERNAME = "Piercies3sc"
REPO_ROOT = Path(__file__).resolve().parent.parent
ASCII_PATH = REPO_ROOT / "assets" / "ascii-art.txt"
DARK_SVG_PATH = REPO_ROOT / "dark_mode.svg"
LIGHT_SVG_PATH = REPO_ROOT / "light_mode.svg"

def get_headers():
    headers = {
        "User-Agent": "Piercies3sc-Profile-Generator",
        "Accept": "application/vnd.github+json"
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def fetch_json(url):
    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req) as resp:
            link = resp.headers.get("Link", "")
            data = json.loads(resp.read().decode())
            return data, link
    except urllib.error.HTTPError as e:
        print(f"HTTPError fetching {url}: {e.code} {e.reason}")
        return None, ""
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, ""

def fetch_stats():
    print(f"Fetching GitHub stats for {USERNAME}...")
    user_data, _ = fetch_json(f"https://api.github.com/users/{USERNAME}")
    
    repos_count = 0
    followers_count = 0
    if user_data:
        repos_count = user_data.get("public_repos", 0)
        followers_count = user_data.get("followers", 0)
    
    repos, _ = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
    if not repos:
        repos = []
    
    # Filter public non-fork repos owned by USERNAME
    owned_repos = [r for r in repos if not r.get("fork", False)]
    stars_count = sum(r.get("stargazers_count", 0) for r in owned_repos)
    
    total_commits = 0
    total_loc_net = 0
    loc_reliable = True
    
    print(f"Processing {len(owned_repos)} owned repositories...")
    for r in owned_repos:
        repo_name = r["name"]
        
        # 1. Try to fetch stats/contributors (with retries if 202 Accepted)
        stats_url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/stats/contributors"
        contrib_data = None
        for attempt in range(4):
            req = urllib.request.Request(stats_url, headers=get_headers())
            try:
                with urllib.request.urlopen(req) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        if isinstance(data, list) and len(data) > 0:
                            contrib_data = data
                            break
            except Exception:
                pass
            time.sleep(1.5)
        
        repo_commits = 0
        repo_loc = 0
        got_contrib = False
        
        if contrib_data:
            for c in contrib_data:
                author_login = c.get("author", {}).get("login") if c.get("author") else None
                if author_login == USERNAME or len(contrib_data) == 1:
                    repo_commits = c.get("total", 0)
                    additions = sum(w.get("a", 0) for w in c.get("weeks", []))
                    deletions = sum(w.get("d", 0) for w in c.get("weeks", []))
                    repo_loc = additions - deletions
                    got_contrib = True
                    break
        
        # Fallback for commits if contrib_data failed
        if not got_contrib:
            commit_url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits?author={USERNAME}&per_page=1"
            c_data, link = fetch_json(commit_url)
            if c_data is not None:
                if link:
                    m = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link)
                    if m:
                        repo_commits = int(m.group(1))
                    else:
                        repo_commits = len(c_data)
                else:
                    repo_commits = len(c_data)
            loc_reliable = False
        
        total_commits += repo_commits
        total_loc_net += repo_loc
        print(f"  {repo_name}: commits={repo_commits}, contrib_cached={got_contrib}")
    
    loc_display = f"{total_loc_net:,}" if (loc_reliable and total_loc_net > 0) else ("unavailable" if not loc_reliable else f"{total_loc_net:,}")
    
    stats = {
        "repos": str(repos_count),
        "commits": str(total_commits),
        "stars": str(stars_count),
        "followers": str(followers_count),
        "loc": loc_display
    }
    print(f"Stats summary: {stats}")
    return stats

def render_svg(theme: str, stats: dict, ascii_lines: list) -> str:
    is_dark = (theme == "dark")
    
    # Palette
    if is_dark:
        bg = "#0d1117"
        border = "#30363d"
        dot_red = "#ff5f56"
        dot_yellow = "#ffbd2e"
        dot_green = "#27c93f"
        ascii_color = "#c9d1d9"
        accent = "#ff7b25"       # restrained orange
        text_primary = "#e6edf3"
        text_muted = "#8b949e"
        divider = "#30363d"
    else:
        bg = "#ffffff"
        border = "#d0d7de"
        dot_red = "#ff5f56"
        dot_yellow = "#ffbd2e"
        dot_green = "#27c93f"
        ascii_color = "#24292f"
        accent = "#ea580c"       # restrained orange
        text_primary = "#1f2328"
        text_muted = "#57606a"
        divider = "#d0d7de"

    width = 1040
    height = 530
    
    # ASCII configuration
    ascii_font_size = 6.9
    ascii_line_height = 7.5
    ascii_start_x = 28
    ascii_start_y = 52

    # Build ASCII tspans / texts
    ascii_elements = []
    for i, line in enumerate(ascii_lines):
        y = ascii_start_y + i * ascii_line_height
        safe_line = html.escape(line.rstrip("\r\n"))
        ascii_elements.append(f'<text x="{ascii_start_x}" y="{y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{ascii_font_size}px" fill="{ascii_color}" xml:space="preserve">{safe_line}</text>')
    ascii_svg = "\n    ".join(ascii_elements)

    # Right panel configuration
    panel_x = 490
    panel_y_start = 82
    panel_line_h = 23
    font_size = 13.5

    # Rows definition: (type, label, value)
    # Types: "header", "divider", "empty", "item", "section_header", "stat"
    rows = [
        ("header", "mert@github", ""),
        ("divider", "--------------------------------", ""),
        ("empty", "", ""),
        ("item", "Role........ ", "Computer Engineering Student"),
        ("item", "Focus....... ", "Backend, Web, Interactive 3D"),
        ("empty", "", ""),
        ("item", "Languages... ", "C, C++, JavaScript, TypeScript, SQL"),
        ("item", "Web......... ", "React, Next.js, HTML, CSS, Tailwind"),
        ("item", "Backend/DB.. ", "Supabase, PostgreSQL"),
        ("item", "3D/WebGL.... ", "Three.js, React Three Fiber"),
        ("empty", "", ""),
        ("section_header", "GitHub Stats", ""),
        ("stat", "Repos....... ", stats["repos"]),
        ("stat", "Commits..... ", stats["commits"]),
        ("stat", "Stars....... ", stats["stars"]),
        ("stat", "Followers... ", stats["followers"]),
        ("stat", "LOC......... ", stats["loc"]),
    ]

    panel_elements = []
    cur_y = panel_y_start
    for r_type, label, val in rows:
        if r_type == "empty":
            cur_y += 12
            continue
        
        safe_label = html.escape(label)
        safe_val = html.escape(val)

        if r_type == "header":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="15px" font-weight="700" fill="{accent}" xml:space="preserve">{safe_label}</text>'
            )
        elif r_type == "divider":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" fill="{divider}" xml:space="preserve">{safe_label}</text>'
            )
        elif r_type == "item":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" xml:space="preserve">'
                f'<tspan fill="{text_muted}">{safe_label}</tspan>'
                f'<tspan fill="{text_primary}">{safe_val}</tspan>'
                f'</text>'
            )
        elif r_type == "section_header":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="14px" font-weight="700" fill="{accent}" xml:space="preserve">{safe_label}</text>'
            )
        elif r_type == "stat":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" xml:space="preserve">'
                f'<tspan fill="{text_muted}">{safe_label}</tspan>'
                f'<tspan fill="{text_primary}" font-weight="600">{safe_val}</tspan>'
                f'</text>'
            )
        cur_y += panel_line_h

    panel_svg = "\n    ".join(panel_elements)

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <style>
      text {{
        font-feature-settings: "liga" 0;
        text-rendering: geometricPrecision;
      }}
    </style>
  </defs>

  <!-- Background and Window Border -->
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="{bg}" stroke="{border}" stroke-width="1"/>

  <!-- Terminal Window Controls -->
  <circle cx="24" cy="20" r="4.5" fill="{dot_red}" opacity="0.85"/>
  <circle cx="38" cy="20" r="4.5" fill="{dot_yellow}" opacity="0.85"/>
  <circle cx="52" cy="20" r="4.5" fill="{dot_green}" opacity="0.85"/>

  <!-- ASCII Portrait -->
  <g id="ascii-portrait">
    {ascii_svg}
  </g>

  <!-- Terminal Information Panel -->
  <g id="info-panel">
    {panel_svg}
  </g>
</svg>'''
    return svg_content

def main():
    if not ASCII_PATH.exists():
        raise FileNotFoundError(f"ASCII source file not found at {ASCII_PATH}")
    
    with open(ASCII_PATH, "r", encoding="utf-8") as f:
        ascii_lines = f.readlines()
    
    print(f"Loaded ASCII portrait: {len(ascii_lines)} lines from {ASCII_PATH}")
    
    stats = fetch_stats()
    
    print("Generating dark_mode.svg...")
    dark_svg = render_svg("dark", stats, ascii_lines)
    with open(DARK_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(dark_svg)
    print(f"Saved: {DARK_SVG_PATH}")

    print("Generating light_mode.svg...")
    light_svg = render_svg("light", stats, ascii_lines)
    with open(LIGHT_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(light_svg)
    print(f"Saved: {LIGHT_SVG_PATH}")

if __name__ == "__main__":
    main()
