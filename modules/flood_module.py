import ee
import folium
from datetime import datetime, timedelta
import requests
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from geopy.distance import geodesic
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet
import streamlit as st

# ---------------- INIT ----------------
@st.cache_resource
def init_ee():
    ee.Initialize(project='rare-host-474609-d8')

# ---------------- REGION ----------------
def get_region(name, mode):
    fc = ee.FeatureCollection(
        "projects/rare-host-474609-d8/assets/INDIA_DIST_BDY__UPDATED__2023_LCC"
    )
    if mode == "district":
        return fc.filter(ee.Filter.eq("District", name.upper())).geometry()
    else:
        return fc.filter(ee.Filter.eq("STATE", name.upper())).geometry()

# ---------------- DATE ----------------
def find_date(region, user_date):
    for i in range(15):
        d = user_date - timedelta(days=i)
        col = ee.ImageCollection("COPERNICUS/S1_GRD") \
            .filterBounds(region) \
            .filterDate(d.strftime("%Y-%m-%d"),
                        (d + timedelta(days=1)).strftime("%Y-%m-%d"))
        if col.size().getInfo() > 0:
            return d.strftime("%Y-%m-%d")
    return None

# ---------------- SAR ----------------
def get_sar(region, start, end):
    return ee.ImageCollection("COPERNICUS/S1_GRD") \
        .filterBounds(region) \
        .filterDate(start, end) \
        .select(['VV','VH']).median()

# ---------------- WATER ----------------
def get_water(img):
    vv = img.select('VV')
    vh = img.select('VH')

    water = vv.lt(-17).And(vh.lt(-20))
    water = water.focal_max(20, 'circle', 'meters')
    water = water.focal_min(10, 'circle', 'meters')

    connected = water.connectedPixelCount(100, True)
    return water.updateMask(connected.gte(30))

# ---------------- SAFE IMAGE FETCH ----------------
def safe_gee_image(image, region, palette, dim):

    try:
        url = image.getThumbURL({
            "region": region,
            "dimensions": dim,
            "palette": palette
        })

        res = requests.get(url)

        if res.status_code != 200 or "html" in res.headers.get("Content-Type",""):
            return None

        return Image.open(BytesIO(res.content)).convert("RGBA")

    except:
        return None

# ---------------- MAIN ----------------
@st.cache_data
def get_flood_map(name, date, mode):

    init_ee()
    region = get_region(name, mode)

    user_date = datetime.strptime(date, "%Y-%m-%d")
    actual = find_date(region, user_date)

    if actual is None:
        return None, 0, None, None, region, "No Data"

    d = datetime.strptime(actual, "%Y-%m-%d")

    before = get_sar(region,
        (d - timedelta(days=60)).strftime("%Y-%m-%d"),
        (d - timedelta(days=10)).strftime("%Y-%m-%d"))

    after = get_sar(region,
        actual,
        (d + timedelta(days=3)).strftime("%Y-%m-%d"))

    water_before = get_water(before)
    water_after = get_water(after)

    flood = water_after.subtract(water_before).gt(0)
    flood = flood.updateMask(flood).clip(region)

    area = flood.multiply(ee.Image.pixelArea()).reduceRegion(
        ee.Reducer.sum(), region, 60, maxPixels=1e9
    )

    flood_area = area.getInfo().get('VV', 0) / 10000

    center = region.centroid().coordinates().getInfo()[::-1]

    m = folium.Map(location=center, zoom_start=7)
    folium.TileLayer('OpenStreetMap').add_to(m)

    folium.TileLayer(
        tiles=flood.selfMask().getMapId({"palette":["red"]})["tile_fetcher"].url_format,
        attr="GEE", name="Flood"
    ).add_to(m)

    folium.TileLayer(
        tiles=water_before.selfMask().getMapId({"palette":["blue"]})["tile_fetcher"].url_format,
        attr="GEE", name="Water"
    ).add_to(m)

    folium.GeoJson(region.getInfo()).add_to(m)
    folium.LayerControl().add_to(m)

    return m, flood_area, flood, water_before, region, actual

# ---------------- PNG ----------------
def generate_png(flood, water, region, name, date):

    coords = region.bounds().coordinates().getInfo()[0]
    width = abs(coords[1][0] - coords[0][0])

    dim = 512 if width > 5 else 1024

    water_img = safe_gee_image(water, region, ["white","blue"], dim)
    flood_img = safe_gee_image(flood, region, ["white","red"], dim)
    boundary = ee.Image().byte().paint(region, 1, 2)
    boundary_img = safe_gee_image(boundary, region, ["black"], dim)
    mask = ee.Image.constant(1).clip(region)
    mask_img = safe_gee_image(mask, region, ["white"], dim)

    if water_img is None or flood_img is None:
        raise Exception("❌ Image fetch failed (area too large)")

    combined = Image.alpha_composite(water_img, flood_img)

    if boundary_img:
        combined = Image.alpha_composite(combined, boundary_img)

    if mask_img:
        combined.putalpha(mask_img.convert("L"))

    # SCALE
    width_km = geodesic((coords[0][1], coords[0][0]),
                        (coords[1][1], coords[1][0])).km

    scale_km = 20 if width_km > 100 else 10 if width_km > 50 else 5
    scale_frac = scale_km / width_km

    # PLOT
    fig = plt.figure(figsize=(10,10))

    ax = fig.add_axes([0.05,0.05,0.7,0.9])
    ax.imshow(combined)
    ax.axis("off")

    fig.suptitle(f"{name} Flood Map\nDate: {date}")

    # legend
    legend_ax = fig.add_axes([0.75,0.6,0.2,0.2])
    legend_ax.axis("off")
    legend_ax.legend(handles=[
        mpatches.Patch(color='blue', label='Permanent Water'),
        mpatches.Patch(color='red', label='Flood')
    ])

    # north
    north_ax = fig.add_axes([0.8,0.4,0.1,0.2])
    north_ax.axis("off")
    north_ax.annotate('N', xy=(0.5,0.9), xytext=(0.5,0.2),
                      arrowprops=dict(facecolor='black'))

    # scale
    ax.plot([0.05,0.05+scale_frac],[0.05,0.05],
            transform=ax.transAxes, linewidth=4)
    ax.text(0.05+scale_frac/2,0.01,f"{scale_km} km",
            transform=ax.transAxes, ha='center')

    # metadata
    fig.text(0.75,0.25,
        "Satellite: Sentinel-1 SAR\nMethod: Change Detection",
        fontsize=9, bbox=dict(facecolor='white', alpha=0.7))

    plt.savefig("map.png", dpi=300, bbox_inches='tight')
    plt.close()

    return "map.png"

# ---------------- PDF ----------------
def generate_pdf(name, user_date, sat_date, area, img):

    doc = SimpleDocTemplate("report.pdf")
    styles = getSampleStyleSheet()

    content = [
        Paragraph(f"<b>{name} Flood Report</b>", styles['Title']),
        Spacer(1,10),
        Paragraph(f"""
        Satellite Date: {sat_date}<br/>
        User Date: {user_date}<br/>
        Flood Area: {round(area,2)} ha
        """, styles['Normal']),
        Spacer(1,20),
        RLImage(img, width=400, height=400)
    ]

    doc.build(content)
    return "report.pdf"