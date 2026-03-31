import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (require_data, sidebar_filters, fmt_idr, fmt_pct, fmt_vol,
                   C_REVENUE, C_COST, C_GP, C_VOLUME, MONTH_ORDER)

st.set_page_config(page_title="By Location | Blitz", page_icon="🗺️", layout="wide")
st.title("🗺️ By Location")
st.caption("Location performance ranking, week-over-week variance, and trend analysis.")

df_full = require_data()
df = sidebar_filters(df_full, page_key="locs")

if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Location ranking ──────────────────────────────────────────────────────────
st.subheader("Location Rankings")

loc_agg = (
    df.groupby('Client Location', observed=True)
    .agg(
        Volume=('Delivery Volume', 'sum'),
        Revenue=('Total Revenue', 'sum'),
        Cost=('Total Cost', 'sum'),
        GP=('GP', 'sum'),
    )
    .reset_index()
)
loc_agg['GP Margin %'] = loc_agg.apply(
    lambda r: r['GP'] / r['Revenue'] * 100 if r['Revenue'] else 0, axis=1
)
loc_agg = loc_agg.sort_values('GP', ascending=False).reset_index(drop=True)

# Horizontal GP bar chart
fig_rank = px.bar(
    loc_agg.sort_values('GP'), x='GP', y='Client Location', orientation='h',
    color='GP', color_continuous_scale=['red', 'yellow', 'green'],
    template='plotly_white', height=max(350, len(loc_agg) * 28),
    title="Gross Profit by Location",
    labels={'GP': 'Gross Profit (IDR)', 'Client Location': 'Location'}
)
fig_rank.update_coloraxes(showscale=False)
st.plotly_chart(fig_rank, use_container_width=True)

# Summary table
disp = loc_agg.copy()
disp['Revenue']    = disp['Revenue'].apply(fmt_idr)
disp['Cost']       = disp['Cost'].apply(fmt_idr)
disp['GP']         = disp['GP'].apply(fmt_idr)
disp['GP Margin %']= disp['GP Margin %'].apply(fmt_pct)
disp['Volume']     = disp['Volume'].apply(fmt_vol)
st.dataframe(
    disp[['Client Location', 'Volume', 'Revenue', 'Cost', 'GP', 'GP Margin %']],
    use_container_width=True, hide_index=True
)

st.divider()

# ── Week-over-Week variance ───────────────────────────────────────────────────
st.subheader("Week-over-Week GP Change")
st.caption("Compares each location's GP in the latest week vs. the previous week.")

max_year = int(df['Year'].max())
year_df  = df[df['Year'] == max_year].copy()
max_week = int(year_df['Week (by Year)'].max())
prev_week = max_week - 1

curr_w = year_df[year_df['Week (by Year)'] == max_week]
prev_w = year_df[year_df['Week (by Year)'] == prev_week]

if not curr_w.empty and not prev_w.empty:
    curr_loc = curr_w.groupby('Client Location', observed=True)['GP'].sum().reset_index().rename(columns={'GP': 'GP_curr'})
    prev_loc = prev_w.groupby('Client Location', observed=True)['GP'].sum().reset_index().rename(columns={'GP': 'GP_prev'})
    wow = curr_loc.merge(prev_loc, on='Client Location', how='outer').fillna(0)
    wow['GP Change'] = wow['GP_curr'] - wow['GP_prev']
    wow['WoW %'] = wow.apply(
        lambda r: (r['GP_curr'] - r['GP_prev']) / abs(r['GP_prev']) * 100 if r['GP_prev'] != 0 else None, axis=1
    )
    wow = wow.sort_values('WoW %', ascending=False)

    fig_wow = px.bar(
        wow.dropna(subset=['WoW %']),
        x='Client Location', y='WoW %',
        color='WoW %', color_continuous_scale=['red', 'white', 'green'],
        color_continuous_midpoint=0,
        template='plotly_white', height=380,
        title=f"GP Week-over-Week Change (W{prev_week} → W{max_week}, {max_year})",
        labels={'WoW %': 'WoW Change (%)'}
    )
    fig_wow.update_coloraxes(showscale=False)
    fig_wow.add_hline(y=0, line_dash='dash', line_color='grey')
    st.plotly_chart(fig_wow, use_container_width=True)

    wow_disp = wow.copy()
    wow_disp['GP (This Week)']  = wow_disp['GP_curr'].apply(fmt_idr)
    wow_disp['GP (Prior Week)'] = wow_disp['GP_prev'].apply(fmt_idr)
    wow_disp['GP Change']       = wow_disp['GP Change'].apply(fmt_idr)
    wow_disp['WoW %']           = wow_disp['WoW %'].apply(lambda v: fmt_pct(v) if pd.notna(v) else '—')
    st.dataframe(
        wow_disp[['Client Location', 'GP (Prior Week)', 'GP (This Week)', 'GP Change', 'WoW %']],
        use_container_width=True, hide_index=True
    )
