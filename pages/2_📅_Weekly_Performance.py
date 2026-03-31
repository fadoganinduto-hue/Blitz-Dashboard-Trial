import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils import (require_data, sidebar_filters, fmt_idr, fmt_pct, fmt_vol,
                   C_REVENUE, C_COST, C_GP, MONTH_ORDER,
                   get_available_periods, filter_period, prev_period_info,
                   pop_pct, pop_label)

st.set_page_config(page_title="Period Performance | Blitz", page_icon="📅", layout="wide")
st.title("📅 Period Performance")
st.caption(
    "Client-by-client P&L with period-over-period % change. "
    "Compare any two weeks, any two months, or the same month across years (e.g. Jan 2024 vs Jan 2025)."
)

df_full = require_data()
df = sidebar_filters(df_full, page_key="period_perf")

if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Period mode + selectors ───────────────────────────────────────────────────
view_mode = st.radio("View by", ["Weekly", "Monthly"], horizontal=True, key="pp_view")
pop = pop_label(view_mode)

periods = get_available_periods(df, view_mode)
period_labels = [p[2] for p in periods]  # e.g. ["2024 W1", "2024 W2", ...]

col_a, col_b = st.columns(2)
with col_a:
    curr_label = st.selectbox(
        "Current period", period_labels[::-1], index=0,
        help="The period you want to analyse"
    )
with col_b:
    # Only allow periods strictly before the current one
    curr_idx = period_labels.index(curr_label)
    prior_options = period_labels[:curr_idx][::-1]  # most recent first
    if prior_options:
        prior_label = st.selectbox(
            "Compare against",
            prior_options,
            index=0,
            help="Pick any earlier period — consecutive or year-over-year"
        )
    else:
        st.info("No earlier period available for comparison.")
        prior_label = None

# Map labels back to (year, period_val)
label_map = {p[2]: (p[0], p[1]) for p in periods}
curr_yr, curr_p   = label_map[curr_label]
curr_df = filter_period(df, view_mode, curr_yr, curr_p)

if prior_label:
    prior_yr, prior_p = label_map[prior_label]
    prior_df = filter_period(df, view_mode, prior_yr, prior_p)
else:
    prior_yr, prior_p = None, None
    prior_df = pd.DataFrame()

if view_mode == "Weekly":
    date_range = curr_df['Date Range'].dropna().iloc[0] if not curr_df['Date Range'].dropna().empty else ''
    st.caption(f"Current: **{curr_label}**  ·  {date_range}")
else:
    st.caption(f"Current: **{curr_label}**")

st.divider()


# ── Helper: build client summary for a given period dataframe ─────────────────
def period_summary(d: pd.DataFrame) -> pd.DataFrame:
    if d.empty:
        return pd.DataFrame()
    agg = (
        d.groupby('Client Name', observed=True)
        .agg(
            Volume=('Delivery Volume', 'sum'),
            Revenue=('Total Revenue', 'sum'),
            Cost=('Total Cost', 'sum'),
            GP=('GP', 'sum'),
        )
        .reset_index()
    )
    agg['GP Margin %'] = np.where(agg['Revenue'] != 0, agg['GP'] / agg['Revenue'] * 100, 0)
    return agg


def fmt_pop(val):
    if val is None or pd.isna(val):
        return "—"
    arrow = "▲" if val > 0 else "▼"
    color_tag = "green" if val > 0 else "red"
    return f":{color_tag}[{arrow} {abs(val):.1f}%]"


curr_summary  = period_summary(curr_df)
prior_summary = period_summary(prior_df)

# Merge and compute PoP %
if not prior_summary.empty:
    merged = curr_summary.merge(
        prior_summary, on='Client Name', how='outer', suffixes=('', '_prior')
    ).fillna(0)
    for m in ['Volume', 'Revenue', 'GP']:
        merged[f'{m}_pop'] = merged.apply(
            lambda r, col=m: pop_pct(r[col], r[f'{col}_prior']), axis=1
        )
else:
    merged = curr_summary.copy()
    for m in ['Volume', 'Revenue', 'GP']:
        merged[f'{m}_pop'] = None
        merged[f'{m}_prior'] = 0.0

