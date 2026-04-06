"""HABRI Streamlit Dashboard — interactive explorer for the Hazard-Adjusted Broadband Reliability Index."""

from __future__ import annotations

import sys
from pathlib import Path

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CRS_WGS84,
    DATA_PROCESSED,
    COUNTY_FIPS,
    W_HAZARD_EXPOSURE,
    W_INFRA_FRAGILITY,
    W_COPING_CAPACITY,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="HABRI Dashboard",
    page_icon=":satellite:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_habri() -> gpd.GeoDataFrame:
    path = DATA_PROCESSED / "habri_composite.gpkg"
    if not path.exists():
        st.error(f"Baseline data not found: {path}\nRun Notebook 04 to generate outputs.")
        st.stop()
    gdf = gpd.read_file(path)
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
    gdf["county_fips"] = gdf["GEOID"].str[2:5]
    gdf["state_fips"] = gdf["GEOID"].str[:2]
    # Build county name lookup from FIPS
    fips_to_name = {v: k for k, v in COUNTY_FIPS.items()}
    gdf["county_name"] = gdf["county_fips"].map(fips_to_name).fillna("Unknown")
    return gdf.to_crs(CRS_WGS84)


@st.cache_data
def load_current() -> gpd.GeoDataFrame | None:
    candidates = sorted(DATA_PROCESSED.glob("habri_current_*.gpkg"))
    if not candidates:
        return None
    latest = candidates[-1]
    gdf = gpd.read_file(latest)
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
    return gdf.to_crs(CRS_WGS84)


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("HABRI Explorer")
st.sidebar.markdown(
    "**Hazard-Adjusted Broadband Reliability Index**  \n"
    "North Carolina — 2,660 census tracts"
)
st.sidebar.markdown("---")

habri = load_habri()
current = load_current()

# County filter
all_counties = sorted(habri["county_name"].dropna().unique())
selected_counties = st.sidebar.multiselect(
    "Filter by county",
    options=all_counties,
    default=[],
    placeholder="All counties",
)

# Risk profile filter
all_profiles = sorted(habri["risk_profile"].dropna().unique()) if "risk_profile" in habri.columns else []
selected_profiles = st.sidebar.multiselect(
    "Filter by risk profile",
    options=all_profiles,
    default=[],
    placeholder="All profiles",
)

# Quintile filter
all_quintiles = ["Very High", "High", "Moderate", "Low", "Very Low"]
existing_quintiles = [q for q in all_quintiles if q in habri.get("HABRI_quintile", pd.Series()).values]
selected_quintiles = st.sidebar.multiselect(
    "Filter by risk quintile",
    options=all_quintiles,
    default=[],
    placeholder="All quintiles",
)

# Layer toggle
show_towers = st.sidebar.checkbox("Show cellular towers", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**Index weights**  \n"
    f"- Hazard Exposure: {W_HAZARD_EXPOSURE:.0%}  \n"
    f"- Infra Fragility: {W_INFRA_FRAGILITY:.0%}  \n"
    f"- Coping Capacity: {W_COPING_CAPACITY:.0%}"
)

# ── Apply filters ─────────────────────────────────────────────────────────────

filtered = habri.copy()
if selected_counties:
    filtered = filtered[filtered["county_name"].isin(selected_counties)]
if selected_profiles and "risk_profile" in filtered.columns:
    filtered = filtered[filtered["risk_profile"].isin(selected_profiles)]
if selected_quintiles and "HABRI_quintile" in filtered.columns:
    filtered = filtered[filtered["HABRI_quintile"].isin(selected_quintiles)]

# ── Header ────────────────────────────────────────────────────────────────────

st.title("HABRI: Hazard-Adjusted Broadband Reliability Index")
st.markdown(
    "Composite risk index identifying NC communities most vulnerable to broadband outages "
    "during natural disasters. Score range **0–1** (1 = highest risk)."
)

# ── Summary KPIs ──────────────────────────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Tracts shown", f"{len(filtered):,}")
col2.metric("Mean HABRI", f"{filtered['HABRI'].mean():.3f}")
col3.metric("Highest risk", f"{filtered['HABRI'].max():.3f}")
col4.metric(
    "High/Very High",
    f"{(filtered['HABRI_quintile'].isin(['High','Very High'])).sum():,}"
    if "HABRI_quintile" in filtered.columns else "—",
)
col5.metric(
    "Current version",
    sorted(DATA_PROCESSED.glob("habri_current_*.gpkg"))[-1].stem.replace("habri_current_", "")
    if sorted(DATA_PROCESSED.glob("habri_current_*.gpkg")) else "Baseline only",
)

st.markdown("---")

# ── Main tabs ─────────────────────────────────────────────────────────────────

tab_map, tab_table, tab_charts, tab_compare = st.tabs(
    ["Map", "Data Table", "Charts", "Baseline vs Current"]
)

# ── Tab 1: Map ────────────────────────────────────────────────────────────────

