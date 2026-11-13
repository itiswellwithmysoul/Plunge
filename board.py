#!/usr/bin/env python3
"""Fort Worden Beach Board: fetch this month's conditions and build the one-screen board.

Run:  python3 board.py            -> writes beach-board.html in the current folder
Data: NOAA CO-OPS gauge 9444900 (tides, water level, wind, pressure, temps), NDBC buoy 46088
      (waves, exposed wind), National Weather Service (today's forecast gusts, rain, alerts).
Design: light edition of The Third Chapter's board config (Geist + Newsreader, ruled cards, numbered kickers), PT Plungers brand.
Needs network access to api.tidesandcurrents.noaa.gov, api.weather.gov and www.ndbc.noaa.gov.
"""
import json, math, html, urllib.request as U, datetime as dt

LAT, LON = 48.135, -122.765
PST = dt.timezone(dt.timedelta(hours=-8))
UA = {"User-Agent": "plunge-board (Fort Worden)"}
GAUGE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=9444900&units=english&time_zone=lst&format=json"
# NOAA 9444900 records (STND->MLLW is -3.36 ft) and Nov 2016-2025 gauge history
BENCH = {"record": 12.00, "record_date": "Dec 27, 2022", "minor_flood": 10.50, "hat": 10.09, "mhhw": 8.52,
         "nov_peak": 10.72, "nov_wt": (48.9, 51.1), "nov_wt_max": 55.6, "nov_p_min": 988.0}
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def get(url, js=True):
    for _ in range(3):
        try:
            r = U.urlopen(U.Request(url, headers=UA), timeout=40).read().decode()
            return json.loads(r) if js else r
        except Exception as e:
            err = e
    raise err

now = dt.datetime.now(PST)
today = now.date()
first = today.replace(day=1)
ahead = today + dt.timedelta(days=7)
d8 = lambda d: d.strftime("%Y%m%d")
T = lambda s: dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=PST)

# ---------------- fetch ----------------
pred = get(GAUGE + f"&product=predictions&datum=MLLW&begin_date={d8(first)}&end_date={d8(ahead)}")["predictions"]
hilo = get(GAUGE + f"&product=predictions&datum=MLLW&interval=hilo&begin_date={d8(first)}&end_date={d8(ahead)}")["predictions"]
obs = get(GAUGE + f"&product=water_level&datum=MLLW&begin_date={d8(first)}&end_date={d8(today)}").get("data", [])
met = {}
for p in ["wind", "air_pressure", "water_temperature", "air_temperature"]:
    met[p] = get(GAUGE + f"&product={p}&interval=h&begin_date={d8(first)}&end_date={d8(today)}").get("data", [])
latest = {p: (get(GAUGE + f"&product={p}&date=latest").get("data") or [None])[0] for p in ["wind", "air_pressure", "water_temperature", "air_temperature"]}
buoy_txt = get("https://www.ndbc.noaa.gov/data/realtime2/46088.txt", False).splitlines()
pt = get(f"https://api.weather.gov/points/{LAT},{LON}")["properties"]
hourly = get(pt["forecastHourly"])["properties"]["periods"]
grid = get(pt["forecastGridData"])["properties"]
alerts = [f["properties"]["event"] for f in get("https://api.weather.gov/alerts/active?zone=PZZ134")["features"]]
alerts += [f["properties"]["event"] for f in get(f"https://api.weather.gov/alerts/active?point={LAT},{LON}")["features"]]

# ---------------- organise by day ----------------
def key(t): return t.strftime("%Y-%m-%d")
def mins(t): return t.hour * 60 + t.minute
days = {}
def day(k): return days.setdefault(k, {"pred": [], "obs": [], "wind": [], "press": [], "wt": [], "at": [], "buoy": []})
for p in pred:
    t = T(p["t"]); day(key(t))["pred"].append([mins(t), round(float(p["v"]), 2)])
for p in obs:
    if p["v"]:
        t = T(p["t"]); day(key(t))["obs"].append([mins(t), round(float(p["v"]), 2)])
for p in met["wind"]:
    if p["s"]:
        t = T(p["t"]); day(key(t))["wind"].append([mins(t), float(p["s"]) * 1.151, float(p["g"] or 0) * 1.151, p["dr"]])
for name, k2 in [("air_pressure", "press"), ("water_temperature", "wt"), ("air_temperature", "at")]:
    for p in met[name]:
        if p["v"]:
            t = T(p["t"]); day(key(t))[k2].append([mins(t), float(p["v"])])
bh = buoy_txt[0].lstrip("#").split()
for line in buoy_txt[2:]:
    r = dict(zip(bh, line.split()))
    t = dt.datetime(int(r["YY"]), int(r["MM"]), int(r["DD"]), int(r["hh"]), int(r["mm"]), tzinfo=dt.timezone.utc).astimezone(PST)
    if t.date() < first: continue
    num = lambda f, c=1.0: None if r[f] == "MM" else float(r[f]) * c
    day(key(t))["buoy"].append([mins(t), num("WVHT", 3.281), num("GST", 2.237), num("WSPD", 2.237), num("PRES")])
for k in days:
    for s in days[k].values(): s.sort(key=lambda x: x[0])

