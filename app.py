import streamlit as st
import MetaTrader5 as mt5
import pandas as pd

# ---------------------------------------------------------
# CONFIGURATION PAJ LA
# ---------------------------------------------------------
st.set_page_config(page_title="SMC Bot Execution", layout="wide")
st.title("🤖 SMC Forex Bot - Konèksyon Zòn MT5")

# ---------------------------------------------------------
# KONEKSYON AUTOMATIK AK METATRADER 5 SOU PC
# ---------------------------------------------------------
if not mt5.initialize():
    st.sidebar.error("❌ MT5 pa louvri sou PC a. Souple louvri MT5!")
else:
    account_info = mt5.account_info()
    if account_info is not None:
        st.sidebar.success("✅ Konekte ak MT5 sou PC!")
        st.sidebar.write(f"**Kont:** {account_info.login}")
        st.sidebar.write(f"**Sèvè:** {account_info.server}")
        st.sidebar.write(f"**Solde (Balance):** ${account_info.balance:.2f}")

# ---------------------------------------------------------
# FONKSYON POU PASE LÒD
# ---------------------------------------------------------
def ekzekite_trade(symbol, action, lot):
    if not mt5.initialize():
        return "❌ Erè: Asire w MetaTrader 5 louvri sou PC w la."

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return f"❌ Senbòl {symbol} pa jwenn nan MT5."

    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if action == "BUY":
        trade_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        trade_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": trade_type,
        "price": price,
        "deviation": 20,
        "magic": 100200,
        "comment": "SMC Bot Direct PC",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return f"❌ Erè ({result.retcode}): {result.comment}"

    return f"🚀 Lòd {action} sou {symbol} pase ak siksè! Ticket: {result.order}"

# ---------------------------------------------------------
# INTÈFAS SENP POU KONTWÒLE BOT LA
# ---------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("⚙️ Paramèt Trade")
    symbol = st.text_input("Senbòl MT5", value="EURUSD")
    lot = st.number_input("Volim (Lot)", value=0.01, step=0.01, format="%.2f")

    st.write("---")
    btn_buy = st.button("🟢 Achte (BUY)", use_container_width=True)
    btn_sell = st.button("🔴 Vann (SELL)", use_container_width=True)

    if btn_buy:
        res = ekzekite_trade(symbol, "BUY", lot)
        st.info(res)

    if btn_sell:
        res = ekzekite_trade(symbol, "SELL", lot)
        st.info(res)

with col2:
    st.subheader("📊 Statut Mache & Analiz SMC")
    st.write("Isit la ou ka gade grafik SMC ou an ak siyal yo san okenn fòmilè pa ankonbre w.")
    # Ou ka mete grafik Plotly/SMC ou te genyen an nan pati sa a
