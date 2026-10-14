"""Player page (phones). Everyone has a seat; only the shacho sees the full money detail.
Run: streamlit run app.py"""
import time

import streamlit as st

import engine as E
import scenario as S
import store
import ui

st.set_page_config(page_title="Fleet Tycoon", page_icon="🚚", layout="centered")
ui.inject_css()

MID_OWNER = {1: 3, 2: 3, 3: 0, 4: 1, 5: 1}      # which seat handles each year's mid-year card


# ---- background refresh ----------------------------------------------------------------------------------
@st.fragment(run_every=4)
def watcher():
    """Reruns the page when the host moves the game on; also shows the timer."""
    s = store.get_state()
    key = (s["phase"], s["year"], s["updated"] if s["phase"] == "lobby" else 0, len(s.get("merged_into", {})))
    old = st.session_state.get("_seen")
    st.session_state["_seen"] = key
    if old is not None and old != key:
        st.rerun()
    if s["phase"] in ("design", "midyear") and s.get("deadline"):
        left = int(s["deadline"] - time.time())
        st.caption(f"⏱ {left // 60}:{left % 60:02d} left 残り時間" if left > 0 else "⏱ Time is up 時間切れ")


def title():
    st.title("🚚 Fleet Tycoon")


state = store.get_state()
title()
if not state["started"]:
    st.info("Waiting for the host to start the game. ゲーム開始をお待ちください。")
    watcher()
    st.stop()

# ---- login ----------------------------------------------------------------------------------------------
qp = st.query_params
who = st.session_state.get("who")
if who is None and "t" in qp and "c" in qp and "p" in qp:
    try:
        t_, p_ = int(qp["t"]), int(qp["p"])
        if 0 <= t_ < S.N_TEAMS and 1 <= p_ <= 5 and store.verify_login(state, t_, qp["c"]):
            who = st.session_state["who"] = dict(team=t_, member=p_ - 1)
    except ValueError:
        pass
if who is None:
    st.subheader("Join your team チームに参加")
    default_t = int(qp["t"]) if "t" in qp and str(qp["t"]).isdigit() and int(qp["t"]) < S.N_TEAMS else 0
    team = st.selectbox("Team チーム", range(S.N_TEAMS), index=default_t,
                        format_func=lambda i: f"{S.TEAM_EMOJI[i]} {S.TEAM_NAMES[i]}")
    player = st.selectbox("Your player number 自分の番号", [1, 2, 3, 4, 5])
    code = st.text_input("Team code チームコード (4 digits)", value=str(qp.get("c", "")), max_chars=4)
    if st.button("Join 参加", type="primary", width="stretch"):
        if store.verify_login(state, team, code):
            st.session_state["who"] = dict(team=team, member=player - 1)
            st.query_params.update(t=str(team), c=code, p=str(player))
            st.rerun()
        else:
            st.error("Wrong code. コードが違います。")
    watcher()
    st.stop()

team, member = who["team"], who["member"]
year, phase = state["year"], state["phase"]
cid = store.company_of(state, team)
co = state["companies"][cid]
color = store.company_color(co)
seat = S.seat_of(member, max(year, 1))
seat_en, seat_ja, seat_emoji, seat_img = S.SEATS[seat]
shacho_player = [(m + 1) for m in range(5) if S.seat_of(m, max(year, 1)) == 0][0]

top = st.columns([4, 1])
top[0].markdown(f"<div class='tname' style='color:{color}'>{store.company_name(co)} · Player {member + 1}</div>",
                unsafe_allow_html=True)
if top[1].button("Leave", help="Log out of this phone"):
    del st.session_state["who"]
    st.query_params.clear()
    st.rerun()
if len(co["members"]) > 1:
    st.markdown(ui.img("stamp_merged", "🤝", 40) + " <b>Merged company 合併会社</b>: you share your seat with a partner.",
                unsafe_allow_html=True)

st.markdown(
    f"<div class='seatbar' style='background:{color}'>{ui.img(seat_img, seat_emoji, 44)} "
    f"<b>Year {year}: you are {seat_en} {seat_ja}</b><br>Shacho this year: Player {shacho_player}</div>",
    unsafe_allow_html=True)
if year >= 1 and member is not None:
    pass


