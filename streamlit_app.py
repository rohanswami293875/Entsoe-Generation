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

# Country name to ENTSO-E code mapping
country_code_map = {
    'France': 'FR', 'Germany': 'DE', 'Italy': 'IT', 'Spain': 'ES', 'Sweden': 'SE',
    'Denmark': 'DK', 'Belgium': 'BE', 'Netherlands': 'NL', 'Austria': 'AT', 'Poland': 'PL',
    'Czech': 'CZ', 'Portugal': 'PT', 'Finland': 'FI', 'Norway': 'NO', 'Switzerland': 'CH',
    'Ireland': 'IE', 'Hungary': 'HU', 'Slovakia': 'SK', 'Slovenia': 'SI', 'Greece': 'GR',
    'Romania': 'RO', 'Bulgaria': 'BG', 'Croatia': 'HR', 'Estonia': 'EE', 'Latvia': 'LV', 'Lithuania': 'LT'
}

# Function to parse natural language query
def parse_query(query):
    # Extract all dates from the query
    date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', query)
    if len(date_matches) >= 2:
        start_date = date_matches[0]
        end_date = date_matches[1]
    else:
        start_date = None
        end_date = None

    # Fuzzy match for country name
    words = re.findall(r'\b\w+\b', query)
    country_name = None
    for word in words:
        matches = get_close_matches(word.capitalize(), country_code_map.keys(), n=1, cutoff=0.7)
        if matches:
            country_name = matches[0]
            break

    return country_name, start_date, end_date

# Streamlit UI
st.title("ENTSO-E Generation Data Bot")
query = st.text_input("Enter your query (e.g., 'Germany 2025-01-01 2025-03-31')")

if query:
    country_name, start_date_str, end_date_str = parse_query(query)
    if not country_name or not start_date_str or not end_date_str:
        st.error("Could not parse query. Please include a recognizable country name and two valid dates (YYYY-MM-DD).")
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


