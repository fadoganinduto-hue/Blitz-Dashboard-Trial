import pandas as pd
import numpy as np
import streamlit as st
import io

MONTH_ORDER = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

REVENUE_COLS = [
    'Selling Price (Regular Rate)',
    'Additional Charge (KM, KG, Etc)',
    'Return/Delivery Rate',
    'Lalamove Bills (Invoicing to Client)',
    'TOTAL DELIVERY REVENUE',
    'EV Reduction (3PL & KSJ)',
    'EV Manpower',
    'EV Revenue + Battery (Rental Client)',
    'Claim/COD/Own Risk',
    'Hub, COD Fee (SBY) & Service Korlap',
    'Other Revenue',
    'Attribute Fee',
    'Total Revenue',
]

COST_COLS = [
    'Rider Cost',
    'Manpower Cost',
    'OEM Cost',
    'Mid-Mile/ Linehaul Cost',
    'Add. 3PL Cost',
    'DM Program',
    'Claim Damaged/Loss',
    'Outstanding COD',
    'Claim Ownrisk',
    'Attribute Cost',
    'HUB Cost',
    'Other Cost',
    'Total Cost',
]

COST_COMPONENTS = {
    'Rider Cost': 'Rider',
    'Manpower Cost': 'Manpower',
    'OEM Cost': 'OEM',
    'Mid-Mile/ Linehaul Cost': 'Mid-Mile',
    'Add. 3PL Cost': '3PL',
    'DM Program': 'DM Program',
    'HUB Cost': 'Hub',
    'Other Cost': 'Other',
}


def _fix_week(w):
    """Fix 2026 week numbers that have year appended (e.g. 12026 → 1, 102026 → 10)."""
    if pd.isna(w):
        return np.nan
    w = int(w)
    if w > 100:
        s = str(w)
        if len(s) > 4:
            return int(s[:-4])
    return w


def _detect_sheet(file_bytes: bytes) -> str:
    """
    Find the correct sheet to load.
    Priority: 'Raw Data Source' → 'PowerQuery' → first sheet.
    This allows uploading the full file OR just the Raw Data Source tab exported alone.
    """
    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    for candidate in ['Raw Data Source', 'PowerQuery']:
        if candidate in xl.sheet_names:
            return candidate
    return xl.sheet_names[0]  # Fallback: use whatever sheet is there


@st.cache_data(show_spinner="Loading data...")
def load_main_data(file_bytes: bytes) -> pd.DataFrame:
    sheet = _detect_sheet(file_bytes)
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=0)

    # Strip whitespace from column names (handles ' HUB Cost ' etc.)
    df.columns = [str(c).strip() for c in df.columns]

    # Fix week numbers
    df['Week (by Year)'] = df['Week (by Year)'].apply(_fix_week)

    # Numeric columns – fill nulls with 0
    numeric_cols = REVENUE_COLS + COST_COLS + ['Delivery Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Derived metrics
    df['GP'] = df['Total Revenue'] - df['Total Cost']
    df['GP Margin %'] = np.where(
        df['Total Revenue'] != 0,
        df['GP'] / df['Total Revenue'] * 100,
        0
    )
    vol = df['Delivery Volume'].replace(0, np.nan)
    df['SRPO'] = df['Selling Price (Regular Rate)'] / vol
    df['RCPO'] = df['Rider Cost'] / vol
    df['TCPO'] = df['Total Cost'] / vol
    df['TRPO'] = df['Total Revenue'] / vol
    df[['SRPO', 'RCPO', 'TCPO', 'TRPO']] = df[['SRPO', 'RCPO', 'TCPO', 'TRPO']].fillna(0)

    # Ordered month category
    df['Month'] = pd.Categorical(df['Month'], categories=MONTH_ORDER, ordered=True)

    # Ensure Year is int
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce').dropna().astype(int)

    return df


@st.cache_data(show_spinner=False)
def load_ev_data(file_bytes: bytes) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name='Test EV Rental ', header=0)
        df.columns = [str(c).strip() for c in df.columns]
        numeric_cols = ['Unit', 'EV Revenue + Battery (Rental Client)', 'Others',
                        'Total Revenue', 'OEM Cost', 'Insurance Cost', 'IOT Cost', 'Total Cost']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df['GP'] = df['Total Revenue'] - df['Total Cost']
        df['Month'] = pd.Categorical(df['Month'], categories=MONTH_ORDER, ordered=True)
        return df
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_action_items(file_bytes: bytes) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name='Action Items',
            header=1,
            usecols=range(10)
        )
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how='all')
        return df
    except Exception:
        return None


def generate_weekly_insights(df: pd.DataFrame) -> dict | None:
    """Compare the latest week to the prior week and surface key insights."""
    max_year = int(df['Year'].max())
    year_df = df[df['Year'] == max_year].copy()
    max_week = int(year_df['Week (by Year)'].max())
    prev_week = max_week - 1

    curr = year_df[year_df['Week (by Year)'] == max_week]
    prev = year_df[year_df['Week (by Year)'] == prev_week]

    if curr.empty or prev.empty:
        return None

    def pct(c, p):
        return (c - p) / abs(p) * 100 if p != 0 else None

    summary = {}
    for m in ['Total Revenue', 'Total Cost', 'GP', 'Delivery Volume']:
        if m == 'GP':
            cv = (curr['Total Revenue'] - curr['Total Cost']).sum()
            pv = (prev['Total Revenue'] - prev['Total Cost']).sum()
        else:
            cv = curr[m].sum()
            pv = prev[m].sum()
        summary[m] = {'current': cv, 'previous': pv, 'pct_change': pct(cv, pv)}

    # Client GP comparison
    def client_gp(d):
        return d.groupby('Client Name')[['Total Revenue', 'Total Cost']].sum().eval(
            'GP = `Total Revenue` - `Total Cost`'
        )[['GP']].reset_index()

    curr_gp = client_gp(curr)
    prev_gp = client_gp(prev)
    merged = curr_gp.merge(prev_gp, on='Client Name', how='outer', suffixes=('', '_prev')).fillna(0)
    merged['GP_change'] = merged['GP'] - merged['GP_prev']
    merged['GP_pct'] = merged.apply(
        lambda r: pct(r['GP'], r['GP_prev']), axis=1
    )

    summary['week'] = max_week
    summary['year'] = max_year
    summary['date_range'] = curr['Date Range'].dropna().iloc[0] if not curr['Date Range'].dropna().empty else ''
    summary['top_clients'] = curr_gp.nlargest(5, 'GP')
    summary['biggest_improvers'] = merged[merged['GP_pct'].notna() & (merged['GP_pct'] > 0)].nlargest(3, 'GP_pct')
    summary['biggest_decliners'] = merged[merged['GP_pct'].notna() & (merged['GP_pct'] < 0)].nsmallest(3, 'GP_pct')
    summary['negative_gp'] = curr_gp[curr_gp['GP'] < 0]

    return summary
