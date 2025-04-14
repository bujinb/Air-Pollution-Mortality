import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import streamlit as st

st.title("Air Pollution Mortality Estimator")
st.write("This tool estimates how many more deaths will occur if PM₂.₅ increases.")

# Step 1: Load shapefiles and data
@st.cache_data
def load_data():
    # County shapefile
    county = gpd.read_file('/Users/bujin/Documents/Air-pollution-mortality/nhgis0025_shape-nhgis0025_shapefile_tl2010_us_county_2010/US_county_2010.shp')
    county['GEOID10'] = pd.to_numeric(county['GEOID10'], errors='coerce')
    county = county[['GEOID10', 'geometry']]

    # Grid cell CSV (with lat/lon)
    gridcells_gdf = pd.read_csv('/Users/bujin/Documents/Air-pollution-mortality/LUR2020.csv')
    geometry = [Point(xy) for xy in zip(gridcells_gdf['lon'], gridcells_gdf['lat'])]
    gdf = gpd.GeoDataFrame(gridcells_gdf, geometry=geometry, crs="EPSG:4326")

    # Block groups shapefile
    fips = gpd.read_file('//Users/bujin/Documents/Air-pollution-mortality/cb_2022_us_bg_500k/cb_2022_us_bg_500k.shp')
    fips = fips.to_crs("EPSG:4326")

    # Spatial join: points in polygons
    joined = gpd.sjoin(gdf, fips, how="right", predicate="within")
    joined = joined.dropna()

    # Load census data
    census = pd.read_excel("/Users/bujin/Documents/Air-pollution-mortality/2016census.xlsx")
    census['County Code'] = pd.to_numeric(census['County Code'], errors='coerce')
    census = census.rename(columns={'County Code': 'GEOID10'})
    
    # Merge county geometry with census
    data = pd.merge(county, census, on='GEOID10')
    data = data.drop(columns=['GEOID10', 'County', 'Crude Rate'])
    data = data.rename(columns={'Deaths': 'MortalityR', 'Population': 'TotalPop'})
    data = gpd.GeoDataFrame(data, geometry='geometry')

    # Reproject all to CA CRS
    ca = gpd.read_file('/Users/bujin/Documents/Air-pollution-mortality/OutputFile.shp')
    mycrs = ca.crs
    data = data.to_crs(mycrs)
    joined = joined.to_crs(mycrs)

    # Area calculations
    joined['Grid_area'] = joined.area
    data['FIP_area'] = data.area

    # Overlay
    overlay_gdf = gpd.overlay(joined, data, how='intersection')
    overlay_gdf['intersection_area'] = overlay_gdf.geometry.area
    overlay_gdf['area_ratio'] = overlay_gdf['intersection_area'] / overlay_gdf['FIP_area']

    # Estimate population and mortality
    for col in ['TotalPop', 'MortalityR']:
        overlay_gdf[col] = overlay_gdf['area_ratio'] * overlay_gdf[col]

    # Aggregate by grid cell (use fips or your own grid ID)
    result_df = overlay_gdf.groupby('fips').agg({
        'TotalPop': 'sum',
        'MortalityR': 'sum',
        'pred_wght': 'first'  # keep original PM2.5 weight if it exists
    }).reset_index()

    result_df['MortalityR'] = result_df['MortalityR'] / result_df['TotalPop'] * 100000  # Rate per 100k

    return result_df

# Load processed data
result = load_data()

# Calculate current mean PM2.5 concentration and current deaths
current_mean_concentration = result['pred_wght'].mean()
current_deaths = (result['TotalPop'] * result['MortalityR'] / 100000).sum()

# Display current data
st.write(f"Current mean PM₂.₅ concentration: {current_mean_concentration:.2f} μg/m³")
st.write(f"Current total deaths based on PM₂.₅ concentration: {current_deaths:,.0f}")

# User input: new PM2.5 level
pm25_input = st.slider("Increase PM₂.₅ concentration to (μg/m³)", 5, 20, 12)

# Filter the grid cells where the current concentration is below the selected PM2.5 value
result_filtered = result[result['pred_wght'] < pm25_input]

# Calculate excess mortality for cells with PM2.5 < selected value
result_filtered['ExcessDeaths'] = (
    (np.exp(np.log(1.06) / 10 * (pm25_input - result_filtered['pred_wght'])) - 1)
    * result_filtered['TotalPop'] * result_filtered['MortalityR'] / 100000
)

# Calculate the total excess deaths
total_excess_deaths = int(result_filtered['ExcessDeaths'].sum())

# Display metric
st.metric(label=f"Estimated additional deaths at {pm25_input} μg/m³", value=f"{total_excess_deaths:,}")

# Show table (optional)
if st.checkbox("Show detailed data"):
    st.dataframe(result_filtered[['fips', 'TotalPop', 'MortalityR', 'pred_wght', 'ExcessDeaths']])
