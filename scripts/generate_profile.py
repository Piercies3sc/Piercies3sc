#!/usr/bin/env python3
"""
Generate dark_mode.svg and light_mode.svg for GitHub profile.
Fetches real statistics from GitHub API for Piercies3sc.
Renders a dense, clean, terminal-inspired profile card with warm amber & red styling.
1080x520 canvas with large ASCII portrait and readable 18px terminal text.
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
CACHE_PATH = REPO_ROOT / "profile_stats_cache.json"

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

def load_cached_loc():
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("loc_display") or (f"{data['loc']:,}" if data.get("loc") else None)
        except Exception as e:
            print(f"Error reading cache: {e}")
    return None

def save_cached_loc(loc_int, loc_str):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "loc": loc_int,
                "loc_display": loc_str,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }, f, indent=2)
        print(f"Saved real LOC to cache: {loc_str}")
    except Exception as e:
        print(f"Error writing cache: {e}")

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
        for attempt in range(5):
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
            time.sleep(2.0)
        
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
    
    # Handle LOC: real calculation or last real cached value
    if loc_reliable and total_loc_net > 0:
        loc_display = f"{total_loc_net:,}"
        save_cached_loc(total_loc_net, loc_display)
        print(f"Calculated and cached real LOC: {loc_display}")
    else:
        cached = load_cached_loc()
        if cached:
            loc_display = cached
            print(f"Using previously cached real LOC: {loc_display}")
        else:
            loc_display = "unavailable"
            print("LOC unavailable (no cache found)")
    
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
        ascii_color = "#c9d1d9"
        
        # Dark mode: warm amber & red accents
        primary_text = "#f0f6fc"     # soft white for values
        text_muted = "#6e7681"       # muted gray for dots & dividers
        accent_amber = "#d29922"     # warm amber / dark yellow for labels
        accent_red = "#f85149"       # red accent for bullets & section markers
        divider_color = "#30363d"
    else:
        bg = "#ffffff"
        ascii_color = "#24292f"
        
        # Light mode: adapted for clean white background
        primary_text = "#24292f"     # dark charcoal for values
        text_muted = "#57606a"       # muted dots
        accent_amber = "#9a6700"     # dark warm amber for labels
        accent_red = "#cf222e"       # red accent
        divider_color = "#d0d7de"

    # SVG Canvas: 1080x520 (fills card, large content scale)
    width = 1080
    height = 520
    
    # ASCII configuration (62 lines, 102 chars)
    # Scaled up to fill ~40-42% width and ~91% height
    ascii_font_size = 7.0
    ascii_line_height = 7.6
    ascii_start_x = 20
    ascii_start_y = 26

    ascii_elements = []
    for i, line in enumerate(ascii_lines):
        y = ascii_start_y + i * ascii_line_height
        safe_line = html.escape(line.rstrip("\r\n"))
        ascii_elements.append(
            f'<text x="{ascii_start_x}" y="{y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{ascii_font_size}px" fill="{ascii_color}" xml:space="preserve">{safe_line}</text>'
        )
    ascii_svg = "\n    ".join(ascii_elements)

    # Right panel configuration
    # panel_x = 425 provides a clean 15-20px gutter from ASCII right edge
    # Text sizes: 21px title, 19px section headers, 18px body text
    # letter-spacing: -0.3px ensures comfortable fit with ~25px right padding
    panel_x = 425
    panel_y_start = 42
    panel_line_h = 25
    gap_h = 15
    font_size = 18
    header_size = 21
    section_header_size = 19

    def format_item(label, total_width, value):
        # Prefix is '· ' (2) + label + ' ' (1) + dots + ' ' (1) = total_width
        dots_count = max(1, total_width - len(label) - 4)
        dots_str = "." * dots_count
        return (
            f'<tspan fill="{accent_red}">\u00b7 </tspan>'
            f'<tspan fill="{accent_amber}">{html.escape(label)}</tspan>'
            f'<tspan fill="{text_muted}"> {dots_str} </tspan>'
            f'<tspan fill="{primary_text}">{html.escape(value)}</tspan>'
        )

    # Rows structure
    panel_elements = []
    cur_y = panel_y_start

    # 1. Header (mert@github: 21px, divider: 52 dashes, total 65 chars)
    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{header_size}px" font-weight="700" xml:space="preserve">'
        f'<tspan fill="{accent_amber}">mert</tspan>'
        f'<tspan fill="{text_muted}">@</tspan>'
        f'<tspan fill="{accent_amber}">github</tspan>'
        f'<tspan fill="{divider_color}">  ----------------------------------------------------</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h + gap_h

    # 2. System: OS, Uptime
    system_items = [
        ("OS:", 28, "Windows 11, macOS, iOS"),
        ("Uptime:", 28, "3rd Year CENG Student"),
    ]
    for label, width_col, val in system_items:
        panel_elements.append(
            f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">{format_item(label, width_col, val)}</text>'
        )
        cur_y += panel_line_h
    cur_y += gap_h

    # 3. Languages: Programming, Computer, Real
    lang_items = [
        ("Languages.Programming:", 28, "C, C++, JavaScript, TypeScript, SQL"),
        ("Languages.Computer:", 28, "HTML, CSS, JSON, Markdown"),
        ("Languages.Real:", 28, "Turkish, English"),
    ]
    for label, width_col, val in lang_items:
        panel_elements.append(
            f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">{format_item(label, width_col, val)}</text>'
        )
        cur_y += panel_line_h
    cur_y += gap_h

    # 4. Hobbies: Software, Hardware
    hobby_items = [
        ("Hobbies.Software:", 28, "AI Tools, Fine-tuning, Web Development"),
        ("Hobbies.Hardware:", 28, "PC Building, Performance Tuning"),
    ]
    for label, width_col, val in hobby_items:
        panel_elements.append(
            f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">{format_item(label, width_col, val)}</text>'
        )
        cur_y += panel_line_h
    cur_y += gap_h

    # 5. Contact Section Header (19px, divider: 55 dashes, total 65 chars)
    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{section_header_size}px" font-weight="700" xml:space="preserve">'
        f'<tspan fill="{accent_red}">- </tspan>'
        f'<tspan fill="{accent_amber}">Contact</tspan>'
        f'<tspan fill="{divider_color}"> -------------------------------------------------------</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h

    contact_items = [
        ("Email.Personal:", 28, "mertpural@gmail.com"),
        ("Discord:", 28, "piercies3sc"),
    ]
    for label, width_col, val in contact_items:
        panel_elements.append(
            f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">{format_item(label, width_col, val)}</text>'
        )
        cur_y += panel_line_h
    cur_y += gap_h

    # 6. GitHub Stats Section Header (19px, divider: 50 dashes, total 65 chars)
    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{section_header_size}px" font-weight="700" xml:space="preserve">'
        f'<tspan fill="{accent_red}">- </tspan>'
        f'<tspan fill="{accent_amber}">GitHub Stats</tspan>'
        f'<tspan fill="{divider_color}"> --------------------------------------------------</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h

    # GitHub Stats rows (2 columns)
    # Repos / Stars
    repos_dots = "." * 8
    stars_dots = "." * 8
    r_val = stats['repos']
    s_val = stats["stars"]
    col1_spaces = " " * max(1, 35 - 18 - len(r_val))

    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">'
        f'<tspan fill="{accent_red}">\u00b7 </tspan>'
        f'<tspan fill="{accent_amber}">Repos:</tspan>'
        f'<tspan fill="{text_muted}"> {repos_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(r_val)}</tspan>'
        f'<tspan fill="{text_muted}">{col1_spaces}</tspan>'
        f'<tspan fill="{accent_amber}">Stars:</tspan>'
        f'<tspan fill="{text_muted}"> {stars_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(s_val)}</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h

    # Commits / Followers
    commits_dots = "." * 6
    followers_dots = "." * 4
    c_val = stats['commits']
    f_val = stats["followers"]
    col1_c_spaces = " " * max(1, 35 - 18 - len(c_val))

    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">'
        f'<tspan fill="{accent_red}">\u00b7 </tspan>'
        f'<tspan fill="{accent_amber}">Commits:</tspan>'
        f'<tspan fill="{text_muted}"> {commits_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(c_val)}</tspan>'
        f'<tspan fill="{text_muted}">{col1_c_spaces}</tspan>'
        f'<tspan fill="{accent_amber}">Followers:</tspan>'
        f'<tspan fill="{text_muted}"> {followers_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(f_val)}</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h

    # Lines of Code on GitHub
    loc_dots = "." * 3
    l_val = stats["loc"]
    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">'
        f'<tspan fill="{accent_red}">\u00b7 </tspan>'
        f'<tspan fill="{accent_amber}">Lines of Code on GitHub:</tspan>'
        f'<tspan fill="{text_muted}"> {loc_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(l_val)}</tspan>'
        f'</text>'
    )

    panel_svg = "\n    ".join(panel_elements)

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <style>
      text {{
        font-feature-settings: "liga" 0;
        text-rendering: geometricPrecision;
      }}
      #info-panel text {{
        letter-spacing: -0.3px;
      }}
    </style>
  </defs>

  <!-- SVG Background -->
  <rect width="{width}" height="{height}" fill="{bg}"/>

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
