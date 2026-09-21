import streamlit as st
import pandas as pd

# Try-except pou anpeche Streamlit Cloud kraze (crash)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

st.set_page_config(page_title="SMC Forex Bot", layout="wide")
st.title("🤖 SMC Forex Bot Execution")

# ---------------------------------------------------------
# DETEKSYON ANVIWÒNMAN (PC LOKAL VOR CLOUD)
# ---------------------------------------------------------
if MT5_AVAILABLE:
    st.sidebar.success("💻 Kòd la ap kouri sou PC lokal")
    if not mt5.initialize():
        st.sidebar.error("❌ MT5 pa louvri sou PC a. Souple louvri lojisyèl MT5 la!")
    else:
        acc = mt5.account_info()
        if acc:
            st.sidebar.write(f"**Kont:** {acc.login}")
            st.sidebar.write(f"**Solde:** ${acc.balance:.2f}")
else:
    st.sidebar.warning("☁️ Kòd la ap kouri sou Streamlit Cloud")
    st.sidebar.info("Libreri MetaTrader5 lokal pa ka kouri dirèkteman sou Cloud.")

# ---------------------------------------------------------
# FONKSYON EKZEKISYON
# ---------------------------------------------------------
def ekzekite_trade(symbol, action, lot):
    if not MT5_AVAILABLE:
        return "❌ Ou sou Streamlit Cloud. Pou sèvi ak MT5 lokal gratis, kouri app a sou PC w (streamlit run app.py)."
    
    if not mt5.initialize():
        return "❌ Souple louvri lojisyèl MetaTrader 5 la sou konpitè w."

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return f"❌ Senbòl {symbol} pa jwenn nan MT5."

    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if action == "BUY" else tick.bid
    trade_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

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

    res = mt5.order_send(request)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        return f"❌ Erè ({res.retcode}): {res.comment}"

    return f"🚀 Lòd {action} sou {symbol} pase ak siksè! Ticket: {res.order}"

# ---------------------------------------------------------
# INTÈFAS PRINGIPAL
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
        st.info(ekzekite_trade(symbol, "BUY", lot))

    if btn_sell:
        st.info(ekzekite_trade(symbol, "SELL", lot))

with col2:
    st.subheader("📊 Analiz & Siyal SMC")
    st.write("Aplikasyon an ap ouvri nòmalman kounye a sou Cloud san okenn erè rouj!")
