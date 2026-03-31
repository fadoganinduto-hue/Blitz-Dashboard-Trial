import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (require_data, sidebar_filters, fmt_idr, fmt_pct, fmt_vol,
                   C_REVENUE, C_COST, C_GP, C_VOLUME, MONTH_ORDER)
from data_loader import COST_COMPONENTS

st.set_page_config(page_title="By Client | Blitz", page_icon="👥", layout="wide")
st.title("👥 By Client")
st.caption("Per-client P&L, unit economics, and weekly drilldown.")

df_full = require_data()
df = sidebar_filters(df_full, page_key="client")

if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Client summary table ──────────────────────────────────────────────────────
st.subheader("Client Rankings")

client_agg = (
    df.groupby('Client Name', observed=True)
    .agg(
        Volume=('Delivery Volume', 'sum'),
        Revenue=('Total Revenue', 'sum'),
        Cost=('Total Cost', 'sum'),
        GP=('GP', 'sum'),
    )
    .reset_index()
)
client_agg['GP Margin %'] = client_agg.apply(
    lambda r: r['GP'] / r['Revenue'] * 100 if r['Revenue'] else 0, axis=1
)
client_agg['SRPO'] = df[df['Delivery Volume'] > 0].groupby('Client Name')['SRPO'].mean().reindex(client_agg['Client Name']).values
client_agg['RCPO'] = df[df['Delivery Volume'] > 0].groupby('Client Name')['RCPO'].mean().reindex(client_agg['Client Name']).values
client_agg['TCPO'] = df[df['Delivery Volume'] > 0].groupby('Client Name')['TCPO'].mean().reindex(client_agg['Client Name']).values

sort_col = st.selectbox("Sort by", ['GP', 'Revenue', 'Volume', 'GP Margin %'], index=0)
client_agg = client_agg.sort_values(sort_col, ascending=False).reset_index(drop=True)

disp = client_agg.copy()
disp['Revenue']    = disp['Revenue'].apply(fmt_idr)
disp['Cost']       = disp['Cost'].apply(fmt_idr)
disp['GP']         = disp['GP'].apply(fmt_idr)
disp['GP Margin %']= disp['GP Margin %'].apply(fmt_pct)
disp['Volume']     = disp['Volume'].apply(fmt_vol)
disp['SRPO']       = disp['SRPO'].apply(lambda v: fmt_idr(v, 0) if pd.notna(v) else '-')
disp['RCPO']       = disp['RCPO'].apply(lambda v: fmt_idr(v, 0) if pd.notna(v) else '-')
disp['TCPO']       = disp['TCPO'].apply(lambda v: fmt_idr(v, 0) if pd.notna(v) else '-')

st.dataframe(
    disp[['Client Name', 'Volume', 'Revenue', 'Cost', 'GP', 'GP Margin %', 'SRPO', 'RCPO', 'TCPO']],
    use_container_width=True, hide_index=True
)

st.divider()

# ── Client drilldown ──────────────────────────────────────────────────────────
st.subheader("Client Drilldown")

all_clients = sorted(df['Client Name'].dropna().unique().tolist())
selected_client = st.selectbox("Select a client", all_clients)

cdf = df[df['Client Name'] == selected_client].copy()

if cdf.empty:
    st.info("No data for this client with current filters.")
    st.stop()

# KPIs
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue",    fmt_idr(cdf['Total Revenue'].sum()))
c2.metric("Cost",       fmt_idr(cdf['Total Cost'].sum()))
c3.metric("GP",         fmt_idr(cdf['GP'].sum()))
gpm = cdf['GP'].sum() / cdf['Total Revenue'].sum() * 100 if cdf['Total Revenue'].sum() else 0
c4.metric("GP Margin",  fmt_pct(gpm))
c5.metric("Volume",     fmt_vol(cdf['Delivery Volume'].sum()))

# Project breakdown
proj_agg = (
    cdf.groupby('Project', observed=True)
    .agg(Revenue=('Total Revenue', 'sum'), Cost=('Total Cost', 'sum'), GP=('GP', 'sum'),
         Volume=('Delivery Volume', 'sum'))
    .reset_index()
    .sort_values('GP', ascending=False)
)

tab1, tab2, tab3 = st.tabs(["Weekly Trend", "Project Breakdown", "Cost Structure"])

with tab1:
    weekly_c = (
        cdf.groupby(['Year', 'Week (by Year)'], observed=True)
        .agg(Revenue=('Total Revenue', 'sum'), Cost=('Total Cost', 'sum'), GP=('GP', 'sum'))
        .reset_index().sort_values(['Year', 'Week (by Year)'])
    )
    weekly_c['Label'] = weekly_c['Year'].astype(str) + ' W' + weekly_c['Week (by Year)'].astype(str)

    fig = go.Figure()
    fig.add_bar(x=weekly_c['Label'], y=weekly_c['Revenue'], name='Revenue', marker_color=C_REVENUE, opacity=0.8)
    fig.add_bar(x=weekly_c['Label'], y=weekly_c['Cost'],    name='Cost',    marker_color=C_COST,    opacity=0.8)
    fig.add_scatter(x=weekly_c['Label'], y=weekly_c['GP'], mode='lines+markers', name='GP',
                    line=dict(color=C_GP, width=2))
    fig.update_layout(barmode='group', hovermode='x unified', template='plotly_white',
                      height=400, legend=dict(orientation='h', y=1.05), yaxis_title='IDR',
                      title=f"{selected_client} — Weekly P&L")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    proj_disp = proj_agg.copy()
    proj_disp['Revenue'] = proj_disp['Revenue'].apply(fmt_idr)
    proj_disp['Cost']    = proj_disp['Cost'].apply(fmt_idr)
    proj_disp['GP']      = proj_disp['GP'].apply(fmt_idr)
    proj_disp['Volume']  = proj_disp['Volume'].apply(fmt_vol)
    st.dataframe(proj_disp, use_container_width=True, hide_index=True)

    if len(proj_agg) > 1:
        fig_p = px.bar(proj_agg, x='Project', y='GP', color='GP',
                       color_continuous_scale=['red', 'yellow', 'green'],
                       template='plotly_white', height=360,
                       title=f"{selected_client} — GP by Project")
        st.plotly_chart(fig_p, use_container_width=True)

with tab3:
    cost_data = {}
    for col, label in COST_COMPONENTS.items():
        if col in cdf.columns:
            val = cdf[col].sum()
            if val > 0:
                cost_data[label] = val

    if cost_data:
        cost_df = pd.DataFrame({'Component': list(cost_data.keys()), 'Amount': list(cost_data.values())})
        cost_df['% of Total Cost'] = cost_df['Amount'] / cost_df['Amount'].sum() * 100
        cost_df['Amount_fmt'] = cost_df['Amount'].apply(fmt_idr)

        fig_cost = px.pie(cost_df, values='Amount', names='Component',
                          hole=0.35, template='plotly_white', height=380,
                          title=f"{selected_client} — Cost Structure")
        st.plotly_chart(fig_cost, use_container_width=True)

        cost_df['% of Total Cost'] = cost_df['% of Total Cost'].apply(fmt_pct)
        st.dataframe(cost_df[['Component', 'Amount_fmt', '% of Total Cost']].rename(
            columns={'Amount_fmt': 'Amount'}), use_container_width=True, hide_index=True)