# ---------------- sun ----------------
def sun(d):
    n = d.timetuple().tm_yday; g = 2 * math.pi / 365 * (n - 1)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = 0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g)
    la = math.radians(LAT)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(dec)) - math.tan(la) * math.tan(dec)))
    rise = 720 - 4 * (LON + ha) - eq - 480; set_ = 720 - 4 * (LON - ha) - eq - 480
    return round(rise), round(set_)

# ---------------- helpers ----------------
def clock(m):
    m = int(round(m)) % 1440; h, mm = divmod(m, 60)
    return f"{h % 12 or 12}:{mm:02d} {'am' if h < 12 else 'pm'}"
def ft(x): return ("−" if x < 0 else "") + f"{abs(x):.1f}"
def band(v, g, r): return "go" if v < g else ("warn" if v < r else "stop")
ORDER = {"go": 0, "warn": 1, "stop": 2, "info": -1, "none": -1}
NAMES = {"resid": "high water", "gust": "gusts", "wave": "waves", "press": "falling pressure", "rain": "heavy rain", "alert": "a gale warning"}
HREF = {"resid": "https://tidesandcurrents.noaa.gov/waterlevels.html?id=9444900", "gust": "https://www.ndbc.noaa.gov/station_page.php?station=46088",
        "wave": "https://www.ndbc.noaa.gov/station_page.php?station=46088", "alert": "https://forecast.weather.gov/shmrn.php?mz=PZZ134",
        "press": "https://tidesandcurrents.noaa.gov/met.html?id=9444900", "rain": "https://forecast.weather.gov/MapClick.php?lat=48.135&lon=-122.765",
        "water": "https://tidesandcurrents.noaa.gov/physocean.html?id=9444900", "wind": "https://tidesandcurrents.noaa.gov/met.html?id=9444900"}
def tile(k, label, kick, val, sub, s): return {"k": k, "l": label, "kk": kick, "v": val, "s": sub, "st": s, "h": HREF[k]}
def press_drop(series):
    worst = 0.0
    for i, (t, v) in enumerate(series):
        prev = [pv for pt_, pv in series if t - 180 <= pt_ < t - 170]
        if prev: worst = min(worst, v - prev[0])
    return worst

# NWS today
def expand(vals, conv):
    out = []
    for v in vals:
        a, b = v["validTime"].split("/"); s = dt.datetime.fromisoformat(a).astimezone(PST)
        n = int(b.replace("PT", "").replace("H", "")) if b.startswith("PT") and b.endswith("H") else 1
        out += [(s + dt.timedelta(hours=i), None if v["value"] is None else v["value"] * conv) for i in range(n)]
    return out
gusts = expand(grid["windGust"]["values"], 1 / 1.609)
qpf = expand(grid["quantitativePrecipitation"]["values"], 1 / 25.4)
hr = [(dt.datetime.fromisoformat(p["startTime"]).astimezone(PST), p) for p in hourly]
hr_now = next((p for t, p in hr if t <= now < t + dt.timedelta(hours=1)), hr[0][1])

