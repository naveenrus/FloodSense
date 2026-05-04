# 🌊 FloodSense: SAR-Based Flood Mapping System

FloodSense detects flood-affected areas using Sentinel-1 SAR data and Google Earth Engine.

## Features

* Flood detection using SAR change detection
* Interactive map (Streamlit + Folium)
* Flood area calculation (hectares)
* PDF report generation

## Run

pip install -r requirements.txt
earthengine authenticate
streamlit run app.py

## Output

* Flood map (PNG)
* Flood report (PDF)

## Disclaimer

Results depend on SAR data availability and environmental conditions.
