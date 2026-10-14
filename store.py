"""Tiny shared game store on SQLite (one file, WAL). Phones, projector and admin all read and write here.

Keys
  state                         phase, year, seed, companies, merged_into, codes ...
  grp:{year}:{company}:{group}  one decision group (written by the seat that owns it, or by the shacho)
  sign:{year}:{company}:{stage} the shacho's sign-off (stage "design" or "mid")
  final:{year}:{company}        the decision actually used that year
  res:{year}:{company}          the result record (every line item)
  lots:{year}                   tender outcome
"""
import json
import os
import random
import sqlite3
import time

import engine as E
import scenario as S

DB_PATH = os.environ.get("GAME_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "game.db"))
GROUPS = ["pt", "grade", "comfort", "mountain", "swap", "kit", "bids"]


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
    return c


def _get(k, default=None):
    with _conn() as c:
        row = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(row[0]) if row else default


def _set(k, v):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (k, json.dumps(v)))


def _scan(prefix):
    with _conn() as c:
        rows = c.execute("SELECT k, v FROM kv WHERE k LIKE ?", (prefix + "%",)).fetchall()
    return {k: json.loads(v) for k, v in rows}


# ---- state -----------------------------------------------------------------------------------------
def blank_state():
    return dict(phase="lobby", year=0, seed=0, deadline=None, url="", started=False, companies={}, merged_into={},
                codes={}, log=[], updated=time.time())


def get_state():
    s = _get("state")
    return s if s else blank_state()


def save_state(s):
    s["updated"] = time.time()
    _set("state", s)


def reset_all():
    with _conn() as c:
        c.execute("DELETE FROM kv")
    save_state(blank_state())


def start_game(seed, url=""):
    with _conn() as c:
        c.execute("DELETE FROM kv")
    s = blank_state()
    s.update(seed=int(seed), url=url, started=True, phase="design", year=1)
    s["companies"] = {str(t): E.new_company(t) for t in range(S.N_TEAMS)}
    s["codes"] = {str(t): str(random.Random(f"{seed}:code:{t}").randint(1000, 9999)) for t in range(S.N_TEAMS)}
    save_state(s)
    return s


def log(s, text):
    s["log"] = (s.get("log") or [])[-30:] + [text]


# ---- names, companies, seats ---------------------------------------------------------------------
def team_name(t):
    return S.TEAM_NAMES[t % len(S.TEAM_NAMES)]


def team_color(t):
    return S.TEAM_COLORS[t % len(S.TEAM_COLORS)]


def company_of(s, team):
    cid = str(team)
    seen = 0
    while cid in s["merged_into"] and seen < 10:
        cid = s["merged_into"][cid]
        seen += 1
    return cid


def company_name(co):
    return " + ".join(team_name(t) for t in co["members"])


def company_color(co):
    return team_color(co["members"][0])


def verify_login(s, team, code):
    return str(s["codes"].get(str(team))) == str(code).strip()


# ---- decisions -------------------------------------------------------------------------------------
def set_group(year, cid, group, value):
    _set(f"grp:{year}:{cid}:{group}", value)


def get_groups(year, cid):
    out = {}
    for g in GROUPS:
        v = _get(f"grp:{year}:{cid}:{g}")
        if v is not None:
            out[g] = v
    return out


def last_final(cid, year):
    for y in range(year - 1, 0, -1):
        d = _get(f"final:{y}:{cid}")
        if d:
            return d
    return None


def compose(s, year, cid):
    """The decision as it stands: the seats' choices over last year's decision over the reference plan."""
    co = s["companies"][cid]
    prev = last_final(cid, year)
    if len(co["members"]) > 1 and not (prev and len(prev["fleets"]) == len(co["fleets"])):
        fl = []                                      # a merged company inherits whatever its parts did
        for t in co["members"]:
            p = last_final(str(t), year)
            fl.append(p["fleets"][0] if p and p["fleets"] else {})
        prev = dict(fleets=fl)
    dec = E.default_dec(co, prev)
    g = get_groups(year, cid)
    n = len(co["fleets"])
    for i in range(n):
        fd = dec["fleets"][i]
        if "pt" in g and i < len(g["pt"]):
            fd["pt"] = g["pt"][i]
        if "grade" in g and i < len(g["grade"]):
            fd["grade"] = g["grade"][i]
        if "comfort" in g and i < len(g["comfort"]):
            fd.update({k: bool(g["comfort"][i].get(k, fd[k])) for k in ("ac", "damper", "seat")})
    for k in ("mountain", "swap", "kit"):
        if k in g:
            dec["mid"][k] = list(g[k])
    if "bids" in g:
        dec["mid"]["bids"] = dict(g["bids"])
    return E.clean_dec(co, dec)


