import streamlit as st
import pandas as pd
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from entsoe import EntsoePandasClient
from difflib import get_close_matches

# Initialize ENTSO-E client with API key
API_KEY = '08876cd7-1363-4f9c-b260-f0dd5710f825'
client = EntsoePandasClient(api_key=API_KEY)

# Expanded country name to ENTSO-E code mapping
country_code_map = {
    'france': 'FR', 'germany': 'DE', 'italy': 'IT', 'spain': 'ES', 'sweden': 'SE',
    'denmark': 'DK', 'belgium': 'BE', 'netherlands': 'NL', 'austria': 'AT', 'poland': 'PL',
    'czech': 'CZ', 'portugal': 'PT', 'finland': 'FI', 'norway': 'NO', 'switzerland': 'CH',
    'ireland': 'IE', 'hungary': 'HU', 'slovakia': 'SK', 'slovenia': 'SI', 'greece': 'GR',
    'romania': 'RO', 'bulgaria': 'BG', 'croatia': 'HR', 'estonia': 'EE', 'latvia': 'LV', 'lithuania': 'LT',
    'luxembourg': 'LU', 'cyprus': 'CY', 'malta': 'MT'
}

# Function to parse natural language query with fuzzy matching
def parse_query(query):
    query = query.lower()
    country_match = re.search(r'for\s+([a-zA-Z]+)', query)
    country_name = country_match.group(1) if country_match else None

    # Fuzzy match country name
    if country_name:
        matched = get_close_matches(country_name, country_code_map.keys(), n=1, cutoff=0.6)
        country_name = matched[0] if matched else None

    # Extract dates
    date_match = re.search(r'from\s+(\d{4}-\d{2}-\d{2})\s*(to|-)\s*(\d{4}-\d{2}-\d{2})', query)
    if date_match:
        start_date = date_match.group(1)
        end_date = date_match.group(3)
    else:
        # Try to find any two dates in the query
        date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', query)
        if len(date_matches) >= 2:
            start_date, end_date = date_matches[0], date_matches[1]
        else:
            start_date, end_date = None, None

    return country_name, start_date, end_date

# Streamlit UI
st.title("ENTSO-E Generation Data Bot")
query = st.text_input("Enter your query (e.g., 'Get hourly generation data for Germany from 2025-01-01 to 2025-03-31')")

if query:
    country_name, start_date_str, end_date_str = parse_query(query)
    if not country_name or not start_date_str or not end_date_str:
        st.error("Could not parse query. Please use format like: 'Get hourly generation data for Germany from YYYY-MM-DD to YYYY-MM-DD'")
    else:
        country_code = country_code_map.get(country_name)
        if not country_code:
            st.error(f"Country '{country_name}' not recognized.")
        else:
            start_date = pd.Timestamp(start_date_str + ' 00:00', tz='UTC')
            end_date = pd.Timestamp(end_date_str + ' 23:59', tz='UTC')

            current_start = start_date
            zone_data = []

            with st.spinner(f"Fetching data for {country_code} from {start_date.date()} to {end_date.date()}..."):
                while current_start < end_date:
                    current_end = min(current_start + relativedelta(months=1), end_date)
                    try:
                        df_part = client.query_generation(
                            country_code=country_code,
                            start=current_start,
                            end=current_end,
                            psr_type=None
                        )
                        df_part.index = df_part.index.tz_convert(None)
                        zone_data.append(df_part)
                    except Exception as e:
                        st.warning(f"Error fetching data from {current_start} to {current_end}: {e}")
                    current_start = current_end

            if zone_data:
                df_full = pd.concat(zone_data)
                df_hourly = df_full.resample('h').mean()
                st.subheader("Data Preview")
                st.dataframe(df_hourly.head(10))

                output_file = f"{country_code}_generation_{start_date.date()}_to_{end_date.date()}.xlsx"
                df_hourly.to_excel(output_file)

                with open(output_file, "rb") as f:
                    st.download_button(
                        label="Download Excel File",
                        data=f,
                        file_name=output_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.warning("No data fetched for the given query.")



