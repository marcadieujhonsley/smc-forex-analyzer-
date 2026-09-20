import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# -------------------------------------------------------------
# KONFIGIRASYON PAJ LA
# -------------------------------------------------------------
st.set_page_config(
    page_title="SMC Forex Analyzer",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SMC (Smart Money Concepts) Forex Analyzer")

# -------------------------------------------------------------
# SIDEBAR PARAMÈT
# -------------------------------------------------------------
st.sidebar.header("⚙️ Paramèt Analiz")

symbol = st.sidebar.selectbox(
    "Chwazi Pè / Aktif",
    ["EURUSD=X", "GBPUSD=X", "GC=F", "USDJPY=X", "AUDUSD=X", "BTC-USD"]
)

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

# -------------------------------------------------------------
# TELECHAJE DONE AN TAN REYÈL
# -------------------------------------------------------------
@st.cache_data(ttl=60)
def load_data(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

with st.spinner("Ap telechaje done mache yo..."):
    df = load_data(symbol, period, interval)

if df.empty:
    st.error("Mwen pa ka jwenn done pou senbòl sa a anba kondisyon sa yo.")
    st.stop()

# -------------------------------------------------------------
# LOGIC SMC (DETEKSYON FVG AK ORDER BLOCKS)
# -------------------------------------------------------------

# 1. Detekte Fair Value Gaps (FVG)
def get_fvgs(df):
    fvgs = []
    for i in range(2, len(df)):
        # Bullish FVG
        if df['Low'].iloc[i] > df['High'].iloc[i-2]:
            fvgs.append({
                'Type': 'Bullish FVG',
                'Start_Time': df.index[i-2],
                'End_Time': df.index[i],
                'Top': float(df['Low'].iloc[i]),
                'Bottom': float(df['High'].iloc[i-2])
            })
        # Bearish FVG
        elif df['High'].iloc[i] < df['Low'].iloc[i-2]:
            fvgs.append({
                'Type': 'Bearish FVG',
                'Start_Time': df.index[i-2],
                'End_Time': df.index[i],
                'Top': float(df['Low'].iloc[i-2]),
                'Bottom': float(df['High'].iloc[i])
            })
    return fvgs

# 2. Detekte Order Blocks (OB)
def get_order_blocks(df):
    obs = []
    for i in range(2, len(df)-1):
        # Bullish OB: Bouji wouj anvan gwo enpilsyon monte
        if df['Close'].iloc[i-1] < df['Open'].iloc[i-1] and df['Close'].iloc[i] > df['High'].iloc[i-1]:
            obs.append({
                'Type': 'Bullish OB',
                'Time': df.index[i-1],
                'Top': float(df['High'].iloc[i-1]),
                'Bottom': float(df['Low'].iloc[i-1])
            })
        # Bearish OB: Bouji vèt anvan gwo enpilsyon desann
        elif df['Close'].iloc[i-1] > df['Open'].iloc[i-1] and df['Close'].iloc[i] < df['Low'].iloc[i-1]:
            obs.append({
                'Type': 'Bearish OB',
                'Time': df.index[i-1],
                'Top': float(df['High'].iloc[i-1]),
                'Bottom': float(df['Low'].iloc[i-1])
            })
    return obs

fvgs = get_fvgs(df)
obs = get_order_blocks(df)

# -------------------------------------------------------------
# AFICHAJ GRAFIK CANDLESTICK AK PLOTLY
# -------------------------------------------------------------
fig = go.Figure(data=[go.Candlestick(
    x=df.index,
    open=df['Open'],
    high=df['High'],
    low=df['Low'],
    close=df['Close'],
    name="Price"
)])

# Trace dènye FVG yo sou Grafik la
for fvg in fvgs[-15:]:
    color = "rgba(0, 255, 0, 0.25)" if fvg['Type'] == 'Bullish FVG' else "rgba(255, 0, 0, 0.25)"
    fig.add_shape(
        type="rect",
        x0=fvg['Start_Time'], y0=fvg['Bottom'],
        x1=df.index[-1], y1=fvg['Top'],
        fillcolor=color,
        line=dict(width=0),
        name=fvg['Type']
    )

fig.update_layout(
    title=f"Analiz SMC pou {symbol} ({interval})",
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
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔥 Dènye Fair Value Gaps (FVG)")
    if fvgs:
        st.dataframe(pd.DataFrame(fvgs).tail(5), use_container_width=True)
    else:
        st.info("Pa gen FVG detekte.")

with col2:
    st.subheader("📦 Dènye Order Blocks (OB)")
    if obs:
        st.dataframe(pd.DataFrame(obs).tail(5), use_container_width=True)
    else:
        st.info("Pa gen OB detekte.")