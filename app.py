import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import websocket
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------------------
# DERIV API — FONKSYON KONEKSYON AK TRANZAKSYON (KONT DEMO)
# -------------------------------------------------------------
DERIV_SYMBOL_MAP = {
    "EURUSD=X": "frxEURUSD",
    "GBPUSD=X": "frxGBPUSD",
    "USDJPY=X": "frxUSDJPY",
    "AUDUSD=X": "frxAUDUSD",
    "GC=F": "frxXAUUSD",
    "BTC-USD": "cryBTCUSD",
}


def deriv_send_recv(ws, request, expected_msg_type=None, timeout=10):
    ws.settimeout(timeout)
    ws.send(json.dumps(request))
    while True:
        raw = ws.recv()
        data = json.loads(raw)
        if data.get("error"):
            raise RuntimeError(data["error"].get("message", "Erè Deriv API"))
        if expected_msg_type is None or data.get("msg_type") == expected_msg_type:
            return data


def deriv_connect(token):
    ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089", timeout=10)
    auth = deriv_send_recv(ws, {"authorize": token}, "authorize")
    return ws, auth["authorize"]


def deriv_buy(ws, symbol, direction, stake, multiplier):
    contract_type = "MULTUP" if direction == "ACHTE" else "MULTDOWN"
    request = {
        "buy": 1,
        "price": stake,
        "parameters": {
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "multiplier": multiplier,
            "symbol": symbol,
        },
    }
    resp = deriv_send_recv(ws, request, "buy")
    return resp["buy"]["contract_id"]


def deriv_sell(ws, contract_id):
    resp = deriv_send_recv(ws, {"sell": contract_id, "price": 0}, "sell")
    return resp["sell"]

# -------------------------------------------------------------
# MT5 — FONKSYON KONEKSYON AK TRANZAKSYON (SÈLMAN SI KOURI LOKAL SOU WINDOWS)
# -------------------------------------------------------------
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


def mt5_place_order(symbol, direction, lot):
    order_type = mt5.ORDER_TYPE_BUY if direction == "ACHTE" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if direction == "ACHTE" else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": 10,
        "magic": 234000,
        "comment": "bot-smc-dashboard",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    return mt5.order_send(request)


def mt5_close_order(ticket, symbol, direction, lot):
    close_type = mt5.ORDER_TYPE_SELL if direction == "ACHTE" else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
    price = tick.bid if direction == "ACHTE" else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 10,
        "magic": 234000,
        "comment": "bot-smc-close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    return mt5.order_send(request)

# -------------------------------------------------------------
# METAAPI — MT5 NAN NWAJ (FONKSYONE SOU STREAMLIT CLOUD TOU)
# -------------------------------------------------------------
import asyncio
try:
    from metaapi_cloud_sdk import MetaApi
    METAAPI_AVAILABLE = True
except ImportError:
    METAAPI_AVAILABLE = False


async def _metaapi_get_connection(token, account_id):
    api = MetaApi(token)
    account = await api.metatrader_account_api.get_account(account_id)
    if account.state not in ("DEPLOYED", "DEPLOYING"):
        await account.deploy()
    await account.wait_connected()
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()
    return connection


async def _metaapi_place_order(token, account_id, symbol, direction, volume):
    connection = await _metaapi_get_connection(token, account_id)
    if direction == "ACHTE":
        return await connection.create_market_buy_order(symbol, volume)
    return await connection.create_market_sell_order(symbol, volume)


async def _metaapi_close_position(token, account_id, position_id):
    connection = await _metaapi_get_connection(token, account_id)
    return await connection.close_position(position_id)


def metaapi_place_order(token, account_id, symbol, direction, volume):
    return asyncio.run(_metaapi_place_order(token, account_id, symbol, direction, volume))


def metaapi_close_position(token, account_id, position_id):
    return asyncio.run(_metaapi_close_position(token, account_id, position_id))


# -------------------------------------------------------------
# KONFIGIRASYON PAJ LA
# -------------------------------------------------------------
st.set_page_config(
    page_title="SMC Forex Analyzer",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SMC (Smart Money Concepts) Forex Analyzer")

st_autorefresh(interval=60 * 1000, key="auto_refresh")

# -------------------------------------------------------------
# SIDEBAR PARAMÈT
# -------------------------------------------------------------
st.sidebar.header("⚙️ Paramèt Analiz")

preset_symbols = ["EURUSD=X", "GBPUSD=X", "GC=F", "USDJPY=X", "AUDUSD=X", "BTC-USD"]
choice = st.sidebar.selectbox(
    "Chwazi Pè / Aktif",
    preset_symbols + ["✏️ Antre pwòp senbòl (Yahoo Finance)"]
)

if choice == "✏️ Antre pwòp senbòl (Yahoo Finance)":
    symbol = st.sidebar.text_input(
        "Tape senbòl la (egz: EURJPY=X, XAUUSD=X, ETH-USD, AAPL)",
        value="EURJPY=X"
    ).strip().upper()
else:
    symbol = choice

interval = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1)
period = st.sidebar.selectbox("Peryòd Done", ["5d", "1mo", "3mo", "6mo"], index=1)

