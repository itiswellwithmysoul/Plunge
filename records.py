#!/usr/bin/env python3
"""One-time builder for records.json: monthly records at Port Townsend (NOAA 9444900) and buoy 46088.

board.py keeps records.json current after this: every refresh checks the newest readings and
raises a record when one is beaten. Re-run this script only to rebuild from scratch.
"""
import json, gzip, io, datetime as dt, urllib.request as U
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "plunge-board (Fort Worden)"}
GAUGE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=9444900&units=english&time_zone=lst&format=json"
THIS_YEAR = dt.date.today().year

def get(url, raw=False):
    for _ in range(3):
        try:
            b = U.urlopen(U.Request(url, headers=UA), timeout=90).read()
            return b if raw else json.loads(b.decode())
        except Exception as e:
            err = e
    raise err

rec = {m: {} for m in range(1, 13)}
def bump(m, key, val, when, hi=True):
    if val is None: return
    cur = rec[m].get(key)
    if cur is None or (val > cur["v"] if hi else val < cur["v"]):
        rec[m][key] = {"v": round(val, 2), "d": when}
since = {}

# 1) water level: monthly highest from NOAA's monthly means (back to 1972)
mm = get(GAUGE + f"&product=monthly_mean&datum=MLLW&begin_date=19700101&end_date={THIS_YEAR}1231").get("data", [])
for r in mm:
    if r.get("highest"):
        bump(int(r["month"]), "wl_max", float(r["highest"]), f"{r['year']}-{int(r['month']):02d}")
since["wl"] = min(int(r["year"]) for r in mm if r.get("highest"))

# 2) water temp, air temp, pressure: hourly, one year per request
def year(args):
    product, y = args
    try:
        return product, y, get(GAUGE + f"&product={product}&interval=h&begin_date={y}0101&end_date={y}1231").get("data", [])
    except Exception:
        return product, y, []
jobs = [(p, y) for p in ("water_temperature", "air_temperature", "air_pressure") for y in range(1992, THIS_YEAR + 1)]
with ThreadPoolExecutor(6) as ex:
    for product, y, rows in ex.map(year, jobs):
        k = {"water_temperature": "wt", "air_temperature": "at", "air_pressure": "p"}[product]
        for r in rows:
            if not r["v"]: continue
            v = float(r["v"]); m = int(r["t"][5:7]); d = r["t"][:10]
            if product == "air_pressure" and not (930 < v < 1070): continue
            if product != "air_pressure" and not (10 < v < 100): continue
            bump(m, k + "_max", v, d, True); bump(m, k + "_min", v, d, False)
            since[k] = min(since.get(k, 9999), y)

# 3) buoy 46088 waves and gusts: NDBC yearly archives, then this year's recent file
def buoy_rows(text):
    lines = text.splitlines(); head = lines[0].lstrip("#").split()
    for ln in lines[1:]:
        if ln.startswith("#"): continue
        r = dict(zip(head, ln.split()))
        yy = r.get("YY") or r.get("YYYY")
        if not yy: continue
        yield int(yy), int(r["MM"]), int(r["DD"]), r
def buoy_year(y):
    try:
        b = get(f"https://www.ndbc.noaa.gov/view_text_file.php?filename=46088h{y}.txt.gz&dir=data/historical/stdmet/", raw=True)
        return y, b.decode(errors="ignore")
    except Exception:
        return y, ""
with ThreadPoolExecutor(6) as ex:
    texts = list(ex.map(buoy_year, range(2004, THIS_YEAR)))
try:
    texts.append((THIS_YEAR, get("https://www.ndbc.noaa.gov/data/realtime2/46088.txt", raw=True).decode()))
except Exception:
    pass
for y0, t in texts:
    if not t: continue
    for y, m, d, r in buoy_rows(t):
        when = f"{y}-{m:02d}-{d:02d}"
        try:
            w = float(r["WVHT"]); g = float(r["GST"])
        except (KeyError, ValueError):
            continue
        if 0 < w < 30: bump(m, "wave_max", w * 3.281, when); since["wave"] = min(since.get("wave", 9999), y)
        if 0 < g < 60: bump(m, "gust_max", g * 2.237, when); since["gust"] = min(since.get("gust", 9999), y)

out = {"station": "NOAA 9444900 Port Townsend; NDBC 46088 New Dungeness", "built": dt.datetime.now().isoformat(timespec="minutes"),
       "since": since, "all_time": {"wl_max": {"v": 12.00, "d": "2022-12-27"}},
       "months": {str(m): rec[m] for m in range(1, 13)}}
json.dump(out, open("records.json", "w"), indent=1)
print(json.dumps(out["since"]), json.dumps(out["months"]["11"], indent=0))
