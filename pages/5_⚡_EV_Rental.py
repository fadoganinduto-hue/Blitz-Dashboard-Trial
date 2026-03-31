import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import require_data, fmt_idr, fmt_pct, fmt_vol, C_REVENUE, C_COST, C_GP, MONTH_ORDER

st.set_page_config(page_title="EV Rental | Blitz", page_icon="⚡", layout="wide")
st.title("⚡ EV Rental")
st.caption("Electric vehicle rental business line — units, revenue, and cost breakdown.")

# Load EV-specific data
if 'ev_data' not in st.session_state or st.session_state['ev_data'] is None:
    # Fallback: filter main data for EV rental clients
    df_main = require_data()
    ev_clients = df_main[df_main['Client Name'].str.contains('EV Rental', na=False)].copy()
    use_test_tab = False
else:
    ev_df = st.session_state['ev_data'].copy()
    use_test_tab = True

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")

if use_test_tab:
    df = ev_df.copy()

    with st.sidebar:
        years = sorted(df['Year'].dropna().unique().tolist()) if 'Year' in df.columns else []
        if years:
            sel_years = st.multiselect("Year", years, default=[max(years)], key="ev_year")
            df = df[df['Year'].isin(sel_years)] if sel_years else df

        clients = sorted(df['Client Name'].dropna().unique().tolist()) if 'Client Name' in df.columns else []
        sel_clients = st.multiselect("EV Client", clients, default=clients, key="ev_client")
        if sel_clients:
            df = df[df['Client Name'].isin(sel_clients)]

    if df.empty:
        st.warning("No data matches the current filters.")
        st.stop()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_units = df['Unit'].sum() if 'Unit' in df.columns else 0
    total_rev   = df['Total Revenue'].sum() if 'Total Revenue' in df.columns else 0
    total_cost  = df['Total Cost'].sum()    if 'Total Cost'    in df.columns else 0
    total_gp    = df['GP'].sum()            if 'GP'            in df.columns else 0
    gp_margin   = total_gp / total_rev * 100 if total_rev else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Units",  fmt_vol(total_units))
    k2.metric("Revenue",      fmt_idr(total_rev))
    k3.metric("Total Cost",   fmt_idr(total_cost))
    k4.metric("Gross Profit", fmt_idr(total_gp))
    k5.metric("GP Margin",    fmt_pct(gp_margin))

    st.divider()

    # ── Revenue vs cost by client ─────────────────────────────────────────────
    st.subheader("Revenue & GP by EV Client")

    if 'Client Name' in df.columns:
        client_agg = (
            df.groupby('Client Name', observed=True)
            .agg(Units=('Unit', 'sum') if 'Unit' in df.columns else ('Total Revenue', 'count'),
                 Revenue=('Total Revenue', 'sum'),
                 Cost=('Total Cost', 'sum'),
                 GP=('GP', 'sum'))
            .reset_index()
            .sort_values('GP', ascending=False)
        )
        client_agg['GP Margin %'] = client_agg.apply(
            lambda r: r['GP'] / r['Revenue'] * 100 if r['Revenue'] else 0, axis=1
        )

        fig_cl = px.bar(client_agg, x='Client Name', y=['Revenue', 'Cost', 'GP'],
                        barmode='group', color_discrete_map={'Revenue': C_REVENUE, 'Cost': C_COST, 'GP': C_GP},
                        template='plotly_white', height=400,
                        title="Revenue, Cost & GP by EV Rental Client")
        fig_cl.update_layout(hovermode='x unified', legend=dict(orientation='h', y=1.05))
        st.plotly_chart(fig_cl, use_container_width=True)

    st.divider()

    # ── Cost breakdown: OEM / Insurance / IoT ────────────────────────────────
    st.subheader("Cost Component Breakdown")

    cost_cols = [c for c in ['OEM Cost', 'Insurance Cost', 'IOT Cost'] if c in df.columns]
    if cost_cols and 'Client Name' in df.columns:
        cost_agg = df.groupby('Client Name', observed=True)[cost_cols].sum().reset_index()
        cost_long = cost_agg.melt(id_vars='Client Name', var_name='Component', value_name='Amount')

        fig_comp = px.bar(cost_long, x='Client Name', y='Amount', color='Component',
                          barmode='stack', template='plotly_white', height=380,
                          title="OEM / Insurance / IoT Cost per Client",
                          labels={'Amount': 'IDR'})
        fig_comp.update_layout(hovermode='x unified', legend=dict(orientation='h', y=1.05))
        st.plotly_chart(fig_comp, use_container_width=True)

    st.divider()

    # ── Weekly units trend ────────────────────────────────────────────────────
    st.subheader("Units Rented — Weekly Trend")

    if 'Week (by Year)' in df.columns and 'Unit' in df.columns:
        weekly_ev = (
            df.groupby(['Year', 'Week (by Year)', 'Client Name'], observed=True)['Unit']
            .sum().reset_index()
            .sort_values(['Year', 'Week (by Year)'])
        )
        weekly_ev['Label'] = (weekly_ev['Year'].astype(str) + ' W' +
                              weekly_ev['Week (by Year)'].astype(str))

        fig_units = px.bar(weekly_ev, x='Label', y='Unit', color='Client Name',
                           barmode='stack', template='plotly_white', height=380,
                           title="Weekly EV Units Rented",
                           labels={'Unit': 'Units'})
        fig_units.update_layout(hovermode='x unified', xaxis_tickangle=-45,
                                legend=dict(orientation='h', y=1.05))
        st.plotly_chart(fig_units, use_container_width=True)

    # ── Summary table ─────────────────────────────────────────────────────────
    st.subheader("Summary Table")
    if 'Client Name' in df.columns:
        disp = client_agg.copy()
        disp['Revenue']     = disp['Revenue'].apply(fmt_idr)
        disp['Cost']        = disp['Cost'].apply(fmt_idr)
        disp['GP']          = disp['GP'].apply(fmt_idr)
        disp['GP Margin %'] = disp['GP Margin %'].apply(fmt_pct)
        st.dataframe(disp, use_container_width=True, hide_index=True)

else:
    # ── Fallback: EV clients from main data ────────────────────────────────────
    st.info("Using EV Rental data from main Raw Data Source. For full EV metrics (OEM, Insurance, IoT), ensure the 'Test EV Rental' sheet is present in your file.")

    df_main = require_data()
    ev_df_main = df_main[df_main['Client Name'].str.contains('EV Rental', na=False)].copy()

    if ev_df_main.empty:
        st.warning("No EV Rental clients found in the data.")
        st.stop()

    ev_agg = (
        ev_df_main.groupby('Client Name', observed=True)
        .agg(Revenue=('Total Revenue', 'sum'), Cost=('Total Cost', 'sum'), GP=('GP', 'sum'))
        .reset_index().sort_values('GP', ascending=False)
    )
    ev_agg['GP Margin %'] = ev_agg.apply(
        lambda r: r['GP'] / r['Revenue'] * 100 if r['Revenue'] else 0, axis=1
    )

    disp = ev_agg.copy()
    disp['Revenue']     = disp['Revenue'].apply(fmt_idr)
    disp['Cost']        = disp['Cost'].apply(fmt_idr)
    disp['GP']          = disp['GP'].apply(fmt_idr)
    disp['GP Margin %'] = disp['GP Margin %'].apply(fmt_pct)
    st.dataframe(disp, use_container_width=True, hide_index=True)
