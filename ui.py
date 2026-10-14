"""Shared UI helpers: CSS, the image loader (with emoji fallback), charts, small renderers."""
import base64
import io
import os
from functools import lru_cache

import plotly.graph_objects as go
import streamlit as st

import engine as E
import scenario as S

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
EXTS = (".png", ".webp", ".jpg", ".jpeg", ".gif")

# key, group, size, fallback emoji, what it shows (text-free pictures; the app adds all words)
ASSETS = (
    [(c[0], "event card", "1600x900", e, f"{c[1]} ({y})") for y in range(1, 6)
     for c, e in [(S.CARDS[y]["announced"][i], "📰") for i in range(len(S.CARDS[y]["announced"]))]
     + [(S.CARDS[y]["surprise"][i], "⚡") for i in range(len(S.CARDS[y]["surprise"]))]
     + [((S.CARDS[y]["card"][0], S.CARDS[y]["card"][1]), "🃏")]]
    + [(S.TRUCK_IMG[k], "truck type", "1024x1024 transparent", S.PT_LABEL[k][2], S.PT_LABEL[k][0]) for k in S.TRUCK_IMG]
    + [("stamp_" + k, "status stamp", "1024x1024 transparent", e, d) for k, e, d in [
        ("protest", "✊", "drivers on strike"), ("resigned", "🚪", "mass resignation"), ("bankrupt", "💀", "bankrupt"),
        ("recall", "🛠️", "recall"), ("merged", "🤝", "merger done"), ("crash", "💥", "crash or damage")]]
    + [(sd[3], "seat icon", "512x512 transparent", sd[2], sd[0]) for sd in S.SEATS]
    + [(f"team_{i}", "team mascot", "1024x1024 transparent", S.TEAM_EMOJI[i], S.TEAM_NAMES[i]) for i in range(5)]
    + [("mood_" + k, "driver mood", "512x512 transparent", e, d) for k, e, d in [
        ("happy", "😄", "happy"), ("fine", "🙂", "fine"), ("grumpy", "😠", "grumpy"), ("furious", "🤬", "furious")]]
    + [(S.GRADE_IMG[g], "driver grade", "512x512 transparent", S.GRADE_LABEL[g][2], S.GRADE_LABEL[g][0]) for g in S.GRADES]
    + [("award_" + k, "award icon", "512x512 transparent", e, d) for k, e, d in [
        ("union", "✊", "Union's Enemy"), ("loanshark", "🦈", "Loan Shark's Best Friend"),
        ("happy", "😄", "Happiest Drivers"), ("bestyear", "💰", "Best Single Year"), ("sweaty", "🥵", "Sweatiest Cabs")]]
)
STAMP_EMOJI = {"protest": "✊", "resigned": "🚪", "bankrupt": "💀", "recall": "🛠️", "merged": "🤝", "crash": "💥"}
STAMP_TEXT = {"protest": "STRIKE ストライキ", "resigned": "MASS RESIGNATION 全員退職", "bankrupt": "BANKRUPT 破産",
              "recall": "RECALL リコール", "merged": "MERGED 合併", "crash": "CRASH 事故"}


def asset_path(key):
    for ext in EXTS:
        p = os.path.join(ASSET_DIR, key + ext)
        if os.path.exists(p):
            return p
    return None