swing_window = st.sidebar.slider(
    "Sansiblite Estrikti (BOS/CHoCH)",
    min_value=3, max_value=10, value=5,
    help="Yon chif ba detekte plis kase estrikti (plis siyal, plis bri). Yon chif wo detekte sèlman gwo kase yo."
)

# -------------------------------------------------------------
# SIDEBAR — BOT TRADING (DERIV DEMO)
# -------------------------------------------------------------
st.sidebar.divider()
st.sidebar.header("🤖 Bot Trading (Deriv Demo)")
st.sidebar.caption(
    "Kreye yon API token sou app.deriv.com → Settings → API token (dwa 'Trade'), "
    "sou yon KONT DEMO (Virtual Money) — PA sou kont reyèl ou."
)

for key, default in [
    ("bot_running", False), ("deriv_ws", None), ("open_contract_id", None),
    ("last_signal_acted", None), ("trade_log", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

deriv_token = st.sidebar.text_input("Deriv API Token (Demo)", type="password")
deriv_symbol = st.sidebar.text_input(
    "Senbòl Deriv",
    value=DERIV_SYMBOL_MAP.get(symbol, ""),
    help="Egzanp: frxEURUSD, frxXAUUSD, cryBTCUSD. Verifye li koresponn ak pè ou chwazi anwo a."
)
stake = st.sidebar.number_input("Estak pa tranzaksyon (USD demo)", min_value=1.0, value=10.0, step=1.0)
multiplier = st.sidebar.number_input("Miltipliyè", min_value=5, max_value=1000, value=100, step=5)

bcol1, bcol2 = st.sidebar.columns(2)
start_clicked = bcol1.button("▶️ Lanse", disabled=st.session_state.bot_running or not deriv_token)
stop_clicked = bcol2.button("⏹️ Fèmen", disabled=not st.session_state.bot_running)

if start_clicked:
    try:
        ws, account_info = deriv_connect(deriv_token)
        if account_info.get("is_virtual") != 1:
            st.sidebar.error("⚠️ Sa a se yon KONT REYÈL, pa yon kont demo. Bot la pa lanse pou sekirite w.")
            ws.close()
        else:
            st.session_state.deriv_ws = ws
            st.session_state.bot_running = True
            st.sidebar.success(f"Konekte sou kont demo ({account_info.get('loginid')}) ✅")
    except Exception as e:
        st.sidebar.error(f"Erè koneksyon Deriv: {e}")

if stop_clicked:
    if st.session_state.open_contract_id and st.session_state.deriv_ws:
        try:
            deriv_sell(st.session_state.deriv_ws, st.session_state.open_contract_id)
            st.session_state.trade_log.append(f"Fèmen pozisyon {st.session_state.open_contract_id} (bot fèmen manyèlman)")
        except Exception as e:
            st.sidebar.warning(f"Pa t ka fèmen pozisyon ouvè a: {e}")
    if st.session_state.deriv_ws:
        try:
            st.session_state.deriv_ws.close()
        except Exception:
            pass
    st.session_state.bot_running = False
    st.session_state.deriv_ws = None
    st.session_state.open_contract_id = None
    st.session_state.last_signal_acted = None

# -------------------------------------------------------------
# SIDEBAR — BOT TRADING (MT5 LOKAL)
# -------------------------------------------------------------
st.sidebar.divider()
st.sidebar.header("🖥️ Bot Trading (MT5 Lokal)")

if not MT5_AVAILABLE:
    st.sidebar.warning(
        "MT5 pa disponib nan anviwònman sa a. Sa mache sèlman lè app la ap kouri "
        "lokalman sou Windows, sou menm laptop kote Terminal MT5 la enstale."
    )
else:
    for key, default in [
        ("mt5_running", False), ("mt5_open_ticket", None),
        ("mt5_last_signal_acted", None), ("mt5_trade_log", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    mt5_login = st.sidebar.number_input("Nimewo Kont MT5", min_value=0, step=1, value=0)
    mt5_password = st.sidebar.text_input("Modpas MT5", type="password")
    mt5_server = st.sidebar.text_input("Sèvè MT5", value="Deriv-Demo")
    mt5_symbol = st.sidebar.text_input("Senbòl MT5", value="GBPUSD")
    mt5_lot = st.sidebar.number_input("Lo (lot size)", min_value=0.01, value=0.01, step=0.01)

    mcol1, mcol2 = st.sidebar.columns(2)
    mt5_start = mcol1.button("▶️ Lanse MT5", disabled=st.session_state.mt5_running)
    mt5_stop = mcol2.button("⏹️ Fèmen MT5", disabled=not st.session_state.mt5_running)

    if mt5_start:
        if mt5.initialize(login=int(mt5_login), password=mt5_password, server=mt5_server):
            account_info = mt5.account_info()
            if account_info is not None and account_info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO:
                st.session_state.mt5_running = True
                st.sidebar.success(f"Konekte sou MT5 demo ({account_info.login}) ✅")
            else:
                st.sidebar.error("⚠️ Sa a pa sanble yon kont demo. Bot la pa lanse pou sekirite w.")
                mt5.shutdown()
        else:
            st.sidebar.error(f"Erè koneksyon MT5: {mt5.last_error()}")

    if mt5_stop:
        if st.session_state.mt5_open_ticket:
            try:
                mt5_close_order(st.session_state.mt5_open_ticket, mt5_symbol,
                                 st.session_state.mt5_last_signal_acted, mt5_lot)
                st.session_state.mt5_trade_log.append(
                    f"Fèmen pozisyon MT5 (tikè {st.session_state.mt5_open_ticket}) — bot fèmen manyèlman"
                )
            except Exception as e:
                st.sidebar.warning(f"Pa t ka fèmen pozisyon MT5 ouvè a: {e}")
        mt5.shutdown()
        st.session_state.mt5_running = False
        st.session_state.mt5_open_ticket = None
        st.session_state.mt5_last_signal_acted = None

# -------------------------------------------------------------
# SIDEBAR — BOT TRADING (METAAPI CLOUD — MT5 SAN LAPTOP LIMEN)
# -------------------------------------------------------------
st.sidebar.divider()
st.sidebar.header("☁️ Bot Trading (MT5 via MetaApi)")

if not METAAPI_AVAILABLE:
    st.sidebar.warning("Pake 'metaapi-cloud-sdk' pa enstale. Ajoute l nan requirements.txt.")
else:
    st.sidebar.caption("Sèvi ak API Token ak Account ID ou jwenn sou app.metaapi.cloud.")

    for key, default in [
        ("metaapi_running", False), ("metaapi_open_position", None),
        ("metaapi_last_signal_acted", None), ("metaapi_trade_log", []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    metaapi_token = st.sidebar.text_input("MetaApi API Token", type="password")
    metaapi_account_id = st.sidebar.text_input("MetaApi Account ID")
    metaapi_symbol = st.sidebar.text_input("Senbòl MT5 (MetaApi)", value="EURUSD")
    metaapi_volume = st.sidebar.number_input("Volim (lot)", min_value=0.01, value=0.01, step=0.01)

    macol1, macol2 = st.sidebar.columns(2)
    metaapi_start = macol1.button(
        "▶️ Lanse", key="metaapi_start_btn",
        disabled=st.session_state.metaapi_running or not metaapi_token or not metaapi_account_id
    )
    metaapi_stop = macol2.button(
        "⏹️ Fèmen", key="metaapi_stop_btn", disabled=not st.session_state.metaapi_running
    )

    if metaapi_start:
        st.session_state.metaapi_running = True
        st.sidebar.success("Bot MetaApi aktive — l ap konekte epi aji nan pwochen sik (60s) la.")

    if metaapi_stop:
        if st.session_state.metaapi_open_position:
            try:
                metaapi_close_position(metaapi_token, metaapi_account_id, st.session_state.metaapi_open_position)
                st.session_state.metaapi_trade_log.append(
                    f"Fèmen pozisyon MetaApi {st.session_state.metaapi_open_position} — bot fèmen manyèlman"
                )
            except Exception as e:
                st.sidebar.warning(f"Pa t ka fèmen pozisyon MetaApi: {e}")
        st.session_state.metaapi_running = False
        st.session_state.metaapi_open_position = None
        st.session_state.metaapi_last_signal_acted = None

# -------------------------------------------------------------
# TELECHAJE DONE
# -------------------------------------------------------------
@st.cache_data(ttl=60)
def load_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

if not symbol:
    st.warning("Tanpri antre yon senbòl valab.")
    st.stop()

with st.spinner("Ap telechaje done mache yo..."):
    try:
        df = load_data(symbol, period, interval)
    except Exception as e:
        st.error(f"Erè pandan telechajman done pou {symbol}: {e}")
        st.stop()

if df.empty or len(df) < 5:
    st.error(
        "Mwen pa ka jwenn ase done pou senbòl/timeframe sa a. "
        "Verifye ke senbòl la egziste sou Yahoo Finance, oswa eseye yon lòt timeframe/peryòd."
    )
    st.stop()

df = df.dropna(subset=["Open", "High", "Low", "Close"])

# -------------------------------------------------------------
# EMA200
# -------------------------------------------------------------
df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()
ema_trend = "Bullish 🟢" if df["Close"].iloc[-1] > df["EMA200"].iloc[-1] else "Bearish 🔴"
ema_dir = "bullish" if "Bullish" in ema_trend else "bearish"

# -------------------------------------------------------------
# LOGIC SMC (FVG, ORDER BLOCKS, BOS/CHoCH)
# -------------------------------------------------------------

def get_fvgs(df):
    fvgs = []
    highs, lows, times = df["High"].values, df["Low"].values, df.index

    for i in range(2, len(df)):
        if lows[i] > highs[i - 2]:
            top, bottom = float(lows[i]), float(highs[i - 2])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            fvgs.append({"Type": "Bullish FVG", "Start_Time": times[i - 2], "End_Time": times[i],
                         "Top": top, "Bottom": bottom, "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"})
        elif highs[i] < lows[i - 2]:
            top, bottom = float(lows[i - 2]), float(highs[i])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            fvgs.append({"Type": "Bearish FVG", "Start_Time": times[i - 2], "End_Time": times[i],
                         "Top": top, "Bottom": bottom, "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"})
    return fvgs


def get_order_blocks(df, min_body_multiplier=1.5):
    obs = []
    body = (df["Close"] - df["Open"]).abs()
    avg_body = body.rolling(20).mean()
    highs, lows, closes, opens, times = df["High"].values, df["Low"].values, df["Close"].values, df["Open"].values, df.index

    for i in range(20, len(df) - 1):
        if pd.isna(avg_body.iloc[i]) or avg_body.iloc[i] == 0:
            continue
        strong_move = body.iloc[i] > avg_body.iloc[i] * min_body_multiplier

        if closes[i - 1] < opens[i - 1] and closes[i] > highs[i - 1] and strong_move:
            top, bottom = float(highs[i - 1]), float(lows[i - 1])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            obs.append({"Type": "Bullish OB", "Time": times[i - 1], "Top": top, "Bottom": bottom,
                        "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"})
        elif closes[i - 1] > opens[i - 1] and closes[i] < lows[i - 1] and strong_move:
            top, bottom = float(highs[i - 1]), float(lows[i - 1])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            obs.append({"Type": "Bearish OB", "Time": times[i - 1], "Top": top, "Bottom": bottom,
                        "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"})
    return obs


def get_swing_points(df, window=5):
    highs, lows = df["High"].values, df["Low"].values
    swing_highs, swing_lows = [], []
    for i in range(window, len(df) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            swing_highs.append((i, highs[i]))
        if lows[i] == min(lows[i - window:i + window + 1]):
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def get_structure_events(df, window=5):
    swing_highs, swing_lows = get_swing_points(df, window)
    closes, times = df["Close"].values, df.index

    events = []
    trend = None
    sh_pointer, sl_pointer = 0, 0
    active_high, active_low = None, None

    for i in range(len(df)):
        while sh_pointer < len(swing_highs) and swing_highs[sh_pointer][0] <= i:
            if active_high is None or swing_highs[sh_pointer][1] > active_high[1]:
                active_high = swing_highs[sh_pointer]
            sh_pointer += 1
        while sl_pointer < len(swing_lows) and swing_lows[sl_pointer][0] <= i:
            if active_low is None or swing_lows[sl_pointer][1] < active_low[1]:
                active_low = swing_lows[sl_pointer]
            sl_pointer += 1

        if active_high is not None and closes[i] > active_high[1]:
            label = "CHoCH" if trend == "bearish" else "BOS"
            events.append({"Type": f"Bullish {label}", "Time": times[i], "Nivo": float(active_high[1])})
            trend = "bullish"
            active_high = None

        if active_low is not None and closes[i] < active_low[1]:
            label = "CHoCH" if trend == "bullish" else "BOS"
            events.append({"Type": f"Bearish {label}", "Time": times[i], "Nivo": float(active_low[1])})
            trend = "bearish"
            active_low = None

    return events, trend


fvgs = get_fvgs(df)
obs = get_order_blocks(df)
structure_events, structure_trend = get_structure_events(df, window=swing_window)

# -------------------------------------------------------------
# PREMIUM / DISCOUNT (EKILIB)
# -------------------------------------------------------------
if structure_events:
    range_df = df.loc[structure_events[-1]["Time"]:]
    if len(range_df) < 5:
        range_df = df.tail(min(len(df), 50))
else:
    range_df = df.tail(min(len(df), 100))

range_high = float(range_df["High"].max())
range_low = float(range_df["Low"].min())
equilibrium = (range_high + range_low) / 2
last_price = float(df["Close"].iloc[-1])
zone_side = "Premium" if last_price > equilibrium else "Discount"

# -------------------------------------------------------------
# CHWAZI PI BON ZÒN (FVG + OB) SELON PREMIUM/DISCOUNT
# -------------------------------------------------------------
all_zones = []
for f in fvgs:
    all_zones.append({"Type": f["Type"], "Top": f["Top"], "Bottom": f["Bottom"], "Estati": f["Estati"], "Kalite": "FVG"})
for o in obs:
    all_zones.append({"Type": o["Type"], "Top": o["Top"], "Bottom": o["Bottom"], "Estati": o["Estati"], "Kalite": "OB"})

def zone_mid(z):
    return (z["Top"] + z["Bottom"]) / 2

def zone_distance(z):
    return abs(last_price - zone_mid(z))

def zone_valid_context(z):
    mid = zone_mid(z)
    return mid <= equilibrium if "Bullish" in z["Type"] else mid >= equilibrium

active_zones = [z for z in all_zones if z["Estati"].startswith("Aktif")]
bullish_zones = sorted([z for z in active_zones if "Bullish" in z["Type"]], key=zone_distance)
bearish_zones = sorted([z for z in active_zones if "Bearish" in z["Type"]], key=zone_distance)

def pick_best(zones):
    valid = [z for z in zones if zone_valid_context(z)]
    if valid:
        return valid[0], True
    if zones:
        return zones[0], False
    return None, False

best_bull, bull_valid_ctx = pick_best(bullish_zones)
best_bear, bear_valid_ctx = pick_best(bearish_zones)

# -------------------------------------------------------------
# SIYAL KLÈ (ACHTE / VANN / AP TANN) — apa, kèlkeswa timeframe
# -------------------------------------------------------------

def price_in_zone(zone):
    return zone is not None and zone["Bottom"] <= last_price <= zone["Top"]

clear_signal = None
if ema_dir == structure_trend:
    if ema_dir == "bullish" and bull_valid_ctx and price_in_zone(best_bull):
        clear_signal = "ACHTE"
    elif ema_dir == "bearish" and bear_valid_ctx and price_in_zone(best_bear):
        clear_signal = "VANN"

st.markdown("## 🚦 Siyal Klè")
if clear_signal == "ACHTE":
    st.success(f"🟢 **SIYAL ACHTE** — pri a ({last_price:.5f}) nan yon zòn Bullish valab (Discount), EMA200 ak estrikti dakò.")
elif clear_signal == "VANN":
    st.error(f"🔴 **SIYAL VANN** — pri a ({last_price:.5f}) nan yon zòn Bearish valab (Premium), EMA200 ak estrikti dakò.")
else:
    st.info("⏳ **AP TANN** — kondisyon yo poko reyini (tandans EMA200, estrikti, ak yon zòn valab dwe dakò tout ansanm).")

# -------------------------------------------------------------
# BOT — DESIZYON OTOMATIK (Lachte/Vann Deriv Demo)
# -------------------------------------------------------------
if st.session_state.bot_running and st.session_state.deriv_ws:
    ws = st.session_state.deriv_ws
    try:
        if st.session_state.open_contract_id is None:
            if clear_signal in ("ACHTE", "VANN") and clear_signal != st.session_state.last_signal_acted:
                contract_id = deriv_buy(ws, deriv_symbol, clear_signal, stake, multiplier)
                st.session_state.open_contract_id = contract_id
                st.session_state.last_signal_acted = clear_signal
                st.session_state.trade_log.append(
                    f"{df.index[-1]} — Louvri {clear_signal} sou {deriv_symbol} (kontra {contract_id})"
                )
        else:
            if clear_signal != st.session_state.last_signal_acted:
                result = deriv_sell(ws, st.session_state.open_contract_id)
                st.session_state.trade_log.append(
                    f"{df.index[-1]} — Fèmen pozisyon (kontra {st.session_state.open_contract_id}), "
                    f"rezilta: {result.get('sold_for', 'N/A')} USD"
                )
                st.session_state.open_contract_id = None
                st.session_state.last_signal_acted = None
    except Exception as e:
        st.sidebar.error(f"⚠️ Erè bot pandan tranzaksyon: {e}")

st.subheader("🤖 Estati Bot")
if st.session_state.bot_running:
    st.success("Bot ap kouri (kont demo) ✅")
    if st.session_state.open_contract_id:
        st.write(f"Pozisyon ouvè: kontra `{st.session_state.open_contract_id}` ({st.session_state.last_signal_acted})")
    else:
        st.write("Pa gen pozisyon ouvè kounye a — ap tann yon siyal.")
else:
    st.info("Bot la fèmen — klike 'Lanse' nan sidebar la pou kòmanse.")

if st.session_state.trade_log:
    with st.expander("📜 Istorik Tranzaksyon Deriv (sesyon sa a)"):
        for entry in reversed(st.session_state.trade_log[-20:]):
            st.write(entry)

# -------------------------------------------------------------
# BOT MT5 — DESIZYON OTOMATIK
# -------------------------------------------------------------
if MT5_AVAILABLE and st.session_state.get("mt5_running"):
    try:
        if st.session_state.mt5_open_ticket is None:
            if clear_signal in ("ACHTE", "VANN") and clear_signal != st.session_state.mt5_last_signal_acted:
                result = mt5_place_order(mt5_symbol, clear_signal, mt5_lot)
                if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                    st.session_state.mt5_open_ticket = result.order
                    st.session_state.mt5_last_signal_acted = clear_signal
                    st.session_state.mt5_trade_log.append(
                        f"{df.index[-1]} — Louvri {clear_signal} sou {mt5_symbol} (tikè {result.order})"
                    )
                else:
                    st.sidebar.error(f"Erè lòd MT5: {getattr(result, 'comment', 'echèk')}")
        else:
            if clear_signal != st.session_state.mt5_last_signal_acted:
                mt5_close_order(st.session_state.mt5_open_ticket, mt5_symbol,
                                 st.session_state.mt5_last_signal_acted, mt5_lot)
                st.session_state.mt5_trade_log.append(
                    f"{df.index[-1]} — Fèmen pozisyon MT5 (tikè {st.session_state.mt5_open_ticket})"
                )
                st.session_state.mt5_open_ticket = None
                st.session_state.mt5_last_signal_acted = None
    except Exception as e:
        st.sidebar.error(f"⚠️ Erè bot MT5: {e}")

if MT5_AVAILABLE:
    st.subheader("🖥️ Estati Bot MT5")
    if st.session_state.get("mt5_running"):
        st.success("Bot MT5 ap kouri (kont demo) ✅")
        if st.session_state.mt5_open_ticket:
            st.write(f"Pozisyon ouvè: tikè `{st.session_state.mt5_open_ticket}` ({st.session_state.mt5_last_signal_acted})")
        else:
            st.write("Pa gen pozisyon ouvè kounye a — ap tann yon siyal.")
    else:
        st.info("Bot MT5 fèmen — klike 'Lanse MT5' nan sidebar la pou kòmanse.")

    if st.session_state.get("mt5_trade_log"):
        with st.expander("📜 Istorik Tranzaksyon MT5 (sesyon sa a)"):
            for entry in reversed(st.session_state.mt5_trade_log[-20:]):
                st.write(entry)

# -------------------------------------------------------------
# BOT METAAPI — DESIZYON OTOMATIK
# -------------------------------------------------------------
if METAAPI_AVAILABLE and st.session_state.get("metaapi_running"):
    try:
        if st.session_state.metaapi_open_position is None:
            if clear_signal in ("ACHTE", "VANN") and clear_signal != st.session_state.metaapi_last_signal_acted:
                result = metaapi_place_order(metaapi_token, metaapi_account_id, metaapi_symbol, clear_signal, metaapi_volume)
                position_id = result.get("positionId") or result.get("orderId")
                st.session_state.metaapi_open_position = position_id
                st.session_state.metaapi_last_signal_acted = clear_signal
                st.session_state.metaapi_trade_log.append(
                    f"{df.index[-1]} — Louvri {clear_signal} sou {metaapi_symbol} (pozisyon {position_id})"
                )
        else:
            if clear_signal != st.session_state.metaapi_last_signal_acted:
                metaapi_close_position(metaapi_token, metaapi_account_id, st.session_state.metaapi_open_position)
                st.session_state.metaapi_trade_log.append(
                    f"{df.index[-1]} — Fèmen pozisyon MetaApi ({st.session_state.metaapi_open_position})"
                )
                st.session_state.metaapi_open_position = None
                st.session_state.metaapi_last_signal_acted = None
    except Exception as e:
        st.sidebar.error(f"⚠️ Erè bot MetaApi: {e}")

if METAAPI_AVAILABLE:
    st.subheader("☁️ Estati Bot MetaApi (MT5 Cloud)")
    if st.session_state.get("metaapi_running"):
        st.success("Bot MetaApi ap kouri ✅")
        if st.session_state.metaapi_open_position:
            st.write(f"Pozisyon ouvè: `{st.session_state.metaapi_open_position}` ({st.session_state.metaapi_last_signal_acted})")
        else:
            st.write("Pa gen pozisyon ouvè kounye a — ap tann yon siyal.")
    else:
        st.info("Bot MetaApi fèmen — klike 'Lanse' nan sidebar la pou kòmanse.")

    if st.session_state.get("metaapi_trade_log"):
        with st.expander("📜 Istorik Tranzaksyon MetaApi (sesyon sa a)"):
            for entry in reversed(st.session_state.metaapi_trade_log[-20:]):
                st.write(entry)

st.divider()

# -------------------------------------------------------------
# TABLO REZIME RAPID
# -------------------------------------------------------------
last_event = structure_events[-1] if structure_events else None
zone_label = "🔴 Premium" if zone_side == "Premium" else "🟢 Discount"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Pri Aktyèl", f"{last_price:.5f}")
c2.metric("📊 EMA200", ema_trend)
c3.metric("🔀 Dènye Estrikti", last_event["Type"] if last_event else "Poko gen")
c4.metric("⚖️ Zòn Mache", zone_label)
c5.metric("🕒 Dènye Mizajou", df.index[-1].strftime("%Y-%m-%d %H:%M"))

# -------------------------------------------------------------
# GRAFIK CANDLESTICK
# -------------------------------------------------------------
fig = go.Figure(data=[go.Candlestick(
    x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"
)])

fig.add_trace(go.Scatter(x=df.index, y=df["EMA200"], mode="lines", name="EMA200",
                          line=dict(color="orange", width=1.5)))

fig.add_hline(y=equilibrium, line_dash="dot", line_color="yellow",
              annotation_text="Ekilib (50%)", annotation_position="right")

# FVG (vèt/wouj)
for fvg in fvgs[-15:]:
    is_bull = fvg["Type"] == "Bullish FVG"
    active = fvg["Estati"].startswith("Aktif")
    color = "0, 255, 0" if is_bull else "255, 0, 0"
    opacity = 0.28 if active else 0.10
    fig.add_shape(type="rect", x0=fvg["Start_Time"], y0=fvg["Bottom"], x1=df.index[-1], y1=fvg["Top"],
                  fillcolor=f"rgba({color}, {opacity})", line=dict(width=0))

# Order Blocks (ble/oranj)
for ob in obs[-10:]:
    is_bull = ob["Type"] == "Bullish OB"
    active = ob["Estati"].startswith("Aktif")
    color = "0, 150, 255" if is_bull else "255, 140, 0"
    opacity = 0.30 if active else 0.10
    fig.add_shape(type="rect", x0=ob["Time"], y0=ob["Bottom"], x1=df.index[-1], y1=ob["Top"],
                  fillcolor=f"rgba({color}, {opacity})", line=dict(width=1, color=f"rgba({color}, 0.6)"))

# BOS/CHoCH markè
for event in structure_events[-10:]:
    is_bull = "Bullish" in event["Type"]
    fig.add_annotation(
        x=event["Time"], y=event["Nivo"], text=event["Type"],
        showarrow=True, arrowhead=2,
        arrowcolor="lime" if is_bull else "red",
        font=dict(color="lime" if is_bull else "red", size=10),
        ay=-30 if is_bull else 30
    )

fig.update_layout(
    title=f"Analiz SMC pou {symbol} ({interval})",
    xaxis_title="Dat / Lè", yaxis_title="Pri",
    template="plotly_dark", xaxis_rangeslider_visible=False, height=650
)

if len(df) > 100:
    fig.update_xaxes(range=[df.index[-100], df.index[-1]])

st.plotly_chart(fig, use_container_width=True)
st.caption("🔍 Chart la ouvri zoome sou dènye bouji yo — dezoome (sourit/dwèt, oswa double-klike) pou wè tout istwa a.")

# -------------------------------------------------------------
# DASHBOARD SIYAL
# -------------------------------------------------------------
st.subheader("🧭 Dashboard Siyal")


def render_zone_card(label, zone, is_valid_ctx):
    if zone is None:
        st.info(f"Pa gen zòn aktif pou **{label}** kounye a.")
        return
    ctx_note = "✅ Valab nan kontèks Premium/Discount" if is_valid_ctx else "⚠️ Pa nan pi bon zòn Premium/Discount la — pran prekosyon"
    st.markdown(
        f"**{label}** — {zone['Kalite']} ({zone['Type']})\n\n"
        f"Zòn: `{zone['Bottom']:.5f}` → `{zone['Top']:.5f}`\n\n"
        f"{ctx_note}"
    )


st.write(f"**Zòn mache aktyèl:** {zone_label}  |  **Nivo ekilib:** `{equilibrium:.5f}`")

if structure_trend is None:
    st.warning("Poko gen ase estrikti detekte pou konpare ak EMA200 — ogmante peryòd done a si posib.")
    best, valid_ctx = (best_bull, bull_valid_ctx) if ema_dir == "bullish" else (best_bear, bear_valid_ctx)
    st.markdown(f"**Tandans EMA200:** {ema_trend}")
    render_zone_card("Zòn pou veye (selon EMA200)", best, valid_ctx)

elif ema_dir == structure_trend:
    bias_label = "Bullish 🟢" if ema_dir == "bullish" else "Bearish 🔴"
    st.success(f"✅ EMA200 ak dènye estrikti dakò — Bias: {bias_label} (Konfyans: Wo)")
    best, valid_ctx = (best_bull, bull_valid_ctx) if ema_dir == "bullish" else (best_bear, bear_valid_ctx)
    render_zone_card("Zòn pou veye", best, valid_ctx)

else:
    st.warning("⚠️ EMA200 ak dènye estrikti PA dakò — men toude pèspektiv separeman:")
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown(f"#### Selon EMA200 (tandans alontèm)\n{ema_trend}")
        best, valid_ctx = (best_bull, bull_valid_ctx) if ema_dir == "bullish" else (best_bear, bear_valid_ctx)
        render_zone_card("Zòn pou veye", best, valid_ctx)
    with dcol2:
        struct_label = "Bullish 🟢" if structure_trend == "bullish" else "Bearish 🔴"
        st.markdown(f"#### Selon Estrikti (BOS/CHoCH pi resan)\n{struct_label}")
        best, valid_ctx = (best_bull, bull_valid_ctx) if structure_trend == "bullish" else (best_bear, bear_valid_ctx)
        render_zone_card("Zòn pou veye", best, valid_ctx)

st.caption(
    "ℹ️ **Premium** = mwatye anwo ekilib la (favorize chèche siyal vann). **Discount** = mwatye anba ekilib "
    "la (favorize chèche siyal achte). Yon zòn ki make ⚠️ ka toujou reyaji, men li mwens ideyal selon lojik "
    "Premium/Discount SMC."
)

# -------------------------------------------------------------
# DETAY (KACHE PA DEFO)
# -------------------------------------------------------------
with st.expander("📋 Wè tout done detaye (FVG, OB, BOS/CHoCH)"):
    dcol1, dcol2, dcol3 = st.columns(3)
    with dcol1:
        st.subheader("🔥 FVG")
        st.dataframe(pd.DataFrame(fvgs).tail(10), use_container_width=True) if fvgs else st.info("Pa gen FVG.")
    with dcol2:
        st.subheader("📦 Order Blocks")
        st.dataframe(pd.DataFrame(obs).tail(10), use_container_width=True) if obs else st.info("Pa gen OB.")
    with dcol3:
        st.subheader("🔀 BOS / CHoCH")
        st.dataframe(pd.DataFrame(structure_events).tail(10), use_container_width=True) if structure_events else st.info("Pa gen estrikti.")

st.caption(
    "⚠️ Done yo soti nan Yahoo Finance (yfinance). Pou pè Forex, done sa yo ka gen ti reta oswa pa 100% "
    "presi parapò ak yon broker pwofesyonèl — itilize app la kòm zouti analiz, pa kòm sèl sous desizyon."
)
