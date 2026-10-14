"""Pure game logic. No Streamlit, no database. A year is resolved from decisions plus the fixed deck in scenario.py."""
import copy
import random

import scenario as S


# ---- companies -------------------------------------------------------------------------------------
def new_company(team):
    return dict(id=str(team), members=[team], cash=float(S.START_CASH), bankrupt=False, peak_debt=0.0, merged_year=0,
                fleets=[dict(profile=S.PROFILES[team], mood=float(S.MOOD_START), ev_share=0.0, tradein_bonus=0.0)])


def score(co):
    """Net worth. A merged company is scored as the average of its former teams (plus the grant, already in cash)."""
    return co["cash"] / len(co["members"])


def default_fleet_dec(profile):
    return dict(pt=S.POWERTRAINS[profile][0], grade="standard", ac=True, damper=False, seat=False)


def default_dec(co, prev=None):
    """Last year's choices if there are any, else the reference plan. Mid-year choices always start empty."""
    fleets = []
    for i, f in enumerate(co["fleets"]):
        base = default_fleet_dec(f["profile"])
        if prev and i < len(prev.get("fleets", [])):
            base.update(prev["fleets"][i])
        fleets.append(base)
    n = len(co["fleets"])
    return dict(fleets=fleets, mid=dict(mountain=[False] * n, swap=[0] * n, kit=[False] * n, bids={}))


def clean_dec(co, dec):
    out = default_dec(co)
    for i, f in enumerate(co["fleets"]):
        src = (dec.get("fleets") or [])
        fd = out["fleets"][i]
        if i < len(src):
            s = src[i]
            if s.get("pt") in S.POWERTRAINS[f["profile"]]:
                fd["pt"] = s["pt"]
            if s.get("grade") in S.GRADES:
                fd["grade"] = s["grade"]
            for k in ("ac", "damper", "seat"):
                if k in s:
                    fd[k] = bool(s[k])
    mid = dec.get("mid") or {}
    n = len(co["fleets"])
    for k, cast, default in (("mountain", bool, False), ("swap", int, 0), ("kit", bool, False)):
        vals = list(mid.get(k) or [])
        out["mid"][k] = [cast(vals[i]) if i < len(vals) else default for i in range(n)]
    out["mid"]["swap"] = [v if v in (0, 5, 10) else 0 for v in out["mid"]["swap"]]
    out["mid"]["bids"] = {lot: int(d) for lot, d in (mid.get("bids") or {}).items()
                          if lot in S.LOTS and int(d) in S.DISCOUNTS}
    return out


def dice(seed):
    return dict(mountain=random.Random(f"{seed}:mountain").random(), crash=S.CRASH_ROLL,
                kit=random.Random(f"{seed}:kit").random())


def mood_face(m):
    return "happy" if m >= 70 else "fine" if m >= S.MOOD_PROTEST else "grumpy" if m >= S.MOOD_RESIGN else "furious"


def mood_target(grade, ac, damper, seat, shift=0):
    t = 40 + (20 if ac else 0) + (10 if damper else 0) + (10 if seat else 0) + shift
    t = 60 + (t - 60) * S.GRADE_TOLERANCE[grade]
    return max(0.0, min(100.0, t))


# ---- tender ------------------------------------------------------------------------------------------
def resolve_tender(companies, bids):
    """companies: {cid: company}; bids: {cid: {lot: discount}}.
    Returns (effects, lots) where effects = {cid: [(label, amount)]} and lots lists each lot's outcome."""
    owner = {}
    for lot, (_, team) in S.LOTS.items():
        for cid, co in companies.items():
            if team in co["members"]:
                owner[lot] = cid
    segs = {cid: {f["profile"] for f in co["fleets"]} for cid, co in companies.items()}
    worth = {cid: score(co) for cid, co in companies.items()}

    def value(cid, lot, d):
        seg = S.LOTS[lot][0]
        v = S.LOT_VALUE - d - (0 if seg in segs[cid] else S.LOT_NEW_SEGMENT)
        return v

    banned = set()
    live = [lot for lot in S.LOTS if lot in owner]
    while True:
        win = {}
        for lot in live:
            cands = [(d, cid) for cid, b in bids.items() if lot in b and (cid, lot) not in banned for d in [b[lot]]]
            if cands:
                cands.sort(key=lambda x: (-x[0], worth[x[1]], x[1]))
                win[lot] = cands[0]
        foreign = {}
        for lot, (d, cid) in win.items():
            if owner[lot] != cid:
                foreign.setdefault(cid, []).append(lot)
        over = {cid: lots for cid, lots in foreign.items() if len(lots) > 1}
        if not over:
            break
        for cid, lots in over.items():
            best = max(lots, key=lambda l: (value(cid, l, win[l][0]), l))
            for lot in lots:
                if lot != best:
                    banned.add((cid, lot))
    effects = {cid: [] for cid in companies}
    lots_out = []
    for lot in live:
        o = owner[lot]
        if lot not in win:
            lots_out.append(dict(lot=lot, owner=o, winner=o, discount=None, kept=True))
            continue
        d, w = win[lot]
        if w == o:
            if d:
                effects[o].append((f"Tender: kept your lot {lot} (discount {d})", -d))
            lots_out.append(dict(lot=lot, owner=o, winner=o, discount=d, kept=True))
        else:
            v = value(w, lot, d)
            tag = "new segment, -5" if S.LOTS[lot][0] not in segs[w] else "own segment"
            effects[w].append((f"Tender: won lot {lot} (discount {d}, {tag})", v))
            effects[o].append((f"Tender: lost your lot {lot}", -S.LOT_LOSS))
            lots_out.append(dict(lot=lot, owner=o, winner=w, discount=d, kept=False))
    return effects, lots_out