merged = merged.sort_values('GP', ascending=False).reset_index(drop=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Client Matrix", "📈 GP Trend (Multi-period)", "🔍 Single Client Detail"])

# ── Tab 1: Full client matrix ─────────────────────────────────────────────────
with tab1:
    compare_str = f"vs {prior_label}" if prior_label else "(no comparison)"
    st.subheader(f"All Clients — {curr_label}  {compare_str}")

    disp_rows = []
    for _, r in merged.iterrows():
        row = {
            'Client':    r['Client Name'],
            'Volume':    fmt_vol(r['Volume']),
            f'Vol {pop}': fmt_pop(r.get('Volume_pop')),
            'Revenue':   fmt_idr(r['Revenue']),
            f'Rev {pop}': fmt_pop(r.get('Revenue_pop')),
            'Cost':      fmt_idr(r['Cost']),
            'GP':        fmt_idr(r['GP']),
            f'GP {pop}': fmt_pop(r.get('GP_pop')),
            'Margin':    fmt_pct(r['GP Margin %']),
        }
        disp_rows.append(row)

    disp_df = pd.DataFrame(disp_rows)
    st.dataframe(disp_df, use_container_width=True, hide_index=True, height=500)

    # GP bar — current period
    st.markdown("---")
    st.markdown(f"**Gross Profit — {curr_label} by Client**")
    fig = px.bar(
        merged.copy().sort_values('GP'),
        x='GP', y='Client Name', orientation='h',
        color='GP', color_continuous_scale=['red', 'yellow', 'green'],
        template='plotly_white', height=max(400, len(merged) * 25),
        labels={'GP': 'Gross Profit (IDR)', 'Client Name': ''}
    )
    fig.add_vline(x=0, line_dash='dash', line_color='grey')
    fig.update_coloraxes(showscale=False)
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)

    # PoP % GP chart
    if prior_label:
        pop_df = merged[merged['GP_pop'].notna()].copy()
        pop_df['GP_pop'] = pop_df['GP_pop'].astype(float)
        pop_df = pop_df.sort_values('GP_pop')

        st.markdown(f"**GP % Change — {prior_label} → {curr_label}**")
        fig_pop = px.bar(
            pop_df, x='GP_pop', y='Client Name', orientation='h',
            color='GP_pop', color_continuous_scale=['red', 'white', 'green'],
            color_continuous_midpoint=0,
            template='plotly_white', height=max(400, len(pop_df) * 25),
            labels={'GP_pop': f'Change (%)', 'Client Name': ''}
        )
        fig_pop.add_vline(x=0, line_dash='dash', line_color='grey')
        fig_pop.update_coloraxes(showscale=False)
        fig_pop.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_pop, use_container_width=True)


# ── Tab 2: Multi-period GP trend ──────────────────────────────────────────────
with tab2:
    st.subheader(f"GP Trend — Last N {'Weeks' if view_mode == 'Weekly' else 'Months'}")

    n_periods = st.slider(
        f"Show last N {'weeks' if view_mode == 'Weekly' else 'months'}",
        min_value=4, max_value=len(periods), value=min(10, len(periods)), step=1
    )
    selected_periods = periods[-n_periods:]

    if view_mode == "Weekly":
        trend_df = pd.concat(
            [filter_period(df, view_mode, yr, p) for yr, p, _ in selected_periods],
            ignore_index=True
        )
        trend_agg = (
            trend_df.groupby(['Client Name', 'Year', 'Week (by Year)'], observed=True)
            .agg(GP=('GP', 'sum'), Revenue=('Total Revenue', 'sum'))
            .reset_index()
        )
        trend_agg['Period Label'] = (trend_agg['Year'].astype(str) + ' W' +
                                     trend_agg['Week (by Year)'].astype(int).astype(str))
        trend_agg = trend_agg.sort_values(['Year', 'Week (by Year)'])
    else:
        trend_df = pd.concat(
            [filter_period(df, view_mode, yr, p) for yr, p, _ in selected_periods],
            ignore_index=True
        )
        trend_agg = (
            trend_df.groupby(['Client Name', 'Year', 'Month'], observed=True)
            .agg(GP=('GP', 'sum'), Revenue=('Total Revenue', 'sum'))
            .reset_index()
        )
        trend_agg['Month'] = pd.Categorical(trend_agg['Month'], categories=MONTH_ORDER, ordered=True)
        trend_agg = trend_agg.sort_values(['Year', 'Month'])
        trend_agg['Period Label'] = trend_agg['Year'].astype(str) + ' ' + trend_agg['Month'].astype(str)

    # Default: top clients by total GP in this window
    top_clients = (
        trend_agg.groupby('Client Name')['GP'].sum()
        .nlargest(10).index.tolist()
    )
    sel_clients = st.multiselect(
        "Filter clients (default: top 10 by GP)",
        sorted(trend_agg['Client Name'].unique()),
        default=top_clients
    )
    if sel_clients:
        trend_agg = trend_agg[trend_agg['Client Name'].isin(sel_clients)]

    fig_trend = px.line(
        trend_agg, x='Period Label', y='GP', color='Client Name',
        markers=True, template='plotly_white', height=500,
        title=f"GP per Client — {view_mode} trend",
        labels={'GP': 'Gross Profit (IDR)', 'Period Label': 'Period'}
    )
    fig_trend.add_hline(y=0, line_dash='dash', line_color='red', opacity=0.4)
    fig_trend.update_layout(hovermode='x unified', legend=dict(orientation='h', y=-0.2),
                            xaxis_tickangle=-45)
    st.plotly_chart(fig_trend, use_container_width=True)