# ---- decision widgets (save on change) -----------------------------------------------------------------
def _k(*parts):
    return "_".join(str(p) for p in parts)


def _save_list(group, key_prefix, n, convert=lambda v: v):
    def cb():
        vals = [convert(st.session_state[_k(key_prefix, i)]) for i in range(n)]
        store.set_group(year, cid, group, vals)
    return cb


def _save_comfort(prefix, n):
    def cb():
        vals = [dict(ac=st.session_state[_k(prefix, "ac", i)], damper=st.session_state[_k(prefix, "damper", i)],
                     seat=st.session_state[_k(prefix, "seat", i)]) for i in range(n)]
        store.set_group(year, cid, "comfort", vals)
    return cb


def _save_bids(prefix):
    def cb():
        bids = {}
        for lot in S.LOTS:
            v = st.session_state[_k(prefix, lot)]
            if v is not None:
                bids[lot] = int(v)
        store.set_group(year, cid, "bids", bids)
    return cb


def fleet_title(i, f):
    lab = S.PROFILE_LABEL[f["profile"]]
    return f"{lab[3]} Fleet {i + 1}: {lab[0]} {lab[1]} ({lab[2]})"


def pt_widgets(prefix, dec):
    n = len(co["fleets"])
    for i, f in enumerate(co["fleets"]):
        opts = S.POWERTRAINS[f["profile"]]
        key = _k(prefix, "pt", i)
        st.session_state.pop(key, None)
        st.markdown(f"**{fleet_title(i, f)}**")
        st.radio("Powertrain パワートレイン", opts, index=opts.index(dec["fleets"][i]["pt"]), key=key,
                 horizontal=True, on_change=_save_list("pt", _k(prefix, "pt"), n),
                 format_func=lambda x: f"{S.PT_LABEL[x][2]} {S.PT_LABEL[x][0]} · fleet ¥{S.FLEET_PRICE[x]}M")
        st.markdown(ui.img(S.TRUCK_IMG[dec["fleets"][i]["pt"]], "🚚", 90), unsafe_allow_html=True)


def grade_widgets(prefix, dec):
    n = len(co["fleets"])
    for i, f in enumerate(co["fleets"]):
        key = _k(prefix, "grade", i)
        st.session_state.pop(key, None)
        st.markdown(f"**{fleet_title(i, f)}**")
        st.radio("Driver grade 運転手", S.GRADES, index=S.GRADES.index(dec["fleets"][i]["grade"]), key=key,
                 horizontal=True, on_change=_save_list("grade", _k(prefix, "grade"), n),
                 format_func=lambda x: f"{S.GRADE_LABEL[x][2]} {S.GRADE_LABEL[x][0]} {S.GRADE_LABEL[x][1]}")
        st.markdown(ui.img(S.GRADE_IMG[dec["fleets"][i]["grade"]], "🧑", 70), unsafe_allow_html=True)


def comfort_widgets(prefix, dec):
    n = len(co["fleets"])
    for i, f in enumerate(co["fleets"]):
        fd = dec["fleets"][i]
        st.markdown(f"**{fleet_title(i, f)}**")
        a, b, c = st.columns(3)
        for col, field, label in ((a, "ac", "❄️ AC エアコン"), (b, "damper", "🔧 Dampers"), (c, "seat", "💺 Seats")):
            key = _k(prefix, field, i)
            st.session_state.pop(key, None)
            col.toggle(label, value=bool(fd[field]), key=key, on_change=_save_comfort(prefix, n))