# ---- one year ----------------------------------------------------------------------------------------
def resolve_year(seed, year, companies, decs, signed=None, tender_bids=None):
    """Returns (new_companies, results, lots). Nothing is mutated."""
    cos = copy.deepcopy(companies)
    rolls = dice(seed)
    tender_fx, lots = ({}, [])
    if year == 2:
        tender_fx, lots = resolve_tender(
            cos, {cid: clean_dec(cos[cid], decs.get(cid) or {})["mid"]["bids"] for cid in cos})
    results = {}
    for cid, co in cos.items():
        dec = clean_dec(co, decs.get(cid) or {})
        n = len(co["fleets"])
        bankrupt = co["bankrupt"]
        notes = []

        # fleet purchase and loan: the bank refuses fleets it cannot fund, so the dearest are downgraded
        def price():
            tot = sum(S.FLEET_PRICE[fd["pt"]] for fd in dec["fleets"])
            return tot / 2 if bankrupt else tot
        while price() - max(co["cash"], 0) > S.LOAN_CAP:
            worst = max(range(n), key=lambda i: S.FLEET_PRICE[dec["fleets"][i]["pt"]])
            cheapest = S.POWERTRAINS[co["fleets"][worst]["profile"]][0]
            if dec["fleets"][worst]["pt"] == cheapest:
                break
            dec["fleets"][worst]["pt"] = cheapest
            notes.append("The bank refused the full fleet, so a cheaper powertrain was used. 融資拒否")
        loan = max(0.0, price() - max(co["cash"], 0))
        interest = loan * (S.RESCUE_RATE if bankrupt else S.LOAN_RATE)

        fleet_res = []
        stamps = []
        for i, f in enumerate(co["fleets"]):
            fd, prof = dec["fleets"][i], f["profile"]
            lines = []

            def add(label, amt, tag="option"):
                if amt:
                    lines.append(dict(label=label, amount=amt, tag=tag))
            add("Base year profit (market, wages, AC)", S.N_BASE[year - 1], "base")
            pt = fd["pt"]
            share = f["ev_share"] if (year == 5 and prof == "urban") else 0.0
            for label, amt in S.EFFECTS[prof][pt].get(year, []):
                add(label, amt * (1 - share), "event")
            if share:
                for label, amt in S.EFFECTS["urban"]["ev"].get(year, []):
                    add(label + " (swapped trucks)", amt * share, "event")
            if year == 5 and f["tradein_bonus"]:
                add("Trade-in cash back", f["tradein_bonus"], "card")
            # drivers
            sc = 1.0 if prof == "urban" else 0.5
            g = fd["grade"]
            if g == "rookie":
                add("Rookie drivers: lower wages", S.GRADE_SWING * sc, "driver")
                add("Rookie drivers: more repairs and fuel", -S.GRADE_SWING * sc, "driver")
            elif g == "veteran":
                add("Veteran drivers: higher wages", -S.GRADE_SWING * sc, "driver")
                add("Veteran drivers: fewer repairs, less fuel", S.GRADE_SWING * sc, "driver")
            # comfort
            if not fd["ac"]:
                add("Air conditioning removed", S.COMFORT_COST, "comfort")
            if fd["damper"]:
                add("Dampers fitted", -S.COMFORT_COST, "comfort")
            if fd["seat"]:
                add("Seats fitted", -S.COMFORT_COST, "comfort")
            # mid-year cards
            shift = 0
            if year == 1 and dec["mid"]["mountain"][i]:
                if pt == "ev":
                    notes.append("EVs cannot take the mountain contract. 電気は山岳不可")
                else:
                    add("Mountain contract: revenue", S.MOUNTAIN_REV, "card")
                    add("Mountain contract: extra costs", -S.MOUNTAIN_COST, "card")
                    p = S.MOUNTAIN_P / (2 if fd["damper"] else 1)
                    if rolls["mountain"] < p:
                        add("Mountain road damage", -S.MOUNTAIN_DAMAGE, "event")
                        stamps.append("crash")
                    if not fd["damper"]:
                        shift += S.MOUNTAIN_MOOD
            if year == 2 and not fd["ac"]:
                shift += S.HEAT_MOOD
            if year == 4:
                p = S.CRASH_P[g] / (2 if fd["seat"] else 1)
                if rolls["crash"] < p:
                    add("Heavy accident (cheap driver)", -S.CRASH_COST, "event")
                    stamps.append("crash")
                s = dec["mid"]["swap"][i]
                if s and prof == "urban" and pt == "diesel":
                    f["ev_share"] = s / 10.0
                    f["tradein_bonus"] = float(s)
                    notes.append(f"Trade-in booked: {s} trucks become EV next year, +{s} cash back. 下取り登録")
            if year == 5 and dec["mid"]["kit"][i]:
                add("Autonomy kit purchase", -S.KIT_COST[prof], "card")
                if rolls["kit"] < S.KIT_P:
                    add("Autonomy kit works: counted in the final valuation", S.KIT_VALUE[prof], "card")
                    if prof == "haul":
                        add("Autonomy kit saves a driver", 5, "card")
                else:
                    add("Autonomy kit recall: fine", -5, "card")
                    stamps.append("recall")
            # mood
            target = mood_target(g, fd["ac"], fd["damper"], fd["seat"], shift)
            mood = f["mood"] + (target - f["mood"]) / 2
            state = "ok"
            if mood < S.MOOD_RESIGN:
                add("Mass resignation: rehiring and lost deliveries", -S.RESIGN_COST[prof], "mood")
                state = "resign"
                stamps.append("resigned")
            elif mood < S.MOOD_PROTEST:
                add("Drivers on strike", -S.PROTEST_COST[prof], "mood")
                state = "protest"
                stamps.append("protest")
            f["mood"] = float(S.MOOD_RESET) if state == "resign" else mood
            if year == 5:
                f["ev_share"], f["tradein_bonus"] = 0.0, 0.0
            if i == 0:
                for label, amt in tender_fx.get(cid, []):
                    add(label, amt, "card")
                if interest:
                    add("Loan interest", -interest, "money")
            profit = sum(l["amount"] for l in lines)
            fleet_res.append(dict(profile=prof, pt=pt, grade=g, ac=fd["ac"], damper=fd["damper"], seat=fd["seat"],
                                  lines=lines, profit=profit, mood=f["mood"], mood_state=state, mood_target=target))
        total = sum(fr["profit"] for fr in fleet_res)
        if bankrupt:
            half = -total / 2
            fleet_res[0]["lines"].append(dict(label="Half fleet under rescue terms", amount=half, tag="money"))
            fleet_res[0]["profit"] += half
            total += half
            stamps.append("bankrupt")
        co["cash"] += total
        co["peak_debt"] = max(co["peak_debt"], -co["cash"] if co["cash"] < 0 else 0, loan)
        co["bankrupt"] = co["cash"] < 0
        if co["bankrupt"] and "bankrupt" not in stamps:
            stamps.append("bankrupt")
        results[cid] = dict(company=cid, members=list(co["members"]), year=year, profit=total, cash_end=co["cash"],
                            score=score(co), bankrupt=co["bankrupt"], stamps=sorted(set(stamps)), fleets=fleet_res,
                            notes=notes, loan=loan, signed=bool((signed or {}).get(cid, True)),
                            dec=dec, nfleets=n)
    return cos, results, lots


# ---- merger ------------------------------------------------------------------------------------------
def merge_eligible(companies):
    """Bottom two by score, or any bankrupt company. Only unmerged companies can merge."""
    singles = [c for c in companies.values() if len(c["members"]) == 1]
    ranked = sorted(singles, key=lambda c: (score(c), c["id"]))
    ok = {c["id"] for c in ranked[:2]} | {c["id"] for c in singles if c["bankrupt"]}
    return ok


def merge(companies, a, b, year):
    """Merge company b into company a. Cash is pooled and each former team gets the grant."""
    cos = copy.deepcopy(companies)
    ca, cb = cos[a], cos.pop(b)
    ca["fleets"] += cb["fleets"]
    ca["members"] += cb["members"]
    ca["cash"] = ca["cash"] + cb["cash"] + 2 * S.MERGER_GRANT
    ca["peak_debt"] = max(ca["peak_debt"], cb["peak_debt"])
    ca["bankrupt"] = score(ca) < 0
    ca["merged_year"] = year
    return cos


def rough_profit(p, nfleets=1):
    p = p / max(1, nfleets)
    return "▲▲" if p >= 15 else "▲" if p >= 5 else "▬" if p > -5 else "▼" if p > -15 else "▼▼"