# ── Tab 3: Single client full history ────────────────────────────────────────
with tab3:
    st.subheader("Single Client — Full History")

    all_clients = sorted(df['Client Name'].dropna().unique())
    sel_client = st.selectbox("Select client", all_clients, key="pp_single_client")
    cdf = df[df['Client Name'] == sel_client].copy()

    detail_view = st.radio("History view", ["Weekly", "Monthly"], horizontal=True,
                           key="pp_client_hist_view")

    if detail_view == "Weekly":
        hist = (
            cdf.groupby(['Year', 'Week (by Year)'], observed=True)
            .agg(Volume=('Delivery Volume', 'sum'), Revenue=('Total Revenue', 'sum'),
                 Cost=('Total Cost', 'sum'), GP=('GP', 'sum'))
            .reset_index().sort_values(['Year', 'Week (by Year)'])
        )
        hist['Label'] = hist['Year'].astype(str) + ' W' + hist['Week (by Year)'].astype(int).astype(str)
    else:
        hist = (
            cdf.groupby(['Year', 'Month'], observed=True)
            .agg(Volume=('Delivery Volume', 'sum'), Revenue=('Total Revenue', 'sum'),
                 Cost=('Total Cost', 'sum'), GP=('GP', 'sum'))
            .reset_index()
        )
        hist['Month'] = pd.Categorical(hist['Month'], categories=MONTH_ORDER, ordered=True)
        hist = hist.sort_values(['Year', 'Month'])
        hist['Label'] = hist['Year'].astype(str) + ' ' + hist['Month'].astype(str)

    hist['GP Margin %'] = np.where(hist['Revenue'] != 0, hist['GP'] / hist['Revenue'] * 100, 0)
    for m in ['Volume', 'Revenue', 'GP']:
        hist[f'{m} PoP%'] = hist[m].pct_change() * 100

    # Chart
    fig_c = go.Figure()
    fig_c.add_bar(x=hist['Label'], y=hist['Revenue'], name='Revenue',
                  marker_color=C_REVENUE, opacity=0.8)
    fig_c.add_bar(x=hist['Label'], y=hist['Cost'], name='Cost',
                  marker_color=C_COST, opacity=0.8)
    fig_c.add_scatter(x=hist['Label'], y=hist['GP'], mode='lines+markers',
                      name='GP', line=dict(color=C_GP, width=2))
    fig_c.update_layout(
        barmode='group', hovermode='x unified', template='plotly_white',
        height=420, legend=dict(orientation='h', y=1.05),
        yaxis_title='IDR', xaxis_tickangle=-45,
        title=f"{sel_client} — {detail_view} P&L History"
    )
    st.plotly_chart(fig_c, use_container_width=True)

    # Table with PoP %
    def fmt_pop_plain(v):
        if pd.isna(v):
            return '—'
        return f"{'▲' if v > 0 else '▼'} {abs(v):.1f}%"

    disp_c = hist.copy()
    disp_c['Revenue']    = disp_c['Revenue'].apply(fmt_idr)
    disp_c['Cost']       = disp_c['Cost'].apply(fmt_idr)
    disp_c['GP']         = disp_c['GP'].apply(fmt_idr)
    disp_c['Margin']     = disp_c['GP Margin %'].apply(fmt_pct)
    disp_c['Volume']     = disp_c['Volume'].apply(fmt_vol)
    disp_c['Rev PoP%']   = disp_c['Revenue PoP%'].apply(fmt_pop_plain)
    disp_c['GP PoP%']    = disp_c['GP PoP%'].apply(fmt_pop_plain)
    disp_c['Vol PoP%']   = disp_c['Volume PoP%'].apply(fmt_pop_plain)

    st.dataframe(
        disp_c[['Label', 'Volume', 'Vol PoP%', 'Revenue', 'Rev PoP%',
                'Cost', 'GP', 'GP PoP%', 'Margin']],
        use_container_width=True, hide_index=True
    )
