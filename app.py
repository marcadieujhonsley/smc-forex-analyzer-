import streamlit as st
import pandas as pd
import time
import requests
import os
import json
from datetime import datetime, timezone, timedelta

# ============================================================
# MT5
# ============================================================
MT5_AVAILABLE = False
try:
    import MetaTrader5 as mt5
    if mt5.initialize():
        MT5_AVAILABLE = True
except Exception:
    MT5_AVAILABLE = False

st.set_page_config(
    page_title="MT5 Master Bot SMC V2",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# FILES / CONSTANTS
# ============================================================
STATE_FILE = "bot_state.txt"
BOT_MAGIC = 100200
TEST_MAGIC = 999999
SIGNAL_FILE = "smc_signal_state.json"

DEFAULT_SYMBOLS = ["EURUSDm", "GBPUSDm", "XAUUSDm"]

# ============================================================
# PERSISTENCE
# ============================================================
def read_bot_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return f.read().strip() == "True"
    except Exception:
        pass
    return False


def write_bot_state(active):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(bool(active)))
    except Exception:
        pass


def load_signal_state():
    try:
        if os.path.exists(SIGNAL_FILE):
            with open(SIGNAL_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {"traded_signals": [], "partial_done": [], "day": "", "day_start_equity": None}


def save_signal_state(data):
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


if "bot_active" not in st.session_state:
    st.session_state.bot_active = read_bot_state()

if "custom_symbols" not in st.session_state:
    st.session_state.custom_symbols = DEFAULT_SYMBOLS.copy()

if "trade_journal" not in st.session_state:
    st.session_state.trade_journal = []

if "engine_state" not in st.session_state:
    st.session_state.engine_state = load_signal_state()

# ============================================================
# UI
# ============================================================
st.markdown("""
<style>
.metric-card {
    background-color: #1E222D;
    border-radius: 10px;
    padding: 15px;
    border-left: 5px solid #2962FF;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    margin-bottom: 10px;
}
.metric-title {
    color: #B2B5BE;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
}
.metric-value {
    color: #FFFFFF;
    font-size: 22px;
    font-weight: bold;
}
.stButton>button {
    border-radius: 8px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

st.title("⚡ MT5 Trading Bot Dashboard, SMC V2")

# ============================================================
# SIDEBAR CONFIG
# ============================================================
st.sidebar.header("⚙️ Risk & Trade Management")

risk_usd = st.sidebar.number_input(
    "Risk pa trade ($)", min_value=1.0, value=25.0, step=1.0
)

min_rr = st.sidebar.number_input(
    "Minimum RR", min_value=1.0, value=2.0, step=0.25
)

max_spread_points = st.sidebar.number_input(
    "Maximum spread (points)", min_value=1, value=35, step=1
)

max_daily_loss_usd = st.sidebar.number_input(
    "Maximum daily loss ($)", min_value=1.0, value=75.0, step=5.0
)

max_daily_drawdown_pct = st.sidebar.number_input(
    "Maximum daily drawdown (%)", min_value=0.5, value=5.0, step=0.5
)

max_consecutive_losses = st.sidebar.number_input(
    "Maximum consecutive losses", min_value=1, value=3, step=1
)

max_trades_day = st.sidebar.number_input(
    "Maximum trades pa jou", min_value=1, value=5, step=1
)

st.sidebar.divider()
st.sidebar.header("🛡️ Trade Management")

be_at_r = st.sidebar.number_input(
    "Breakeven apre R", min_value=0.5, value=1.0, step=0.25
)

partial_at_r = st.sidebar.number_input(
    "Partial TP apre R", min_value=0.5, value=1.0, step=0.25
)

partial_close_pct = st.sidebar.number_input(
    "Partial close (%)", min_value=10, max_value=90, value=30, step=5
)

be_buffer_points = st.sidebar.number_input(
    "BE buffer (points)", min_value=0, value=2, step=1
)

st.sidebar.divider()
st.sidebar.header("⏱️ Sessions")

use_session_filter = st.sidebar.checkbox("Aktive session filter", value=True)

session_london = st.sidebar.checkbox("London", value=True)
session_new_york = st.sidebar.checkbox("New York", value=True)
session_overlap = st.sidebar.checkbox("London/New York overlap", value=True)

st.sidebar.divider()
st.sidebar.header("📰 News")

news_before = st.sidebar.number_input(
    "Minit avan High Impact", min_value=0, value=30, step=5
)

news_after = st.sidebar.number_input(
    "Minit apre High Impact", min_value=0, value=60, step=5
)

st.sidebar.divider()
st.sidebar.header("📡 Senbòl")

symbols_text = st.sidebar.text_area(
    "Yon senbòl pa liy",
    value="\n".join(st.session_state.custom_symbols)
)
st.session_state.custom_symbols = [
    s.strip() for s in symbols_text.split("\n") if s.strip()
]

# ============================================================
# HELPERS
# ============================================================
def utc_now():
    return datetime.now(timezone.utc)


def symbol_info(symbol):
    if not MT5_AVAILABLE:
        return None
    return mt5.symbol_info(symbol)


def normalize_price(symbol, price):
    info = symbol_info(symbol)
    if not info:
        return price
    return round(float(price), int(info.digits))


def get_pip_size(symbol):
    info = symbol_info(symbol)
    if not info:
        return 0.0001
    # FX 5/3 digit symbols use 10 points per pip.
    if info.digits in (3, 5):
        return info.point * 10
    return info.point


def ensure_symbol(symbol):
    if not MT5_AVAILABLE:
        return False
    info = mt5.symbol_info(symbol)
    if info is None:
        return False
    if not info.visible:
        try:
            mt5.symbol_select(symbol, True)
        except Exception:
            return False
    return True


def get_positions(symbol=None):
    if not MT5_AVAILABLE:
        return []
    try:
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return list(positions) if positions else []
    except Exception:
        return []


def bot_positions(symbol=None):
    return [
        p for p in get_positions(symbol)
        if getattr(p, "magic", None) == BOT_MAGIC
    ]


def current_spread_points(symbol):
    if not ensure_symbol(symbol):
        return None
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if not info or not tick or info.point <= 0:
        return None
    return (tick.ask - tick.bid) / info.point


def normalize_volume(symbol, volume):
    info = symbol_info(symbol)
    if not info:
        return 0.0

    step = info.volume_step or 0.01
    minimum = info.volume_min or step
    maximum = info.volume_max or volume

    volume = max(minimum, min(maximum, volume))
    steps = int(volume / step)
    normalized = steps * step

    if normalized < minimum:
        normalized = minimum

    decimals = max(0, len(str(step).split(".")[-1].rstrip("0")))
    return round(normalized, decimals)


# ============================================================
# RISK / LOT CALCULATION
# Uses MT5 order_calc_profit instead of assuming 10 points = 1 pip.
# ============================================================
def calculate_lot_size(symbol, risk_amount, entry_price, stop_price, order_type):
    if not MT5_AVAILABLE:
        return 0.01

    info = symbol_info(symbol)
    if not info:
        return 0.0

    try:
        loss_one_lot = mt5.order_calc_profit(
            order_type,
            symbol,
            1.0,
            entry_price,
            stop_price
        )

        if loss_one_lot is None:
            return 0.0

        loss_one_lot = abs(float(loss_one_lot))
        if loss_one_lot <= 0:
            return 0.0

        lot = risk_amount / loss_one_lot
        return normalize_volume(symbol, lot)
    except Exception:
        return 0.0


# ============================================================
# ATR
# ============================================================
def calculate_atr(df, period=14):
    if df is None or len(df) < period + 2:
        return None

    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ],
        axis=1
    ).max(axis=1)

    return float(tr.rolling(period).mean().iloc[-1])


# ============================================================
# SESSIONS
# Times are UTC. Adjust these if your broker/session definition differs.
# ============================================================
def session_allowed():
    if not use_session_filter:
        return True, "ALL"

    hour = utc_now().hour

    london = 7 <= hour < 16
    new_york = 13 <= hour < 22
    overlap = 13 <= hour < 16

    if session_overlap and overlap:
        return True, "OVERLAP"

    if session_london and london:
        return True, "LONDON"

    if session_new_york and new_york:
        return True, "NEW_YORK"

    return False, "OUTSIDE_SESSION"


# ============================================================
# NEWS FILTER
# ============================================================
def currencies_for_symbol(symbol):
    s = symbol.upper().replace("M", "")
    mapping = {
        "XAUUSD": ["USD"],
        "XAGUSD": ["USD"],
        "US30": ["USD"],
        "NAS100": ["USD"],
        "USTEC": ["USD"],
        "BTCUSD": ["USD"],
    }

    if s in mapping:
        return mapping[s]

    if len(s) >= 6:
        return [s[:3], s[3:6]]

    return [s[:3]]


def get_news_block(symbol):
    currencies = currencies_for_symbol(symbol)

    try:
        url = "https://n3ws-api.vercel.app/api/news"
        response = requests.get(url, timeout=3)

        if response.status_code != 200:
            return False, ""

        events = response.json()
        now = utc_now()

        for event in events:
            if event.get("impact") != "High":
                continue

            currency = str(event.get("currency", "")).upper()
            if not any(c in currency for c in currencies):
                continue

            date_value = event.get("date")
            if not date_value:
                continue

            event_time = datetime.fromisoformat(
                str(date_value).replace("Z", "+00:00")
            )

            diff_minutes = (event_time - now).total_seconds() / 60.0

            if -news_after <= diff_minutes <= news_before:
                return True, event.get("title", "High Impact News")

    except Exception:
        # Fail-open here only means news API unavailable.
        # For stricter live trading, change this to fail-closed.
        pass

    return False, ""


# ============================================================
# MARKET DATA
# ONLY CLOSED CANDLES ARE USED.
# copy_rates_from_pos(..., 0, N) includes the current candle.
# We remove the last row before analysis.
# ============================================================
def get_closed_rates(symbol, timeframe, count):
    if not ensure_symbol(symbol):
        return None

    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count + 1)

        if rates is None or len(rates) < count:
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

        # Remove current, still-forming candle.
        df = df.iloc[:-1].copy()

        if len(df) < count - 1:
            return None

        return df.reset_index(drop=True)
    except Exception:
        return None


# ============================================================
# SWINGS
# ============================================================
def get_swing_points(df, window=3):
    swing_highs = []
    swing_lows = []

    if df is None or len(df) < (window * 2 + 5):
        return swing_highs, swing_lows

    for i in range(window, len(df) - window):
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])

        left_high = df["high"].iloc[i-window:i]
        right_high = df["high"].iloc[i+1:i+window+1]

        left_low = df["low"].iloc[i-window:i]
        right_low = df["low"].iloc[i+1:i+window+1]

        if h > float(left_high.max()) and h >= float(right_high.max()):
            swing_highs.append((i, h))

        if l < float(left_low.min()) and l <= float(right_low.min()):
            swing_lows.append((i, l))

    return swing_highs, swing_lows


def get_structure(df, window=3):
    swing_highs, swing_lows = get_swing_points(df, window)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None

    sh1, sh2 = swing_highs[-2], swing_highs[-1]
    sl1, sl2 = swing_lows[-2], swing_lows[-1]

    if sh2[1] > sh1[1] and sl2[1] > sl1[1]:
        structure = "bullish"
    elif sh2[1] < sh1[1] and sl2[1] < sl1[1]:
        structure = "bearish"
    else:
        structure = "range"

    return {
        "trend": structure,
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "last_high": sh2,
        "previous_high": sh1,
        "last_low": sl2,
        "previous_low": sl1,
    }


# ============================================================
# BOS / CHOCH
# Uses the latest closed candle.
# ============================================================
def detect_structure_break(df, structure):
    if structure is None or len(df) < 5:
        return None

    last_close = float(df["close"].iloc[-1])
    last_high = float(structure["last_high"][1])
    last_low = float(structure["last_low"][1])

    if last_close > last_high:
        previous_trend = structure["trend"]
        event = "BOS_BULLISH" if previous_trend == "bullish" else "CHOCH_BULLISH"
        return event

    if last_close < last_low:
        previous_trend = structure["trend"]
        event = "BOS_BEARISH" if previous_trend == "bearish" else "CHOCH_BEARISH"
        return event

    return None


# ============================================================
# LIQUIDITY SWEEP
# Detects a wick through a recent swing followed by a close back inside.
# ============================================================
def detect_liquidity_sweep(df, structure, lookback=12):
    if structure is None or len(df) < lookback + 2:
        return None

    last = df.iloc[-1]

    recent_highs = [
        x[1] for x in structure["swing_highs"]
        if x[0] < len(df) - 1
    ]
    recent_lows = [
        x[1] for x in structure["swing_lows"]
        if x[0] < len(df) - 1
    ]

    if recent_highs:
        buy_side = max(recent_highs[-3:])
        if float(last["high"]) > buy_side and float(last["close"]) < buy_side:
            return {
                "type": "BUY_SIDE_SWEEP",
                "level": buy_side
            }

    if recent_lows:
        sell_side = min(recent_lows[-3:])
        if float(last["low"]) < sell_side and float(last["close"]) > sell_side:
            return {
                "type": "SELL_SIDE_SWEEP",
                "level": sell_side
            }

    return None


# ============================================================
# DISPLACEMENT
# ============================================================
def detect_displacement(df, atr, multiplier=1.2):
    if atr is None or len(df) < 3:
        return None

    candle = df.iloc[-1]
    body = abs(float(candle["close"]) - float(candle["open"]))

    if body < atr * multiplier:
        return None

    if candle["close"] > candle["open"]:
        return "BULLISH_DISPLACEMENT"

    if candle["close"] < candle["open"]:
        return "BEARISH_DISPLACEMENT"

    return None


# ============================================================
# FVG
# 3-candle imbalance using closed candles.
# ============================================================
def detect_fvg(df):
    if len(df) < 3:
        return None

    a = df.iloc[-3]
    b = df.iloc[-2]
    c = df.iloc[-1]

    # Bullish FVG: candle A high below candle C low.
    if float(a["high"]) < float(c["low"]):
        return {
            "type": "BULLISH_FVG",
            "low": float(a["high"]),
            "high": float(c["low"])
        }

    # Bearish FVG: candle A low above candle C high.
    if float(a["low"]) > float(c["high"]):
        return {
            "type": "BEARISH_FVG",
            "low": float(c["high"]),
            "high": float(a["low"])
        }

    return None


# ============================================================
# ORDER BLOCK
# Approximation: last opposite candle before displacement.
# ============================================================
def detect_order_block(df, direction, search=8):
    if len(df) < search + 2:
        return None

    start = max(0, len(df) - search - 1)
    end = len(df) - 1

    for i in range(end - 1, start - 1, -1):
        candle = df.iloc[i]

        if direction == "BUY":
            # Last bearish candle before bullish displacement.
            if float(candle["close"]) < float(candle["open"]):
                return {
                    "type": "BULLISH_OB",
                    "low": float(candle["low"]),
                    "high": float(candle["high"]),
                    "index": i
                }

        if direction == "SELL":
            # Last bullish candle before bearish displacement.
            if float(candle["close"]) > float(candle["open"]):
                return {
                    "type": "BEARISH_OB",
                    "low": float(candle["low"]),
                    "high": float(candle["high"]),
                    "index": i
                }

    return None


# ============================================================
# PREMIUM / DISCOUNT
# ============================================================
def premium_discount(df, structure):
    if structure is None:
        return None

    high = float(structure["last_high"][1])
    low = float(structure["last_low"][1])

    if high <= low:
        return None

    equilibrium = (high + low) / 2.0
    price = float(df["close"].iloc[-1])

    return "DISCOUNT" if price < equilibrium else "PREMIUM"


# ============================================================
# LIQUIDITY TARGET
# ============================================================
def find_liquidity_target(symbol, action, structure, entry):
    if structure is None:
        return None

    if action == "BUY":
        levels = [
            x[1] for x in structure["swing_highs"]
            if x[1] > entry
        ]
        return min(levels) if levels else None

    levels = [
        x[1] for x in structure["swing_lows"]
        if x[1] < entry
    ]
    return max(levels) if levels else None


# ============================================================
# SMC SCORE / SIGNAL
# ============================================================
def analyze_smc(symbol):
    try:
        h4 = get_closed_rates(symbol, mt5.TIMEFRAME_H4, 210)
        m15 = get_closed_rates(symbol, mt5.TIMEFRAME_M15, 180)

        if h4 is None or m15 is None:
            return None

        if len(h4) < 200 or len(m15) < 50:
            return None

        # HTF bias.
        ema200 = h4["close"].ewm(span=200, adjust=False).mean().iloc[-1]
        h4_close = float(h4["close"].iloc[-1])
        bias = "bullish" if h4_close > ema200 else "bearish"

        structure = get_structure(m15, window=3)
        if structure is None:
            return None

        atr = calculate_atr(m15, 14)
        if atr is None or atr <= 0:
            return None

        displacement = detect_displacement(m15, atr)
        fvg = detect_fvg(m15)
        liquidity = detect_liquidity_sweep(m15, structure)
        structure_break = detect_structure_break(m15, structure)
        location = premium_discount(m15, structure)

        # Determine direction from HTF bias.
        action = "BUY" if bias == "bullish" else "SELL"

        score = 0
        reasons = []

        # HTF bias.
        score += 1
        reasons.append("HTF_BIAS")

        # Liquidity sweep must be aligned with the setup.
        if action == "BUY" and liquidity and liquidity["type"] == "SELL_SIDE_SWEEP":
            score += 2
            reasons.append("SELL_SIDE_SWEEP")

        if action == "SELL" and liquidity and liquidity["type"] == "BUY_SIDE_SWEEP":
            score += 2
            reasons.append("BUY_SIDE_SWEEP")

        # BOS / CHOCH.
        if action == "BUY" and structure_break in ("BOS_BULLISH", "CHOCH_BULLISH"):
            score += 2
            reasons.append(structure_break)

        if action == "SELL" and structure_break in ("BOS_BEARISH", "CHOCH_BEARISH"):
            score += 2
            reasons.append(structure_break)

        # Displacement.
        if action == "BUY" and displacement == "BULLISH_DISPLACEMENT":
            score += 1
            reasons.append("BULLISH_DISPLACEMENT")

        if action == "SELL" and displacement == "BEARISH_DISPLACEMENT":
            score += 1
            reasons.append("BEARISH_DISPLACEMENT")

        # FVG.
        if action == "BUY" and fvg and fvg["type"] == "BULLISH_FVG":
            score += 1
            reasons.append("BULLISH_FVG")

        if action == "SELL" and fvg and fvg["type"] == "BEARISH_FVG":
            score += 1
            reasons.append("BEARISH_FVG")

        # OB.
        ob = detect_order_block(m15, action)
        if ob:
            score += 1
            reasons.append(ob["type"])

        # Premium / discount.
        if action == "BUY" and location == "DISCOUNT":
            score += 1
            reasons.append("DISCOUNT")

        if action == "SELL" and location == "PREMIUM":
            score += 1
            reasons.append("PREMIUM")

        # Require a real liquidity + structure confirmation.
        liquidity_ok = (
            (action == "BUY" and liquidity and liquidity["type"] == "SELL_SIDE_SWEEP")
            or
            (action == "SELL" and liquidity and liquidity["type"] == "BUY_SIDE_SWEEP")
        )

        structure_ok = (
            (action == "BUY" and structure_break in ("BOS_BULLISH", "CHOCH_BULLISH"))
            or
            (action == "SELL" and structure_break in ("BOS_BEARISH", "CHOCH_BEARISH"))
        )

        if score < 8 or not liquidity_ok or not structure_ok:
            return {
                "action": None,
                "score": score,
                "bias": bias,
                "structure": structure["trend"],
                "reasons": reasons,
                "atr": atr,
                "fvg": fvg,
                "ob": ob,
                "liquidity": liquidity,
                "structure_break": structure_break,
                "location": location,
                "candle_time": str(m15["time"].iloc[-1])
            }

        # Entry at current market.
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None

        entry = float(tick.ask if action == "BUY" else tick.bid)

        # Structure-based SL.
        if action == "BUY":
            candidates = [float(structure["last_low"][1])]
            if ob:
                candidates.append(float(ob["low"]))
            if liquidity:
                candidates.append(float(liquidity["level"]))
            sl = min(candidates) - (atr * 0.10)
        else:
            candidates = [float(structure["last_high"][1])]
            if ob:
                candidates.append(float(ob["high"]))
            if liquidity:
                candidates.append(float(liquidity["level"]))
            sl = max(candidates) + (atr * 0.10)

        # Liquidity target.
        target = find_liquidity_target(symbol, action, structure, entry)

        if target is None:
            return None

        risk_distance = abs(entry - sl)
        reward_distance = abs(target - entry)

        if risk_distance <= 0 or reward_distance <= 0:
            return None

        rr = reward_distance / risk_distance

        if rr < min_rr:
            return {
                "action": None,
                "score": score,
                "bias": bias,
                "structure": structure["trend"],
                "reasons": reasons,
                "atr": atr,
                "fvg": fvg,
                "ob": ob,
                "liquidity": liquidity,
                "structure_break": structure_break,
                "location": location,
                "candle_time": str(m15["time"].iloc[-1]),
                "rr": rr
            }

        return {
            "action": action,
            "score": score,
            "bias": bias,
            "structure": structure["trend"],
            "reasons": reasons,
            "atr": atr,
            "fvg": fvg,
            "ob": ob,
            "liquidity": liquidity,
            "structure_break": structure_break,
            "location": location,
            "candle_time": str(m15["time"].iloc[-1]),
            "entry": entry,
            "sl": sl,
            "tp": target,
            "rr": rr
        }

    except Exception:
        return None


# ============================================================
# DAILY RISK ENGINE
# ============================================================
def reset_day_state():
    state = st.session_state.engine_state
    today = utc_now().strftime("%Y-%m-%d")

    if state.get("day") != today:
        account = mt5.account_info() if MT5_AVAILABLE else None
        state["day"] = today
        state["day_start_equity"] = float(account.equity) if account else None
        state["traded_signals"] = []
        state["partial_done"] = []
        save_signal_state(state)


def today_closed_pnl():
    if not MT5_AVAILABLE:
        return 0.0

    start = datetime.combine(
        utc_now().date(),
        datetime.min.time(),
        tzinfo=timezone.utc
    )
    end = utc_now() + timedelta(minutes=1)

    try:
        deals = mt5.history_deals_get(start, end)
        if not deals:
            return 0.0

        pnl = 0.0
        for d in deals:
            if getattr(d, "magic", None) != BOT_MAGIC:
                continue

            if d.entry == mt5.DEAL_ENTRY_OUT:
                pnl += float(d.profit) + float(d.swap) + float(d.commission)

        return pnl
    except Exception:
        return 0.0


def consecutive_losses():
    if not MT5_AVAILABLE:
        return 0

    start = utc_now() - timedelta(days=30)
    end = utc_now() + timedelta(minutes=1)

    try:
        deals = mt5.history_deals_get(start, end)
        if not deals:
            return 0

        exits = [
            d for d in deals
            if getattr(d, "magic", None) == BOT_MAGIC
            and d.entry == mt5.DEAL_ENTRY_OUT
        ]

        exits.sort(key=lambda x: x.time, reverse=True)

        count = 0
        for d in exits:
            pnl = float(d.profit) + float(d.swap) + float(d.commission)
            if pnl < 0:
                count += 1
            else:
                break

        return count
    except Exception:
        return 0


def trades_today():
    if not MT5_AVAILABLE:
        return 0

    start = datetime.combine(
        utc_now().date(),
        datetime.min.time(),
        tzinfo=timezone.utc
    )
    end = utc_now() + timedelta(minutes=1)

    try:
        deals = mt5.history_deals_get(start, end)
        if not deals:
            return 0

        return sum(
            1 for d in deals
            if getattr(d, "magic", None) == BOT_MAGIC
            and d.entry == mt5.DEAL_ENTRY_IN
        )
    except Exception:
        return 0


def daily_risk_ok():
    reset_day_state()

    account = mt5.account_info()
    if not account:
        return False, "ACCOUNT_ERROR"

    pnl = today_closed_pnl()
    floating = sum(float(p.profit) for p in bot_positions())

    total_today = pnl + floating

    if total_today <= -abs(max_daily_loss_usd):
        return False, "DAILY_LOSS_LIMIT"

    start_equity = st.session_state.engine_state.get("day_start_equity")
    if start_equity:
        dd_pct = ((float(account.equity) - start_equity) / start_equity) * 100
        if dd_pct <= -abs(max_daily_drawdown_pct):
            return False, "DAILY_DRAWDOWN_LIMIT"

    if consecutive_losses() >= max_consecutive_losses:
        return False, "CONSECUTIVE_LOSS_LIMIT"

    if trades_today() >= max_trades_day:
        return False, "MAX_TRADES_DAY"

    return True, "OK"


# ============================================================
# DUPLICATE SIGNAL PROTECTION
# ============================================================
def signal_id(symbol, analysis):
    return (
        f"{symbol}|{analysis.get('action')}|"
        f"{analysis.get('candle_time')}|"
        f"{analysis.get('structure_break')}"
    )


def signal_already_traded(sid):
    return sid in st.session_state.engine_state.get("traded_signals", [])


def register_signal(sid):
    state = st.session_state.engine_state
    signals = state.setdefault("traded_signals", [])

    if sid not in signals:
        signals.append(sid)

    # Keep the file small.
    state["traded_signals"] = signals[-500:]
    save_signal_state(state)


# ============================================================
# ORDER VALIDATION
# ============================================================
def validate_order(symbol, action, entry, sl, tp, lot):
    if not ensure_symbol(symbol):
        return False, "SYMBOL_NOT_AVAILABLE"

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if not info or not tick:
        return False, "NO_MARKET_DATA"

    if lot <= 0:
        return False, "INVALID_LOT"

    spread = current_spread_points(symbol)
    if spread is None:
        return False, "SPREAD_ERROR"

    if spread > max_spread_points:
        return False, f"SPREAD_TOO_HIGH:{spread:.1f}"

    stop_level = getattr(info, "trade_stops_level", 0) * info.point

    if action == "BUY":
        if sl >= entry or tp <= entry:
            return False, "INVALID_BUY_LEVELS"
        if entry - sl < stop_level:
            return False, "SL_TOO_CLOSE"
        if tp - entry < stop_level:
            return False, "TP_TOO_CLOSE"
        order_type = mt5.ORDER_TYPE_BUY
    else:
        if sl <= entry or tp >= entry:
            return False, "INVALID_SELL_LEVELS"
        if sl - entry < stop_level:
            return False, "SL_TOO_CLOSE"
        if entry - tp < stop_level:
            return False, "TP_TOO_CLOSE"
        order_type = mt5.ORDER_TYPE_SELL

    try:
        margin = mt5.order_calc_margin(
            order_type,
            symbol,
            lot,
            entry
        )
        account = mt5.account_info()
        if margin is not None and account and margin > account.margin_free:
            return False, "INSUFFICIENT_MARGIN"
    except Exception:
        pass

    return True, "OK"


# ============================================================
# TRADE EXECUTION
# ============================================================
def execute_trade(symbol, analysis):
    action = analysis["action"]
    entry = float(analysis["entry"])
    sl = normalize_price(symbol, analysis["sl"])
    tp = normalize_price(symbol, analysis["tp"])

    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

    lot = calculate_lot_size(
        symbol,
        risk_usd,
        entry,
        sl,
        order_type
    )

    valid, reason = validate_order(symbol, action, entry, sl, tp, lot)

    if not valid:
        st.session_state.trade_journal.append(
            f"{utc_now().strftime('%H:%M:%S')} | ❌ {symbol} {reason}"
        )
        return False

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": entry,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": BOT_MAGIC,
        "comment": "SMC_V2",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    try:
        result = mt5.order_send(request)
    except Exception as exc:
        st.session_state.trade_journal.append(
            f"{utc_now().strftime('%H:%M:%S')} | ❌ order_send exception: {exc}"
        )
        return False

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        st.session_state.trade_journal.append(
            f"{utc_now().strftime('%H:%M:%S')} | 🚀 {action} {symbol} | "
            f"Lot {lot} | SL {sl} | TP {tp} | "
            f"RR {analysis.get('rr', 0):.2f} | Score {analysis.get('score', 0)}"
        )
        return True

    comment = getattr(result, "comment", "Unknown")
    retcode = getattr(result, "retcode", "Unknown")

    st.session_state.trade_journal.append(
        f"{utc_now().strftime('%H:%M:%S')} | ❌ {symbol} | "
        f"retcode={retcode} | {comment}"
    )
    return False


# ============================================================
# TRADE MANAGEMENT
# ============================================================
def modify_sl(position, new_sl):
    info = symbol_info(position.symbol)
    if not info:
        return False

    new_sl = normalize_price(position.symbol, new_sl)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "symbol": position.symbol,
        "sl": new_sl,
        "tp": position.tp,
    }

    result = mt5.order_send(request)

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return True

    return False


def partial_close(position, percent):
    volume_to_close = float(position.volume) * (percent / 100.0)
    volume_to_close = normalize_volume(position.symbol, volume_to_close)

    info = symbol_info(position.symbol)
    if not info:
        return False

    # Never close the entire position through partial TP.
    if volume_to_close >= position.volume:
        volume_to_close = normalize_volume(
            position.symbol,
            position.volume - info.volume_step
        )

    if volume_to_close <= 0:
        return False

    tick = mt5.symbol_info_tick(position.symbol)
    if not tick:
        return False

    if position.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": volume_to_close,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": BOT_MAGIC,
        "comment": "SMC_V2_PARTIAL",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    return bool(
        result and result.retcode == mt5.TRADE_RETCODE_DONE
    )


def manage_positions():
    if not MT5_AVAILABLE:
        return

    state = st.session_state.engine_state
    partial_done = set(state.get("partial_done", []))

    for pos in bot_positions():
        info = symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)

        if not info or not tick:
            continue

        # Determine original risk distance from current SL.
        # Once SL is moved, we use position history when possible.
        # For reliable live operation, store original SL at entry.
        risk_distance = None

        try:
            if pos.type == mt5.POSITION_TYPE_BUY:
                current_price = tick.bid
                if pos.tp and pos.tp > pos.price_open:
                    reward_distance = abs(pos.tp - pos.price_open)
                else:
                    reward_distance = 0
            else:
                current_price = tick.ask
                if pos.tp and pos.tp < pos.price_open:
                    reward_distance = abs(pos.price_open - pos.tp)
                else:
                    reward_distance = 0

            # TP is liquidity-based. Use TP distance as a fallback proxy.
            # This is conservative for management.
            if reward_distance > 0:
                current_profit_distance = (
                    current_price - pos.price_open
                    if pos.type == mt5.POSITION_TYPE_BUY
                    else pos.price_open - current_price
                )

                r_value = current_profit_distance / reward_distance * min_rr

                # Partial close.
                partial_key = str(pos.ticket)
                if (
                    r_value >= partial_at_r
                    and partial_key not in partial_done
                ):
                    if partial_close(pos, partial_close_pct):
                        partial_done.add(partial_key)
                        st.session_state.trade_journal.append(
                            f"{utc_now().strftime('%H:%M:%S')} | "
                            f"📌 Partial {pos.symbol} ticket {pos.ticket}"
                        )

                # Breakeven.
                if r_value >= be_at_r:
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        be_sl = pos.price_open + (
                            info.point * be_buffer_points
                        )
                        if pos.sl == 0 or pos.sl < be_sl:
                            modify_sl(pos, be_sl)
                    else:
                        be_sl = pos.price_open - (
                            info.point * be_buffer_points
                        )
                        if pos.sl == 0 or pos.sl > be_sl:
                            modify_sl(pos, be_sl)

        except Exception:
            continue

    state["partial_done"] = list(partial_done)[-500:]
    save_signal_state(state)


# ============================================================
# MANUAL CLOSE
# Only bot positions are affected.
# ============================================================
def close_bot_positions(mode="ALL"):
    for pos in bot_positions():
        should_close = (
            mode == "ALL"
            or (mode == "WINNERS" and pos.profit > 0)
            or (mode == "LOSERS" and pos.profit < 0)
        )

        if not should_close:
            continue

        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            continue

        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": BOT_MAGIC,
            "comment": "SMC_V2_MANUAL_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        mt5.order_send(request)


# ============================================================
# DASHBOARD ACCOUNT
# ============================================================
if MT5_AVAILABLE:
    acc = mt5.account_info()

    if acc:
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Balance", f"${acc.balance:,.2f}")
        c2.metric("Equity", f"${acc.equity:,.2f}")
        c3.metric("Floating P/L", f"${acc.profit:,.2f}")
        c4.metric("Spread / symbols", f"{len(st.session_state.custom_symbols)}")

else:
    st.error("⚠️ MT5 pa konekte. Verifye terminal MT5 la.")

st.divider()

# ============================================================
# BOT CONTROL
# ============================================================
st.subheader("⚙️ Contrôle & Status")

col_status, col_start, col_stop = st.columns([2, 1, 1])

st.session_state.bot_active = read_bot_state()

with col_status:
    if st.session_state.bot_active:
        st.success("🟢 BOT ACTIF")
    else:
        st.error("🔴 BOT EN PAUSE")

with col_start:
    if st.button("▶️ DÉMARRER", use_container_width=True, type="primary"):
        write_bot_state(True)
        st.session_state.bot_active = True
        st.rerun()

with col_stop:
    if st.button("⏹️ ARRÊTER", use_container_width=True):
        write_bot_state(False)
        st.session_state.bot_active = False
        st.rerun()

# ============================================================
# SAFER TEST ORDER
# ============================================================
if st.button(
    "🧪 TEST ORDER, premye symbol, DEMO ONLY",
    use_container_width=True
):
    st.warning(
        "Bouton sa toujou voye yon order reyèl sou MT5 si terminal/account la pèmèt trading. "
        "Sèvi ak yon demo account pou teste."
    )

    if MT5_AVAILABLE and st.session_state.custom_symbols:
        sym = st.session_state.custom_symbols[0]

        if ensure_symbol(sym):
            tick = mt5.symbol_info_tick(sym)
            info = mt5.symbol_info(sym)

            if tick and info:
                action = "BUY"
                entry = float(tick.ask)
                atr_df = get_closed_rates(sym, mt5.TIMEFRAME_M15, 50)
                atr = calculate_atr(atr_df, 14) if atr_df is not None else info.point * 100

                sl = normalize_price(sym, entry - atr)
                tp = normalize_price(sym, entry + atr * 2)

                order_type = mt5.ORDER_TYPE_BUY
                lot = calculate_lot_size(sym, risk_usd, entry, sl, order_type)

                valid, reason = validate_order(sym, action, entry, sl, tp, lot)

                if valid:
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": sym,
                        "volume": lot,
                        "type": order_type,
                        "price": entry,
                        "sl": sl,
                        "tp": tp,
                        "deviation": 20,
                        "magic": TEST_MAGIC,
                        "comment": "DEMO_TEST_ONLY",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }

                    result = mt5.order_send(req)

                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        st.success(f"Test order ouvri, lot={lot}")
                    else:
                        st.error(
                            f"MT5 error: {getattr(result, 'comment', 'Unknown')}"
                        )
                else:
                    st.error(f"Test order bloke: {reason}")

st.write("Fermeture manuel, sèlman positions bot la")

p1, p2, p3 = st.columns(3)

if p1.button("🚨 Tout Fermer", use_container_width=True):
    close_bot_positions("ALL")
    st.rerun()

if p2.button("🟢 Fermer Gagnants", use_container_width=True):
    close_bot_positions("WINNERS")
    st.rerun()

if p3.button("🔴 Fermer Perdants", use_container_width=True):
    close_bot_positions("LOSERS")
    st.rerun()

st.divider()

# ============================================================
# POSITIONS
# ============================================================
st.subheader("📋 Positions Bot")

if MT5_AVAILABLE:
    positions = bot_positions()

    if positions:
        rows = []

        for p in positions:
            rows.append({
                "État": "🟢" if p.profit >= 0 else "🔴",
                "Ticket": p.ticket,
                "Paire": p.symbol,
                "Type": "BUY" if p.type == 0 else "SELL",
                "Lot": p.volume,
                "Entrée": p.price_open,
                "SL": p.sl,
                "TP": p.tp,
                "Profit ($)": round(p.profit, 2)
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True
        )
    else:
        st.info("Pa gen position bot ouvè.")

st.divider()

# ============================================================
# HISTORY / STATISTICS
# ============================================================
st.subheader("📜 Historique Bot")

if MT5_AVAILABLE:
    start = utc_now() - timedelta(days=30)
    end = utc_now() + timedelta(minutes=1)

    try:
        deals = mt5.history_deals_get(start, end)
    except Exception:
        deals = None

    if deals:
        exits = [
            d for d in deals
            if getattr(d, "magic", None) == BOT_MAGIC
            and d.entry == mt5.DEAL_ENTRY_OUT
        ]

        rows = []
        total_pnl = 0.0
        wins = 0
        losses = 0

        for d in exits:
            pnl = float(d.profit) + float(d.swap) + float(d.commission)
            total_pnl += pnl

            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1

            rows.append({
                "Date": datetime.fromtimestamp(
                    d.time,
                    tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M"),
                "Ticket": d.position_id,
                "Order": d.order,
                "Paire": d.symbol,
                "Lot": d.volume,
                "Profit ($)": round(pnl, 2)
            })

        total = wins + losses
        win_rate = (wins / total * 100) if total else 0

        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Trades", total)
        h2.metric("Win Rate", f"{win_rate:.1f}%")
        h3.metric("Profit Net", f"${total_pnl:,.2f}")
        h4.metric("Consecutive Losses", consecutive_losses())

        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True
            )
    else:
        st.info("Aucun historique bot disponible.")

# ============================================================
# LIVE LOG
# ============================================================
if st.session_state.trade_journal:
    with st.expander("📜 Logs"):
        for entry in reversed(st.session_state.trade_journal[-50:]):
            st.write(entry)

# ============================================================
# MARKET ANALYSIS PANEL
# ============================================================
st.divider()
st.subheader("🧠 SMC Scanner")

scanner_rows = []

if MT5_AVAILABLE:
    for symbol in st.session_state.custom_symbols:
        if not ensure_symbol(symbol):
            scanner_rows.append({
                "Symbol": symbol,
                "Signal": "INVALID SYMBOL",
                "Score": 0,
                "Bias": "-",
                "Structure": "-",
                "RR": 0
            })
            continue

        analysis = analyze_smc(symbol)

        if not analysis:
            scanner_rows.append({
                "Symbol": symbol,
                "Signal": "NO DATA",
                "Score": 0,
                "Bias": "-",
                "Structure": "-",
                "RR": 0
            })
            continue

        scanner_rows.append({
            "Symbol": symbol,
            "Signal": analysis.get("action") or "NO TRADE",
            "Score": analysis.get("score", 0),
            "Bias": analysis.get("bias", "-"),
            "Structure": analysis.get("structure", "-"),
            "Break": analysis.get("structure_break", "-"),
            "Liquidity": (
                analysis.get("liquidity", {}) or {}
            ).get("type", "-"),
            "Location": analysis.get("location", "-"),
            "RR": round(float(analysis.get("rr", 0)), 2)
        })

if scanner_rows:
    st.dataframe(
        pd.DataFrame(scanner_rows),
        use_container_width=True
    )

# ============================================================
# AUTOMATIC LOOP
# ============================================================
if st.session_state.bot_active and MT5_AVAILABLE:
    reset_day_state()

    # Manage existing bot positions first.
    manage_positions()

    risk_ok, risk_reason = daily_risk_ok()

    if not risk_ok:
        st.warning(f"🛑 Trading pause: {risk_reason}")

    for symbol in st.session_state.custom_symbols:
        if not risk_ok:
            break

        if not ensure_symbol(symbol):
            continue

        # Session filter.
        session_ok, session_name = session_allowed()
        if not session_ok:
            continue

        # Spread filter.
        spread = current_spread_points(symbol)
        if spread is None or spread > max_spread_points:
            continue

        # News filter.
        news_block, news_title = get_news_block(symbol)
        if news_block:
            st.warning(
                f"📰 {symbol}: High Impact News, {news_title}"
            )
            continue

        # One bot position per symbol.
        if bot_positions(symbol):
            continue

        analysis = analyze_smc(symbol)

        if not analysis or not analysis.get("action"):
            continue

        sid = signal_id(symbol, analysis)

        if signal_already_traded(sid):
            continue

        success = execute_trade(symbol, analysis)

        # Register only after successful order.
        if success:
            register_signal(sid)

            st.toast(
                f"🚀 {analysis['action']} {symbol} | "
                f"Score {analysis['score']} | "
                f"RR {analysis.get('rr', 0):.2f}"
            )

    time.sleep(5)
    st.rerun()
