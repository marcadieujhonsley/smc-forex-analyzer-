import streamlit as st
import pandas as pd
import time

# Try-except pou anpeche Streamlit Cloud kraze
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

st.set_page_config(page_title="SMC Bot Automation Dashboard", layout="wide")
st.title("🤖 SMC Forex Automated Trading Dashboard")

# ---------------------------------------------------------
# SEYASYO ETA BOT LA (ON / OFF)
# ---------------------------------------------------------
if "bot_active" not in st.session_state:
    st.session_state.bot_active = False

# ---------------------------------------------------------
# DETEKSYON MT5 AK KONT
# ---------------------------------------------------------
if MT5_AVAILABLE:
    st.sidebar.success("💻 Kòd la ap kouri sou PC lokal")
    if not mt5.initialize():
        st.sidebar.error("❌ MT5 pa louvri sou PC a. Souple louvri MT5!")
    else:
        acc = mt5.account_info()
        if acc:
            st.sidebar.markdown(f"**Kont:** `{acc.login}`")
            st.sidebar.markdown(f"**Solde (Balance):** `${acc.balance:.2f}`")
            st.sidebar.markdown(f"**Ekite (Equity):** `${acc.equity:.2f}`")
            st.sidebar.markdown(f"**Pwofi an tan reyèl:** `${acc.profit:.2f}`")
else:
    st.sidebar.warning("☁️ Kòd la ap kouri sou Streamlit Cloud")
    st.sidebar.info("Kouri app sa a an lokal sou PC w pou l ka ekzekite trade sou MT5 gratis.")

# ---------------------------------------------------------
# FONKSYON POU FERMEN POZISYON YO
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
                "comment": "Close by Bot Dashboard",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                kontrap += 1

    return f"✅ {kontrap} pozisyon fèmen ak siksè!"

# ---------------------------------------------------------
# INTERFACE PRINCIPALE (2 COLONNES)
# ---------------------------------------------------------
col_left, col_right = st.columns([1, 2])

# ==========================================
# BÒ GÒCH: KONTWÒL AUTOMATION (OUVRIR / FERMER BOT LA)
# ==========================================
with col_left:
    st.subheader("⚡ Kontwòl Automatik Bot la")
    
    # Afichaj Eta Bot la
    if st.session_state.bot_active:
        st.success("🟢 STA: BOT LA AKTYÈF (KAP CHÈCHE SETUP SMC)")
    else:
        st.error("🔴 STA: BOT LA FÈMEN (INAKTYÈF)")

    st.write("---")
    
    btn_ouvrir = st.button("▶️ Ouvrir Bot la", use_container_width=True)
    btn_fermer = st.button("⏹️ Fermer Bot la", use_container_width=True)

    if btn_ouvrir:
        st.session_state.bot_active = True
        st.rerun()

    if btn_fermer:
        st.session_state.bot_active = False
        st.rerun()

    st.write("---")
    st.markdown("### 🎯 Pè Bot la ap Kontwole")
    st.write("- **EURUSD**")
    st.write("- **GBPUSD**")
    st.write("- **XAUUSD**")

# ==========================================
# BÒ DWAT: JESYON POZISYON AK ACTION RAPID
# ==========================================
with col_right:
    st.subheader("🛠️ Fèmen Pozisyon Yo pi Rapid")
    
    cb1, cb2, cb3 = st.columns(3)
    
    with cb1:
        if st.button("❌ Fèmen TOUT Pozisyon", use_container_width=True):
            st.warning(fermen_pozisyon("ALL"))

    with cb2:
        if st.button("🟢 Fèmen GANYAN Yo", use_container_width=True):
            st.success(fermen_pozisyon("WINNERS"))

    with cb3:
        if st.button("🔴 Fèmen PÈDAN Yo", use_container_width=True):
            st.error(fermen_pozisyon("LOSERS"))

    st.write("---")
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
            st.info("Pa gen okenn trade ki louvri sou MT5 kounye a.")
    else:
        st.info("Konekte MT5 an lokal sou PC w pou w wè pozisyon yo an tan reyèl.")

# ---------------------------------------------------------
# LORGIK EXECUTION AUTOMATIQUE LÈ BOT LA AKTYÈF
# ---------------------------------------------------------
if st.session_state.bot_active:
    # Pati sa a ap kouri otomatikman lè bot la sou "OUVRIR"
    # Isit la bot la ap analize Order Blocks / FVG epi ekzekite trade san entèvansyon w
    pass