def mid_widgets(prefix, dec):
    """The controls of this year's mid-year card. Returns True if there was something to show."""
    n = len(co["fleets"])
    mid = dec["mid"]
    if year == 1:
        for i, f in enumerate(co["fleets"]):
            key = _k(prefix, "mountain", i)
            st.session_state.pop(key, None)
            ev = dec["fleets"][i]["pt"] == "ev"
            st.toggle(f"⛰️ Fleet {i + 1}: take the mountain contract", value=bool(mid["mountain"][i]) and not ev, key=key,
                      disabled=ev, on_change=_save_list("mountain", _k(prefix, "mountain"), n),
                      help="EVs cannot take it" if ev else None)
            if ev:
                st.caption("EV fleets cannot take the mountain contract. 電気は不可")
        return True
    if year == 2:
        my_lots = [lot for lot, (_, tm) in S.LOTS.items() if tm in co["members"]]
        for lot, (seg, tm) in S.LOTS.items():
            key = _k(prefix, lot)
            st.session_state.pop(key, None)
            cur = mid["bids"].get(lot)
            mine = lot in my_lots
            label = f"{'🏠 YOUR lot ' if mine else '🎯 Lot '}{lot}: {S.PROFILE_LABEL[seg][0]} ({store.team_name(tm)})"
            st.select_slider(label, options=[None] + S.DISCOUNTS, value=cur, key=key, on_change=_save_bids(prefix),
                             format_func=lambda v: "no bid" if v is None else f"discount {v}")
        st.caption("Largest discount wins. Winner earns 10 minus the discount (5 less in a new segment). "
                   "Losing your own lot costs 15. You can win at most one lot that is not yours. "
                   "最大の値引きが落札。自社の案件を失うと-15。")
        return True
    if year == 4:
        shown = False
        for i, f in enumerate(co["fleets"]):
            if f["profile"] == "urban" and dec["fleets"][i]["pt"] == "diesel":
                key = _k(prefix, "swap", i)
                st.session_state.pop(key, None)
                st.select_slider(f"🔄 Fleet {i + 1}: trucks to swap to EV", options=[0, 5, 10], value=mid["swap"][i],
                                 key=key, on_change=_save_list("swap", _k(prefix, "swap"), n))
                shown = True
        if not shown:
            st.info("Only light diesel fleets can use the trade-in. 軽油の小型車のみ。")
        return shown
    if year == 5:
        for i, f in enumerate(co["fleets"]):
            key = _k(prefix, "kit", i)
            st.session_state.pop(key, None)
            cost = S.KIT_COST[f["profile"]]
            st.toggle(f"🤖 Fleet {i + 1}: buy the autonomy kit (cost {cost})", value=bool(mid["kit"][i]), key=key,
                      on_change=_save_list("kit", _k(prefix, "kit"), n))
        return True
    return False


def facts_block():
    for s_, kind, text in S.FACTS.get(year, []):
        if s_ == seat:
            st.markdown(f"<div class='fact {kind}'>{text}</div>", unsafe_allow_html=True)


def seat_sheet():
    if seat == 1:
        with st.expander("Price sheet 価格表", expanded=False):
            st.markdown(
                "| Option | Fleet price | Truck cost / yr | Energy | Maint. | Other |\n| --- | --- | --- | --- | --- | --- |\n"
                "| Diesel (light) | 80 | 20 | 0 | 0 | |\n| Hybrid (light) | 100 | 25 | -5 | 0 | |\n"
                "| EV (light) | 120 | 30 | -5 | -5 | charger +5, green premium +5 |\n"
                "| Standard (heavy) | 80 | 20 | 0 | 0 | |\n| Eco pack (heavy) | 100 | 25 | -5 | 0 | |\n\n"
                "Trucks are bought each year and resold at 75%, so the yearly truck cost is 25% of the price.")
    elif seat == 2:
        with st.expander("Driver sheet 運転手", expanded=False):
            st.markdown(
                "| Grade | Wages | Repairs and fuel | Mood |\n| --- | --- | --- | --- |\n"
                "| Rookie 新人 | -10 | +10 | tolerates missing comfort, sloppy driving |\n"
                "| Standard 標準 | 0 | 0 | normal |\n"
                "| Veteran ベテラン | +10 | -10 | demands more comfort, careful driving |\n\n"
                "Heavy fleets pay half these amounts. Mood below 47: strike. Below 33: mass resignation.")
    elif seat == 3:
        with st.expander("Market sheet 市場", expanded=False):
            mk = S.MARKET[year - 1]
            st.markdown(f"Market revenue this year: urban {mk[0]}, haul {mk[1]}. Mid-year cards: "
                        "year 1 mountain contract, year 2 tender, year 3 merger window, year 4 trade-in, year 5 autonomy kit.")
    elif seat == 4:
        with st.expander("Cab sheet キャブ", expanded=False):
            st.markdown("AC ❄️, dampers 🔧 and seats 💺 each cost 5 per year. The reference plan has AC only. "
                        "Comfort lifts driver mood. Hot, rough or long jobs hit mood hard. "
                        "Mood below 47: strike. Below 33: mass resignation.")


