import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------------------
# KONFIGIRASYON PAJ LA
# -------------------------------------------------------------
st.set_page_config(
    page_title="SMC Forex Analyzer",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SMC (Smart Money Concepts) Forex Analyzer")

# Rechaje done otomatikman chak 60 segond
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

interval = st.sidebar.selectbox(
    "Timeframe",
    ["15m", "1h", "4h", "1d"],
    index=1
)

period = st.sidebar.selectbox(
    "Peryòd Done",
    ["5d", "1mo", "3mo", "6mo"],
    index=1
)

swing_window = st.sidebar.slider(
    "Sansiblite Estrikti (BOS/CHoCH)",
    min_value=3, max_value=10, value=5,
    help="Yon chif ba detekte plis kase estrikti (plis siyal, plis bri). Yon chif wo detekte sèlman gwo kase yo."
)

# -------------------------------------------------------------
# TELECHAJE DONE AN TAN REYÈL
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
# EMA200 - FILT TANDANS JENERAL
# -------------------------------------------------------------
df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()
ema_trend = "Bullish 🟢" if df["Close"].iloc[-1] > df["EMA200"].iloc[-1] else "Bearish 🔴"

# -------------------------------------------------------------
# LOGIC SMC (FVG, ORDER BLOCKS, BOS/CHoCH)
# -------------------------------------------------------------

def get_fvgs(df):
    """Detekte Fair Value Gaps epi tcheke si yo deja 'mitigate' (pri a tounen ladan yo)."""
    fvgs = []
    highs = df["High"].values
    lows = df["Low"].values
    times = df.index

    for i in range(2, len(df)):
        if lows[i] > highs[i - 2]:
            top, bottom = float(lows[i]), float(highs[i - 2])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            fvgs.append({
                "Type": "Bullish FVG",
                "Start_Time": times[i - 2],
                "End_Time": times[i],
                "Top": top,
                "Bottom": bottom,
                "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"
            })
        elif highs[i] < lows[i - 2]:
            top, bottom = float(lows[i - 2]), float(highs[i])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            fvgs.append({
                "Type": "Bearish FVG",
                "Start_Time": times[i - 2],
                "End_Time": times[i],
                "Top": top,
                "Bottom": bottom,
                "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"
            })
    return fvgs


def get_order_blocks(df, min_body_multiplier=1.5):
    """Detekte Order Blocks, men sèlman lè gen yon vrè 'displacement'
    (bouji ki pi gwo pase mwayèn) — sa evite anpil fo siyal."""
    obs = []
    body = (df["Close"] - df["Open"]).abs()
    avg_body = body.rolling(20).mean()
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values
    opens = df["Open"].values
    times = df.index

    for i in range(20, len(df) - 1):
        if pd.isna(avg_body.iloc[i]) or avg_body.iloc[i] == 0:
            continue
        strong_move = body.iloc[i] > avg_body.iloc[i] * min_body_multiplier

        # Bullish OB: bouji wouj anvan gwo enpilsyon monte
        if closes[i - 1] < opens[i - 1] and closes[i] > highs[i - 1] and strong_move:
            top, bottom = float(highs[i - 1]), float(lows[i - 1])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            obs.append({
                "Type": "Bullish OB",
                "Time": times[i - 1],
                "Top": top,
                "Bottom": bottom,
                "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"
            })

        # Bearish OB: bouji vèt anvan gwo enpilsyon desann
        elif closes[i - 1] > opens[i - 1] and closes[i] < lows[i - 1] and strong_move:
            top, bottom = float(highs[i - 1]), float(lows[i - 1])
            mitigated = any(lows[j] <= top and highs[j] >= bottom for j in range(i + 1, len(df)))
            obs.append({
                "Type": "Bearish OB",
                "Time": times[i - 1],
                "Top": top,
                "Bottom": bottom,
                "Estati": "Mitigate ✅" if mitigated else "Aktif 🔥"
            })
    return obs


def get_swing_points(df, window=5):
    """Jwenn pwen swing high/low (ekstrèm lokal) pou konstwi estrikti mache a."""
    highs = df["High"].values
    lows = df["Low"].values
    swing_highs, swing_lows = [], []
    for i in range(window, len(df) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            swing_highs.append((i, highs[i]))
        if lows[i] == min(lows[i - window:i + window + 1]):
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def get_structure_events(df, window=5):
    """Detekte BOS (Break of Structure = kontinyasyon tandans) ak
    CHoCH (Change of Character = ranvèsman tandans)."""
    swing_highs, swing_lows = get_swing_points(df, window)
    closes = df["Close"].values
    times = df.index

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
# TABLO REZIME RAPID
# -------------------------------------------------------------
last_price = float(df["Close"].iloc[-1])
last_event = structure_events[-1] if structure_events else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Pri Aktyèl", f"{last_price:.5f}")
c2.metric("📊 Tandans EMA200", ema_trend)
c3.metric("🔀 Dènye Estrikti", last_event["Type"] if last_event else "Poko gen")
c4.metric("🕒 Dènye Mizajou", df.index[-1].strftime("%Y-%m-%d %H:%M"))

# -------------------------------------------------------------
# AFICHAJ GRAFIK CANDLESTICK AK PLOTLY
# -------------------------------------------------------------
fig = go.Figure(data=[go.Candlestick(
    x=df.index,
    open=df["Open"],
    high=df["High"],
    low=df["Low"],
    close=df["Close"],
    name="Price"
)])

fig.add_trace(go.Scatter(
    x=df.index, y=df["EMA200"],
    mode="lines", name="EMA200",
    line=dict(color="orange", width=1.5)
))

# Trace FVG yo (aktif yo pi vif, mitigate yo pi transparan)
for fvg in fvgs[-15:]:
    is_bull = fvg["Type"] == "Bullish FVG"
    active = fvg["Estati"].startswith("Aktif")
    base_color = "0, 255, 0" if is_bull else "255, 0, 0"
    opacity = 0.28 if active else 0.10
    fig.add_shape(
        type="rect",
        x0=fvg["Start_Time"], y0=fvg["Bottom"],
        x1=df.index[-1], y1=fvg["Top"],
        fillcolor=f"rgba({base_color}, {opacity})",
        line=dict(width=0),
    )

fig.update_layout(
    title=f"Analiz SMC pou {symbol} ({interval}) — Tandans estrikti: {structure_trend or 'N/A'}",
    xaxis_title="Dat / Lè",
    yaxis_title="Pri",
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------
# TABLO STATISTIK AK REZIME
# -------------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🔥 Fair Value Gaps (FVG)")
    if fvgs:
        st.dataframe(pd.DataFrame(fvgs).tail(8), use_container_width=True)
    else:
        st.info("Pa gen FVG detekte.")

with col2:
    st.subheader("📦 Order Blocks (OB)")
    if obs:
        st.dataframe(pd.DataFrame(obs).tail(8), use_container_width=True)
    else:
        st.info("Pa gen OB detekte.")

with col3:
    st.subheader("🔀 BOS / CHoCH")
    if structure_events:
        st.dataframe(pd.DataFrame(structure_events).tail(8), use_container_width=True)
    else:
        st.info("Pa gen kase estrikti detekte.")

st.caption(
    "⚠️ Done yo soti nan Yahoo Finance (yfinance). Pou pè Forex, done sa yo ka gen ti reta oswa "
    "pa 100% presi parapò ak yon broker pwofesyonèl — itilize app la kòm zouti analiz, "
    "pa kòm sèl sous desizyon."
)
