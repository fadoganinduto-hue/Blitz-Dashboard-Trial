import streamlit as st
import pandas as pd
from utils import require_data, fmt_idr

st.set_page_config(page_title="Action Items | Blitz", page_icon="📋", layout="wide")
st.title("📋 Action Items")
st.caption("Client management tracker — status, issues, and action items.")

require_data()  # Ensure main data is loaded

if 'action_items' not in st.session_state or st.session_state['action_items'] is None:
    st.warning("Action Items sheet could not be loaded from the uploaded file.")
    st.stop()

ai_df = st.session_state['action_items'].copy()

if ai_df.empty:
    st.info("No action items data found.")
    st.stop()

# ── Clean up the dataframe ────────────────────────────────────────────────────
# The Action Items sheet has merged cells; forward-fill the client column
first_col = ai_df.columns[0]
ai_df[first_col] = ai_df[first_col].ffill()

# Drop fully empty rows
ai_df = ai_df.dropna(how='all').reset_index(drop=True)

# Rename columns sensibly
col_names = ai_df.columns.tolist()
rename_map = {}
for i, col in enumerate(col_names):
    c = str(col).strip()
    if i == 0:
        rename_map[col] = 'Client'
    elif 'status' in c.lower() or i == 1:
        rename_map[col] = 'Status'
    elif 'problem' in c.lower() or i == 2:
        rename_map[col] = 'Problems'
    elif 'action' in c.lower() or i == 3:
        rename_map[col] = 'Action Items'
    elif 'add' in c.lower() or i == 4:
        rename_map[col] = 'Notes'
    else:
        rename_map[col] = col
ai_df = ai_df.rename(columns=rename_map)

# ── Filter bar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")
    clients = sorted(ai_df['Client'].dropna().unique().tolist())
    sel_clients = st.multiselect("Client", clients, default=clients)

if sel_clients:
    ai_df = ai_df[ai_df['Client'].isin(sel_clients)]

# ── Status board ─────────────────────────────────────────────────────────────
st.subheader("Client Status Overview")

status_col = 'Status' if 'Status' in ai_df.columns else None

if status_col:
    statuses = ai_df[status_col].dropna().unique().tolist()
    stat_counts = ai_df.groupby('Client')[status_col].first().value_counts().reset_index()
    stat_counts.columns = ['Status', 'Count']
    st.dataframe(stat_counts, use_container_width=False, hide_index=True)

st.divider()

# ── Client-by-client view ─────────────────────────────────────────────────────
st.subheader("Client Detail")

grouped = ai_df.groupby('Client', sort=False)

for client, group in grouped:
    with st.expander(f"**{client}**", expanded=False):
        display_cols = [c for c in ['Status', 'Problems', 'Action Items', 'Notes']
                        if c in group.columns]
        g_disp = group[display_cols].dropna(how='all').reset_index(drop=True)
        if not g_disp.empty:
            st.dataframe(g_disp, use_container_width=True, hide_index=True)
        else:
            st.caption("No detailed action items recorded.")

st.divider()

# ── Raw table ─────────────────────────────────────────────────────────────────
with st.expander("View raw Action Items table"):
    st.dataframe(ai_df, use_container_width=True, hide_index=True)