def summary_html(dec, with_mid=False):
    rows = []
    for i, f in enumerate(co["fleets"]):
        fd = dec["fleets"][i]
        comfort = "".join(e for e, k in (("❄️", "ac"), ("🔧", "damper"), ("💺", "seat")) if fd[k]) or "none"
        extra = ""
        if with_mid:
            if year == 1 and dec["mid"]["mountain"][i]:
                extra = " · ⛰️ mountain"
            if year == 4 and dec["mid"]["swap"][i]:
                extra = f" · 🔄 swap {dec['mid']['swap'][i]}"
            if year == 5 and dec["mid"]["kit"][i]:
                extra = " · 🤖 kit"
        rows.append(f"<div class='card'>{ui.img(S.TRUCK_IMG[fd['pt']], '🚚', 48)} <b>{fleet_title(i, f)}</b><br>"
                    f"{S.PT_LABEL[fd['pt']][2]} {S.PT_LABEL[fd['pt']][0]} · {S.GRADE_LABEL[fd['grade']][2]} "
                    f"{S.GRADE_LABEL[fd['grade']][0]} · comfort: {comfort}{extra}</div>")
    if with_mid and year == 2 and dec["mid"]["bids"]:
        rows.append("<div class='card'>📨 Bids: " + ", ".join(f"{l} −{d}" for l, d in sorted(dec["mid"]["bids"].items())) + "</div>")
    return "".join(rows)


# ---- shacho panel (live) -------------------------------------------------------------------------------
@st.fragment(run_every=4)
def shacho_live(stage):
    s = store.get_state()
    if s["year"] != year or s["phase"] != phase:
        return
    d = store.compose(s, year, cid)
    c = s["companies"][cid]
    m1, m2 = st.columns(2)
    m1.metric("Cash 現金", f"¥{c['cash']:.0f}M")
    m2.metric("Net worth 純資産", f"¥{E.score(c):.0f}M")
    st.markdown(summary_html(d, with_mid=(stage == "mid")), unsafe_allow_html=True)
    if store.is_signed(year, cid, stage):
        st.success("✅ Signed off. You can still change it until the host moves on. 承認済み")
    else:
        st.warning("Not signed off yet. Talk to your team, then sign. 未承認")


# ---- phases --------------------------------------------------------------------------------------------
dec_now = store.compose(state, year, cid) if phase in ("design", "midyear") else None

if phase == "design":
    st.subheader(f"Year {year} / {S.YEARS} · Plan the year 年間計画")
    st.caption("Everyone only sees part of the picture. Share what you know. 情報は人によって違います。話し合いましょう。")
    facts_block()
    seat_sheet()
    if seat == 1:
        st.markdown("#### Your decision: powertrain 技術")
        pt_widgets("s", dec_now)
    elif seat == 2:
        st.markdown("#### Your decision: drivers 人事")
        grade_widgets("s", dec_now)
    elif seat == 4:
        st.markdown("#### Your decision: cab comfort 整備")
        comfort_widgets("s", dec_now)
    elif seat == 3:
        st.info("Operations has no design decision now. Your job is the market and the mid-year card. "
                "運行管理は中間カードを担当。")
    else:
        st.markdown("#### Shacho 社長: the team's plan")
        shacho_live("design")
        if st.button("✍️ Sign off the plan 承認", type="primary", width="stretch"):
            store.sign(year, cid, "design")
            st.rerun()
        with st.expander("Override a seat's choice (final say) 変更"):
            st.caption("Changes the same fields the other seats edit.")
            pt_widgets("o", dec_now)
            grade_widgets("o", dec_now)
            comfort_widgets("o", dec_now)
    if seat != 0:
        st.caption("Your choice saves automatically. The shacho signs off for the team. 選択は自動保存されます。")
    watcher()

