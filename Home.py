import streamlit as st
import pandas as pd
from data_loader import load_main_data, load_ev_data, load_action_items, generate_weekly_insights
from utils import fmt_idr, fmt_pct, fmt_vol, delta_badge

st.set_page_config(
    page_title="Blitz Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🚀 Blitz Operations Dashboard")
st.caption("Weekly P&L and operations tracker. Upload your latest Excel file to refresh all views.")

st.divider()

# ── File uploader ─────────────────────────────────────────────────────────────
with st.container():
    col_upload, col_status = st.columns([2, 1])
    with col_upload:
        uploaded = st.file_uploader(
            "**Upload data file** (W38 Data Collection .xlsx)",
            type=['xlsx'],
            help="Upload the master Excel file. All pages will update automatically.",
            label_visibility="visible"
        )

    if uploaded:
        file_bytes = uploaded.getvalue()
        with st.spinner("Loading data..."):
            df = load_main_data(file_bytes)
            ev_df = load_ev_data(file_bytes)
            ai_df = load_action_items(file_bytes)

        st.session_state['data']         = df
        st.session_state['ev_data']      = ev_df
        st.session_state['action_items'] = ai_df
        st.session_state['file_bytes']   = file_bytes

        with col_status:
            st.success(f"✅ Loaded {len(df):,} rows")
            st.caption(
                f"Years: {sorted(df['Year'].dropna().unique().tolist())} · "
                f"Clients: {df['Client Name'].nunique()} · "
                f"Locations: {df['Client Location'].nunique()}"
            )

st.divider()

# ── Weekly Insights ───────────────────────────────────────────────────────────
if 'data' in st.session_state and st.session_state['data'] is not None:
    df = st.session_state['data']
    insights = generate_weekly_insights(df)

    if insights:
        yr   = insights['year']
        wk   = insights['week']
        dr   = insights['date_range']
        st.subheader(f"📋 Weekly Insights — Week {wk} of {yr}  ·  {dr}")

        # ── Top KPI row ───────────────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        for col, metric, label, formatter in [
            (k1, 'Total Revenue', '💰 Revenue',      fmt_idr),
            (k2, 'Total Cost',    '💸 Total Cost',   fmt_idr),
            (k3, 'GP',            '📈 Gross Profit', fmt_idr),
            (k4, 'Delivery Volume','📦 Volume',       fmt_vol),
        ]:
            d = insights[metric]
            pct = d['pct_change']
            delta_str = f"{pct:+.1f}% WoW" if pct is not None else None
            delta_c = "normal" if (pct or 0) >= 0 else "inverse"
            if metric == 'Total Cost':
                delta_c = "inverse" if (pct or 0) >= 0 else "normal"
            col.metric(label, formatter(d['current']), delta_str, delta_color=delta_c)

        # ── Two-column insight cards ──────────────────────────────────────────
        left, right = st.columns(2)

        with left:
            st.markdown("#### 🏆 Top 5 Clients by GP this week")
            top = insights['top_clients'].copy()
            top['GP'] = top['GP'].apply(fmt_idr)
            st.dataframe(top.rename(columns={'GP': 'Gross Profit'}),
                         use_container_width=True, hide_index=True)

        with right:
            neg = insights['negative_gp']
            if not neg.empty:
                st.markdown("#### 🔴 Clients with Negative GP")
                neg_disp = neg.copy()
                neg_disp['GP'] = neg_disp['GP'].apply(fmt_idr)
                st.dataframe(neg_disp.rename(columns={'GP': 'Gross Profit'}),
                             use_container_width=True, hide_index=True)
            else:
                st.markdown("#### ✅ No clients with negative GP this week")
                st.success("All clients are profitable this week.")

        # ── Movers ────────────────────────────────────────────────────────────
        m_left, m_right = st.columns(2)
        with m_left:
            imp = insights['biggest_improvers']
            if not imp.empty:
                st.markdown("#### ⬆️ Biggest Improvers (GP % WoW)")
                for _, r in imp.iterrows():
                    st.markdown(
                        f"**{r['Client Name']}** — GP {fmt_idr(r['GP'])}  "
                        f"{delta_badge(r['GP_pct'])}"
                    )

        with m_right:
            dec = insights['biggest_decliners']
            if not dec.empty:
                st.markdown("#### ⬇️ Biggest Decliners (GP % WoW)")
                for _, r in dec.iterrows():
                    st.markdown(
                        f"**{r['Client Name']}** — GP {fmt_idr(r['GP'])}  "
                        f"{delta_badge(r['GP_pct'])}"
                    )
    else:
        st.info("Insights will appear here once there are at least two weeks of data loaded.")

else:
    # ── Placeholder when no file is loaded ───────────────────────────────────
    st.markdown("""
    ### Getting started
    1. Upload the **W38 Data Collection .xlsx** file using the uploader above.
    2. Navigate between pages using the **sidebar** on the left.
    3. Use the **filters** on each page to slice by year, team, month, and more.

    #### Pages available
    | Page | What it shows |
    |------|--------------|
    | 📊 Overview | Revenue, cost, GP trend by week/month |
    | 👥 By Client | Per-client P&L, drilldown, unit economics |
    | 🗺️ By Location | Location ranking + week-over-week variance |
    | 🏙️ By Team | Jakarta vs. Surabaya comparison |
    | ⚡ EV Rental | EV business line — units, revenue, OEM/IoT costs |
    | 📋 Action Items | Client management tracker |
    | 📈 Finance Check | Year-over-year comparison + anomaly flags |
    """)
