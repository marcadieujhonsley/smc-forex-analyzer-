import streamlit as st
import pandas as pd

# Try-except pou anpeche Streamlit Cloud kraze (crash)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

st.set_page_config(page_title="SMC Forex Advanced Dashboard", layout="wide")
st.title("🤖 SMC Forex Advanced Trading Dashboard")

# ---------------------------------------------------------
# DETEKSYON ANVIWÒNMAN AK ENFÒMASYON KONT
# ---------------------------------------------------------
if MT5_AVAILABLE:
    st.sidebar.success("💻 Kòd la ap kouri sou PC lokal")
    if not mt5.initialize():
        st.sidebar.error("❌ MT5 pa louvri sou PC a. Souple louvri lojisyèl MT5 la!")
    else:
        acc = mt5.account_info()
        if acc:
            st.sidebar.markdown(f"**Kont:** `{acc.login}`")
            st.sidebar.markdown(f"**Solde (Balance):** `${acc.balance:.2f}`")
            st.sidebar.markdown(f"**Ekite (Equity):** `${acc.equity:.2f}`")
            st.sidebar.markdown(f"**Pwofi an tan reyèl:** `${acc.profit:.2f}`")
else:
    st.sidebar.warning("☁️ Kòd la ap kouri sou Streamlit Cloud")
    st.sidebar.info("Sèvi ak 'streamlit run app.py' sou PC w pou w pase trade sou MT5 gratis.")

# ---------------------------------------------------------
# FONKSYON POU EKZEKITE TRADE (BUY / SELL)
# ---------------------------------------------------------
def ekzekite_trade(symbol, action, lot, sl_pips=50, tp_pips=100):
    if not MT5_AVAILABLE or not mt5.initialize():
        return "❌ MT5 pa konekte sou PC a."

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return f"❌ Senbòl {symbol} pa jwenn nan MT5."

    if not symbol_info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    point = symbol_info.point
    
    if action == "BUY":
        price = tick.ask
        trade_type = mt5.ORDER_TYPE_BUY
        sl = price - (sl_pips * point * 10)
        tp = price + (tp_pips * point * 10)
    else:
        price = tick.bid
        trade_type = mt5.ORDER_TYPE_SELL
        sl = price + (sl_pips * point * 10)
        tp = price - (tp_pips * point * 10)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": trade_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 100200,
        "comment": "SMC Bot Direct",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    res = mt5.order_send(request)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        return f"❌ Erè ({res.retcode}): {res.comment}"

    return f"🚀 Lòd {action} sou {symbol} pase ak siksè! Ticket: {res.order}"

# ---------------------------------------------------------
# FONKSYON POU FERMEN POZISYON YO (CLOSE ALL / PROFIT / LOSS)
# ---------------------------------------------------------
def fermen_pozisyon(option="ALL"):
    if not MT5_AVAILABLE or not mt5.initialize():
        return "❌ MT5 pa konekte sou PC a."

    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return "ℹ️ Pa gen okenn pozisyon ki louvri kounye a."

    kontrap = 0
    for pos in positions:
        femen = False
        if option == "ALL":
            femen = True
        elif option == "WINNERS" and pos.profit > 0:
            femen = True
        elif option == "LOSERS" and pos.profit < 0:
            femen = True

        if femen:
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 100200,
                "comment": "Close by Bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                kontrap += 1

    return f"✅ {kontrap} pozisyon fèmen ak siksè!"

# ---------------------------------------------------------
# SECTION 1: JESYON AK KONTWÒL POZISYON (PANIC BUTTONS)
# ---------------------------------------------------------
st.subheader("🛠️ Kontwòl Rapid Pozisyon Yo")
col_b1, col_b2, col_b3 = st.columns(3)

with col_b1:
    if st.button("❌ Fèmen TOUT Pozisyon Yo", use_container_width=True):
        st.warning(fermen_pozisyon("ALL"))

with col_b2:
    if st.button("🟢 Fèmen Pozisyon GANYAN Yo", use_container_width=True):
        st.success(fermen_pozisyon("WINNERS"))

with col_b3:
    if st.button("🔴 Fèmen Pozisyon PÈDAN Yo", use_container_width=True):
        st.error(fermen_pozisyon("LOSERS"))

st.write("---")

# ---------------------------------------------------------
# SECTION 2: EXEKISYON SOU 3 PÈ PWOFECHONÈL
# ---------------------------------------------------------
st.subheader("📈 Trade sou 3 Pè Mache Alysé")

pe1, pe2, pe3 = st.columns(3)

pere_lis = [
    {"name": "EURUSD", "col": pe1},
    {"name": "GBPUSD", "col": pe2},
    {"name": "XAUUSD", "col": pe3}
]

for item in pere_lis:
    p_name = item["name"]
    p_col = item["col"]
    
    with p_col:
        st.markdown(f"### 💱 {p_name}")
        lot_val = st.number_input(f"Lot {p_name}", value=0.01, step=0.01, format="%.2f", key=f"lot_{p_name}")
        sl_val = st.number_input(f"SL (Pips) {p_name}", value=30, step=5, key=f"sl_{p_name}")
        tp_val = st.number_input(f"TP (Pips) {p_name}", value=60, step=5, key=f"tp_{p_name}")
        
        btn_buy = st.button(f"🟢 BUY {p_name}", use_container_width=True, key=f"buy_{p_name}")
        btn_sell = st.button(f"🔴 SELL {p_name}", use_container_width=True, key=f"sell_{p_name}")
        
        if btn_buy:
            st.info(ekzekite_trade(p_name, "BUY", lot_val, sl_val, tp_val))
            
        if btn_sell:
            st.info(ekzekite_trade(p_name, "SELL", lot_val, sl_val, tp_val))

st.write("---")

# ---------------------------------------------------------
# SECTION 3: TAYBLLO POZISYON KIPWOBLÈM KIPWOBIYIN KOU N OUVRI
# ---------------------------------------------------------
st.subheader("📋 Pozisyon Ki Louvri An Tan Reyèl")

if MT5_AVAILABLE and mt5.initialize():
    pos_raw = mt5.positions_get()
    if pos_raw and len(pos_raw) > 0:
        data = []
        for p in pos_raw:
            tipo = "BUY" if p.type == 0 else "SELL"
            data.append({
                "Ticket": p.ticket,
                "Senbòl": p.symbol,
                "Tip": tipo,
                "Volim (Lot)": p.volume,
                "Pri Ouvèti": p.price_open,
                "SL": p.sl,
                "TP": p.tp,
                "Pwofi ($)": p.profit
            })
        df_pos = pd.DataFrame(data)
        st.dataframe(df_pos, use_container_width=True)
    else:
        st.info("Pa gen okenn trade ki louvri sou MT5 pou kounye a.")
else:
    st.info("Konekte MT5 an lokal sou PC w pou w ka wè tablo pozisyon yo an tan reyèl.")