def sign(year, cid, stage, value=True):
    _set(f"sign:{year}:{cid}:{stage}", value)


def is_signed(year, cid, stage):
    return bool(_get(f"sign:{year}:{cid}:{stage}", False))


def signed_map(s, stage):
    return {cid: is_signed(s["year"], cid, stage) for cid in s["companies"]}


# ---- phase control ---------------------------------------------------------------------------------
def to_midyear():
    s = get_state()
    s["phase"] = "midyear"
    s["deadline"] = None
    save_state(s)


def reveal_year():
    """Close the mid-year step: resolve this year for every company and store the records."""
    s = get_state()
    year = s["year"]
    decs = {cid: compose(s, year, cid) for cid in s["companies"]}
    signed = {cid: is_signed(year, cid, "design") for cid in s["companies"]}
    cos, results, lots = E.resolve_year(s["seed"], year, s["companies"], decs, signed)
    for cid, r in results.items():
        r["signed"] = signed[cid]
        _set(f"res:{year}:{cid}", r)
        _set(f"final:{year}:{cid}", decs[cid])
    _set(f"lots:{year}", lots)
    s["companies"] = cos
    s["phase"] = "reveal"
    s["deadline"] = None
    save_state(s)


def next_year():
    s = get_state()
    if s["year"] >= S.YEARS:
        s["phase"] = "final"
    else:
        s["year"] += 1
        s["phase"] = "design"
    s["deadline"] = None
    save_state(s)


def set_deadline(minutes):
    s = get_state()
    s["deadline"] = time.time() + minutes * 60 if minutes else None
    save_state(s)


def merge_companies(a, b):
    s = get_state()
    a, b, y = str(a), str(b), s["year"]
    da, db = compose(s, y, a), compose(s, y, b)         # keep what both teams already chose this year
    both = da["fleets"] + db["fleets"]
    signed_design = is_signed(y, a, "design") and is_signed(y, b, "design")
    cos = E.merge(s["companies"], a, b, y)
    s["companies"] = cos
    s["merged_into"][b] = a
    set_group(y, a, "pt", [f["pt"] for f in both])
    set_group(y, a, "grade", [f["grade"] for f in both])
    set_group(y, a, "comfort", [dict(ac=f["ac"], damper=f["damper"], seat=f["seat"]) for f in both])
    for k in ("mountain", "swap", "kit"):
        set_group(y, a, k, da["mid"][k] + db["mid"][k])
    set_group(y, a, "bids", {**db["mid"]["bids"], **da["mid"]["bids"]})
    sign(y, a, "design", signed_design)
    log(s, f"Year {s['year']}: {team_name(int(b))} merged into {team_name(int(a))}")
    save_state(s)


def results():
    """{year: {company: result}}"""
    out = {}
    for k, v in _scan("res:").items():
        _, y, cid = k.split(":")
        out.setdefault(int(y), {})[cid] = v
    return out


def result_for_team(res_year, team):
    for r in (res_year or {}).values():
        if team in r["members"]:
            return r
    return None


def get_lots(year):
    return _get(f"lots:{year}", [])


# ---- bots for dry runs -------------------------------------------------------------------------------
def random_groups(co, year, rng):
    n = len(co["fleets"])
    pts = [rng.choice(S.POWERTRAINS[f["profile"]]) for f in co["fleets"]]
    return dict(
        pt=pts,
        grade=[rng.choice(S.GRADES) for _ in range(n)],
        comfort=[dict(ac=rng.random() < .8, damper=rng.random() < .3, seat=rng.random() < .3) for _ in range(n)],
        mountain=[rng.random() < .5 for _ in range(n)],
        swap=[rng.choice([0, 0, 5, 10]) for _ in range(n)],
        kit=[rng.random() < .5 for _ in range(n)],
        bids={lot: rng.choice(S.DISCOUNTS) for lot in S.LOTS if rng.random() < .5},
    )


def fill_bots(stage=None, only_unsigned=True, seed=None):
    """Give every unsigned company random choices and sign for it (dry run helper)."""
    s = get_state()
    rng = random.Random(seed if seed is not None else time.time())
    stage = stage or ("design" if s["phase"] == "design" else "mid")
    for cid, co in s["companies"].items():
        if only_unsigned and is_signed(s["year"], cid, stage):
            continue
        for g, v in random_groups(co, s["year"], rng).items():
            set_group(s["year"], cid, g, v)
        sign(s["year"], cid, stage)
