import os
import re
import html
import json
import time
import datetime
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

USERNAME = "Piercies3sc"
REPO_ROOT = Path(__file__).resolve().parent.parent
ASCII_PATH = REPO_ROOT / "assets" / "ascii-art.txt"
CACHE_PATH = REPO_ROOT / "profile_stats_cache.json"
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

def calculate_uptime():
    """
    Calculates age in calendar-aware years, months, and days from birth date 2004-05-17.
    Uses Europe/Istanbul timezone.
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Europe/Istanbul")).date()
    except Exception:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date()
    
    birth = datetime.date(2004, 5, 17)
    
    years = now.year - birth.year
    months = now.month - birth.month
    days = now.day - birth.day
    
    if days < 0:
        first_of_current_month = now.replace(day=1)
        last_of_prev_month = first_of_current_month - datetime.timedelta(days=1)
        days += last_of_prev_month.day
        months -= 1
        
    if months < 0:
        months += 12
        years -= 1
        
    parts = []
    parts.append(f"{years} {'year' if years == 1 else 'years'}")
    parts.append(f"{months} {'month' if months == 1 else 'months'}")
    parts.append(f"{days} {'day' if days == 1 else 'days'}")
    return ", ".join(parts)

def load_cached_stats():
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cache: {e}")
    return {}

def save_cached_stats(stats_dict):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                **stats_dict,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }, f, indent=2)
        print(f"Saved stats to cache: {stats_dict}")
    except Exception as e:
        print(f"Error writing cache: {e}")

def fetch_contributed_repos():
    """
    Fetches real count of repositories Piercies3sc has contributed to.
    Uses GitHub GraphQL API with fallback to Search API.
    """
    headers = get_headers()
    # 1. Try GraphQL
    graphql_url = "https://api.github.com/graphql"
    query = """
    query {
      user(login: "%s") {
        repositoriesContributedTo(contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
          totalCount
        }
      }
    }
    """ % USERNAME
    try:
        req = urllib.request.Request(
            graphql_url,
            data=json.dumps({"query": query}).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            count = data.get("data", {}).get("user", {}).get("repositoriesContributedTo", {}).get("totalCount")
            if count is not None:
                print(f"Fetched contributed repos via GraphQL: {count}")
                return str(count)
    except Exception as e:
        print(f"GraphQL contributed repos error: {e}")

    # 2. Fallback to Search API
    try:
        search_url = f"https://api.github.com/search/issues?q=author:{USERNAME}+-user:{USERNAME}"
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            count = data.get("total_count")
            if count is not None:
                print(f"Fetched contributed repos via Search API: {count}")
                return str(count)
    except Exception as e:
        print(f"Search API contributed repos error: {e}")

    return "unavailable"

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
    
    owned_repos = [r for r in repos if not r.get("fork", False)]
    stars_count = sum(r.get("stargazers_count", 0) for r in owned_repos)
    
    contributed_count = fetch_contributed_repos()
    
    total_commits = 0
    total_add = 0
    total_del = 0
    loc_reliable = True
    
    print(f"Processing {len(owned_repos)} owned repositories...")
    for r in owned_repos:
        repo_name = r["name"]
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
            time.sleep(1.5)
        
        repo_commits = 0
        repo_add = 0
        repo_del = 0
        got_contrib = False
        
        if contrib_data:
            for c in contrib_data:
                author_login = c.get("author", {}).get("login") if c.get("author") else None
                if author_login == USERNAME or len(contrib_data) == 1:
                    repo_commits = c.get("total", 0)
                    weeks = c.get("weeks", [])
                    repo_add = sum(w.get("a", 0) for w in weeks)
                    repo_del = sum(w.get("d", 0) for w in weeks)
                    got_contrib = True
                    break
        
        # Fallback for 202 or missing stats: inspect commits individually if needed
        if not got_contrib:
            commit_url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits?author={USERNAME}&per_page=100"
            c_data, link = fetch_json(commit_url)
            if c_data is not None and isinstance(c_data, list):
                repo_commits = len(c_data)
                # Fetch detailed commit stats for additions/deletions
                for c in c_data:
                    sha = c.get("sha")
                    if sha:
                        c_detail, _ = fetch_json(f"https://api.github.com/repos/{USERNAME}/{repo_name}/commits/{sha}")
                        if c_detail and "stats" in c_detail:
                            repo_add += c_detail["stats"].get("additions", 0)
                            repo_del += c_detail["stats"].get("deletions", 0)
                got_contrib = True
            else:
                loc_reliable = False
        
        total_commits += repo_commits
        total_add += repo_add
        total_del += repo_del
        print(f"  {repo_name}: commits={repo_commits}, add={repo_add}, del={repo_del}, contrib_cached={got_contrib}")
    
    total_loc_net = total_add - total_del
    cached = load_cached_stats()
    
    if loc_reliable and total_add > 0:
        loc_net_display = f"{total_loc_net:,}"
        loc_add_display = f"{total_add:,}"
        loc_del_display = f"{total_del:,}"
        save_cached_stats({
            "loc_net": total_loc_net,
            "loc_net_display": loc_net_display,
            "loc_additions": total_add,
            "loc_additions_display": loc_add_display,
            "loc_deletions": total_del,
            "loc_deletions_display": loc_del_display,
            "contributed": contributed_count
        })
        print(f"Calculated and cached real LOC: net={loc_net_display}, add={loc_add_display}, del={loc_del_display}")
    else:
        if cached.get("loc_net_display"):
            loc_net_display = cached["loc_net_display"]
            loc_add_display = cached.get("loc_additions_display", "0")
            loc_del_display = cached.get("loc_deletions_display", "0")
            print(f"Using previously cached real LOC: net={loc_net_display}, add={loc_add_display}, del={loc_del_display}")
        else:
            loc_net_display = "unavailable"
            loc_add_display = "unavailable"
            loc_del_display = "unavailable"
            print("LOC unavailable (no cache found)")
            
        if contributed_count == "unavailable" and cached.get("contributed"):
            contributed_count = cached["contributed"]
    
    uptime_display = calculate_uptime()
    
    stats = {
        "uptime": uptime_display,
        "repos": str(repos_count),
        "contributed": contributed_count,
        "commits": str(total_commits),
        "stars": str(stars_count),
        "followers": str(followers_count),
        "loc_net": loc_net_display,
        "loc_add": loc_add_display,
        "loc_del": loc_del_display
    }
    print(f"Stats summary: {stats}")
    return stats

def render_svg(theme: str, stats: dict, ascii_lines: list) -> str:
    is_dark = (theme == "dark")
    
    if is_dark:
        bg = "#0d1117"
        ascii_color = "#c9d1d9"
        primary_text = "#f0f6fc"     # soft white for values
        text_muted = "#6e7681"       # muted gray for dots & dividers
        accent_amber = "#d29922"     # warm amber / dark yellow for labels
        accent_red = "#f85149"       # red accent for bullets & section markers
        divider_color = "#30363d"
        add_color = "#3fb950"        # dark mode green for additions
        del_color = "#f85149"        # dark mode red for deletions
    else:
        bg = "#ffffff"
        ascii_color = "#24292f"
        primary_text = "#24292f"     # dark charcoal for values
        text_muted = "#57606a"       # muted dots
        accent_amber = "#9a6700"     # dark warm amber for labels
        accent_red = "#cf222e"       # red accent
        divider_color = "#d0d7de"
        add_color = "#1a7f37"        # light mode green for additions
        del_color = "#cf222e"        # light mode red for deletions

    width = 1080
    height = 520
    
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

    panel_x = 425
    panel_y_start = 42
    panel_line_h = 25
    gap_h = 15
    font_size = 18
    header_size = 21
    section_header_size = 19

    def format_item(label, total_width, value):
        dots_count = max(1, total_width - len(label) - 4)
        dots_str = "." * dots_count
        return (
            f'<tspan fill="{accent_red}">\u00b7 </tspan>'
            f'<tspan fill="{accent_amber}">{html.escape(label)}</tspan>'
            f'<tspan fill="{text_muted}"> {dots_str} </tspan>'
            f'<tspan fill="{primary_text}">{html.escape(value)}</tspan>'
        )

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

    # 2. System: OS, Uptime (dynamically calculated age)
    system_items = [
        ("OS:", 28, "Windows 11, macOS, iOS"),
        ("Uptime:", 28, stats["uptime"]),
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

    # GitHub Stats rows (Andrew-style denser 3-row layout)
    # Row 1: Repos: .... {repos} {Contributed: {contrib}} | Stars: ........ {stars}
    r_val = stats["repos"]
    contrib_val = stats["contributed"]
    s_val = stats["stars"]
    
    # Prefix: '· Repos: .... ' (14) + r_val + ' {Contributed: ' (15) + contrib_val + '}' (1)
    # Total left part length: 30 + len(r_val) + len(contrib_val)
    left_part_len = 30 + len(r_val) + len(contrib_val)
    # Align '| ' at column 35
    col1_sep_spaces = " " * max(1, 35 - left_part_len)
    stars_dots = "." * 8

    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">'
        f'<tspan fill="{accent_red}">\u00b7 </tspan>'
        f'<tspan fill="{accent_amber}">Repos:</tspan>'
        f'<tspan fill="{text_muted}"> .... </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(r_val)}</tspan>'
        f'<tspan fill="{text_muted}"> {{</tspan>'
        f'<tspan fill="{accent_amber}">Contributed:</tspan>'
        f'<tspan fill="{primary_text}" font-weight="700"> {html.escape(contrib_val)}</tspan>'
        f'<tspan fill="{text_muted}">}}</tspan>'
        f'<tspan fill="{text_muted}">{col1_sep_spaces}| </tspan>'
        f'<tspan fill="{accent_amber}">Stars:</tspan>'
        f'<tspan fill="{text_muted}"> {stars_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(s_val)}</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h

    # Row 2: Commits: .. {commits}                   | Followers: ..... {followers}
    c_val = stats["commits"]
    f_val = stats["followers"]
    # Prefix: '· Commits: .. ' (14) + c_val
    left_c_len = 14 + len(c_val)
    col2_sep_spaces = " " * max(1, 35 - left_c_len)
    followers_dots = "." * 5

    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">'
        f'<tspan fill="{accent_red}">\u00b7 </tspan>'
        f'<tspan fill="{accent_amber}">Commits:</tspan>'
        f'<tspan fill="{text_muted}"> .. </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(c_val)}</tspan>'
        f'<tspan fill="{text_muted}">{col2_sep_spaces}| </tspan>'
        f'<tspan fill="{accent_amber}">Followers:</tspan>'
        f'<tspan fill="{text_muted}"> {followers_dots} </tspan>'
        f'<tspan fill="{primary_text}" font-weight="700">{html.escape(f_val)}</tspan>'
        f'</text>'
    )
    cur_y += panel_line_h

    # Row 3: Lines of Code on GitHub: NET ( ADDITIONS++, DELETIONS-- )
    loc_net_val = stats["loc_net"]
    loc_add_val = stats["loc_add"]
    loc_del_val = stats["loc_del"]
    
    if loc_add_val != "unavailable" and loc_del_val != "unavailable":
        loc_tspan_breakdown = (
            f'<tspan fill="{text_muted}"> ( </tspan>'
            f'<tspan fill="{add_color}" font-weight="700">{html.escape(loc_add_val)}++</tspan>'
            f'<tspan fill="{text_muted}">, </tspan>'
            f'<tspan fill="{del_color}" font-weight="700">{html.escape(loc_del_val)}--</tspan>'
            f'<tspan fill="{text_muted}"> )</tspan>'
        )
    else:
        loc_tspan_breakdown = ""

    panel_elements.append(
        f'<text x="{panel_x}" y="{cur_y:.1f}" font-family="SFMono-Regular, Consolas, \'Liberation Mono\', Menlo, monospace" font-size="{font_size}px" xml:space="preserve">'
        f'<tspan fill="{accent_red}">\u00b7 </tspan>'
        f'<tspan fill="{accent_amber}">Lines of Code on GitHub:</tspan>'
        f'<tspan fill="{primary_text}" font-weight="700"> {html.escape(loc_net_val)}</tspan>'
        f'{loc_tspan_breakdown}'
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