with tab_map:
    st.subheader("HABRI Score Map")

    PROFILE_COLORS = {
        "Dual-Risk": "#d62728",
        "Power-Dependent": "#1f77b4",
        "Transport-Fragile": "#9467bd",
    }
    QUINTILE_COLORS = {
        "Very High": "#67000d",
        "High": "#cb181d",
        "Moderate": "#fc4e2a",
        "Low": "#feb24c",
        "Very Low": "#ffffb2",
    }

    map_mode = st.radio(
        "Color by",
        ["HABRI score", "Risk profile", "Quintile"],
        horizontal=True,
    )

    center = filtered.geometry.centroid.to_crs(CRS_WGS84)
    map_center = [center.y.mean(), center.x.mean()]
    m = folium.Map(location=map_center, zoom_start=7, tiles="CartoDB positron")

    if map_mode == "HABRI score":
        score_col = "HABRI"
        colormap = folium.LinearColormap(
            colors=["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
            vmin=filtered[score_col].min(),
            vmax=filtered[score_col].max(),
            caption="HABRI Score",
        )
        for _, row in filtered.iterrows():
            if row.geometry is None:
                continue
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda feat, score=row[score_col]: {
                    "fillColor": colormap(score) if pd.notna(score) else "#cccccc",
                    "color": "none",
                    "fillOpacity": 0.75,
                },
                tooltip=folium.Tooltip(
                    f"<b>{row.get('county_name', '')}</b><br>"
                    f"GEOID: {row['GEOID']}<br>"
                    f"HABRI: {row['HABRI']:.3f}<br>"
                    f"Profile: {row.get('risk_profile', 'N/A')}"
                ),
            ).add_to(m)
        colormap.add_to(m)

    elif map_mode == "Risk profile" and "risk_profile" in filtered.columns:
        for _, row in filtered.iterrows():
            if row.geometry is None:
                continue
            color = PROFILE_COLORS.get(row.get("risk_profile", ""), "#888888")
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda feat, c=color: {
                    "fillColor": c,
                    "color": "none",
                    "fillOpacity": 0.7,
                },
                tooltip=folium.Tooltip(
                    f"<b>{row.get('county_name', '')}</b><br>"
                    f"Profile: {row.get('risk_profile', 'N/A')}<br>"
                    f"HABRI: {row['HABRI']:.3f}"
                ),
            ).add_to(m)

        for profile, color in PROFILE_COLORS.items():
            folium.Marker(
                [0, 0], icon=folium.DivIcon(html=f'<div style="display:none">{profile}</div>')
            ).add_to(m)

    else:  # Quintile
        for _, row in filtered.iterrows():
            if row.geometry is None:
                continue
            quintile = row.get("HABRI_quintile", "")
            color = QUINTILE_COLORS.get(str(quintile), "#cccccc")
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda feat, c=color: {
                    "fillColor": c,
                    "color": "none",
                    "fillOpacity": 0.75,
                },
                tooltip=folium.Tooltip(
                    f"<b>{row.get('county_name', '')}</b><br>"
                    f"Quintile: {quintile}<br>"
                    f"HABRI: {row['HABRI']:.3f}"
                ),
            ).add_to(m)

    if show_towers:
        tower_path = DATA_PROCESSED.parent / "raw" / "hifld_cellular_towers.geojson"
        if tower_path.exists():
            towers = gpd.read_file(tower_path)
            for _, t in towers.iterrows():
                if t.geometry:
                    folium.CircleMarker(
                        location=[t.geometry.y, t.geometry.x],
                        radius=2,
                        color="#2ca02c",
                        fill=True,
                        fill_opacity=0.6,
                        tooltip="Cell tower",
                    ).add_to(m)

    st_folium(m, width=None, height=580, returned_objects=[])

# ── Tab 2: Data Table ─────────────────────────────────────────────────────────

with tab_table:
    st.subheader("Tract-Level HABRI Scores")

    display_cols = [
        c for c in [
            "GEOID", "county_name", "HABRI", "HABRI_quintile",
            "H_E", "I_F", "C_C", "risk_profile",
            "tower_density_norm", "latency_norm", "road_fragility",
            "no_vehicle_vuln", "mobile_only_vuln", "disability_vuln",
            "income_vuln", "poverty_vuln",
        ]
        if c in filtered.columns
    ]

    sort_col = st.selectbox("Sort by", options=["HABRI", "H_E", "I_F", "C_C"], index=0)
    sort_asc = st.checkbox("Ascending", value=False)

    table_df = (
        filtered[display_cols]
        .sort_values(sort_col, ascending=sort_asc)
        .reset_index(drop=True)
    )

    st.dataframe(
        table_df.style.background_gradient(subset=["HABRI"], cmap="YlOrRd"),
        use_container_width=True,
        height=500,
    )

    csv_bytes = table_df.to_csv(index=False).encode()
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name="habri_filtered.csv",
        mime="text/csv",
    )

# ── Tab 3: Charts ─────────────────────────────────────────────────────────────