@lru_cache(maxsize=256)
def _data_uri(key, max_px):
    p = asset_path(key)
    if not p:
        return None
    try:
        from PIL import Image
        im = Image.open(p)
        im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, "PNG" if im.mode in ("RGBA", "LA", "P") else "JPEG", **({} if im.mode in ("RGBA", "LA", "P") else {"quality": 88}))
        mime = "image/png" if im.mode in ("RGBA", "LA", "P") else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        with open(p, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def img(key, fallback="❔", h=64):
    """Small inline picture (or the emoji if the file is not there yet)."""
    uri = _data_uri(key, max(64, int(h * 2)))
    if uri:
        return f"<img src='{uri}' style='height:{h}px;vertical-align:middle'/>"
    return f"<span style='font-size:{h * 0.8:.0f}px;vertical-align:middle'>{fallback}</span>"


def card_image(key, fallback="📰", caption=None, use_column_width=True):
    """Big picture for event cards. Falls back to a coloured banner with the emoji."""
    p = asset_path(key)
    if p:
        st.image(p, caption=caption, width="stretch")
    else:
        st.markdown(f"<div class='banner' style='background:#2b3a67;text-align:center'><h1 style='font-size:4rem'>{fallback}</h1></div>",
                    unsafe_allow_html=True)


_CSS = """<style>
.block-container {padding-top: 1rem; max-width: 760px;}
.meter {height: 14px; background: rgba(128,128,128,.25); border-radius: 8px; overflow: hidden;}
.meter > div {height: 100%; border-radius: 8px;}
.chip {display:inline-block; padding: 2px 10px; border-radius: 12px; font-size: .85rem; margin: 2px 4px 2px 0; background: rgba(128,128,128,.2);}
.chip.bad {background: #e5484d; color: white;}
.chip.warn {background: #f5a524; color: #111;}
.chip.good {background: #30a46c; color: white;}
.banner {border-radius: 18px; padding: 16px 22px; margin: 8px 0 12px 0; color: white;}
.banner h1 {margin: 0; font-size: 2rem; color: white;}
.banner p {margin: 4px 0 0 0; font-size: 1.05rem; opacity: .95;}
.card {border-radius: 14px; padding: 12px 14px; background: rgba(128,128,128,.12); margin-bottom: 8px;}
.tname {font-weight: 700; font-size: 1.1rem;}
.big {font-size: 2rem; font-weight: 800;}
.fact {border-left: 5px solid #3e63dd; padding: 6px 12px; margin: 6px 0; background: rgba(62,99,221,.08); border-radius: 0 10px 10px 0;}
.fact.rumor {border-left-color: #f5a524; background: rgba(245,165,36,.10);}
.fact.announced {border-left-color: #30a46c; background: rgba(48,164,108,.10);}
.seatbar {border-radius: 14px; padding: 10px 14px; color: white; margin: 6px 0 10px 0;}
.plus {color: #30a46c; font-weight: 700;} .minus {color: #e5484d; font-weight: 700;}
</style>"""
_CSS_PROJECTOR = """<style>
.block-container {max-width: 1500px;}
.stApp {background: #0b1020; color: #f2f4f8;}
.card {background: rgba(255,255,255,.07);}
h1, h2, h3, p, span, div, label {color: #f2f4f8;}
header[data-testid="stHeader"] {background: transparent;}
</style>"""


def inject_css(projector=False):
    st.markdown(_CSS, unsafe_allow_html=True)
    if projector:
        st.markdown(_CSS_PROJECTOR, unsafe_allow_html=True)


def t(en, ja=""):
    return f"{en} {ja}".strip()


def money(x, sign=False):
    x = round(x * 2) / 2
    s = f"{x:+.0f}" if sign else f"{x:.0f}"
    if abs(x - round(x)) > 1e-9:
        s = f"{x:+.1f}" if sign else f"{x:.1f}"
    return s


def meter_html(m, label=None):
    color = "#30a46c" if m >= 62 else ("#f5a524" if m >= S.MOOD_PROTEST else "#e5484d")
    lab = label if label is not None else f"{E.mood_face(m)} {m:.0f}"
    return (f"<div style='display:flex;align-items:center;gap:10px'><div style='flex:1' class='meter'>"
            f"<div style='width:{max(2, min(100, m)):.0f}%;background:{color}'></div></div><span>{lab}</span></div>")


def stamps_html(stamps, h=56):
    out = []
    for k in stamps:
        out.append(f"<span title='{STAMP_TEXT.get(k, k)}'>{img('stamp_' + k, STAMP_EMOJI.get(k, '❔'), h)}</span> "
                   f"<span class='chip bad'>{STAMP_TEXT.get(k, k)}</span>")
    return " ".join(out)


# ---- charts ------------------------------------------------------------------------------------------
def _layout(fig, height, dark):
    fig.update_layout(height=height, margin=dict(l=0, r=10, t=10, b=0), template="plotly_dark" if dark else None,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def fig_score_bar(companies, dark=True, values=False):
    rows = sorted(((E.score(c), c) for c in companies.values()), key=lambda x: x[0])
    names = [(("💀 " if c["bankrupt"] else "") + " + ".join(S.TEAM_NAMES[m] for m in c["members"])) for _, c in rows]
    fig = go.Figure(go.Bar(x=[max(v, 0) if not values else v for v, _ in rows], y=names, orientation="h",
                           marker_color=[S.TEAM_COLORS[c["members"][0]] for _, c in rows],
                           text=[f"¥{v:.0f}M" for v, _ in rows] if values else None, textposition="outside",
                           cliponaxis=False))
    fig.update_xaxes(title="Net worth 純資産" + (" (¥M)" if values else ""), showticklabels=values)
    return _layout(fig, 70 + 56 * len(rows), dark)


def fig_score_line(results, upto, dark=True):
    fig = go.Figure()
    for t_id in range(S.N_TEAMS):
        xs, ys = [0], [S.START_CASH]
        for y in range(1, upto + 1):
            r = next((r for r in results.get(y, {}).values() if t_id in r["members"]), None)
            if r:
                xs.append(y)
                ys.append(r["score"])
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=S.TEAM_NAMES[t_id],
                                 line=dict(color=S.TEAM_COLORS[t_id], width=4), marker=dict(size=9)))
    fig.add_hline(y=0, line_dash="dot", line_color="#e5484d")
    fig.update_xaxes(title="Year 年", dtick=1)
    fig.update_yaxes(title="Net worth (¥M)")
    fig.update_layout(legend=dict(orientation="h", y=-0.25))
    return _layout(fig, 340, dark)


