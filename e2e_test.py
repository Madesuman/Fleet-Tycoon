"""Headless end to end test: plays full games with bots, opens every page in every phase and every seat.
Run: python e2e_test.py"""
import os
import random
import sys
import tempfile

db = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["GAME_DB"] = db
PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
os.chdir(PROJ)
from streamlit.testing.v1 import AppTest

import engine as E
import scenario as S
import store

FAILS = []


def run(path, label, setup=None, timeout=90):
    at = AppTest.from_file(os.path.join(PROJ, path), default_timeout=timeout)
    if setup:
        setup(at)
    at.run()
    errs = [str(e.value)[:300] for e in at.exception]
    if errs:
        FAILS.append((label, errs))
    return at, errs


def member_for_seat(seat, year):
    return [m for m in range(5) if S.seat_of(m, year) == seat][0]


def as_player(team, member):
    def f(at):
        at.session_state["who"] = dict(team=team, member=member)
    return f


def all_seats(team, label):
    s = store.get_state()
    for seat in range(5):
        m = member_for_seat(seat, s["year"])
        at, errs = run("app.py", f"{label} team{team} seat{seat}", as_player(team, m))
        if errs:
            print("   ERR", label, "team", team, "seat", seat, errs[:1])


def test_login_and_interaction():
    store.start_game(4242, "https://example.streamlit.app")
    at, errs = run("app.py", "login screen")
    assert not errs, errs
    # engineering seat picks EV for team 0 in year 1
    m = member_for_seat(1, 1)
    at, errs = run("app.py", "eng seat", as_player(0, m))
    assert at.radio, "engineering radio missing"
    at.radio[0].set_value("ev").run()
    g = store.get_groups(1, "0")
    assert g.get("pt") == ["ev"], g
    # HR seat sets rookie
    at, _ = run("app.py", "hr seat", as_player(0, member_for_seat(2, 1)))
    at.radio[0].set_value("rookie").run()
    assert store.get_groups(1, "0")["grade"] == ["rookie"]
    # C&M seat removes AC
    at, _ = run("app.py", "cm seat", as_player(0, member_for_seat(4, 1)))
    toggles = [t for t in at.toggle if "AC" in t.label]
    toggles[0].set_value(False).run()
    assert store.get_groups(1, "0")["comfort"][0]["ac"] is False
    # shacho signs
    at, _ = run("app.py", "shacho seat", as_player(0, member_for_seat(0, 1)))
    btn = [b for b in at.button if "Sign off" in b.label]
    assert btn, [b.label for b in at.button]
    btn[0].click().run()
    assert store.is_signed(1, "0", "design")
    d = store.compose(store.get_state(), 1, "0")
    assert d["fleets"][0]["pt"] == "ev" and d["fleets"][0]["grade"] == "rookie" and d["fleets"][0]["ac"] is False, d
    print("interaction test OK")


def play_game(seed, merge_pair=("3", "4"), verbose=False):
    store.start_game(seed, "https://example.streamlit.app")
    rng = random.Random(seed)
    for y in range(1, S.YEARS + 1):
        s = store.get_state()
        assert s["phase"] == "design" and s["year"] == y
        # a few pages while planning
        run("pages/1_Leaderboard.py", f"board design y{y}")
        if y in (1, 3, 5):
            for t_ in (0, 2):
                all_seats(t_, f"design y{y}")
        store.fill_bots("design", seed=rng.random())
        store.to_midyear()
        s = store.get_state()
        if y == 3:
            a, b = merge_pair
            store.merge_companies(a, b)
            s = store.get_state()
            assert store.company_of(s, int(b)) == a and len(s["companies"]) == 4
        run("pages/1_Leaderboard.py", f"board mid y{y}")
        for t_ in (0, 2, 3, 4):
            all_seats(t_, f"mid y{y}")
        store.fill_bots("mid", only_unsigned=False, seed=rng.random())
        store.reveal_year()
        run("pages/1_Leaderboard.py", f"board reveal y{y}")
        for t_ in (0, 2, 3, 4):
            all_seats(t_, f"reveal y{y}")
        run("pages/2_Admin.py", f"admin y{y}", lambda at: at.session_state.__setitem__("admin_ok", True))
        store.next_year()
    s = store.get_state()
    assert s["phase"] == "final"
    run("pages/1_Leaderboard.py", "board final")
    for t_ in (0, 2, 3, 4):
        all_seats(t_, "final")
    run("pages/2_Admin.py", "admin final", lambda at: at.session_state.__setitem__("admin_ok", True))
    ranked = sorted(s["companies"].values(), key=lambda c: -E.score(c))
    print("final:", [(store.company_name(c), round(E.score(c), 1)) for c in ranked])
    return s


if __name__ == "__main__":
    test_login_and_interaction()
    for sd in (11, 22):
        play_game(sd)
    run("pages/1_Leaderboard.py", "board lobby before start")
    if FAILS:
        print("\nFAILURES")
        for lab, errs in FAILS[:15]:
            print(" ", lab, errs)
        raise SystemExit(1)
    print("\nE2E PASSED: pages and phases ran without exceptions")