with tab_charts:
    st.subheader("Risk Distribution & Profiles")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**HABRI Score Distribution**")
        fig, ax = plt.subplots(figsize=(5, 3.5))
        filtered["HABRI"].hist(bins=40, ax=ax, color="#cb181d", edgecolor="white", linewidth=0.4)
        ax.axvline(filtered["HABRI"].mean(), color="black", linestyle="--", linewidth=1, label=f"Mean={filtered['HABRI'].mean():.3f}")
        ax.set_xlabel("HABRI Score")
        ax.set_ylabel("Tracts")
        ax.legend(fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with chart_col2:
        if "risk_profile" in filtered.columns:
            st.markdown("**Vulnerability Profiles**")
            profile_counts = filtered["risk_profile"].value_counts()
            PROFILE_COLORS_MPL = {
                "Dual-Risk": "#d62728",
                "Power-Dependent": "#1f77b4",
                "Transport-Fragile": "#9467bd",
            }
            fig2, ax2 = plt.subplots(figsize=(5, 3.5))
            colors = [PROFILE_COLORS_MPL.get(p, "#888") for p in profile_counts.index]
            profile_counts.plot(kind="bar", ax=ax2, color=colors, edgecolor="white")
            ax2.set_xlabel("")
            ax2.set_ylabel("Tracts")
            ax2.tick_params(axis="x", rotation=25)
            ax2.spines[["top", "right"]].set_visible(False)
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)

    st.markdown("**Top 20 Highest-Risk Tracts**")
    top20 = (
        filtered[["GEOID", "county_name", "HABRI", "H_E", "I_F", "C_C", "risk_profile"]]
        .nlargest(20, "HABRI")
        .reset_index(drop=True)
    )
    st.dataframe(
        top20.style.background_gradient(subset=["HABRI", "H_E", "I_F", "C_C"], cmap="YlOrRd"),
        use_container_width=True,
    )

    st.markdown("**County-Level Summary**")
    county_summary = (
        filtered.groupby("county_name")
        .agg(
            tracts=("HABRI", "count"),
            mean_habri=("HABRI", "mean"),
            max_habri=("HABRI", "max"),
            high_risk=("HABRI", lambda x: (x >= x.quantile(0.8)).sum()),
        )
        .sort_values("mean_habri", ascending=False)
        .reset_index()
    )
    st.dataframe(
        county_summary.style.background_gradient(subset=["mean_habri", "max_habri"], cmap="YlOrRd"),
        use_container_width=True,
        height=400,
    )

# ── Tab 4: Baseline vs Current ────────────────────────────────────────────────

with tab_compare:
    st.subheader("Baseline vs. Current-Conditions Comparison")

    if current is None:
        st.info(
            "No current-conditions layer found in `data/processed/`. "
            "Run `scripts/update_ookla_quarterly.py` to generate a versioned update."
        )
    else:
        current_tag = sorted(DATA_PROCESSED.glob("habri_current_*.gpkg"))[-1].stem.replace("habri_current_", "")
        st.markdown(f"Comparing **baseline** (Q3 2024) vs **{current_tag}** Ookla latency update.")

        current_clean = current[["GEOID", "HABRI", "I_F", "latency_norm"]].copy()
        current_clean.columns = ["GEOID", f"HABRI_{current_tag}", f"I_F_{current_tag}", f"latency_{current_tag}"]

        compare = habri[["GEOID", "county_name", "HABRI", "H_E", "I_F", "C_C", "risk_profile"]].merge(
            current_clean, on="GEOID", how="inner"
        )
        compare["HABRI_delta"] = compare[f"HABRI_{current_tag}"] - compare["HABRI"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Mean delta", f"{compare['HABRI_delta'].mean():+.4f}")
        c2.metric("Improved (lower score)", f"{(compare['HABRI_delta'] < -0.01).sum():,}")
        c3.metric("Worsened (higher score)", f"{(compare['HABRI_delta'] > 0.01).sum():,}")

        fig3, ax3 = plt.subplots(figsize=(6, 4))
        ax3.scatter(
            compare["HABRI"],
            compare[f"HABRI_{current_tag}"],
            alpha=0.3,
            s=4,
            c=compare["HABRI_delta"],
            cmap="RdBu_r",
        )
        lim = [
            min(compare["HABRI"].min(), compare[f"HABRI_{current_tag}"].min()) - 0.02,
            max(compare["HABRI"].max(), compare[f"HABRI_{current_tag}"].max()) + 0.02,
        ]
        ax3.plot(lim, lim, "k--", linewidth=0.8, label="No change")
        ax3.set_xlabel("Baseline HABRI")
        ax3.set_ylabel(f"HABRI ({current_tag})")
        ax3.legend(fontsize=8)
        ax3.spines[["top", "right"]].set_visible(False)
        st.pyplot(fig3, use_container_width=True)
        plt.close(fig3)

        st.markdown("**Largest score changes**")
        st.dataframe(
            compare[["GEOID", "county_name", "HABRI", f"HABRI_{current_tag}", "HABRI_delta", "risk_profile"]]
            .assign(abs_delta=compare["HABRI_delta"].abs())
            .nlargest(20, "abs_delta")
            .drop(columns="abs_delta")
            .reset_index(drop=True)
            .style.background_gradient(subset=["HABRI_delta"], cmap="RdBu_r"),
            use_container_width=True,
        )
