import io
import re
import time
from datetime import datetime, date
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta
from entsoe import EntsoePandasClient

# =========================
# Streamlit page settings
# =========================
st.set_page_config(page_title="🔌 ENTSO-E Generation Bot (Zones)", layout="wide")

st.markdown(
    "<h1 style='text-align:center;color:#1f2937;'>🔌 ENTSO-E Generation Data Bot — Bidding Zones</h1>",
    unsafe_allow_html=True,
)
st.caption(
    "Tip: pick a country + zones from the dropdowns. "
    "You can also type dates like `2025-01-01 2025-03-31` in the Date Range box."
)


try:
    API_KEY = st.secrets["API_KEY"]
except Exception:
    st.error("Missing API key. Add API_KEY to your Streamlit secrets.")
    st.stop()

client = EntsoePandasClient(api_key=API_KEY)

# =========================
# Country + Zone catalog
# =========================
# For each country: a 'total' domain (country aggregate) and a list of zonal domains.
# Domain strings can be ENTSO-E short codes (e.g., 'SE_1') or full EICs ('10Y...').
COUNTRIES: Dict[str, Dict[str, List[str]]] = {
    # --- Zonal countries ---
    "Italy": {
        "total": ["IT"],  # Country aggregate
        # Bidding zones with EIC overrides (more robust)
        "zones": [
            "10Y1001A1001A70O",  # IT_CNOR
            "10Y1001A1001A71M",  # IT_CSUD
            "10Y1001A1001A788",  # IT_SUD
            "10Y1001C--00096J",  # IT_CALA
            "10Y1001A1001A74G",  # IT_SARD
            "10Y1001A1001A73I",  # IT_NORD
            "10Y1001A1001A75E",  # IT_SICI
        ],
    },
    "Sweden": {
        "total": ["SE"],
        "zones": ["SE_1", "SE_2", "SE_3", "SE_4"],
    },
    "Norway": {
        "total": ["NO"],
        "zones": ["NO_1", "NO_2", "NO_3", "NO_4", "NO_5"],
    },
    "Denmark": {
        "total": ["DK"],
        "zones": ["DK_1", "DK_2"],
    },
    # --- Mostly single-zone (use country total) ---
    "France": {"total": ["FR"], "zones": ["FR"]},
    "Germany–Luxembourg (DE-LU)": {"total": ["DE_LU"], "zones": ["DE_LU"]},
    "Spain": {"total": ["ES"], "zones": ["ES"]},
    "Portugal": {"total": ["PT"], "zones": ["PT"]},
    "Netherlands": {"total": ["NL"], "zones": ["NL"]},
    "Belgium": {"total": ["BE"], "zones": ["BE"]},
    "Austria": {"total": ["AT"], "zones": ["AT"]},
    "Poland": {"total": ["PL"], "zones": ["PL"]},
    "Czech": {"total": ["CZ"], "zones": ["CZ"]},
    "Slovakia": {"total": ["SK"], "zones": ["SK"]},
    "Slovenia": {"total": ["SI"], "zones": ["SI"]},
    "Hungary": {"total": ["HU"], "zones": ["HU"]},
    "Greece": {"total": ["GR"], "zones": ["GR"]},
    "Romania": {"total": ["RO"], "zones": ["RO"]},
    "Bulgaria": {"total": ["BG"], "zones": ["BG"]},
    "Croatia": {"total": ["HR"], "zones": ["HR"]},
    "Finland": {"total": ["FI"], "zones": ["FI"]},
    "Estonia": {"total": ["EE"], "zones": ["EE"]},
    "Latvia": {"total": ["LV"], "zones": ["LV"]},
    "Lithuania": {"total": ["LT"], "zones": ["LT"]},
    "Switzerland": {"total": ["CH"], "zones": ["CH"]},
    "Ireland": {"total": ["IE"], "zones": ["IE"]},
    # Uncomment if you need Northern Ireland separately:
    # "Northern Ireland": {"total": ["GB_NIR"], "zones": ["GB_NIR"]},
}