def fig_waterfall(lines, dark=False):
    labels = [l["label"] for l in lines] + ["Profit 利益"]
    vals = [l["amount"] for l in lines]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative"] * len(vals) + ["total"], x=labels, y=vals + [0],
        text=[f"{v:+.0f}" for v in vals] + [f"{sum(vals):+.0f}"], textposition="outside",
        increasing=dict(marker=dict(color="#30a46c")), decreasing=dict(marker=dict(color="#e5484d")),
        totals=dict(marker=dict(color="#3e63dd")), connector=dict(line=dict(color="rgba(128,128,128,.4)"))))
    fig.update_xaxes(tickangle=-35)
    fig.update_yaxes(title="¥M")
    fig.update_layout(showlegend=False)
    return _layout(fig, 360, dark)


def lines_table_html(lines):
    rows = []
    for l in lines:
        cls = "plus" if l["amount"] > 0 else "minus"
        rows.append(f"<tr><td style='padding:2px 8px 2px 0'>{l['label']}</td>"
                    f"<td style='text-align:right' class='{cls}'>{money(l['amount'], True)}</td></tr>")
    tot = sum(l["amount"] for l in lines)
    rows.append(f"<tr><td style='padding-top:6px'><b>Profit 利益</b></td><td style='text-align:right;padding-top:6px'>"
                f"<b>{money(tot, True)}</b></td></tr>")
    return "<table style='width:100%;font-size:.95rem'>" + "".join(rows) + "</table>"


def write_assets_manifest(path):
    lines = ["# Image assets (49)", "",
             "Put PNG (or WEBP/JPG) files here, named exactly like the key. Missing files fall back to an emoji.",
             "No text inside the pictures: the app adds all words.", "",
             "| key | group | size | shows |", "| --- | --- | --- | --- |"]
    for key, group, size, _, desc in ASSETS:
        lines.append(f"| {key} | {group} | {size} | {desc} |")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
