#!/usr/bin/env python3
"""profile-card.svg dosyasini uretir. GitHub rakamlari (repo, commit, star,
follower, satir sayisi) GitHub'dan otomatik cekilir. Bir sey cekilemezse
stats_cache.json'daki son bilinen rakam kullanilir, kart bozulmaz."""
import json, os, sys, time, html, datetime, urllib.request

# ================== AYARLAR (buradan degistir) ==================
USER   = "Piercies3sc"
BIRTH  = (2004, 5, 17)        # Uptime buradan hesaplanir (yil, ay, gun) -- kontrol et!
INFO = [                       # sabit bilgiler: (etiket, deger)
    ("OS", "Windows 11, macOS, iOS"),
]
PROGRAMMING = "C, C++, JavaScript, TypeScript, SQL"
COMPUTER    = "HTML, CSS, JSON, Markdown"
REAL        = "Turkish, English"
HOB_SOFT    = "AI Tools, Fine-tuning, Web Development"
HOB_HARD    = "PC Building, Performance Tuning"
EMAIL       = "mertpural@gmail.com"
DISCORD     = "pierces3sc"
EDUCATION   = "Computer Engineering"
LOCATION    = "Turkey"
EXTRA_LINES = []               # ornek: [("Projects", "poQRox, Auto Clicker")]  -> Contact'in ustune eklenir
# =================================================================

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

