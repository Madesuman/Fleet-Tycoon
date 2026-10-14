"""The fixed 5-year deck. Money is ¥M per fleet per year, every number a multiple of 5.

Everything the game "knows" lives in this file as tables, so balance changes are edits here.
Spec: "Fleet Tycoon: Scenario Spec v1" (Docs).
"""

YEARS = 5
START_CASH = 120
N_TEAMS = 5
PROFILES = ["urban", "urban", "haul", "haul", "haul"]          # per team id
TEAM_NAMES = ["Tokyo Dashers", "Kanto Couriers", "Green Freight", "Gold Movers", "Purple Cargo"]
TEAM_COLORS = ["#e5484d", "#3e63dd", "#30a46c", "#f5a524", "#8e4ec6"]
TEAM_EMOJI = ["🚀", "📦", "🌿", "🏅", "🔮"]

PROFILE_LABEL = {
    "urban": ("Urban delivery", "都市配送", "10 light trucks 小型10台", "🏙️"),
    "haul": ("Long haul", "長距離輸送", "4 heavy trucks 大型4台", "🛣️"),
}

# ---- powertrains -------------------------------------------------------------------------------
POWERTRAINS = {"urban": ["diesel", "hybrid", "ev"], "haul": ["standard", "eco"]}
PT_LABEL = {
    "diesel": ("Diesel", "ディーゼル", "⛽"),
    "hybrid": ("Hybrid", "ハイブリッド", "🔋⛽"),
    "ev": ("EV", "電気", "⚡"),
    "standard": ("Standard diesel", "標準ディーゼル", "⛽"),
    "eco": ("Eco pack", "エコパック", "🌱⛽"),
}
FLEET_PRICE = {"diesel": 80, "hybrid": 100, "ev": 120, "standard": 80, "eco": 100}   # whole fleet, bought each year
TRUCK_COST = {k: v // 4 for k, v in FLEET_PRICE.items()}       # resold at 75%, so the yearly cost is 25% of price
TRUCK_IMG = {"diesel": "truck_light_diesel", "hybrid": "truck_light_hybrid", "ev": "truck_light_ev",
             "standard": "truck_heavy_standard", "eco": "truck_heavy_eco"}

# Profit of a fleet with every event switched off. Identical for every powertrain, so options net 0 in a normal year.
N_BASE = [10, 5, 10, 15, 10]
# Market revenue per year (information only, it is already inside N_BASE).
MARKET = [(110, 90), (110, 90), (110, 90), (115, 95), (105, 85)]


def _y(**kw):
    """{1: [(label, amount)], ...} from year1=..., year2=... keyword arguments."""
    return {int(k[1:]): v for k, v in kw.items()}


# Event effects per option and year: (label, amount). Sums per option are verified in selftest.py.
EFFECTS = {
    "urban": {
        "diesel": _y(y3=[("War: fuel up, rationing", -10)], y4=[("CO2 rule: diesel fine", -10)]),
        "hybrid": _y(y1=[("EV subsidy (hybrid tier)", 5)], y2=[("Cold winter: battery range", -5)],
                     y3=[("War: partly exposed to fuel", -5)], y4=[("CO2 rule: hybrid fine", -5)],
                     y5=[("Hybrid tax break ends", -5), ("Used-vehicle glut: resale", -5)]),
        "ev": _y(y1=[("EV subsidy", 10)], y2=[("Cold winter: battery range", -10)],
                 y5=[("Green premium ends", -5), ("Electricity price hike", -5), ("Used-vehicle glut: resale", -10)]),
    },
    "haul": {
        "standard": _y(y3=[("War: fuel up, rationing", -10)], y4=[("CO2 rule: diesel fine", -10)]),
        "eco": _y(y1=[("Eco pack teething problems", -5)], y3=[("War: partly exposed to fuel", -5)],
                  y4=[("CO2 rule: eco pack fine", -5)], y5=[("Used-vehicle glut: resale", -5)]),
    },
}

# ---- drivers and comfort ---------------------------------------------------------------------
GRADES = ["rookie", "standard", "veteran"]
GRADE_LABEL = {"rookie": ("Rookie", "新人", "🧒"), "standard": ("Standard", "標準", "🧑"),
               "veteran": ("Veteran", "ベテラン", "🧓")}
GRADE_IMG = {"rookie": "driver_rookie", "standard": "driver_standard", "veteran": "driver_veteran"}
GRADE_SWING = 10           # wages saved or paid; repairs and fuel move the other way (halved for heavy fleets)
CRASH_P = {"rookie": 0.60, "standard": 0.15, "veteran": 0.03}
CRASH_ROLL = 0.40          # shared roll in year 4: rookies crash, standard and veteran do not (unless you change it)
COMFORT_COST = 5           # per item per year; AC is already inside the base profit
MOOD_START = 60
MOOD_PROTEST = 47          # mood below this: protest
MOOD_RESIGN = 33           # mood below this: mass resignation
MOOD_RESET = 50            # mood of the new crew after a resignation
PROTEST_COST = {"urban": 10, "haul": 5}
RESIGN_COST = {"urban": 20, "haul": 10}
GRADE_TOLERANCE = {"rookie": 0.5, "standard": 1.0, "veteran": 1.3}   # scales the distance from 60

# ---- money -----------------------------------------------------------------------------------
LOAN_RATE = 0.05
RESCUE_RATE = 0.15
LOAN_CAP = 40
MERGER_GRANT = 15

# ---- seats -----------------------------------------------------------------------------------
SEATS = [
    ("Shacho", "社長", "🧑‍💼", "seat_shacho"),
    ("Engineering", "技術", "🔧", "seat_engineering"),
    ("HR", "人事", "👥", "seat_hr"),
    ("Operations", "運行管理", "🗺️", "seat_operations"),
    ("Compliance & Maintenance", "法務・整備", "📋", "seat_compliance"),
]
SEAT_OWNS = {  # which seat controls which decision group
    "pt": 1, "grade": 2, "comfort": 4, "mountain": 3, "bids": 3, "swap": 1, "kit": 1,
}


def seat_of(member, year):
    """Players rotate one seat per year, so each player is shacho exactly once."""
    return (member + year) % 5


# ---- the deck --------------------------------------------------------------------------------
# kind: "announced" shows in the forecast, "surprise" appears only as a rumor, "card" is the mid-year card.
CARDS = {
    1: dict(
        announced=[("ev_subsidy", "EV subsidy", "EV補助金", "EV fleets earn +10, hybrid fleets +5 this year.")],
        surprise=[],
        card=("mountain_contract", "Mountain contract", "山岳輸送契約",
              "A mountain lot worth 30% of your fleet: +10 revenue, -5 costs, but a 25% chance of -10 damage "
              "(half that with dampers). Without dampers drivers grumble. EVs cannot take it."),
    ),
    2: dict(
        announced=[("overtime_cap", "Overtime cap", "時間外労働の上限", "Drivers cost +5 for every fleet (already in the base profit).")],
        surprise=[("heat_wave", "Heat wave", "猛暑", "Drivers in trucks without AC lose mood fast."),
                  ("cold_winter", "Cold winter", "厳冬", "EV fleets -10, hybrid fleets -5.")],
        card=("tender", "Open blind-bid tender", "入札", "Five lots, two urban and three haul. Sealed discounts "
              "0, 5, 10 or 15. The biggest discount wins the lot; ties go to the lower net worth."),
    ),
    3: dict(
        announced=[("co2_announced", "CO2 rule announced", "CO2規制の予告",
                    "From next year: diesel fine 10, hybrid 5, EV 0. Heavy standard 10, eco pack 5.")],
        surprise=[("war", "War", "戦争", "Fuel shock: diesel -10, hybrid -5, EV 0. Heavy standard -10, eco pack -5.")],
        card=("merger_window", "Merger window", "合併",
              "The bottom two companies, or any bankrupt one, may merge. The organizers run it."),
    ),
    4: dict(
        announced=[("co2_in_force", "CO2 rule in force", "CO2規制 施行",
                    "Diesel fine 10, hybrid 5, EV 0. Heavy standard 10, eco pack 5.")],
        surprise=[("driver_crash", "Cheap-driver crash", "事故",
                   "Seeded dice: rookie fleets crash (60%), standard (15%), veteran (3%). Seats halve the risk. A crash costs 10.")],
        card=("trade_in", "Trade-in programme", "下取り", "Light diesel fleets can swap 5 or 10 trucks to EV. "
              "Next year each 5 swapped trucks earn +5, and those trucks run as EV."),
    ),
    5: dict(
        announced=[("subsidy_party_over", "The party is over", "補助金終了",
                    "Green premium ends (EV -5), electricity hike (EV -5), hybrid tax break ends (hybrid -5).")],
        surprise=[("driver_boom", "Driver boom", "運転手余り", "Wages -5 for every fleet (already in the base profit)."),
                  ("used_glut", "Used-vehicle glut", "中古車だぶつき", "Resale hit: EV -10, hybrid -5, eco pack -5.")],
        card=("autonomy_kit", "Autonomy kit", "自動運転キット",
              "Costs 25 (heavy) or 30 (light). 70%: it works and counts 35 (heavy) or 40 (light) in the final "
              "valuation, and saves 5 for heavy fleets. 30%: recall, it counts 0 and a fine of 5."),
    ),
}

KIT_COST = {"urban": 30, "haul": 25}
KIT_VALUE = {"urban": 40, "haul": 35}
KIT_P = 0.70
MOUNTAIN_P = 0.25
MOUNTAIN_REV, MOUNTAIN_COST, MOUNTAIN_DAMAGE = 10, 5, 10
MOUNTAIN_MOOD = -20        # target mood shift when the contract is taken without dampers
HEAT_MOOD = -30            # year 2 target mood shift without AC
CRASH_COST = 10

LOTS = {"U1": ("urban", 0), "U2": ("urban", 1), "H1": ("haul", 2), "H2": ("haul", 3), "H3": ("haul", 4)}  # lot -> (segment, owner team)
LOT_VALUE = 10
LOT_NEW_SEGMENT = 5
LOT_LOSS = 15
DISCOUNTS = [0, 5, 10, 15]

# ---- information, split by seat ----------------------------------------------------------------
# (seat index, kind, text). "rumor" is a surprise seen only as a hint.
FACTS = {
    1: [
        (1, "info", "Diesel is ¥150/L and electricity ¥25/kWh, both steady this year."),
        (2, "info", "Driver market is normal this year. Wages are at their usual level."),
        (3, "info", "Customers are stable. Market revenue: urban 110, haul 90. A mid-year contract card is coming."),
        (4, "announced", "Government: EV SUBSIDY this year. EV fleets +10, hybrid fleets +5."),
    ],
    2: [
        (1, "rumor", "Rumor: battery makers warn that their cells hate very cold weather."),
        (2, "rumor", "Rumor: the drivers' union newsletter says cabs without AC are already complaining before summer."),
        (3, "announced", "A tender is planned mid-year: five lots, two urban and three haul, sealed discount bids."),
        (4, "announced", "OVERTIME CAP takes effect: drivers cost +5 for every fleet (already in everyone's base profit)."),
    ],
    3: [
        (1, "rumor", "Rumor: oil traders say a supply route may be cut. Fuel prices could jump."),
        (2, "info", "The union is quiet. Reminder: mood below 47 means protest, below 33 means mass resignation."),
        (3, "announced", "Demand is steady (110 / 90). A merger window opens mid-year for the two weakest companies."),
        (4, "announced", "CO2 RULE announced for NEXT year: diesel fine 10, hybrid 5, EV 0. Heavy standard 10, eco pack 5."),
    ],
    4: [
        (1, "info", "Charging networks are now everywhere. A trade-in programme may be offered mid-year."),
        (2, "rumor", "Rumor: cheap drivers have been seen dozing at the wheel at depots."),
        (3, "announced", "Demand is up: market revenue urban 115, haul 95."),
        (4, "announced", "CO2 RULE IN FORCE: diesel fine 10, hybrid 5, EV 0. Heavy standard 10, eco pack 5."),
    ],
    5: [
        (1, "info", "A supplier is demonstrating an autonomy kit. It may be offered mid-year."),
        (2, "rumor", "Rumor: recruiters expect a wave of new drivers to hit the market."),
        (3, "rumor", "Rumor: other companies are selling off lots of used trucks. Demand is softer: urban 105, haul 85."),
        (4, "announced", "GREEN PREMIUM ENDS (EV -5), ELECTRICITY HIKE (EV -5), HYBRID TAX BREAK ENDS (hybrid -5)."),
    ],
}


def option_total(profile, pt, grade="standard", ac=True, damper=False, seat=False):
    """Profit per year of a plan with no cards, used by tests and balance checks."""
    out = []
    for y in range(1, YEARS + 1):
        t = N_BASE[y - 1] + sum(a for _, a in EFFECTS[profile][pt].get(y, []))
        t += 0 if ac else COMFORT_COST
        t -= COMFORT_COST * (int(damper) + int(seat))
        out.append(t)
    return out