elif phase == "midyear":
    card = S.CARDS[year]["card"]
    st.subheader(f"Year {year} · Mid-year card 中間カード")
    ui.card_image(card[0], "🃏", None)
    st.markdown(f"<div class='banner' style='background:#6e56cf'><h1>{card[1]} {card[2]}</h1><p>{card[3]}</p></div>",
                unsafe_allow_html=True)
    owner = MID_OWNER[year]
    if seat == owner and seat != 0:
        st.markdown(f"#### Your decision ({seat_en}) 担当")
        mid_widgets("m", dec_now)
    elif seat == 0:
        if year == 3:
            eligible = cid in E.merge_eligible(state["companies"])
            if len(co["members"]) > 1:
                st.success("You have already merged. 合併済み")
            elif eligible:
                st.warning("Your company is eligible to merge. Agree with your partner and tell the organizers. "
                           "合併の資格があります。")
            else:
                st.info("Your company is not eligible to merge. 資格なし")
        else:
            st.markdown(f"#### Shacho 社長: the card is handled by {S.SEATS[owner][0]}")
        shacho_live("mid")
        if year != 3 and st.button("✍️ Sign off 承認", type="primary", width="stretch"):
            store.sign(year, cid, "mid")
            st.rerun()
        if year != 3:
            with st.expander("Override (final say) 変更"):
                mid_widgets("om", dec_now)
    else:
        st.info(f"{S.SEATS[owner][0]} handles this card. Advise them! {S.SEATS[owner][1]}が担当です。")
        facts_block()
    watcher()

elif phase in ("reveal", "final"):
    allres = store.results()
    myres = store.result_for_team(allres.get(year), team)
    if phase == "final":
        st.subheader("🏁 Game over ゲーム終了")
        ranked = sorted(state["companies"].values(), key=lambda c: -E.score(c))
        rank = [i for i, c in enumerate(ranked) if c["id"] == cid][0] + 1
        st.metric("Your rank 順位", f"#{rank} / {len(ranked)}",
                  delta=f"¥{E.score(co):.0f}M net worth" if seat == 0 else None, delta_color="off")
        if rank == 1:
            st.success("🏆 Champions! 優勝おめでとう！")
    else:
        st.subheader(f"Year {year} / {S.YEARS} · Results 結果")
        st.info("Look at the big screen! The shacho has the details. スクリーンを見てください。詳細は社長の画面に。")
    if myres:
        st.markdown(ui.stamps_html(myres["stamps"]), unsafe_allow_html=True)
        if seat != 0:
            for i, fr in enumerate(myres["fleets"]):
                face = E.mood_face(fr["mood"])
                st.markdown(f"{ui.img('mood_' + face, {'happy': '😄', 'fine': '🙂', 'grumpy': '😠', 'furious': '🤬'}[face], 60)} "
                            f"Fleet {i + 1} drivers are <b>{face}</b>. Profit this year: "
                            f"<b>{E.rough_profit(fr['profit'])}</b>", unsafe_allow_html=True)
            st.caption("Only the shacho sees the money detail. 金額の詳細は社長のみ。")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Profit 利益", f"¥{myres['profit']:.0f}M")
            c2.metric("Cash 現金", f"¥{myres['cash_end']:.0f}M")
            c3.metric("Net worth 純資産", f"¥{myres['score']:.0f}M")
            for n_ in myres["notes"]:
                st.warning(n_)
            for i, fr in enumerate(myres["fleets"]):
                st.markdown(f"##### {fleet_title(i, co['fleets'][i])}")
                st.markdown(ui.lines_table_html(fr["lines"]), unsafe_allow_html=True)
                face = E.mood_face(fr["mood"])
                st.markdown(ui.meter_html(fr["mood"], f"drivers {face} {fr['mood']:.0f}"), unsafe_allow_html=True)
                with st.expander("Waterfall chart"):
                    st.plotly_chart(ui.fig_waterfall(fr["lines"]), width="stretch", key=f"wf{i}")
            if not myres.get("signed", True):
                st.info("The plan was not signed off, so last year's plan was used. 未承認のため前年の計画を使用")
            lots = store.get_lots(year) if year == 2 else []
            if lots:
                with st.expander("Tender results 入札結果", expanded=True):
                    for l in lots:
                        w = state["companies"].get(l["winner"]) or {"members": [int(l["winner"])]}
                        st.write(f"Lot {l['lot']}: {'kept by' if l['kept'] else 'won by'} "
                                 f"{store.company_name(w)}" + (f" (discount {l['discount']})" if l["discount"] is not None else " (no bids)"))
    if phase == "reveal":
        st.caption("Next year starts when the host moves on. 次の年をお待ちください。")
    watcher()
