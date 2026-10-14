"""Projector screen. Open full screen on the meeting room laptop. Refreshes itself every 3 seconds.
Shows only the rough picture: ranks, stamps, mood faces, profit arrows. Details are on the shacho's phone."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import segno
import streamlit as st

import engine as E
import scenario as S
import store
import ui

st.set_page_config(page_title="Fleet Tycoon Live", page_icon="🚚", layout="wide", initial_sidebar_state="collapsed")
ui.inject_css(projector=True)


def qr_data_uri(url):
    return segno.make(url, error="m").png_data_uri(scale=9, border=2, dark="#0b1020", light="#ffffff")


def awards(results, companies):
    per = {}
    for y, rs in results.items():
        for r in rs.values():
            for t_ in r["members"]:
                d = per.setdefault(t_, dict(strikes=0, moods=[], best=-999))
                d["strikes"] += sum(1 for s_ in r["stamps"] if s_ in ("protest", "resigned"))
                d["moods"] += [f["mood"] for f in r["fleets"]]
                d["best"] = max(d["best"], r["profit"] / max(1, r["nfleets"]))
    debt = {}
    for c in companies.values():
        for t_ in c["members"]:
            debt[t_] = c["peak_debt"]
    teams = list(per) or list(range(S.N_TEAMS))
    if not per:
        return []
    avg = {t_: sum(d["moods"]) / max(1, len(d["moods"])) for t_, d in per.items()}
    top = lambda d, f=max: f(teams, key=lambda t_: d[t_])
    out = []
    ts = {t_: per[t_]["strikes"] for t_ in teams}
    b = top(ts)
    out.append(("award_union", "✊", "Union's Enemy 組合の敵", store.team_name(b) if ts[b] else "Nobody!",
                f"{ts[b]} strike or resignation years" if ts[b] else "No one angered the union"))
    b = top(debt)
    out.append(("award_loanshark", "🦈", "Loan Shark's Best Friend 借金王", store.team_name(b) if debt[b] > 0 else "Nobody!",
                f"peak loan ¥{debt[b]:.0f}M" if debt[b] > 0 else "No loans taken"))
    b = top(avg)
    out.append(("award_happy", "😄", "Happiest Drivers 最高の職場", store.team_name(b), f"average mood {avg[b]:.0f}"))
    best = {t_: per[t_]["best"] for t_ in teams}
    b = top(best)
    out.append(("award_bestyear", "💰", "Best Single Year 最高の一年", store.team_name(b), f"profit ¥{best[b]:.0f}M per fleet"))
    b = top(avg, min)
    out.append(("award_sweaty", "🥵", "Sweatiest Cabs 灼熱の運転席", store.team_name(b), f"average mood {avg[b]:.0f}"))
    return out


def company_cards(s, res_year, cols=3):
    cs = sorted(s["companies"].values(), key=lambda c: -E.score(c))
    grid = st.columns(min(cols, len(cs)))
    for idx, c in enumerate(cs):
        r = res_year.get(c["id"]) if res_year else None
        with grid[idx % len(grid)]:
            html = (f"<div class='card' style='border-left:8px solid {store.company_color(c)}'>"
                    f"<div class='tname'>{ui.img('team_' + str(c['members'][0]), S.TEAM_EMOJI[c['members'][0]], 56)} "
                    f"#{idx + 1} {store.company_name(c)}</div>")
            if r:
                trucks = "".join(ui.img(S.TRUCK_IMG[f["pt"]], S.PT_LABEL[f["pt"]][2], 52) for f in r["fleets"])
                moods = "".join(ui.img("mood_" + E.mood_face(f["mood"]),
                                       {"happy": "😄", "fine": "🙂", "grumpy": "😠", "furious": "🤬"}[E.mood_face(f["mood"])], 44)
                                for f in r["fleets"])
                html += f"<div>{trucks} {moods}</div>"
                html += f"<div style='font-size:1.6rem'>Profit 利益 {E.rough_profit(r['profit'], r['nfleets'])}</div>"
                html += f"<div>{ui.stamps_html(r['stamps'], 44)}</div>"
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)


def event_row(year, kinds):
    items = []
    for kind in kinds:
        items += [(kind, it) for it in S.CARDS[year][kind]]
    if not items:
        return
    cols = st.columns(len(items))
    for col, (kind, it) in zip(cols, items):
        with col:
            ui.card_image(it[0], "📰" if kind == "announced" else "⚡")
            tag = "📰 ANNOUNCED 予告" if kind == "announced" else "⚡ SURPRISE 突発"
            st.markdown(f"<div class='card'><b>{tag}</b><br><span style='font-size:1.3rem'><b>{it[1]} {it[2]}</b></span>"
                        f"<br>{it[3]}</div>", unsafe_allow_html=True)


@st.fragment(run_every=3)
def board():
    s = store.get_state()
    results = store.results()
    phase, year = s["phase"], s["year"]

    if not s["started"] or phase == "lobby":
        st.markdown("# 🚚 FLEET TYCOON")
        st.markdown("### CAE Offsite · Run a delivery company. Be the richest. Avoid bankruptcy.")
        st.markdown("##### 運送会社を経営しよう。一番お金持ちになった会社が優勝。破産しないように！")
        a, b = st.columns([1, 1])
        with a:
            st.markdown("""
