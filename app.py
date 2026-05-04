import streamlit as st
from modules.flood_module import *

st.title("🌊 Flood Intelligence System")

if "result" not in st.session_state:
    st.session_state.result = None

mode = st.radio("Select Level", ["district", "state"])
name = st.text_input("Enter Name", "CACHAR")
date = st.date_input("Select Date")

if st.button("Run Analysis"):
    with st.spinner("Processing..."):
        st.session_state.result = get_flood_map(name, str(date), mode)

if st.session_state.result:

    m, area, flood, water, region, actual = st.session_state.result

    if actual == "No Data":
        st.error("No data available")
        st.stop()

    st.success(f"Satellite Date: {actual}")
    st.success(f"Flood Area: {round(area,2)} ha")

    st.components.v1.html(m._repr_html_(), height=600)

    if st.button("Generate PNG"):
        png = generate_png(flood, water, region, name, actual)
        with open(png, "rb") as f:
            st.download_button("Download PNG", f, "map.png", "image/png")

    if st.button("Generate PDF"):
        pdf = generate_pdf(name, str(date), actual, area, "map.png")
        with open(pdf, "rb") as f:
            st.download_button("Download PDF", f, "report.pdf", "application/pdf")

if st.button("🔄 Refresh"):
    st.session_state.result = None