# Optional reverse-map for friendlier labels on zone dropdown
ZONE_LABELS = {
    # Italy
    "10Y1001A1001A70O": "IT_CNOR",
    "10Y1001A1001A71M": "IT_CSUD",
    "10Y1001A1001A788": "IT_SUD",
    "10Y1001C--00096J": "IT_CALA",
    "10Y1001A1001A74G": "IT_SARD",
    "10Y1001A1001A73I": "IT_NORD",
    "10Y1001A1001A75E": "IT_SICI",
    # Sweden
    "SE_1": "SE1",
    "SE_2": "SE2",
    "SE_3": "SE3",
    "SE_4": "SE4",
    # Norway
    "NO_1": "NO1",
    "NO_2": "NO2",
    "NO_3": "NO3",
    "NO_4": "NO4",
    "NO_5": "NO5",
    # Denmark
    "DK_1": "DK1",
    "DK_2": "DK2",
    # Single-zone examples
    "FR": "France (Total)",
    "DE_LU": "Germany–Lux (Total)",
    "ES": "Spain (Total)",
    "PT": "Portugal (Total)",
    "NL": "Netherlands (Total)",
    "BE": "Belgium (Total)",
    "AT": "Austria (Total)",
    "PL": "Poland (Total)",
    "CZ": "Czech (Total)",
    "SK": "Slovakia (Total)",
    "SI": "Slovenia (Total)",
    "HU": "Hungary (Total)",
    "GR": "Greece (Total)",
    "RO": "Romania (Total)",
    "BG": "Bulgaria (Total)",
    "HR": "Croatia (Total)",
    "FI": "Finland (Total)",
    "EE": "Estonia (Total)",
    "LV": "Latvia (Total)",
    "LT": "Lithuania (Total)",
    "CH": "Switzerland (Total)",
    "IE": "Ireland (Total)",
    # "GB_NIR": "Northern Ireland (Total)",
    "IT": "Italy (Total)",
    "SE": "Sweden (Total)",
    "NO": "Norway (Total)",
    "DK": "Denmark (Total)",
}

def zone_label(zone_code: str) -> str:
    return ZONE_LABELS.get(zone_code, zone_code)

# =========================
# Helpers
# =========================
def parse_date_text(s: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Parse a free-text date range like '2025-01-01 2025-03-31'.
    Returns (start_utc, end_utc). Raises ValueError if it can't parse two dates.
    """
    matches = re.findall(r"\d{4}-\d{2}-\d{2}", s)
    if len(matches) < 2:
        raise ValueError("Please provide two dates in YYYY-MM-DD format.")
    start_str, end_str = matches[0], matches[1]
    start = pd.Timestamp(start_str + " 00:00", tz="UTC")
    end = pd.Timestamp(end_str + " 23:59", tz="UTC")
    if end < start:
        raise ValueError("End date is before start date.")
    return start, end

def iter_months(start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    cur = start_ts
    while cur < end_ts:
        nxt = min(cur + relativedelta(months=1), end_ts)
        yield cur, nxt
        cur = nxt

@st.cache_data(show_spinner=False)
def fetch_zone_generation(zone_domain: str,
                          start_ts: pd.Timestamp,
                          end_ts: pd.Timestamp,
                          max_retries: int = 5,
                          backoff_base: float = 1.8) -> pd.DataFrame:
    """
    Fetch generation for a single zone (domain string), month-chunked with retries.
    Cached by Streamlit to avoid hitting the API repeatedly.
    Returns tz-naive hourly dataframe (mean-resampled when needed).
    """
    frames = []
    for s, e in iter_months(start_ts, end_ts):
        attempt = 0
        while True:
            try:
                df = client.query_generation(country_code=zone_domain, start=s, end=e)
                if df is not None and not df.empty:
                    if df.index.tz is not None:
                        df = df.tz_convert(None)
                else:
                    df = pd.DataFrame()
                frames.append(df)
                break
            except Exception as ex:
                attempt += 1
                if attempt > max_retries:
                    raise RuntimeError(f"Failed after {max_retries} retries for {zone_domain} {s}→{e}: {ex}")
                sleep_s = backoff_base ** attempt
                time.sleep(sleep_s)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames) if len(frames) > 1 else frames[0]
    if full is None or full.empty:
        return pd.DataFrame()

    full = full[~full.index.duplicated(keep="last")].sort_index()
    hourly = full.resample("H").mean()
    return hourly

def excel_bytes(sheets: Dict[str, pd.DataFrame], meta: Dict[str, str]) -> bytes:
    """Build an Excel file in-memory with one sheet per zone + a README sheet."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm:ss") as xw:
        # README
        pd.DataFrame({"Key": list(meta.keys()), "Value": list(meta.values())}).to_excel(
            xw, sheet_name="README", index=False
        )
        for sheet_name, df in sheets.items():
            # Clean column names (strings) and truncate sheet names to <=31 chars
            df = df.copy()
            df.columns = [str(c) for c in df.columns]
            safe_name = sheet_name[:31]
            df.to_excel(xw, sheet_name=safe_name)
            # Basic formatting
            try:
                ws = xw.sheets[safe_name]
                ws.freeze_panes(1, 1)
            except Exception:
                pass
    return output.getvalue()