else:
    st.info("Not enough weekly data to calculate WoW change.")

st.divider()

# ── Location drilldown ────────────────────────────────────────────────────────
st.subheader("Location Drilldown")

all_locs = sorted(df['Client Location'].dropna().unique().tolist())
sel_loc  = st.selectbox("Select a location", all_locs)

loc_df = df[df['Client Location'] == sel_loc].copy()

if loc_df.empty:
    st.stop()

kc1, kc2, kc3, kc4 = st.columns(4)
kc1.metric("Revenue",  fmt_idr(loc_df['Total Revenue'].sum()))
kc2.metric("Cost",     fmt_idr(loc_df['Total Cost'].sum()))
kc3.metric("GP",       fmt_idr(loc_df['GP'].sum()))
gpm = loc_df['GP'].sum() / loc_df['Total Revenue'].sum() * 100 if loc_df['Total Revenue'].sum() else 0
kc4.metric("Margin",   fmt_pct(gpm))

weekly_l = (
    loc_df.groupby(['Year', 'Week (by Year)'], observed=True)
    .agg(Revenue=('Total Revenue', 'sum'), Cost=('Total Cost', 'sum'), GP=('GP', 'sum'))
    .reset_index().sort_values(['Year', 'Week (by Year)'])
)
weekly_l['Label'] = weekly_l['Year'].astype(str) + ' W' + weekly_l['Week (by Year)'].astype(str)

fig_loc = go.Figure()
fig_loc.add_bar(x=weekly_l['Label'], y=weekly_l['Revenue'], name='Revenue', marker_color=C_REVENUE, opacity=0.8)
fig_loc.add_bar(x=weekly_l['Label'], y=weekly_l['Cost'],    name='Cost',    marker_color=C_COST,    opacity=0.8)
fig_loc.add_scatter(x=weekly_l['Label'], y=weekly_l['GP'], mode='lines+markers',
                    name='GP', line=dict(color=C_GP, width=2))
fig_loc.update_layout(barmode='group', hovermode='x unified', template='plotly_white',
                      height=400, legend=dict(orientation='h', y=1.05),
                      yaxis_title='IDR', title=f"{sel_loc} — Weekly Trend")
st.plotly_chart(fig_loc, use_container_width=True)

# Clients in this location
cl_agg = (
    loc_df.groupby('Client Name', observed=True)
    .agg(Revenue=('Total Revenue', 'sum'), Cost=('Total Cost', 'sum'), GP=('GP', 'sum'),
         Volume=('Delivery Volume', 'sum'))
    .reset_index().sort_values('GP', ascending=False)
)
cl_disp = cl_agg.copy()
cl_disp['Revenue'] = cl_disp['Revenue'].apply(fmt_idr)
cl_disp['Cost']    = cl_disp['Cost'].apply(fmt_idr)
cl_disp['GP']      = cl_disp['GP'].apply(fmt_idr)
cl_disp['Volume']  = cl_disp['Volume'].apply(fmt_vol)
st.markdown(f"**Clients in {sel_loc}**")
st.dataframe(cl_disp, use_container_width=True, hide_index=True)