- 🧑‍💼 Five seats, one shacho. Everyone moves one seat each year 毎年席が一つ動く
- 📰 Each seat sees **different news**. Talk! 席ごとに見える情報が違う
- ✊ Cut comfort and drivers **protest, then quit** 快適装備を削ると反乱
- 🃏 One **mid-year card** every year 毎年、中間カード
- 🏆 After **5 years**, richest company wins 5年後の純資産で勝負
""")
        with b:
            if s.get("url"):
                st.markdown(f"<div style='text-align:center'><img src='{qr_data_uri(s['url'])}' width='260'/>"
                            f"<h3>{s['url']}</h3></div>", unsafe_allow_html=True)
            else:
                st.info("Host: open the Admin page, start the game and set the join URL.")
        return

    st.markdown(f"## 🚚 FLEET TYCOON · Year {min(year, S.YEARS)} / {S.YEARS}")

    if phase == "design":
        left = max(0, int(s["deadline"] - time.time())) if s.get("deadline") else None
        top = st.columns([3, 1])
        with top[0]:
            st.markdown("<div class='banner' style='background:#2b3a67'><h1>🗣️ Planning time 計画の時間</h1>"
                        "<p>Every seat sees different news. Share it, decide, and let your shacho sign. "
                        "席ごとに情報が違います。共有して決めましょう。</p></div>", unsafe_allow_html=True)
        with top[1]:
            if left is not None:
                st.markdown(f"<div class='big' style='text-align:center;font-size:4rem'>⏱ {left // 60}:{left % 60:02d}</div>",
                            unsafe_allow_html=True)
        a, b = st.columns([1, 1])
        with a:
            st.markdown("**Signed off 承認状況**")
            for c in s["companies"].values():
                ok = store.is_signed(year, c["id"], "design")
                st.markdown(f"<div class='card' style='border-left:8px solid {store.company_color(c)}'>"
                            f"<span class='tname'>{store.company_name(c)}</span>"
                            f"<span style='float:right;font-size:1.4rem'>{'✅' if ok else '⏳'}</span></div>",
                            unsafe_allow_html=True)
        with b:
            st.markdown("**Standings 現在の順位 (bars only)**")
            st.plotly_chart(ui.fig_score_bar(s["companies"], dark=True), width="stretch", key="lb_bar_d")
        if results:
            st.plotly_chart(ui.fig_score_line(results, year - 1, dark=True), width="stretch", key="lb_line_d")

    elif phase == "midyear":
        card = S.CARDS[year]["card"]
        st.markdown("### 🃏 Mid-year card 中間カード")
        a, b = st.columns([1, 1])
        with a:
            ui.card_image(card[0], "🃏")
        with b:
            st.markdown(f"<div class='banner' style='background:#6e56cf'><h1>{card[1]}<br>{card[2]}</h1><p>{card[3]}</p></div>",
                        unsafe_allow_html=True)
            if year == 3:
                if s["merged_into"]:
                    names = " + ".join(store.company_name(c) for c in s["companies"].values() if len(c["members"]) > 1)
                    st.markdown(ui.img("stamp_merged", "🤝", 80) + f" **A merger happened! 合併成立！ {names}**",
                                unsafe_allow_html=True)
                else:
                    elig = E.merge_eligible(s["companies"])
                    names = ", ".join(store.company_name(s["companies"][c]) for c in sorted(elig))
                    st.markdown(f"<div class='card'>Eligible to merge 合併可能: <b>{names or 'nobody'}</b></div>",
                                unsafe_allow_html=True)
            else:
                for c in s["companies"].values():
                    ok = store.is_signed(year, c["id"], "mid")
                    st.markdown(f"<div class='card' style='border-left:8px solid {store.company_color(c)}'>"
                                f"<span class='tname'>{store.company_name(c)}</span>"
                                f"<span style='float:right;font-size:1.4rem'>{'✅' if ok else '⏳'}</span></div>",
                                unsafe_allow_html=True)

    elif phase == "reveal":
        st.markdown("### What happened this year 今年の出来事")
        event_row(year, ["announced", "surprise"])
        yr = results.get(year, {})
        a, b = st.columns([1, 1])
        with a:
            st.plotly_chart(ui.fig_score_bar(s["companies"], dark=True), width="stretch", key="lb_bar_r")
        with b:
            st.plotly_chart(ui.fig_score_line(results, year, dark=True), width="stretch", key="lb_line_r")
        company_cards(s, yr)
        if year == 2:
            lots = store.get_lots(2)
            if lots:
                st.markdown("### Tender results 入札結果")
                cols = st.columns(len(lots))
                for col, l in zip(cols, lots):
                    w = s["companies"].get(l["winner"]) or {"members": [int(l["winner"])]}
                    col.markdown(f"<div class='card'><b>Lot {l['lot']}</b><br>"
                                 f"{'kept by' if l['kept'] else 'won by'}<br><b>{store.company_name(w)}</b>"
                                 + (f"<br>discount {l['discount']}" if l["discount"] is not None else "<br>no bids")
                                 + "</div>", unsafe_allow_html=True)

    else:
        ranked = sorted(s["companies"].values(), key=lambda c: -E.score(c))
        medals = ["🥇", "🥈", "🥉"]
        st.markdown("# 🏆 FINAL RESULT 最終結果")
        cols = st.columns(min(3, len(ranked)))
        for idx, c in enumerate(ranked[:3]):
            cols[idx].markdown(
                f"<div class='banner' style='background:{store.company_color(c)};text-align:center'>"
                f"<h1>{medals[idx]} {store.company_name(c)}</h1><p style='font-size:2rem'>¥{E.score(c):.0f}M</p></div>",
                unsafe_allow_html=True)
        if not st.session_state.get("_balloons"):
            st.session_state["_balloons"] = True
            st.balloons()
        a, b = st.columns([1, 1])
        with a:
            st.plotly_chart(ui.fig_score_bar(s["companies"], dark=True, values=True), width="stretch", key="lb_bar_f")
        with b:
            st.plotly_chart(ui.fig_score_line(results, S.YEARS, dark=True), width="stretch", key="lb_line_f")
        st.markdown("### Awards 特別賞")
        aw = awards(results, s["companies"])
        if aw:
            cols = st.columns(len(aw))
            for c, (key, emo, ttl, who, why) in zip(cols, aw):
                c.markdown(f"<div class='card' style='text-align:center'>{ui.img(key, emo, 80)}"
                           f"<div style='opacity:.8'>{ttl}</div><div class='tname'>{who}</div>"
                           f"<div style='opacity:.8'>{why}</div></div>", unsafe_allow_html=True)


board()