# ---------------- per-day summaries ----------------
summ = {}
k_today = key(now)
for k in sorted(days):
    D = days[k]; d = dt.date.fromisoformat(k); is_today = k == k_today; future = d > today
    pmap = dict((t, h) for t, h in D["pred"])
    rs = [h - pmap[t] for t, h in D["obs"] if t in pmap]
    rise, sset = sun(d)
    S = {"date": k, "label": f"{WD[d.weekday()]}, {d.strftime('%b')} {d.day}", "sun": [rise, sset], "mode": "future" if future else ("today" if is_today else "past")}
    st = {}; tiles = []
    if future or not D["obs"]:
        his = [x for x in hilo if x["t"].startswith(k)]
        hi = max(his, key=lambda x: float(x["v"])) if his else None
        S["big"] = ft(float(hi["v"])) if hi else "—"
        S["bigtx"] = f"Predicted high at <b>{clock(mins(T(hi['t'])))}</b>. Forecast conditions aren't stored ahead; check the day before." if hi else "No predictions."
        S["kick"] = "01 / Predicted tide"; S["verdict"] = ("info", "A look ahead.", "Predicted tides only.")
        S["resid"] = 0; S["tiles"] = []; summ[k] = S; continue
    resid = (sum(rs[-30:]) / len(rs[-30:])) if is_today else (sum(rs) / len(rs) if rs else 0)
    peak_t, peak_h = max(D["obs"], key=lambda x: x[1])
    S["peak"] = [peak_t, peak_h]; S["resid"] = round(resid, 2)
    st["resid"] = "warn" if resid >= 1.0 else "go"   # informational: high water is worth knowing, not a stop
    tiles.append(tile("resid", "Above prediction", "Gauge", f"{resid:+.1f} ft", f"{min(rs):+.1f} to {max(rs):+.1f} through the day" if rs else "", st["resid"]))
    day_b = [b for b in D["buoy"] if rise <= b[0] <= sset]
    if is_today:
        g6 = max([g for t, g in gusts if now <= t <= now + dt.timedelta(hours=6) and g is not None] or [0])
        st["gust"] = band(g6, 20, 26)
        tiles.append(tile("gust", "Gusts", "NWS · next 6 h", f"{g6:.0f} mph", f"{hr_now['windDirection']} {hr_now['windSpeed']} now", st["gust"]))
    else:
        bg = [b[2] for b in day_b if b[2] is not None]
        g = max(bg) if bg else None
        st["gust"] = band(g, 20, 26) if g is not None else "none"
        tiles.append(tile("gust", "Gusts", "Buoy · daylight max", f"{g:.0f} mph" if g is not None else "—", "measured at New Dungeness", st["gust"]))
    waves = [b[1] for b in (day_b if not is_today else D["buoy"][-6:]) if b[1] is not None]
    wv = (waves[-1] if is_today else max(waves)) if waves else None
    st["wave"] = band(wv, 1, 3) if wv is not None else "none"
    tiles.append(tile("wave", "Waves", "Buoy 46088" + ("" if is_today else " · day max"), f"{wv:.1f} ft" if wv is not None else "—", "New Dungeness", st["wave"]))
    if is_today:
        st["alert"] = "stop" if any(w in a for a in alerts for w in ("Gale Warning", "Storm Warning", "Hurricane")) else ("warn" if alerts else "go")
        tiles.append(tile("alert", "Marine alerts", "NWS", alerts[0] if alerts else "None", " + ".join(alerts[1:]) or "Admiralty Inlet", st["alert"]))
    else:
        tiles.append(tile("alert", "Marine alerts", "NWS", "—", "past alerts aren't archived", "info"))
    if D["press"]:
        pv = D["press"][-1][1] if is_today else min(v for t, v in D["press"])
        drop = press_drop(D["press"][-4:] if is_today else D["press"])
        st["press"] = "stop" if drop <= -3 else ("warn" if drop < -0.5 else "go")
        lvl = "high, settled" if pv >= 1020 else ("normal" if pv >= 1009 else ("lowish, unsettled" if pv >= 1000 else "low, stormy"))
        trend = "falling" if drop <= -1 else ("rising" if drop >= 1 else "steady")
        tiles.append(tile("press", "Air pressure", "Gauge" + ("" if is_today else " · day low"), f"{pv:.0f} mb · {lvl.split(',')[0]}", f"{lvl.capitalize()} (normal ~1013) · {trend}", st["press"]))
    if is_today:
        r12 = sum(q for t, q in qpf if now <= t <= now + dt.timedelta(hours=12) and q is not None)
        st["rain"] = band(r12, 0.25, 1.0)
        tiles.append(tile("rain", "Rain", "NWS · next 12 h", f"{r12:.2f} in", "runoff raises bacteria", st["rain"]))
    else:
        tiles.append(tile("rain", "Rain", "Measured", "—", "no rain gauge on record nearby", "info"))
    if D["wt"]:
        wt = (latest["water_temperature"] and float(latest["water_temperature"]["v"])) if is_today else sum(v for t, v in D["wt"]) / len(D["wt"])
        at = D["at"][-1][1] if (is_today and D["at"]) else (sum(v for t, v in D["at"]) / len(D["at"]) if D["at"] else None)
        tiles.append(tile("water", "Water", "Gauge" + ("" if is_today else " · day avg"), f"{wt:.1f}°F",
                          ("warmest Nov in 10 yrs" if wt > BENCH["nov_wt_max"] else f"Nov normal {BENCH['nov_wt'][0]}–{BENCH['nov_wt'][1]}°") + (f" · air {at:.0f}°" if at else ""), "info"))
    if D["wind"]:
        w = D["wind"][-1] if is_today else max(D["wind"], key=lambda x: x[2])
        tiles.append(tile("wind", "Wind" + (" now" if is_today else ""), "Gauge" + ("" if is_today else " · max"), f"{w[1]:.0f} mph", f"{w[3]} · gust {w[2]:.0f} · harbor, reads low", "info"))
    WORDS = {"gust": "gusty", "wave": "choppy", "resid": "high water", "alert": "marine alert up", "rain": "wet", "press": "pressure falling"}
    flagged = sorted([n for n, x in st.items() if x in ("warn", "stop")], key=lambda n: -ORDER[st[n]])
    if flagged:
        phrase = ", ".join(WORDS[n] for n in flagged[:2]) + "."
        head = phrase[0].upper() + phrase[1:]
    else:
        head = "Calm and quiet."
    v = ("info", head, "Here's what's out there. Your call." if is_today else "Here's what it was like.")
    S["verdict"] = v; S["tiles"] = tiles
    if is_today:
        lt, lh = D["obs"][-1]
        S["kick"] = "01 / Tide right now"; S["big"] = ft(lh)
        nxt = next((x for x in hilo if T(x["t"]) > now), None)
        S["bigtx"] = (f"Tables said <b>{ft(pmap.get(lt, lh))} ft</b> at {clock(lt)}: running <span class='r'>{resid:+.1f} ft high</span>."
                      + (f" Next {'high' if nxt['type']=='H' else 'low'} <b>{(WD[T(nxt['t']).weekday()] + ' ') if T(nxt['t']).date()!=today else ''}{clock(mins(T(nxt['t'])))}</b>, {ft(float(nxt['v']))} ft." if nxt else ""))
        S["asof"] = clock(lt)
    else:
        S["kick"] = f"01 / Tide on {d.strftime('%b')} {d.day}"; S["big"] = ft(peak_h)
        S["bigtx"] = f"Peak at <b>{clock(peak_t)}</b>. Water ran <span class='r'>{resid:+.1f} ft</span> {'above' if resid >= 0 else 'below'} the tables on average."
    summ[k] = S

