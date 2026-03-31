import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (require_data, sidebar_filters, fmt_idr, fmt_pct, fmt_vol,
                   C_REVENUE, C_COST, C_GP, C_VOLUME, MONTH_ORDER,
                   revenue_cost_gp_bar, trend_line)

st.set_page_config(page_title="Overview | Blitz", page_icon="📊", layout="wide")
st.title("📊 Overview")
st.caption("High-level P&L summary across all clients, teams, and locations.")

df_full = require_data()
df = sidebar_filters(df_full, page_key="overview")

if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Summary KPIs ──────────────────────────────────────────────────────────────
st.subheader("Key Metrics")
total_rev  = df['Total Revenue'].sum()
total_cost = df['Total Cost'].sum()
total_gp   = df['GP'].sum()
total_vol  = df['Delivery Volume'].sum()
gp_margin  = total_gp / total_rev * 100 if total_rev else 0
avg_srpo   = df[df['Delivery Volume'] > 0]['SRPO'].mean()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total Revenue",    fmt_idr(total_rev))
k2.metric("Total Cost",       fmt_idr(total_cost))
k3.metric("Gross Profit",     fmt_idr(total_gp))
k4.metric("GP Margin",        fmt_pct(gp_margin))
k5.metric("Delivery Volume",  fmt_vol(total_vol))
k6.metric("Avg Selling/Order",fmt_idr(avg_srpo))

st.divider()

# ── Weekly trend ──────────────────────────────────────────────────────────────
st.subheader("Weekly Trend")

weekly = (
    df.groupby(['Year', 'Week (by Year)'], observed=True)
    .agg(Revenue=('Total Revenue', 'sum'),
         Cost=('Total Cost', 'sum'),
         GP=('GP', 'sum'),
         Volume=('Delivery Volume', 'sum'))
    .reset_index()
    .sort_values(['Year', 'Week (by Year)'])
)
weekly['Label'] = weekly['Year'].astype(str) + ' W' + weekly['Week (by Year)'].astype(str)

tab1, tab2 = st.tabs(["Revenue & GP", "Volume"])

with tab1:
    fig = go.Figure()
    fig.add_bar(x=weekly['Label'], y=weekly['Revenue'], name='Revenue', marker_color=C_REVENUE, opacity=0.8)
    fig.add_bar(x=weekly['Label'], y=weekly['Cost'],    name='Cost',    marker_color=C_COST,    opacity=0.8)
    fig.add_scatter(x=weekly['Label'], y=weekly['GP'], mode='lines+markers', name='GP',
                    line=dict(color=C_GP, width=2), yaxis='y')
    fig.update_layout(barmode='group', hovermode='x unified', template='plotly_white',
                      height=400, legend=dict(orientation='h', y=1.05),
                      yaxis_title='IDR')
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig_vol = px.bar(weekly, x='Label', y='Volume', color_discrete_sequence=[C_VOLUME],
                     labels={'Volume': 'Deliveries', 'Label': 'Week'})
    fig_vol.update_layout(template='plotly_white', height=360, hovermode='x unified')
    st.plotly_chart(fig_vol, use_container_width=True)

st.divider()

# ── Monthly breakdown ─────────────────────────────────────────────────────────
st.subheader("Monthly Breakdown")

monthly = (
    df.groupby(['Year', 'Month'], observed=True)
    .agg(Revenue=('Total Revenue', 'sum'),
         Cost=('Total Cost', 'sum'),
         GP=('GP', 'sum'),
         Volume=('Delivery Volume', 'sum'))
    .reset_index()
)
monthly['GP Margin %'] = monthly.apply(
    lambda r: r['GP'] / r['Revenue'] * 100 if r['Revenue'] else 0, axis=1
)
monthly['Month'] = pd.Categorical(monthly['Month'], categories=MONTH_ORDER, ordered=True)
monthly = monthly.sort_values(['Year', 'Month'])

m_left, m_right = st.columns([3, 2])

with m_left:
    fig_m = px.bar(monthly, x='Month', y=['Revenue', 'Cost', 'GP'],
                   facet_col='Year', barmode='group',
                   color_discrete_map={'Revenue': C_REVENUE, 'Cost': C_COST, 'GP': C_GP},
                   height=380, template='plotly_white')
    fig_m.update_layout(hovermode='x unified', legend=dict(orientation='h', y=1.1))
    st.plotly_chart(fig_m, use_container_width=True)

with m_right:
    st.markdown("**Monthly Summary Table**")
    disp = monthly.copy()
    disp['Revenue'] = disp['Revenue'].apply(fmt_idr)
    disp['Cost']    = disp['Cost'].apply(fmt_idr)
    disp['GP']      = disp['GP'].apply(fmt_idr)
    disp['Margin']  = disp['GP Margin %'].apply(fmt_pct)
    disp['Volume']  = disp['Volume'].apply(fmt_vol)
    st.dataframe(
        disp[['Year', 'Month', 'Revenue', 'Cost', 'GP', 'Margin', 'Volume']],
        use_container_width=True, hide_index=True
    )

st.divider()

# ── Client mix ────────────────────────────────────────────────────────────────
st.subheader("Client Revenue Mix")

client_rev = (
    df.groupby('Client Name', observed=True)['Total Revenue']
    .sum().reset_index()
    .sort_values('Total Revenue', ascending=False)
)
# Show top 15, group rest as "Others"
top15 = client_rev.head(15)
others_val = client_rev.iloc[15:]['Total Revenue'].sum()
if others_val > 0:
    others_row = pd.DataFrame([{'Client Name': 'Others', 'Total Revenue': others_val}])
    top15 = pd.concat([top15, others_row], ignore_index=True)

fig_pie = px.pie(top15, values='Total Revenue', names='Client Name',
                 hole=0.4, template='plotly_white', height=420)
fig_pie.update_traces(textposition='inside', textinfo='percent+label')
fig_pie.update_layout(legend=dict(orientation='v'))
st.plotly_chart(fig_pie, use_container_width=True)