def api(url, data=None):
    h = {"User-Agent": "profile-card", "Accept": "application/vnd.github+json"}
    if TOKEN: h["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=30) as f:
        return json.load(f), f.status

def graphql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    d, _ = api("https://api.github.com/graphql", body)
    if "errors" in d: raise RuntimeError(d["errors"])
    return d["data"]

def fetch_stats(cache):
    s = dict(cache)
    # 1) repo / star / follower / contributed
    try:
        d = graphql("""query($l:String!){user(login:$l){createdAt followers{totalCount}
          repositories(ownerAffiliations:OWNER,isFork:false,first:100){totalCount nodes{name stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}
          contrib:repositories(ownerAffiliations:[COLLABORATOR,ORGANIZATION_MEMBER],first:1){totalCount}}}""", {"l": USER})["user"]
        s["repos"] = d["repositories"]["totalCount"]
        s["stars"] = sum(n["stargazerCount"] for n in d["repositories"]["nodes"])
        s["followers"] = d["followers"]["totalCount"]
        s["contributed"] = d["contrib"]["totalCount"]
        langs = {}
        for n in d["repositories"]["nodes"]:
            for e in n["languages"]["edges"]:
                langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
        if langs: s["top_lang"] = max(langs, key=langs.get)
        names = [n["name"] for n in d["repositories"]["nodes"]]
        created = int(d["createdAt"][:4])
    except Exception as e:
        print("uyari: repo/star/follower cekilemedi:", e); names = []; created = None
    # 2) toplam commit (hesap acildigindan beri, yil yil)
    try:
        if created is None: raise RuntimeError("createdAt yok")
        now = datetime.datetime.utcnow().year
        parts = " ".join(f'y{y}:contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{y}-12-31T23:59:59Z"){{totalCommitContributions restrictedContributionsCount}}' for y in range(created, now + 1))
        d = graphql("query($l:String!){user(login:$l){%s}}" % parts, {"l": USER})["user"]
        s["commits"] = sum(v["totalCommitContributions"] + v["restrictedContributionsCount"] for v in d.values())
    except Exception as e:
        print("uyari: commit sayisi cekilemedi:", e)
    # 2b) son commit tarihi
    try:
        d, _ = api(f"https://api.github.com/search/commits?q=author:{USER}&sort=author-date&order=desc&per_page=1")
        dt = datetime.datetime.strptime(d["items"][0]["commit"]["author"]["date"][:10], "%Y-%m-%d")
        s["last_commit"] = dt.strftime("%d %b %Y")
    except Exception as e:
        print("uyari: son commit cekilemedi:", e)
    # 3) eklenen / silinen satir (repo istatistiklerinden)
    try:
        if not names: raise RuntimeError("repo listesi yok")
        add = dele = 0
        for n in names:
            for _ in range(6):
                d, st = api(f"https://api.github.com/repos/{USER}/{n}/stats/contributors")
                if st == 200 and isinstance(d, list): break
                time.sleep(4)          # 202 = GitHub hesapliyor, bekle
            else:
                raise RuntimeError(f"{n} istatistigi hazir degil")
            for c in d:
                if c["author"] and c["author"]["login"].lower() == USER.lower():
                    for w in c["weeks"]: add += w["a"]; dele += w["d"]
        s["loc_add"], s["loc_del"] = add, dele
    except Exception as e:
        print("uyari: satir sayisi cekilemedi:", e)
    return s

def uptime():
    t = datetime.date.today(); y, m, d = BIRTH
    yy = t.year - y; mm = t.month - m; dd = t.day - d
    if dd < 0:
        mm -= 1
        pm = t.month - 1 or 12; py = t.year if t.month > 1 else t.year - 1
        import calendar; dd += calendar.monthrange(py, pm)[1]
    if mm < 0: yy -= 1; mm += 12
    u = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{u(yy,'year')}, {u(mm,'month')}, {u(dd,'day')}"

def build(s):
    rows_art = json.load(open(os.path.join(HERE, "ascii_art.json"), encoding="utf-8"))
    # bos kenarlari kirp (foto kartin icinde daha buyuk dursun)
    ys = [i for i, r in enumerate(rows_art) if any(c != " " for c, _ in r)]
    xs = [j for j in range(len(rows_art[0])) if any(rows_art[i][j][0] != " " for i in ys)]
    rows_art = [r[min(xs):max(xs) + 1] for r in rows_art[min(ys):max(ys) + 1]]
    COLS = len(rows_art[0]); ROWS = len(rows_art)
    FS = 14; C = FS * 0.6
    AFS = 13; CW = AFS * 0.6; LH = AFS * 1.1
    PADL = 24; ART_W = COLS * CW; GAP = 44
    RX = PADL + ART_W + GAP; RIGHT_W = 68 * C + 70; W = int(RX + RIGHT_W)
    GOLD="#d4a540"; WHITE="#e6edf3"; GRAY="#6e7681"; ORANGE="#f0883e"; GREEN="#3fb950"; RED="#f85149"
    loc = s["loc_add"] - s["loc_del"]
    rows = [("head",), ("kv","OS","Windows 11, macOS, iOS"), ("kv","Uptime",uptime()),
            ("kv","Education",EDUCATION), ("kv","Location",LOCATION), ("gap",),
            ("kv","Languages.Programming",PROGRAMMING), ("kv","Languages.Computer",COMPUTER), ("kv","Languages.Real",REAL),
            ("kv","Top.Language",s.get("top_lang","-")), ("gap",),
            ("kv","Hobbies.Software",HOB_SOFT), ("kv","Hobbies.Hardware",HOB_HARD), ("gap",)]
    if EXTRA_LINES:
        rows += [("kv", k, v) for k, v in EXTRA_LINES] + [("gap",)]
    rows += [("sec","Contact"), ("kv","Email.Personal",EMAIL), ("kv","Discord",DISCORD)] + [("gap",),
             ("sec","GitHub Stats"), ("kv","Repos",f"{s['repos']} {{Contributed: {s['contributed']}}}"),
             ("kv","Commits",f"{s['commits']:,}"), ("kv","Stars / Followers",f"{s['stars']:,} / {s['followers']:,}"), ("kv","Last.Commit",s.get("last_commit","-")), ("loc",)]
    LHR = 26
    hg = lambda r: {"head":40,"gap":14,"sec":LHR+4}.get(r[0], LHR)
    block_h = sum(hg(r) for r in rows) + 30
    H = int(max(ROWS * LH, block_h) + 60)
    top_art = (H - ROWS * LH) / 2; y = (H - block_h) / 2 + 22
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         '<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono","Courier New",monospace;white-space:pre}'
         '.a{opacity:0;animation:f .3s forwards}@keyframes f{to{opacity:1}}@keyframes b{50%{opacity:0}}.cur{animation:b 1s step-end infinite}</style>',
         f'<rect width="{W}" height="{H}" rx="12" fill="#0d1117"/>']
    for i, row in enumerate(rows_art):
        runs = []; cur = None; buf = ""
        for ch, c in row:
            key = None if c is None else "#%02x%02x%02x" % tuple(c)
            if ch == " ": key = cur
            if key != cur and buf: runs.append((cur, buf)); buf = ""
            cur = key; buf += ch
        if buf: runs.append((cur, buf))
        sp = "".join((f'<tspan fill="{k}">{html.escape(t)}</tspan>' if k else html.escape(t)) for k, t in runs)
        o.append(f'<text class="a" x="{PADL}" y="{top_art+i*LH+AFS:.1f}" font-size="{AFS:.2f}" textLength="{COLS*CW:.1f}" lengthAdjust="spacing" style="animation-delay:{0.2+i*0.03:.2f}s">{sp}</text>')
    t = 1.4; defs = []; body = []; step = 0
    for r in rows:
        k = r[0]
        if k == "gap": y += 14; continue
        step += 1; cid = f"c{step}"
        if k == "head":
            n = 11; yy = y + 10; adv = 40
            txt = (f'<tspan font-size="22" font-weight="bold" fill="{GOLD}">mert</tspan><tspan font-size="22" font-weight="bold" fill="#8b949e">@</tspan>'
                   f'<tspan font-size="22" font-weight="bold" fill="{GOLD}">github</tspan>')
        elif k == "sec":
            n = 44; yy = y; adv = LHR + 4
            txt = f'<tspan fill="{ORANGE}" font-weight="bold">— {r[1]}</tspan><tspan fill="#484f58"> {"-"*(36-len(r[1]))}</tspan>'
        elif k == "loc":
            n = 48; yy = y; adv = LHR
            txt = (f'<tspan fill="{GRAY}">· </tspan><tspan fill="{GOLD}">Lines of Code:</tspan><tspan fill="{GRAY}"> {"."*11} </tspan>'
                   f'<tspan fill="{WHITE}" font-weight="bold">{loc:,}</tspan><tspan fill="{GRAY}"> ( </tspan><tspan fill="{GREEN}" font-weight="bold">{s["loc_add"]:,}++</tspan>'
                   f'<tspan fill="{GRAY}">, </tspan><tspan fill="{RED}" font-weight="bold">{s["loc_del"]:,}--</tspan><tspan fill="{GRAY}"> )</tspan>')
        else:
            key, v = r[1], r[2]; dots = "." * max(3, 26 - len(key) - 1); yy = y; adv = LHR
            n = 2 + len(key) + 1 + len(dots) + 2 + len(v)
            txt = (f'<tspan fill="{GRAY}">· </tspan><tspan fill="{GOLD}">{html.escape(key)}:</tspan><tspan fill="{GRAY}"> {dots} </tspan>'
                   f'<tspan fill="{WHITE}">{html.escape(v)}</tspan>')
        dur = max(0.2, n * 0.007)
        defs.append(f'<clipPath id="{cid}"><rect x="{RX-4:.1f}" y="{yy-26:.1f}" height="40" width="0"><animate attributeName="width" from="0" to="{RIGHT_W+20:.0f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
        body.append(f'<text x="{RX:.1f}" y="{yy:.1f}" font-size="{FS}" clip-path="url(#{cid})">{txt}</text>')
        t += dur + 0.05; y += adv
    o.append("<defs>" + "".join(defs) + "</defs>"); o += body
    o.append(f'<rect class="cur" x="{RX:.1f}" y="{y-12:.1f}" width="9" height="18" fill="{GREEN}" opacity="0" style="animation-delay:{t:.2f}s"/>')
    o.append("</svg>")
    return "\n".join(o)

if __name__ == "__main__":
    cp = os.path.join(HERE, "stats_cache.json")
    cache = json.load(open(cp))
    stats = cache if "--offline" in sys.argv else fetch_stats(cache)
    svg = build(stats)
    open(os.path.join(HERE, "profile-card.svg"), "w", encoding="utf-8").write(svg)
    json.dump(stats, open(cp, "w"), indent=1)
    print("tamam:", stats)