month_peak = max((s["peak"][1], k) for k, s in summ.items() if "peak" in s)
J = {"days": days, "summ": summ, "today": k_today, "first": key(dt.datetime.combine(first, dt.time(), PST)), "last": key(dt.datetime.combine(ahead, dt.time(), PST)),
     "bench": BENCH, "built": now.strftime("%b %-d, %-I:%M %p").replace("AM", "am").replace("PM", "pm"), "mpeak": month_peak}

# ---------------- page ----------------
CSS = open(__file__).read().split("#CSS-START\n")[1].split("#CSS-END")[0] if False else None
page = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fort Worden Beach Board</title>
<meta name="description" content="Daily cold-plunge conditions for Fort Worden, Port Townsend: measured vs predicted tide, wind, waves, pressure and water temperature.">
<meta name="theme-color" content="#F6F5F1">
<meta property="og:type" content="website">
<meta property="og:title" content="The Plunge Board · Fort Worden">
<meta property="og:description" content="Today's tide, wind, waves and water temperature at Fort Worden, with a go/no-go read for plungers.">
<meta property="og:url" content="https://itiswellwithmysoul.github.io/Plunge/">
<meta property="og:image" content="https://itiswellwithmysoul.github.io/Plunge/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%276%27 fill=%27%23F6F5F1%27/%3E%3Crect x=%279%27 y=%279%27 width=%2714%27 height=%2714%27 rx=%272%27 fill=%27%23C99E28%27/%3E%3C/svg%3E">

<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap">
<style>
:root{--bg:#F6F5F1;--card:#FFFFFF;--line:#E3E1DA;--ink:#0F1B2D;--muted:#5A6577;--faint:#8C94A3;--coral:#D9533B;--blue:#2F6FEB;--amber:#C98A00;--teal:#1A8C7C;--gold:#C99E28;--up:#178A5B;--down:#D23C2F;--warn:#B98200;--lead:var(--gold);
 --f-sans:"Geist","Helvetica Neue",Arial,system-ui,sans-serif;--f-serif:"Newsreader",Georgia,serif;color-scheme:light}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:13px/1.4 var(--f-sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:430px;margin:0 auto;padding:10px 12px 8px;display:grid;gap:8px}
