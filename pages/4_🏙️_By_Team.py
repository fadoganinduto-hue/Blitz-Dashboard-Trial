import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (require_data, sidebar_filters, fmt_idr, fmt_pct, fmt_vol,
                   C_REVENUE, C_COST, C_GP, C_VOLUME)
from data_loader import COST_COMPONENTS

st.set_page_config(page_title="By Team | Blitz", page_icon="🏙️", layout="wide")
st.title("🏙️ By Team")
st.caption("Jakarta vs. Surabaya — side-by-side P&L, cost structure, and trend comparison.")

df_full = require_data()
df = sidebar_filters(df_full, page_key="team")

if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

teams = sorted(df['Blitz Team'].dropna().unique().tolist())
if not teams:
    st.warning("No team data available.")
    st.stop()

# ── Side-by-side KPIs ─────────────────────────────────────────────────────────
st.subheader("Team Comparison")

team_agg = (
    df.groupby('Blitz Team', observed=True)
    .agg(Volume=('Delivery Volume', 'sum'),
         Revenue=('Total Revenue', 'sum'),
         Cost=('Total Cost', 'sum'),
         GP=('GP', 'sum'))
    .reset_index()
)
team_agg['GP Margin %'] = team_agg.apply(
    lambda r: r['GP'] / r['Revenue'] * 100 if r['Revenue'] else 0, axis=1
)

cols = st.columns(len(teams))
for col, (_, row) in zip(cols, team_agg.iterrows()):
    with col:
        st.markdown(f"### 🏙️ {row['Blitz Team']}")
        st.metric("Revenue",   fmt_idr(row['Revenue']))
        st.metric("Cost",      fmt_idr(row['Cost']))
        st.metric("GP",        fmt_idr(row['GP']))
        st.metric("GP Margin", fmt_pct(row['GP Margin %']))
        st.metric("Volume",    fmt_vol(row['Volume']))

st.divider()

# ── Grouped bar: Revenue / Cost / GP per team per period ─────────────────────
st.subheader("Monthly Comparison")

monthly_team = (
    df.groupby(['Blitz Team', 'Year', 'Month'], observed=True)
    .agg(Revenue=('Total Revenue', 'sum'),
         Cost=('Total Cost', 'sum'),
         GP=('GP', 'sum'))
    .reset_index()
)
monthly_team['Label'] = monthly_team['Year'].astype(str) + ' ' + monthly_team['Month'].astype(str)

metric_choice = st.radio("Show metric", ['GP', 'Revenue', 'Cost'], horizontal=True)

fig_m = px.bar(
    monthly_team, x='Label', y=metric_choice, color='Blitz Team',
    barmode='group', template='plotly_white', height=400,
    title=f"{metric_choice} by Month & Team",
    color_discrete_map={'Jakarta': C_REVENUE, 'Surabaya': C_GP}
)
fig_m.update_layout(hovermode='x unified', xaxis_tickangle=-45,
                    legend=dict(orientation='h', y=1.05))
st.plotly_chart(fig_m, use_container_width=True)

st.divider()

# ── Cost structure per team ───────────────────────────────────────────────────
st.subheader("Cost Structure by Team")

cost_cols = [c for c in COST_COMPONENTS.keys() if c in df.columns]
cost_by_team = df.groupby('Blitz Team', observed=True)[cost_cols].sum().reset_index()

cost_long = cost_by_team.melt(id_vars='Blitz Team', var_name='Cost Component', value_name='Amount')
cost_long['Label'] = cost_long['Cost Component'].map(COST_COMPONENTS).fillna(cost_long['Cost Component'])
cost_long = cost_long[cost_long['Amount'] > 0]

fig_cost = px.bar(
    cost_long, x='Blitz Team', y='Amount', color='Label',
    barmode='stack', template='plotly_white', height=420,
    title="Cost Breakdown by Team",
    labels={'Amount': 'IDR', 'Label': 'Cost Component'}
)
fig_cost.update_layout(hovermode='x unified', legend=dict(orientation='h', y=1.05))
st.plotly_chart(fig_cost, use_container_width=True)

# Rider cost as % of revenue — a key efficiency metric
st.markdown("**Rider Cost as % of Revenue (by Team)**")
rider_pct = (
    df.groupby('Blitz Team', observed=True)
    .apply(lambda g: g['Rider Cost'].sum() / g['Total Revenue'].sum() * 100 if g['Total Revenue'].sum() else 0)
    .reset_index().rename(columns={0: 'Rider %'})
)
for _, row in rider_pct.iterrows():
    st.metric(row['Blitz Team'], fmt_pct(row['Rider %']),
              help="Rider cost as percentage of total revenue — lower is more efficient.")

st.divider()

# ── Weekly trend per team ─────────────────────────────────────────────────────
st.subheader("Weekly GP Trend by Team")

weekly_team = (
    df.groupby(['Blitz Team', 'Year', 'Week (by Year)'], observed=True)
    .agg(GP=('GP', 'sum'), Revenue=('Total Revenue', 'sum'))
    .reset_index().sort_values(['Year', 'Week (by Year)'])
)
weekly_team['Label'] = (weekly_team['Year'].astype(str) + ' W' +
                        weekly_team['Week (by Year)'].astype(str))

fig_gp = px.line(
    weekly_team, x='Label', y='GP', color='Blitz Team',
    markers=True, template='plotly_white', height=400,
    title="Weekly Gross Profit per Team",
    color_discrete_map={'Jakarta': C_REVENUE, 'Surabaya': C_GP}
)
fig_gp.update_layout(hovermode='x unified', xaxis_tickangle=-45,
                     legend=dict(orientation='h', y=1.05), yaxis_title='GP (IDR)')
fig_gp.add_hline(y=0, line_dash='dash', line_color='red', opacity=0.5)
st.plotly_chart(fig_gp, use_container_width=True)

st.divider()

# ── SLA mix per team ──────────────────────────────────────────────────────────
st.subheader("SLA Type Mix by Team")

sla_team = (
    df.dropna(subset=['SLA Type'])
    .groupby(['Blitz Team', 'SLA Type'], observed=True)['Delivery Volume']
    .sum().reset_index()
)
fig_sla = px.bar(
    sla_team, x='Blitz Team', y='Delivery Volume', color='SLA Type',
    barmode='stack', template='plotly_white', height=380,
    title="Delivery Volume by SLA Type",
    labels={'Delivery Volume': 'Deliveries'}
)
fig_sla.update_layout(hovermode='x unified', legend=dict(orientation='h', y=1.05))
st.plotly_chart(fig_sla, use_container_width=True)
