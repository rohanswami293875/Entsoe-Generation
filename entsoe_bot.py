from entsoe import EntsoePandasClient
import pandas as pd
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta

API_KEY = '08876cd7-1363-4f9c-b260-f0dd5710f825'  # Replace with your actual API key
client = EntsoePandasClient(api_key=API_KEY)

query = input("Enter your query (e.g., 'Get hourly generation data for France from 2025-03-01 to 2025-06-30'): ")

def parse_query(query):
    country_match = re.search(r'for\\s+(\\w+)', query)
    country_name = country_match.group(1) if country_match else None

    date_match = re.search(r'from\\s+(\\d{4}-\\d{2}-\\d{2})\\s+to\\s+(\\d{4}-\\d{2}-\\d{2})', query)
    start_date = date_match.group(1) if date_match else None
    end_date = date_match.group(2) if date_match else None

    return country_name, start_date, end_date

country_code_map = {
    'France': 'FR', 'Germany': 'DE', 'Italy': 'IT', 'Spain': 'ES', 'Sweden': 'SE',
    'Denmark': 'DK', 'Belgium': 'BE', 'Netherlands': 'NL', 'Austria': 'AT', 'Poland': 'PL',
    'Czech': 'CZ', 'Portugal': 'PT', 'Finland': 'FI', 'Norway': 'NO', 'Switzerland': 'CH',
    'Ireland': 'IE', 'Hungary': 'HU', 'Slovakia': 'SK', 'Slovenia': 'SI', 'Greece': 'GR',
    'Romania': 'RO', 'Bulgaria': 'BG', 'Croatia': 'HR', 'Estonia': 'EE', 'Latvia': 'LV', 'Lithuania': 'LT'
}

country_name, start_date_str, end_date_str = parse_query(query)
country_code = country_code_map.get(country_name.capitalize())

start_date = pd.Timestamp(start_date_str + ' 00:00', tz='UTC')
end_date = pd.Timestamp(end_date_str + ' 23:59', tz='UTC')

current_start = start_date
zone_data = []

while current_start < end_date:
    current_end = min(current_start + relativedelta(months=1), end_date)
    print(f"Fetching data from {current_start} to {current_end}...")

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
        print(f"Error: {e}")

    current_start = current_end

if zone_data:
    df_full = pd.concat(zone_data)
    df_hourly = df_full.resample('H').mean()
    output_file = f"{country_code}_generation_{start_date.date()}_to_{end_date.date()}.xlsx"
    df_hourly.to_excel(output_file)
    print(f"Data saved to {output_file}")
else:
    print("No data fetched.")