.brand{display:flex;justify-content:space-between;align-items:center;padding-bottom:8px;border-bottom:1px solid var(--line)}
.brand .name{font-weight:600;font-size:13.5px;display:flex;align-items:center;gap:7px}
.brand .name .logo{height:34px;width:auto;display:block}.wm b{display:block;font:800 15px/1 var(--f-sans);letter-spacing:-.01em}.wm small{display:block;font:600 8.5px/1.3 var(--f-sans);letter-spacing:.16em;text-transform:uppercase;color:var(--gold);margin-top:3px}
.brand input{font:600 11px var(--f-sans);letter-spacing:.04em;color:var(--ink);background:var(--card);border:1px solid var(--ink);padding:4px 6px;color-scheme:light;border-radius:0}
.hero h1{font:800 30px/1 var(--f-sans);letter-spacing:-.035em}
.hero h1 span{font-size:17px;letter-spacing:-.01em;margin-left:4px;color:var(--lead)}
.hero h1{color:var(--ink)}.hero.stop h1 span{color:var(--down)}.hero.warn h1 span{color:var(--warn)}.hero.go h1 span{color:var(--up)}.hero.info h1 span{color:var(--gold)}
.dl{display:flex;justify-content:space-between;margin-top:5px;font-size:11.5px}.dl em{font-style:normal;color:var(--muted)}
.dl button{font:600 9.5px/1 var(--f-sans);letter-spacing:.12em;text-transform:uppercase;color:var(--teal);background:none;border:0;cursor:pointer;padding:0}
.card{background:var(--card);border:1px solid var(--line);box-shadow:0 1px 0 rgba(15,27,45,.04),0 8px 24px -18px rgba(15,27,45,.25);border-top:3px solid var(--c);padding:10px 11px 11px;display:grid;gap:7px}
.c-teal{--c:var(--teal)}.c-blue{--c:var(--blue)}
.kick{display:flex;justify-content:space-between;font:600 9.5px/1.3 var(--f-sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}.kick b{color:var(--c);font-weight:600}
.now{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:end}
.big{font:400 44px/.85 var(--f-serif);font-variant-numeric:tabular-nums}.big small{font:500 12px var(--f-sans);color:var(--muted);margin-left:2px}
.nowtx{font-size:11.5px;color:var(--muted);line-height:1.35}.nowtx b{color:var(--ink);font-weight:600}.nowtx .r{color:var(--down);font-weight:700}
svg{display:block;width:100%;height:auto;overflow:visible}svg text{font-family:var(--f-sans);fill:var(--faint)}#tc{touch-action:none}
.ro{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:var(--muted);min-height:15px}.ro b{color:var(--ink);font-weight:600}
.lg{display:flex;gap:10px;white-space:nowrap}.lg i{display:inline-block;width:10px;height:2px;vertical-align:middle;margin-right:3px}
.sub{display:flex;justify-content:space-between;align-items:baseline;gap:6px;font:600 8.5px/1.3 var(--f-sans);letter-spacing:.14em;text-transform:uppercase;color:var(--faint);border-top:1px solid var(--line);padding-top:7px}
.sub b{color:var(--ink);font-size:11px;letter-spacing:0;text-transform:none;font-weight:600;text-align:right}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
a.t{display:grid;text-decoration:none;color:inherit;background:var(--bg);border:1px solid var(--line);border-left:3px solid var(--s);padding:5px 8px 6px;min-width:0}
a.t.go{--s:var(--up)}a.t.warn{--s:var(--warn)}a.t.stop{--s:var(--down)}a.t.info,a.t.none{--s:var(--line)}
.tk{display:flex;justify-content:space-between;gap:4px;font-weight:600;font-size:11px;white-space:nowrap}
.tk em{font:600 8px/1.6 var(--f-sans);font-style:normal;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);overflow:hidden;text-overflow:ellipsis}
a.t b{font:400 21px/1.1 var(--f-serif);font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
a.t.stop b{color:var(--down)}a.t.warn b{color:var(--warn)}
.ts{font-size:10px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.empty{font-size:12px;color:var(--muted);padding:6px 0}
.stale{border:1px solid var(--warn);color:var(--warn);font-size:11.5px;padding:7px 9px}
.cols{display:grid;gap:8px}
.about{border-top:1px solid var(--line);padding-top:12px;margin-top:6px}
.about h2{font:700 18px/1.15 var(--f-sans);letter-spacing:-.015em;margin-bottom:8px}
.acols{display:grid;gap:10px}
.acols b{display:block;font:600 9.5px/1.3 var(--f-sans);letter-spacing:.14em;text-transform:uppercase;color:var(--teal);margin-bottom:3px}
.acols p{font-size:12.5px;color:var(--muted);line-height:1.5}
.site{position:sticky;top:0;z-index:5;background:rgba(246,245,241,.92);backdrop-filter:saturate(1.4) blur(10px);-webkit-backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--line)}
.site .bar{max-width:1120px;margin:0 auto;padding:10px 12px;display:flex;align-items:center;gap:14px}
.site .name{white-space:nowrap;display:flex;align-items:center;gap:8px;font:800 15px/1 var(--f-sans);letter-spacing:-.01em;color:var(--ink);text-decoration:none}
.site .name i{width:12px;height:12px;background:var(--gold);border-radius:2px;display:inline-block}
.site nav{display:flex;gap:14px;margin-left:auto}.site nav + .pick{margin-left:0}.site nav a{font:600 11px/1 var(--f-sans);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);text-decoration:none}.site nav a:hover{color:var(--ink)}
.pick{display:flex;align-items:center;gap:6px;margin-left:auto}@media (max-width:620px){.site nav{display:none}.pick{margin-left:auto!important}}
.hero h1 span{display:block;margin:6px 0 0!important;font-size:19px!important}.pick span{display:none}
.pick input{font:600 12px var(--f-sans);color:var(--ink);background:var(--card);border:1px solid var(--ink);padding:5px 7px;border-radius:0;color-scheme:light}
.eyebrow{display:block;font:600 9.5px/1.3 var(--f-sans);letter-spacing:.16em;text-transform:uppercase;color:var(--gold);margin-bottom:8px}
.hero{padding:14px 0 4px}
.shead{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px 10px;margin-top:14px}
.shead h2{font:700 24px/1.05 var(--f-sans);letter-spacing:-.025em}.shead span{font:600 9.5px/1.2 var(--f-sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.glance{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 14px;margin-top:14px}
.glance div{border-left:2px solid var(--c,var(--gold));padding:1px 0 1px 10px;font-size:12px;color:var(--muted)}
.glance div.stop{--c:var(--down)}.glance div.warn{--c:var(--warn)}.glance div.go{--c:var(--up)}.glance div.info,.glance div.none{--c:var(--line)}
.glance b{display:block;font:600 9px/1.4 var(--f-sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.glance strong{display:block;font:400 24px/1.1 var(--f-serif);color:var(--ink)}
.card.c-blue{border-top-color:var(--blue)}
@media (min-width:760px){
 .site .bar{padding:14px 24px}.site .name{font-size:18px}.site nav{gap:26px}.site nav a{font-size:12px}.pick span{display:inline;font:600 10px var(--f-sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}.pick input{font-size:13px;padding:7px 10px}
 .hero{padding:40px 0 10px}.eyebrow{font-size:11px;margin-bottom:14px}
 .glance{grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;margin-top:26px}.glance strong{font-size:34px}.glance div{font-size:13px}
 .shead{margin-top:34px}.shead h2{font-size:clamp(30px,3.6vw,40px)}.shead span{font-size:10.5px}
 #conditions + .card .grid{grid-template-columns:repeat(4,minmax(0,1fr))}

 #tide + .card{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.5fr);column-gap:34px;row-gap:12px;align-items:start}
 #tide + .card .kick{grid-column:1/-1}
 #tide + .card .now{grid-column:1;grid-row:2;grid-template-columns:1fr;gap:12px}
 #tide + .card .sub{grid-column:1;grid-row:3}
 #tide + .card #rec{grid-column:1;grid-row:4}
 #tide + .card #tc{grid-column:2;grid-row:2/5}
 #tide + .card .ro{grid-column:2;grid-row:5}
 #tide + .card .big{font-size:96px}
}
@media (min-width:760px){
 body{font-size:14px}
 .wrap{max-width:1120px;padding:22px 24px 28px;gap:14px}
 .brand .name{font-size:16px}.brand input{font-size:13px;padding:7px 10px}
 .hero h1{font-size:clamp(40px,5.4vw,64px)}.hero h1 span{display:block;font-size:clamp(22px,2.6vw,30px);margin:6px 0 0}
 .dl{font-size:13.5px;margin-top:10px}
 .cols{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:14px;align-items:start}
 .card{padding:18px 20px 20px;gap:12px}
 .kick{font-size:10.5px}
 .big{font-size:72px}.nowtx{font-size:14px}
 .ro{font-size:12.5px}.sub b{font-size:13px}
 .grid{gap:10px}a.t{padding:10px 12px 11px}a.t b{font-size:28px}.tk{font-size:13px}.ts{font-size:11.5px}
 .acols{grid-template-columns:repeat(4,minmax(0,1fr));gap:20px}
 .about h2{font-size:24px}.acols p{font-size:13px}
 .foot{font-size:11px}
}
.foot{font-size:9px;color:var(--faint);line-height:1.35;border-top:1px solid var(--line);padding-top:6px}
</style></head><body><header class="site"><div class="bar">
  <a class="name" href="#today"><i></i><span>PT Plungers</span></a>
  <nav><a href="#tide">Tide</a><a href="#conditions">Conditions</a><a href="#guide">Guide</a></nav>
  <label class="pick"><span>Day</span><input id="day" type="date" aria-label="Pick a day"></label>
</div></header>
<div class="wrap">
<section class="hero" id="hero"><span class="eyebrow">Fort Worden · Port Townsend · cold-plunge conditions</span><h1 id="h1"></h1><div class="dl"><b id="dlabel"></b><em id="asof"></em></div>
  <div class="glance" id="glance"></div></section>
<div class="stale" id="stale" hidden></div>
<div class="shead" id="tide"><h2>The tide.</h2><span>Measured vs predicted · NOAA 9444900</span></div>
<section class="card c-teal">
  <div class="kick"><span id="kick"></span><b>NOAA 9444900</b></div>
  <div class="now"><div class="big"><span id="big"></span><small>ft</small></div><div class="nowtx" id="bigtx"></div></div>
  <svg id="tc" viewBox="0 0 320 104" role="img" aria-label="Predicted and measured tide"></svg>
  <div class="ro"><span id="readout">Drag the chart to read any time</span><span class="lg"><span><i style="background:var(--teal)"></i>Pred.</span><span><i style="background:var(--ink)"></i>Meas.</span><span id="lgh"><i style="background:var(--coral)"></i>If high</span></span></div>
  <div class="sub"><span>Peak vs records</span><b id="recline"></b></div>
  <svg id="rec" viewBox="0 0 320 42" aria-label="Peak water level compared with flood level and records"></svg>
</section>
<div class="shead" id="conditions"><h2>Conditions.</h2><span>Tap any tile for the live source</span></div>
<section class="card c-blue">
  
  <div class="grid" id="grid"></div>
</section>
<section class="about" id="guide">
  <div class="shead"><h2>How to read the board.</h2><span>Colors flag what's unusual</span></div>
  <div class="acols">
    <div><b>Above prediction</b><p>Tide tables only know the moon and sun. Storms, low pressure and this winter's El Niño push the water higher. A foot or more over the tables is flagged: the beach is narrower and logs can float. Air pressure plays in too: normal is about 1013 mb, and lower means stormier weather and higher water.</p></div>
    <div><b>Gusts and waves</b><p>Gusts over 20 mph are amber and over 25 red. Waves come from the New Dungeness buoy: 1–3 ft amber, over 3 ft red. At Fort Worden, wind from the north or west drives waves onto the beach; wind from the south or east flattens it but pushes floaters out.</p></div>
    <div><b>Your call</b><p>The colors flag what's unusual, not a rule: green is typical, amber is worth noticing, red is well outside normal. Whether to go in is up to you. Look at the beach too: logs moving at the waterline, waves at the top of the beach, a fresh bluff slide, lightning or failing light.</p></div>
    <div><b>Look back</b><p>Use the date box to see any day this month. Past days show what was measured; days ahead show predicted tides only. The board rebuilds every morning before 6 am.</p></div>
  </div>
</section>
<footer class="foot" id="foot"></footer>
</div>
<script type="application/json" id="d">__DATA__</script>
<script>
(function(){
var J=JSON.parse(document.getElementById('d').textContent),NS='http://www.w3.org/2000/svg',W=320,DAY=1440,B=J.bench;
function mk(t,a,p){var n=document.createElementNS(NS,t);for(var k in a)n.setAttribute(k,a[k]);if(p)p.appendChild(n);return n;}
function clock(m){m=((Math.round(m)%DAY)+DAY)%DAY;var h=Math.floor(m/60),mm=m%60,ap=h<12?'am':'pm';h=h%12||12;return h+':'+(mm<10?'0':'')+mm+' '+ap;}
function f1(x){return (x<0?'−':'')+Math.abs(x).toFixed(1);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function interp(a,m){for(var i=0;i<a.length-1;i++){if(m>=a[i][0]&&m<=a[i+1][0])return [a[i][1]+(a[i+1][1]-a[i][1])*(m-a[i][0])/(a[i+1][0]-a[i][0]),a[i+1][1]>a[i][1]];}return null;}
var inp=document.getElementById('day'),svg=document.getElementById('tc'),out=document.getElementById('readout'),cur,cl,cc,DD,SS,lo,hi;
inp.min=J.first;inp.max=J.last;
var top=8,bot=86;function x(m){return m/DAY*W;}function y(h){return bot-(h-lo)/(hi-lo)*(bot-top);}
function render(k){
  DD=J.days[k];SS=J.summ[k];if(!DD||!SS){return;}inp.value=k;
  var v=SS.verdict,hero=document.getElementById('hero');hero.className='hero '+v[0];
  document.getElementById('h1').innerHTML=esc(v[1])+'<span>'+esc(v[2])+'</span>';
  document.getElementById('dlabel').textContent=SS.label;
  document.getElementById('asof').innerHTML=SS.mode==='today'?'Readings as of '+SS.asof:'<button type="button" id="back">Back to today</button>';
  var bk=document.getElementById('back');if(bk)bk.onclick=function(){render(J.today);history.replaceState(null,'',location.pathname);};
  document.getElementById('kick').textContent=SS.kick.replace('01 / ','');
  document.getElementById('big').textContent=SS.big;document.getElementById('bigtx').innerHTML=SS.bigtx;
  document.getElementById('lgh').style.display=SS.mode==='today'?'':'none';
  /* chart */
  while(svg.firstChild)svg.removeChild(svg.firstChild);
  var P=DD.pred,O=DD.obs,all=P.map(function(p){return p[1];}).concat(O.map(function(p){return p[1];}));
  lo=Math.min.apply(null,all.concat([0]))-0.4;hi=Math.max.apply(null,all)+0.5;
  mk('rect',{x:0,y:top-6,width:x(SS.sun[0]),height:bot-top+6,fill:'#0F1B2D',opacity:.05},svg);
  mk('rect',{x:x(SS.sun[1]),y:top-6,width:W-x(SS.sun[1]),height:bot-top+6,fill:'#0F1B2D',opacity:.05},svg);
  [0,4,8].forEach(function(v){if(v<lo||v>hi)return;mk('line',{x1:0,x2:W,y1:y(v),y2:y(v),stroke:'#E3E1DA'},svg);var t=mk('text',{x:W,y:y(v)-2,'text-anchor':'end','font-size':8},svg);t.textContent=v+' ft';});
  if(P.length){var d='M'+P.map(function(p){return x(p[0]).toFixed(1)+' '+y(p[1]).toFixed(1);}).join(' L');
    mk('path',{d:d+' L'+x(P[P.length-1][0])+' '+bot+' L'+x(P[0][0])+' '+bot+' Z',fill:'#1A8C7C',opacity:.14},svg);
    mk('path',{d:d,fill:'none',stroke:'#1A8C7C','stroke-width':2},svg);}
  if(SS.mode==='today'&&O.length){var last=O[O.length-1][0],F=P.filter(function(p){return p[0]>=last;});
    if(F.length)mk('path',{d:'M'+F.map(function(p){return x(p[0]).toFixed(1)+' '+y(p[1]+SS.resid).toFixed(1);}).join(' L'),fill:'none',stroke:'#D9533B','stroke-width':1.6,'stroke-dasharray':'4 3'},svg);}
  if(O.length){mk('path',{d:'M'+O.map(function(p){return x(p[0]).toFixed(1)+' '+y(p[1]).toFixed(1);}).join(' L'),fill:'none',stroke:'#0F1B2D','stroke-width':2.2},svg);
    var mp=SS.mode==='today'?O[O.length-1]:SS.peak;mk('circle',{cx:x(mp[0]),cy:y(mp[1]),r:3.5,fill:'#FFFFFF',stroke:'#0F1B2D','stroke-width':2.2},svg);}
  [0,360,720,1080,1440].forEach(function(t,i){var tx=mk('text',{x:x(t),y:99,'text-anchor':i===0?'start':i===4?'end':'middle','font-size':8},svg);tx.textContent=['12a','6a','noon','6p','12a'][i];});
  cur=mk('g',{opacity:0},svg);cl=mk('line',{y1:top-6,y2:bot,stroke:'#2F6FEB'},cur);cc=mk('circle',{r:4,fill:'#2F6FEB',stroke:'#FFFFFF','stroke-width':2},cur);
  out.textContent='Drag the chart to read any time';
  /* records */
  var rec=document.getElementById('rec');while(rec.firstChild)rec.removeChild(rec.firstChild);
  var pk=SS.peak?SS.peak[1]:null,rl=document.getElementById('recline');
  if(pk===null){var hs=P.map(function(p){return p[1];});pk=Math.max.apply(null,hs);rl.textContent='Predicted peak '+f1(pk)+' ft · '+(B.record-pk).toFixed(1)+' ft under record';}
  else rl.textContent=f1(pk)+' ft at '+clock(SS.peak[0])+' · '+(B.record-pk).toFixed(1)+' ft under record';
  var L=8,H=12.4;function X(v){return 4+(Math.max(L,Math.min(H,v))-L)/(H-L)*312;}
  mk('rect',{x:4,y:16,width:312,height:8,fill:'#ECEAE3'},rec);
  mk('rect',{x:X(B.minor_flood),y:16,width:316-X(B.minor_flood),height:8,fill:'#C99E28',opacity:.18},rec);
  mk('rect',{x:4,y:16,width:X(pk)-4,height:8,fill:SS.peak?'#1A8C7C':'#7FBFB4'},rec);
  [[B.mhhw,'Avg high','#8C94A3',0],[B.hat,'Max tide','#8C94A3',1],[B.minor_flood,'Flood','#B98200',0],[B.nov_peak,"Nov '21",'#5A6577',1],[B.record,'Record 12.0','#D23C2F',0]].forEach(function(m){
    var xx=X(m[0]);mk('line',{x1:xx,x2:xx,y1:m[3]?12:16,y2:m[3]?24:28,stroke:m[2],'stroke-width':1.4},rec);
    var t=mk('text',{x:xx,y:m[3]?9:38,'text-anchor':xx>290?'end':'middle','font-size':8.5,fill:m[2]},rec);t.textContent=m[1];});
  mk('circle',{cx:X(pk),cy:20,r:4.5,fill:'#FFFFFF',stroke:'#1A8C7C','stroke-width':2},rec);
  /* tiles */
  var g=document.getElementById('grid');
  g.innerHTML=SS.tiles.length?SS.tiles.map(function(t){return '<a class="t '+t.st+'" href="'+t.h+'" target="_blank" rel="noopener"><span class="tk">'+esc(t.l)+'<em>'+esc(t.kk)+'</em></span><b>'+esc(t.v)+'</b><span class="ts">'+esc(t.s)+'</span></a>';}).join(''):'<div class="empty">Conditions are stored for past days and today. For days ahead, the chart shows predicted tides only.</div>';
  var gl=document.getElementById('glance'),pick=function(k){return SS.tiles.filter(function(t){return t.k===k;})[0];};
  gl.innerHTML=['resid','gust','wave','water'].map(pick).filter(Boolean).map(function(t){return '<div class="'+t.st+'"><b>'+esc(t.l)+'</b><strong>'+esc(t.v)+'</strong>'+esc(t.s)+'</div>';}).join('');
  document.getElementById('foot').textContent='NOAA 9444900 (prelim.) · NWS · NDBC 46088 · updated '+J.built+'. Past days show measured conditions. Colors flag unusual conditions, not official limits.';
}
function show(m){m=Math.max(0,Math.min(DAY,m));var p=interp(DD.pred,m);if(!p)return;cur.setAttribute('opacity',1);cl.setAttribute('x1',x(m));cl.setAttribute('x2',x(m));cc.setAttribute('cx',x(m));cc.setAttribute('cy',y(p[0]));
  var o=null;DD.obs.forEach(function(q){if(Math.abs(q[0]-m)<=3)o=q[1];});
  var lastObs=DD.obs.length?DD.obs[DD.obs.length-1][0]:-1;
  out.innerHTML='<b>'+clock(m)+'</b> · pred. '+f1(p[0])+' ft '+(p[1]?'↑':'↓')+(o!==null?' · meas. '+f1(o):(SS.mode==='today'&&m>lastObs?' · ~'+f1(p[0]+SS.resid)+' if high':''));}
function evm(e){var r=svg.getBoundingClientRect(),cx=(e.touches?e.touches[0].clientX:e.clientX);return (cx-r.left)/r.width*DAY;}
svg.addEventListener('pointerdown',function(e){show(evm(e));});
svg.addEventListener('pointermove',function(e){if(e.buttons||e.pointerType==='mouse')show(evm(e));});
svg.addEventListener('touchmove',function(e){show(evm(e));e.preventDefault();},{passive:false});
inp.addEventListener('change',function(){if(J.summ[inp.value])render(inp.value);else inp.value=DD?SS.date:J.today;});
var vt=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Los_Angeles'}).format(new Date());if(vt>J.today){var sb=document.getElementById('stale');sb.hidden=false;sb.textContent='Heads up: this board was last refreshed '+J.built+'. Today\u2019s readings aren\u2019t in yet, so tap a tile for live data.';}
var h=(location.hash||'').replace('#d','');render(J.summ[h]?h:J.today);
})();
</script></body></html>"""
page = page.replace("__DATA__", json.dumps(J, separators=(",", ":")).replace("</", "<\\/"))
import os
open(os.environ.get("BOARD_OUT", "index.html" if os.path.exists(".git") else "beach-board.html"), "w").write(page)
print("built", k_today, "days", len(summ), "verdict", summ[k_today]["verdict"], f"{len(page)/1024:.0f} KB")