# =========================
# UI — selections
# =========================
left, right = st.columns([1, 1])

with left:
    country = st.selectbox("Country", options=sorted(COUNTRIES.keys()))

with right:
    st.write("")  # spacer
    st.write("")  # spacer
    st.write("Pick zones (or leave as **All zones**).")

zones_for_country = COUNTRIES[country]["zones"]
total_for_country = COUNTRIES[country]["total"]  # usually 1 element list
all_zone_labels = [zone_label(z) for z in zones_for_country]

fetch_all = st.checkbox("All zones", value=True, help="Fetch all bidding zones for the selected country.")
selected_zone_labels = st.multiselect(
    "Zones",
    options=all_zone_labels,
    default=all_zone_labels if fetch_all else [],
    disabled=fetch_all,
    help="If unchecked 'All zones', choose one or more zones here.",
)

# Country-total toggle
include_total = st.checkbox("Include country total", value=True, help="Also fetch the country aggregate time series.")

# Date range input: text OR widget
date_text = st.text_input(
    "Date Range (type two dates like `2025-01-01 2025-03-31`)",
    placeholder="YYYY-MM-DD YYYY-MM-DD",
)
date_widget = st.date_input(
    "…or pick a date range",
    value=(date.today().replace(day=1), date.today()),
    help="If you don't type dates above, this picker is used.",
)

# =========================
# Action
# =========================
if st.button("Fetch generation data", type="primary"):
    # Resolve dates
    try:
        if date_text.strip():
            start_ts, end_ts = parse_date_text(date_text.strip())
        else:
            if isinstance(date_widget, tuple) and len(date_widget) == 2:
                w_start = pd.Timestamp(date_widget[0].strftime("%Y-%m-%d") + " 00:00", tz="UTC")
                w_end = pd.Timestamp(date_widget[1].strftime("%Y-%m-%d") + " 23:59", tz="UTC")
                start_ts, end_ts = w_start, w_end
            else:
                raise ValueError("Please select a start and end date.")
    except Exception as e:
        st.error(f"Date error: {e}")
        st.stop()

    # Resolve zone domains
    if fetch_all:
        chosen_zones = zones_for_country.copy()
    else:
        # Map chosen labels back to codes
        label_to_code = {zone_label(z): z for z in zones_for_country}
        chosen_zones = [label_to_code[lbl] for lbl in selected_zone_labels]

    if include_total:
        # Add country-total domains (avoid duplicates)
        for d in total_for_country:
            if d not in chosen_zones:
                chosen_zones.append(d)

    if not chosen_zones:
        st.warning("No zones selected.")
        st.stop()

    st.info(f"Fetching {len(chosen_zones)} domain(s) from {start_ts.date()} to {end_ts.date()} (UTC)…")

    progress = st.progress(0)
    results: Dict[str, pd.DataFrame] = {}
    errors: List[str] = []
    for i, domain in enumerate(chosen_zones, start=1):
        lbl = zone_label(domain)
        try:
            with st.spinner(f"Fetching {lbl} …"):
                df = fetch_zone_generation(domain, start_ts, end_ts)
            if df is None or df.empty:
                st.warning(f"No data for {lbl}")
            else:
                results[lbl] = df
        except Exception as ex:
            errors.append(f"{lbl}: {ex}")
        progress.progress(i / len(chosen_zones))

    if errors:
        with st.expander("Some requests failed (details)"):
            for line in errors:
                st.write("• " + line)

    if not results:
        st.warning("No data fetched.")
        st.stop()

    st.success("Done! Preview below (first non-empty sheet).")
    # Show the first sheet preview
    first_key = next(iter(results.keys()))
    st.subheader(f"Preview — {first_key}")
    st.dataframe(results[first_key].head(20))

    # Build Excel for download
    meta = {
        "Country": country,
        "Domains": ", ".join(list(results.keys())),
        "Start (UTC)": str(start_ts),
        "End (UTC)": str(end_ts),
        "Generated (UTC)": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "Note": "Columns are generation categories as served by ENTSO-E; hourly mean if needed.",
    }
    xls_bytes = excel_bytes(results, meta)

    file_name = f"{country.replace(' ', '_')}_generation_{start_ts.date()}_to_{end_ts.date()}.xlsx"
    st.download_button(
        "⬇️ Download Excel",
        data=xls_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.caption(
        "If the app 'sleeps' on your hosting platform, consider deploying to a persistent server or enabling an Always-on setting. "
        "Results are cached for repeated queries to reduce API calls."
    )
