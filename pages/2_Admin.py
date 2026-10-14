"""Host controls. Password protected (env ADMIN_PASSWORD or Streamlit secret, default cae2026)."""
import csv
import io
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import engine as E
import scenario as S
import store
import ui

st.set_page_config(page_title="Fleet Tycoon Admin", page_icon="🎛", layout="centered")
ui.inject_css()
st.title("🎛 Host controls")


def admin_password():
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return os.environ.get("ADMIN_PASSWORD", "cae2026")


if not st.session_state.get("admin_ok"):
    pw = st.text_input("Password", type="password")
    if st.button("Enter"):
        if pw == admin_password():
            st.session_state["admin_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()

s = store.get_state()

# ---- lobby ------------------------------------------------------------------------------------------------
if not s["started"]:
    st.subheader("New game")
    seed = st.number_input("Scenario seed (changes the mountain and autonomy kit dice)", value=random.randint(1000, 9999), step=1)
    url = st.text_input("Public app URL for the QR code", value=s.get("url", ""), placeholder="https://your-app.streamlit.app")
    if st.button("▶ Start game", type="primary"):
        store.start_game(int(seed), url.strip())
        st.rerun()
    st.stop()

phase, year = s["phase"], s["year"]
st.markdown(f"**Phase:** `{phase}` · **Year:** {year}/{S.YEARS} · **Seed:** {s['seed']}")

stage = "design" if phase == "design" else "mid"


def flags_block():
    for c in s["companies"].values():
        ok = store.is_signed(year, c["id"], stage)
        st.write(f"{'✅' if ok else '⏳'} {store.company_name(c)}")


if phase == "design":
    flags_block()
    c1, c2 = st.columns(2)
    mins = c1.number_input("Timer (minutes)", 0, 30, 4)
    if c2.button("⏱ Start timer"):
        store.set_deadline(mins)
        st.rerun()
    if st.button("🃏 Reveal the mid-year card", type="primary", width="stretch"):
        store.to_midyear()
        st.rerun()
    if st.button("🤖 Fill unsigned teams with bots (dry run)"):
        store.fill_bots("design")
        st.rerun()

elif phase == "midyear":
    card = S.CARDS[year]["card"]
    st.info(f"Card: {card[1]}. {card[3]}")
    if year != 3:
        flags_block()
    else:
        elig = sorted(E.merge_eligible(s["companies"]))
        st.markdown("**Merger window.** Eligible: " + (", ".join(store.company_name(s["companies"][c]) for c in elig) or "nobody"))
        if s["merged_into"]:
            st.success("A merger already happened this game (one per game).")
        else:
            ids = list(s["companies"])
            a = st.selectbox("Keeps its name (absorber)", ids, format_func=lambda c: store.company_name(s["companies"][c]))
            b = st.selectbox("Merges into it", [c for c in ids if c != a], format_func=lambda c: store.company_name(s["companies"][c]))
            force = st.checkbox("Ignore eligibility (host override)")
            can = force or (a in elig and b in elig)
            if not can:
                st.warning("Both companies must be in the bottom two or bankrupt.")
            if st.button("🤝 Merge now (both shachos agreed)", disabled=not can):
                store.merge_companies(a, b)
                st.rerun()
    c1, c2 = st.columns(2)
    mins = c1.number_input("Timer (minutes)", 0, 30, 2)
    if c2.button("⏱ Start timer"):
        store.set_deadline(mins)
        st.rerun()
    if st.button("🎬 Reveal the year's results", type="primary", width="stretch"):
        store.reveal_year()
        st.rerun()
    if st.button("🤖 Fill unsigned teams with bots (dry run)"):
        store.fill_bots("mid")
        st.rerun()

elif phase == "reveal":
    st.success("Results are on the big screen. Debrief, then continue.")
    last = year >= S.YEARS
    if st.button("🏁 Show final results" if last else f"➡ Start year {year + 1}", type="primary", width="stretch"):
        store.next_year()
        st.rerun()

else:
    st.success("Game finished.")
    res = store.results()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["year", "company", "profit", "cash", "score", "stamps", "fleets"])
    for y in sorted(res):
        for cid in sorted(res[y]):
            r = res[y][cid]
            w.writerow([y, " + ".join(S.TEAM_NAMES[m] for m in r["members"]), r["profit"], r["cash_end"], r["score"],
                        " ".join(r["stamps"]), "; ".join(f"{f['pt']}/{f['grade']}" for f in r["fleets"])])
    st.download_button("⬇ Download results CSV", buf.getvalue(), "fleet_tycoon_results.csv", "text/csv")

st.divider()
st.markdown("**Standings**")
for c in sorted(s["companies"].values(), key=lambda c: -E.score(c)):
    st.write(f"{store.company_name(c)}: net ¥{E.score(c):.0f}M · cash {c['cash']:.0f} · moods "
             + ", ".join(f"{f['mood']:.0f}" for f in c["fleets"]) + (" · 💀" if c["bankrupt"] else ""))

with st.expander("Join links and team codes (give each team its card)"):
    base = s.get("url") or "https://YOUR-APP-URL"
    for t_ in range(S.N_TEAMS):
        st.markdown(f"**{S.TEAM_EMOJI[t_]} {S.TEAM_NAMES[t_]}** · {S.PROFILE_LABEL[S.PROFILES[t_]][0]} · code **{s['codes'][str(t_)]}**")
        st.code(f"{base}/?t={t_}&c={s['codes'][str(t_)]}", language=None)
    st.caption("Each player opens the link and picks their player number (1 to 5).")

with st.expander("Spoiler: this game's deck (host only)"):
    for y in range(1, S.YEARS + 1):
        d = S.CARDS[y]
        st.write(f"Year {y}: announced {', '.join(i[1] for i in d['announced'])} · surprise "
                 f"{', '.join(i[1] for i in d['surprise']) or 'none'} · card {d['card'][1]}")
    from engine import dice
    st.write(f"Shared dice this game: mountain roll {dice(s['seed'])['mountain']:.2f} (damage below 0.25), "
             f"autonomy kit roll {dice(s['seed'])['kit']:.2f} (works below 0.70), year 4 crash roll {S.CRASH_ROLL}.")
    if s["log"]:
        st.write(s["log"])

with st.expander("Danger zone"):
    sure = st.checkbox("I really want to reset everything")
    if st.button("🗑 Reset game", disabled=not sure):
        store.reset_all()
        st.rerun()
