"""Balance and sanity checks for the scenario tables and the engine. Run: python selftest.py"""
import itertools

import engine as E
import scenario as S


def play(team, plan, seed=1, mids=None):
    """plan: function (year, company) -> fleet decision dict. Returns yearly profits and final company."""
    cos = {str(t): E.new_company(t) for t in range(5)}
    profits = []
    for y in range(1, 6):
        decs = {}
        for cid, co in cos.items():
            fd = [plan(y, co, i) for i in range(len(co["fleets"]))]
            mid = (mids or {}).get(cid, {}).get(y, {})
            decs[cid] = dict(fleets=fd, mid=mid)
        cos, res, _ = E.resolve_year(seed, y, cos, decs)
        profits.append(res[str(team)]["profit"])
    return profits, cos[str(team)]


def const(pt, grade="standard", ac=True, damper=False, seat=False):
    return lambda y, co, i: dict(pt=pt if pt in S.POWERTRAINS[co["fleets"][i]["profile"]] else S.POWERTRAINS[co["fleets"][i]["profile"]][0],
                                 grade=grade, ac=ac, damper=damper, seat=seat)


def main():
    ok = True
    print("Reference plans (no cards, standard drivers, AC only):")
    for label, prof, pt in [("urban diesel", "urban", "diesel"), ("urban hybrid", "urban", "hybrid"),
                            ("urban EV", "urban", "ev"), ("haul standard", "haul", "standard"), ("haul eco", "haul", "eco")]:
        t = 0 if prof == "urban" else 2
        profits, co = play(t, const(pt))
        total = sum(profits)
        flag = "OK " if total == 30 and profits == S.option_total(prof, pt) else "BAD"
        ok &= flag == "OK "
        print(f"  {flag} {label:14s} {profits} = {total}  cash {co['cash']}")
    ref = S.option_total("urban", "diesel")
    assert ref == [10, 5, 0, 5, 10], ref

    print("\nBest no-card plan per profile (exhaustive over powertrain, grade, AC, dampers, seats per year):")
    for prof, team in (("urban", 0), ("haul", 2)):
        best = None
        pts = S.POWERTRAINS[prof]
        opts = list(itertools.product(pts, S.GRADES, [True, False], [False, True], [False, True]))
        # greedy by year is exact for profit but mood is stateful, so do a beam search over the mood state
        beams = [(0.0, S.MOOD_START, [])]
        for y in range(1, 6):
            nxt = {}
            for tot, mood, path in beams:
                for o in opts:
                    co = E.new_company(team)
                    co["fleets"][0]["mood"] = mood
                    dec = dict(fleets=[dict(pt=o[0], grade=o[1], ac=o[2], damper=o[3], seat=o[4])], mid={})
                    cos, res, _ = E.resolve_year(1, y, {str(team): co}, {str(team): dec})
                    p = res[str(team)]["profit"]
                    m = cos[str(team)]["fleets"][0]["mood"]
                    key = round(m, 1)
                    cand = (tot + p, m, path + [(o, p)])
                    if key not in nxt or nxt[key][0] < cand[0]:
                        nxt[key] = cand
            beams = list(nxt.values())
        beams.sort(key=lambda b: -b[0])
        print(f"  {prof}: best total {beams[0][0]}")
        for o, p in beams[0][2]:
            print("     ", o, p)

    print("\nStrategies without events help: always-rookie, no AC, no extras:")
    for label, plan in [("rookie noAC", const("diesel", "rookie", False)), ("standard noAC", const("diesel", "standard", False)),
                        ("veteran noAC", const("diesel", "veteran", False)), ("all comfort", const("diesel", "standard", True, True, True))]:
        profits, _ = play(0, plan)
        print(f"  {label:14s} {profits} = {sum(profits)}")

    print("\nTender sanity:")
    cos = {str(t): E.new_company(t) for t in range(5)}
    bids = {"0": {"U1": 0}, "1": {"U1": 5, "U2": 10}, "2": {"U1": 10, "H1": 5}, "3": {}, "4": {"H1": 0, "H2": 0, "H3": 0}}
    fx, lots = E.resolve_tender(cos, bids)
    for l in lots:
        print("  ", l)
    for cid, items in fx.items():
        print("  ", cid, items)
    print("\nALL BASIC CHECKS", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
