#!/usr/bin/env python3
"""
Generate dark_mode.svg and light_mode.svg for GitHub profile.
Fetches real statistics from GitHub API for Piercies3sc.
Renders an elegant, dense, terminal/neofetch-inspired profile card.
"""

import os
import re
import html
import json
import time
import subprocess
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
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        try:
            p = subprocess.Popen(
                ["git", "credential", "fill"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, _ = p.communicate("protocol=https\nhost=github.com\n")
            for line in out.splitlines():
                if line.startswith("password="):
                    token = line.split("=", 1)[1]
                    break
        except Exception:
            pass
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
    
    if is_dark:
        bg = "#0d1117"
        border = "#30363d"
        dot_red = "#ff5f56"
        dot_yellow = "#ffbd2e"
        dot_green = "#27c93f"
        ascii_color = "#c9d1d9"
        
        # Warm amber & red-orange theme
        accent_amber = "#f59e0b"     # warm golden amber
        accent_orange = "#f97316"    # vibrant red-orange
        accent_bright = "#fbbf24"    # light amber highlight
        
        text_primary = "#f0f6fc"     # soft crisp white
        text_turkish = "#9ca3af"     # muted light gray
        text_label = "#e6edf3"       # clear label text
        dots_color = "#30363d"       # subtle dark dots
        slash_color = "#f59e0b"      # amber slash
        divider_line = "#21262d"     # subtle section line
    else:
        bg = "#ffffff"
        border = "#d0d7de"
        dot_red = "#ff5f56"
        dot_yellow = "#ffbd2e"
        dot_green = "#27c93f"
        ascii_color = "#24292f"
        
        # Light mode: warm amber & red-orange
        accent_amber = "#b45309"     # dark warm amber
        accent_orange = "#c2410c"    # dark red-orange
        accent_bright = "#b45309"    # dark amber highlight
        
        text_primary = "#1f2328"     # dark charcoal
        text_turkish = "#656d76"     # muted charcoal
        text_label = "#1f2328"       # dark label text
        dots_color = "#d0d7de"       # light gray dots
        slash_color = "#b45309"      # amber slash
        divider_line = "#e1e4e8"     # light border line

    width = 1140
    height = 560
    
    # ASCII configuration (62 lines, 103 chars)
    ascii_font_size = 6.6
    ascii_line_height = 7.8
    ascii_start_x = 24
    ascii_start_y = 52

    ascii_elements = []
    for i, line in enumerate(ascii_lines):
        y = ascii_start_y + i * ascii_line_height
        safe_line = html.escape(line.rstrip("\r\n"))
        ascii_elements.append(
            f'<text x="{ascii_start_x}" y="{y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{ascii_font_size}px" fill="{ascii_color}" xml:space="preserve">{safe_line}</text>'
        )
    ascii_svg = "\n    ".join(ascii_elements)

    # Right panel configuration
    panel_x = 470
    panel_y_start = 58
    panel_line_h = 17.5
    font_size = 10.8

    line_rule = "\u2500" * 58

    # Rows: (kind, label, dots, val_en, slash, val_tr, accent_type)
    rows = [
        ("header", "mert", "@", "github", "", "", ""),
        ("divider", "", "", "", "", "", ""),
        ("gap", "", "", "", "", "", ""),
        ("section", "ABOUT", "amber", line_rule, "", "", ""),
        ("item", "Role", "........ ", "Computer Engineering Student", " / ", "Bilgisayar M\u00fchendisli\u011fi \u00d6\u011frencisi", "bilingual"),
        ("item", "Focus", "....... ", "Backend, Web, Interactive 3D", " / ", "Backend, Web, Etkile\u015fimli 3D", "bilingual"),
        ("item", "Learning", ".... ", "AI, Full-Stack, 3D Web", " / ", "Yapay Zeka, Full-Stack, 3D Web", "bilingual"),
        ("item", "Interests", "... ", "Fine-tuning, AI tools, UI polish", " / ", "Fine-tuning, yapay zeka ara\u00e7lar\u0131, aray\u00fcz geli\u015ftirme", "bilingual"),
        ("gap", "", "", "", "", "", ""),
        ("section", "STACK", "orange", line_rule, "", "", ""),
        ("item", "Languages", "... ", "C, C++, JavaScript, TypeScript, SQL", "", "", "single"),
        ("item", "Frontend", ".... ", "React, Next.js, HTML, CSS, Tailwind", "", "", "single"),
        ("item", "Backend/DB", ".. ", "Supabase, PostgreSQL", "", "", "single"),
        ("item", "3D/WebGL", ".... ", "Three.js, React Three Fiber", "", "", "single"),
        ("item", "Tools", "....... ", "Git, GitHub, Vercel, VS Code", "", "", "single"),
        ("item", "Platforms", "... ", "Windows, macOS, iOS", "", "", "single"),
        ("gap", "", "", "", "", "", ""),
        ("section", "CONTACT", "amber", line_rule, "", "", ""),
        ("item", "Email", "....... ", "mertpural@gmail.com", "", "", "single"),
        ("item", "GitHub", "...... ", "Piercies3sc", "", "", "single"),
        ("gap", "", "", "", "", "", ""),
        ("section", "GITHUB STATS", "orange", line_rule, "", "", ""),
        ("stat", "Repos", "....... ", stats["repos"], "amber", "", ""),
        ("stat", "Commits", "..... ", stats["commits"], "orange", "", ""),
        ("stat", "Stars", "....... ", stats["stars"], "amber", "", ""),
        ("stat", "Followers", "... ", stats["followers"], "orange", "", ""),
        ("stat", "LOC", "......... ", stats["loc"], "amber", "", ""),
        ("gap", "", "", "", "", "", ""),
        ("footer", "Status", "...... ", "Building and learning every day", " / ", "Her g\u00fcn geli\u015ftiriyorum", "")
    ]

    panel_elements = []
    cur_y = panel_y_start
    for r in rows:
        r_type = r[0]
        if r_type == "gap":
            cur_y += 6
            continue
        
        if r_type == "header":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="14px" font-weight="700" xml:space="preserve">'
                f'<tspan fill="{accent_amber}">mert</tspan>'
                f'<tspan fill="{text_turkish}">@</tspan>'
                f'<tspan fill="{accent_orange}">github</tspan>'
                f'</text>'
            )
        elif r_type == "divider":
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" fill="{divider_line}" xml:space="preserve">{line_rule}</text>'
            )
        elif r_type == "section":
            sec_title = r[1]
            sec_accent = accent_amber if r[2] == "amber" else accent_orange
            sec_line = r[3]
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" font-weight="700" xml:space="preserve">'
                f'<tspan fill="{sec_accent}">\u276f {sec_title}</tspan> '
                f'<tspan fill="{divider_line}">{sec_line}</tspan>'
                f'</text>'
            )
        elif r_type == "item":
            label = r[1]
            dots = r[2]
            val_en = html.escape(r[3])
            slash = r[4]
            val_tr = html.escape(r[5])
            mode = r[6]
            
            if mode == "bilingual":
                panel_elements.append(
                    f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" xml:space="preserve">'
                    f'<tspan fill="{text_label}">{label}</tspan>'
                    f'<tspan fill="{dots_color}">{dots}</tspan>'
                    f'<tspan fill="{text_primary}">{val_en}</tspan>'
                    f'<tspan fill="{slash_color}">{slash}</tspan>'
                    f'<tspan fill="{text_turkish}">{val_tr}</tspan>'
                    f'</text>'
                )
            else:
                panel_elements.append(
                    f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" xml:space="preserve">'
                    f'<tspan fill="{text_label}">{label}</tspan>'
                    f'<tspan fill="{dots_color}">{dots}</tspan>'
                    f'<tspan fill="{text_primary}">{val_en}</tspan>'
                    f'</text>'
                )
        elif r_type == "stat":
            label = r[1]
            dots = r[2]
            val = html.escape(r[3])
            stat_color = accent_bright if r[4] == "amber" else accent_orange
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" xml:space="preserve">'
                f'<tspan fill="{text_label}">{label}</tspan>'
                f'<tspan fill="{dots_color}">{dots}</tspan>'
                f'<tspan fill="{stat_color}" font-weight="700">{val}</tspan>'
                f'</text>'
            )
        elif r_type == "footer":
            label = r[1]
            dots = r[2]
            val_en = html.escape(r[3])
            slash = r[4]
            val_tr = html.escape(r[5])
            panel_elements.append(
                f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" font-size="{font_size}px" xml:space="preserve">'
                f'<tspan fill="{text_label}">{label}</tspan>'
                f'<tspan fill="{dots_color}">{dots}</tspan>'
                f'<tspan fill="{accent_amber}">{val_en}</tspan>'
                f'<tspan fill="{dots_color}">{slash}</tspan>'
                f'<tspan fill="{accent_orange}">{val_tr}</tspan>'
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
