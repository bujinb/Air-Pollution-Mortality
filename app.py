import streamlit as st
import pandas as pd

st.title("Air Pollution Mortality Estimator (Preprocessed)")
st.write("This tool shows how many additional deaths are estimated if PM₂.₅ increases to selected levels (based on precomputed results).")

# Load preprocessed CSV
@st.cache_data
def load_data():
    return pd.read_csv("results_mortality_scenario.csv")

df = load_data()

# Slider for PM2.5 scenario (8 to 12)
pm25_level = st.slider("Select PM₂.₅ concentration (μg/m³)", min_value=8, max_value=12, value=12)

# Make sure the column name is a string
col = str(pm25_level)

# Check if that column exists
if col not in df.columns:
    st.error(f"No data available for PM₂.₅ = {pm25_level} μg/m³")
else:
    total_deaths = int(df[col].sum())
    st.metric(label=f"Estimated additional deaths at {pm25_level} μg/m³", value=f"{total_deaths:,}")

    # Optional: show detailed table
    if st.checkbox("Show detailed data"):
        st.dataframe(df[["fips", "TotalPop", "MortalityR", "pred_wght", col]].rename(columns={col: "ExcessDeaths"}))