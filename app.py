import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Guru Stock Screener",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Guru Stock Screener Dashboard")
st.markdown("**High Piotroski • Magic Formula • Darvas • Zulu • Driehaus • Altman Z**")

# ---------- Load Data ----------
HISTORY_FILE = "holdings_history.json"
RESULTS_FILE = "scan_results.json"

def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

history = load_json(HISTORY_FILE)
results = load_json(RESULTS_FILE)

# ---------- Sidebar ----------
st.sidebar.header("Controls")
st.sidebar.info(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

show_history = st.sidebar.checkbox("Show Shareholding History", value=False)

# ---------- Main Content ----------
if results:
    st.success(f"✅ Last scan found **{results.get('total_stocks', 0)}** unique stocks")
    
    stocks = results.get("stocks", [])
    
    if stocks:
        df = pd.DataFrame(stocks)
        
        st.subheader("📊 Latest Scan Results")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download as CSV",
            data=csv,
            file_name=f"guru_scan_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
else:
    st.warning("No scan results found yet. Run the GitHub Actions workflow first.")

# ---------- History Section ----------
if show_history and history:
    st.subheader("📁 Shareholding History")
    st.json(history)

# ---------- Footer ----------
st.markdown("---")
st.caption("Data from Screener.in | Automated via GitHub Actions + Streamlit")