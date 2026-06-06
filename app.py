"""HABRI and HABRI-GRID Streamlit dashboard."""

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

from src.combined import load_joint_standardized_habri
from src.config import (
    COUNTY_FIPS,
    CRS_WGS84,
    DATA_PROCESSED,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_INFRA_FRAGILITY,
)
from src.habri_grid import available_scenarios, build_habri_grid_bundle

st.set_page_config(
    page_title="HABRI / HABRI-GRID",
    page_icon=":satellite:",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_habri(dataset_mode: str) -> gpd.GeoDataFrame:
    if dataset_mode == "North Carolina baseline":
        path = DATA_PROCESSED / "habri_composite.gpkg"
        if not path.exists():
            st.error(f"Baseline data not found: {path}\nRun Notebook 04 to generate outputs.")
            st.stop()
        gdf = gpd.read_file(path)
        gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
        gdf["county_fips"] = gdf["GEOID"].str[2:5]
        gdf["state_fips"] = gdf["GEOID"].str[:2]
        gdf["state_abbr"] = "NC"
        gdf["state_name"] = "North Carolina"
        fips_to_name = {value: key for key, value in COUNTY_FIPS.items()}
        gdf["county_name"] = gdf["county_fips"].map(fips_to_name).fillna("Unknown")
        gdf["county_label"] = gdf["county_name"]
        return gdf.to_crs(CRS_WGS84)

    path = DATA_PROCESSED / "habri_nc_tn_standardized.gpkg"
    gdf = gpd.read_file(path) if path.exists() else load_joint_standardized_habri()
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
    if "county_name" not in gdf.columns:
        gdf["county_name"] = "Unknown"
    if "state_abbr" not in gdf.columns:
        gdf["state_abbr"] = gdf["GEOID"].str[:2].map({"37": "NC", "47": "TN"}).fillna("NA")
    if "state_name" not in gdf.columns:
        gdf["state_name"] = gdf["state_abbr"].map(
            {"NC": "North Carolina", "TN": "Tennessee"}
        ).fillna("Unknown")
    gdf["county_label"] = gdf["county_name"] + ", " + gdf["state_abbr"]
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


@st.cache_data
def load_habri_grid_bundle_cached(scenario_key: str, budget_musd: float):
    return build_habri_grid_bundle(
        processed_dir=DATA_PROCESSED,
        scenario_key=scenario_key,
        budget_musd=budget_musd,
    )


def _render_folium_map(
    geodata: gpd.GeoDataFrame,
    value_column: str,
    caption: str,
    tooltip_lines: list[tuple[str, str]],
    colors: list[str],
) -> None:
    minx, miny, maxx, maxy = geodata.total_bounds
    map_center = [float((miny + maxy) / 2), float((minx + maxx) / 2)]
    fmap = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
    colormap = folium.LinearColormap(
        colors=colors,
        vmin=float(geodata[value_column].min()),
        vmax=float(geodata[value_column].max()),
        caption=caption,
    )

    for row in geodata.itertuples():
        tooltip = "".join(f"{label}: {getattr(row, field)}<br>" for label, field in tooltip_lines)
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _feature, score=getattr(row, value_column): {
                "fillColor": colormap(score) if pd.notna(score) else "#cccccc",
                "color": "none",
                "fillOpacity": 0.78,
            },
            tooltip=folium.Tooltip(tooltip),
        ).add_to(fmap)

    colormap.add_to(fmap)
    st_folium(fmap, width=None, height=580, returned_objects=[])


def render_habri_grid_pilot() -> None:
    scenario_lookup = {scenario.label: scenario.key for scenario in available_scenarios()}
    scenario_label = st.sidebar.selectbox(
        "Hazard scenario",
        options=list(scenario_lookup.keys()),
        index=0,
    )
    scenario_key = scenario_lookup[scenario_label]
    budget_musd = st.sidebar.slider("Mitigation budget (USD millions)", 5, 40, 20, 5)

    bundle = load_habri_grid_bundle_cached(scenario_key, float(budget_musd))
    forecast = bundle.risk_forecast.copy()

    county_options = sorted(forecast["county_label"].unique())
    selected_counties = st.sidebar.multiselect(
        "Filter pilot counties",
        options=county_options,
        default=[],
        placeholder="All pilot counties",
    )
    selected_profiles = st.sidebar.multiselect(
        "Filter risk profiles",
        options=sorted(forecast["risk_profile"].dropna().unique()),
        default=[],
        placeholder="All profiles",
    )
    selected_bands = st.sidebar.multiselect(
        "Filter forecast bands",
        options=["Very High", "High", "Moderate", "Low", "Very Low"],
        default=[],
        placeholder="All bands",
    )

    filtered = forecast.copy()
    if selected_counties:
        filtered = filtered[filtered["county_label"].isin(selected_counties)]
    if selected_profiles:
        filtered = filtered[filtered["risk_profile"].isin(selected_profiles)]
    if selected_bands:
        filtered = filtered[filtered["forecast_priority_band"].isin(selected_bands)]
    if filtered.empty:
        st.warning("No pilot tracts match the current filters.")
        return

    st.title("HABRI-GRID: Coupled Power + Communications Resilience Pilot")
    st.markdown(
        "Genesis-aligned pilot that treats HABRI as a baseline benchmark and builds a "
        "**public-data asset graph, outage forecast, and mitigation ranking workflow** for "
        "Western North Carolina and Eastern Tennessee."
    )
    st.markdown(
        f"**Scenario:** {filtered['scenario_label'].iloc[0]}  \n"
        f"**Budget:** ${budget_musd}M  \n"
        f"**Pilot scope:** {filtered['pilot_region'].nunique()} regions, {filtered['county_label'].nunique()} counties"
    )

    best_run = bundle.scenario_runs.iloc[0]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pilot tracts", f"{len(filtered):,}")
    col2.metric("Mean outage probability", f"{filtered['outage_probability'].mean():.2%}")
    col3.metric("Highest expected outage", f"{filtered['expected_outage_hours'].max():.1f} hr")
    col4.metric("Top mitigation", best_run["intervention_label"])
    col5.metric("Best outage minutes saved", f"{best_run['outage_minutes_saved']:,.0f}")

    st.markdown("---")

    tab_forecast, tab_scenarios, tab_graph, tab_benchmark = st.tabs(
        ["Forecast Map", "Mitigation Scenarios", "Asset Graph", "Baseline Benchmark"]
    )

    with tab_forecast:
        st.subheader("Scenario Forecast")
        map_metric = st.radio(
            "Color by",
            ["Outage probability", "Expected outage hours", "Priority score"],
            horizontal=True,
        )
        metric_map = {
            "Outage probability": "outage_probability",
            "Expected outage hours": "expected_outage_hours",
            "Priority score": "forecast_priority_score",
        }
        caption_map = {
            "Outage probability": "Outage probability",
            "Expected outage hours": "Expected outage hours",
            "Priority score": "Forecast priority score",
        }
        _render_folium_map(
            filtered,
            value_column=metric_map[map_metric],
            caption=caption_map[map_metric],
            tooltip_lines=[
                ("County", "county_label"),
                ("Profile", "risk_profile"),
                ("HABRI", "HABRI"),
                ("Outage probability", "outage_probability"),
                ("Expected outage hours", "expected_outage_hours"),
                ("Restoration lag hours", "restoration_lag_hours"),
            ],
            colors=["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"],
        )

        st.markdown("**Highest-priority tracts in the selected scenario**")
        priority_table = (
            filtered[
                [
                    "GEOID",
                    "county_label",
                    "risk_profile",
                    "outage_probability",
                    "expected_outage_hours",
                    "restoration_lag_hours",
                    "forecast_priority_score",
                    "forecast_priority_band",
                    "priority_shift_vs_habri",
                ]
            ]
            .sort_values("forecast_priority_score", ascending=False)
            .reset_index(drop=True)
        )
        st.dataframe(
            priority_table.style.background_gradient(
                subset=["outage_probability", "expected_outage_hours", "forecast_priority_score"],
                cmap="YlOrRd",
            ),
            use_container_width=True,
            height=460,
        )

    with tab_scenarios:
        st.subheader("Ranked Mitigation Runs")
        st.markdown(
            "Each intervention is evaluated against the current scenario using the same public-data "
            "pilot graph. The table ranks options by estimated outage minutes saved and reduction "
            "in critical-community exposure."
        )

        scenario_runs = bundle.scenario_runs.copy()
        st.dataframe(
            scenario_runs[
                [
                    "scenario_rank",
                    "intervention_label",
                    "budget_musd",
                    "target_tract_count",
                    "target_counties",
                    "outage_minutes_saved",
                    "critical_exposure_reduction",
                    "mean_probability_delta",
                    "mean_restoration_hours_saved",
                ]
            ].style.background_gradient(
                subset=["outage_minutes_saved", "critical_exposure_reduction"],
                cmap="Greens",
            ),
            use_container_width=True,
            height=420,
        )

        top_runs = scenario_runs.head(6)
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.barh(
            top_runs["intervention_label"][::-1],
            top_runs["outage_minutes_saved"][::-1],
            color="#2c7fb8",
            edgecolor="white",
        )
        ax.set_xlabel("Estimated outage minutes saved")
        ax.set_ylabel("")
        ax.spines[["top", "right"]].set_visible(False)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

        top_choice = scenario_runs.iloc[0]
        st.markdown(
            f"**Recommended first move:** {top_choice['intervention_label']}  \n"
            f"Targets {top_choice['target_tract_count']} tracts across {top_choice['target_counties']}.  \n"
            f"Expected mean restoration improvement: {top_choice['mean_restoration_hours_saved']:.2f} hours."
        )

    with tab_graph:
        st.subheader("Asset Graph Diagnostics")
        nodes = bundle.asset_graph_nodes.copy()
        edges = bundle.asset_graph_edges.copy()

        g1, g2, g3 = st.columns(3)
        g1.metric("Graph nodes", f"{len(nodes):,}")
        g2.metric("Graph edges", f"{len(edges):,}")
        g3.metric("Node types", f"{nodes['node_type'].nunique()}")

        node_counts = nodes["node_type"].value_counts().sort_values(ascending=False)
        edge_counts = edges["edge_type"].value_counts().sort_values(ascending=False)
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Node mix**")
            st.dataframe(node_counts.rename("count").to_frame(), use_container_width=True)
        with col_right:
            st.markdown("**Edge mix**")
            st.dataframe(edge_counts.rename("count").to_frame(), use_container_width=True)

        st.markdown("**Top graph chokepoints by PageRank**")
        chokepoints = (
            nodes[
                [
                    "node_id",
                    "node_type",
                    "county_name",
                    "state_abbr",
                    "data_quality",
                    "graph_pagerank",
                    "graph_degree_centrality",
                ]
            ]
            .sort_values("graph_pagerank", ascending=False)
            .head(25)
            .reset_index(drop=True)
        )
        st.dataframe(
            chokepoints.style.background_gradient(
                subset=["graph_pagerank", "graph_degree_centrality"],
                cmap="Blues",
            ),
            use_container_width=True,
        )

    with tab_benchmark:
        st.subheader("Forecast vs. HABRI Baseline")
        st.markdown(
            "The Genesis-aligned forecast is intentionally benchmarked against the original HABRI "
            "ranking so the baseline remains visible as a comparator."
        )

        bench = filtered[
            [
                "GEOID",
                "county_label",
                "HABRI",
                "habri_rank",
                "forecast_priority_score",
                "forecast_rank",
                "priority_shift_vs_habri",
                "risk_profile",
            ]
        ].copy()

        b1, b2, b3 = st.columns(3)
        b1.metric("Median HABRI rank", f"{int(bench['habri_rank'].median())}")
        b2.metric("Median forecast rank", f"{int(bench['forecast_rank'].median())}")
        b3.metric("Largest upward shift", f"{int(bench['priority_shift_vs_habri'].max())}")

        fig2, ax2 = plt.subplots(figsize=(6, 4))
        ax2.scatter(
            bench["HABRI"],
            bench["forecast_priority_score"],
            c=bench["priority_shift_vs_habri"],
            cmap="coolwarm",
            alpha=0.55,
            s=14,
        )
        ax2.set_xlabel("Baseline HABRI score")
        ax2.set_ylabel("HABRI-GRID priority score")
        ax2.spines[["top", "right"]].set_visible(False)
        st.pyplot(fig2, use_container_width=True)
        plt.close(fig2)

        st.markdown("**Tracts elevated by the graph-based scenario forecast**")
        elevated = bench.sort_values("priority_shift_vs_habri", ascending=False).head(20).reset_index(drop=True)
        st.dataframe(
            elevated.style.background_gradient(subset=["priority_shift_vs_habri"], cmap="RdYlGn"),
            use_container_width=True,
        )


def render_habri_baseline() -> None:
    dataset_mode = st.sidebar.radio(
        "Dataset",
        ["North Carolina baseline", "NC + TN standardized"],
        index=0,
    )
    st.sidebar.markdown(
        "**Hazard-Adjusted Broadband Reliability Index**  \n"
        + (
            "North Carolina - 2,660 census tracts"
            if dataset_mode == "North Carolina baseline"
            else "North Carolina + Tennessee - shared standardized scale"
        )
    )
    st.sidebar.markdown("---")

    habri = load_habri(dataset_mode)
    current = load_current() if dataset_mode == "North Carolina baseline" else None
    county_filter_col = "county_label" if dataset_mode == "NC + TN standardized" else "county_name"

    selected_counties = st.sidebar.multiselect(
        "Filter by county",
        options=sorted(habri[county_filter_col].dropna().unique()),
        default=[],
        placeholder="All counties",
    )
    selected_profiles = st.sidebar.multiselect(
        "Filter by risk profile",
        options=sorted(habri["risk_profile"].dropna().unique()) if "risk_profile" in habri.columns else [],
        default=[],
        placeholder="All profiles",
    )
    selected_quintiles = st.sidebar.multiselect(
        "Filter by risk quintile",
        options=["Very High", "High", "Moderate", "Low", "Very Low"],
        default=[],
        placeholder="All quintiles",
    )
    show_towers = st.sidebar.checkbox("Show cellular towers", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"**Index weights**  \n"
        f"- Hazard Exposure: {W_HAZARD_EXPOSURE:.0%}  \n"
        f"- Infra Fragility: {W_INFRA_FRAGILITY:.0%}  \n"
        f"- Coping Capacity: {W_COPING_CAPACITY:.0%}"
    )

    filtered = habri.copy()
    if selected_counties:
        filtered = filtered[filtered[county_filter_col].isin(selected_counties)]
    if selected_profiles and "risk_profile" in filtered.columns:
        filtered = filtered[filtered["risk_profile"].isin(selected_profiles)]
    if selected_quintiles and "HABRI_quintile" in filtered.columns:
        filtered = filtered[filtered["HABRI_quintile"].isin(selected_quintiles)]
    if filtered.empty:
        st.warning("No tracts match the current baseline filters.")
        return

    st.title("HABRI: Hazard-Adjusted Broadband Reliability Index")
    st.markdown(
        (
            "Legacy baseline explorer for the tract-level HABRI index. Scores range from **0-1** "
            "(1 = highest risk)."
            if dataset_mode == "North Carolina baseline"
            else "Shared-scale baseline across North Carolina and Tennessee. Scores are jointly "
            "standardized on a **0-1** scale."
        )
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Tracts shown", f"{len(filtered):,}")
    col2.metric("Mean HABRI", f"{filtered['HABRI'].mean():.3f}")
    col3.metric("Highest risk", f"{filtered['HABRI'].max():.3f}")
    col4.metric(
        "High/Very High",
        f"{(filtered['HABRI_quintile'].isin(['High', 'Very High'])).sum():,}"
        if "HABRI_quintile" in filtered.columns
        else "-",
    )
    col5.metric(
        "Current version" if dataset_mode == "North Carolina baseline" else "Scale",
        (
            sorted(DATA_PROCESSED.glob("habri_current_*.gpkg"))[-1].stem.replace("habri_current_", "")
            if sorted(DATA_PROCESSED.glob("habri_current_*.gpkg"))
            else "Baseline only"
        )
        if dataset_mode == "North Carolina baseline"
        else "NC+TN joint",
    )

    st.markdown("---")
    tab_map, tab_table, tab_charts, tab_compare = st.tabs(
        ["Map", "Data Table", "Charts", "Baseline vs Current"]
    )

    with tab_map:
        st.subheader("Baseline HABRI Map")
        map_mode = st.radio(
            "Color by",
            ["HABRI score", "Risk profile", "Quintile"],
            horizontal=True,
        )

        if map_mode == "HABRI score":
            _render_folium_map(
                filtered,
                value_column="HABRI",
                caption="HABRI score",
                tooltip_lines=[
                    ("County", "county_label"),
                    ("State", "state_name"),
                    ("HABRI", "HABRI"),
                    ("Profile", "risk_profile"),
                ],
                colors=["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
            )
        else:
            color_lookup = {
                "Dual-Risk": "#d62728",
                "Power-Dependent": "#1f77b4",
                "Transport-Fragile": "#9467bd",
                "Very High": "#67000d",
                "High": "#cb181d",
                "Moderate": "#fc4e2a",
                "Low": "#feb24c",
                "Very Low": "#ffffb2",
            }
            minx, miny, maxx, maxy = filtered.total_bounds
            fmap = folium.Map(
                location=[float((miny + maxy) / 2), float((minx + maxx) / 2)],
                zoom_start=7,
                tiles="CartoDB positron",
            )
            color_column = "risk_profile" if map_mode == "Risk profile" else "HABRI_quintile"
            for row in filtered.itertuples():
                fill = color_lookup.get(str(getattr(row, color_column)), "#cccccc")
                folium.GeoJson(
                    row.geometry.__geo_interface__,
                    style_function=lambda _feature, fill_color=fill: {
                        "fillColor": fill_color,
                        "color": "none",
                        "fillOpacity": 0.76,
                    },
                    tooltip=folium.Tooltip(
                        f"County: {row.county_label}<br>"
                        f"State: {row.state_name}<br>"
                        f"{color_column}: {getattr(row, color_column)}<br>"
                        f"HABRI: {row.HABRI:.3f}"
                    ),
                ).add_to(fmap)

            if show_towers and dataset_mode == "North Carolina baseline":
                tower_path = DATA_PROCESSED.parent / "raw" / "hifld_cellular_towers.geojson"
                if tower_path.exists():
                    towers = gpd.read_file(tower_path)
                    for tower in towers.itertuples():
                        folium.CircleMarker(
                            location=[tower.geometry.y, tower.geometry.x],
                            radius=2,
                            color="#2ca02c",
                            fill=True,
                            fill_opacity=0.6,
                            tooltip="Cell tower",
                        ).add_to(fmap)

            st_folium(fmap, width=None, height=580, returned_objects=[])

    with tab_table:
        st.subheader("Tract-Level Baseline Scores")
        display_cols = [
            column
            for column in [
                "GEOID",
                "state_abbr",
                "county_label",
                "HABRI",
                "HABRI_quintile",
                "H_E",
                "I_F",
                "C_C",
                "risk_profile",
                "tower_density_norm",
                "latency_norm",
                "road_fragility",
                "power_grid_norm",
            ]
            if column in filtered.columns
        ]
        table_df = filtered[display_cols].sort_values("HABRI", ascending=False).reset_index(drop=True)
        st.dataframe(
            table_df.style.background_gradient(subset=["HABRI"], cmap="YlOrRd"),
            use_container_width=True,
            height=500,
        )
        st.download_button(
            label="Download CSV",
            data=table_df.to_csv(index=False).encode(),
            file_name="habri_filtered.csv",
            mime="text/csv",
        )

    with tab_charts:
        st.subheader("Baseline Distribution")
        c1, c2 = st.columns(2)

        with c1:
            fig, ax = plt.subplots(figsize=(5, 3.5))
            filtered["HABRI"].hist(bins=40, ax=ax, color="#cb181d", edgecolor="white", linewidth=0.4)
            ax.axvline(filtered["HABRI"].mean(), color="black", linestyle="--", linewidth=1)
            ax.set_xlabel("HABRI score")
            ax.set_ylabel("Tracts")
            ax.spines[["top", "right"]].set_visible(False)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        with c2:
            if "risk_profile" in filtered.columns:
                counts = filtered["risk_profile"].value_counts()
                fig2, ax2 = plt.subplots(figsize=(5, 3.5))
                counts.plot(kind="bar", ax=ax2, color=["#1f77b4", "#d62728", "#9467bd"], edgecolor="white")
                ax2.set_xlabel("")
                ax2.set_ylabel("Tracts")
                ax2.tick_params(axis="x", rotation=25)
                ax2.spines[["top", "right"]].set_visible(False)
                st.pyplot(fig2, use_container_width=True)
                plt.close(fig2)

        st.markdown("**Top 20 highest-risk tracts**")
        top20 = (
            filtered[
                [column for column in ["GEOID", "county_label", "HABRI", "H_E", "I_F", "C_C", "risk_profile"] if column in filtered.columns]
            ]
            .nlargest(20, "HABRI")
            .reset_index(drop=True)
        )
        st.dataframe(
            top20.style.background_gradient(subset=["HABRI", "H_E", "I_F", "C_C"], cmap="YlOrRd"),
            use_container_width=True,
        )

    with tab_compare:
        st.subheader("Baseline vs Current-Conditions Comparison")
        if dataset_mode != "North Carolina baseline":
            st.info("Current-conditions comparison is only available for the NC baseline layer.")
        elif current is None:
            st.info(
                "No current-conditions layer found in `data/processed/`. "
                "Run `scripts/update_ookla_quarterly.py` to generate a versioned update."
            )
        else:
            current_tag = sorted(DATA_PROCESSED.glob("habri_current_*.gpkg"))[-1].stem.replace(
                "habri_current_", ""
            )
            current_clean = current[["GEOID", "HABRI"]].copy().rename(columns={"HABRI": f"HABRI_{current_tag}"})
            compare = filtered[["GEOID", "county_name", "HABRI", "risk_profile"]].merge(
                current_clean, on="GEOID", how="inner"
            )
            compare["HABRI_delta"] = compare[f"HABRI_{current_tag}"] - compare["HABRI"]

            k1, k2, k3 = st.columns(3)
            k1.metric("Mean delta", f"{compare['HABRI_delta'].mean():+.4f}")
            k2.metric("Improved", f"{(compare['HABRI_delta'] < -0.01).sum():,}")
            k3.metric("Worsened", f"{(compare['HABRI_delta'] > 0.01).sum():,}")

            fig3, ax3 = plt.subplots(figsize=(6, 4))
            ax3.scatter(compare["HABRI"], compare[f"HABRI_{current_tag}"], alpha=0.35, s=8, c=compare["HABRI_delta"], cmap="RdBu_r")
            bounds = [
                min(compare["HABRI"].min(), compare[f"HABRI_{current_tag}"].min()) - 0.02,
                max(compare["HABRI"].max(), compare[f"HABRI_{current_tag}"].max()) + 0.02,
            ]
            ax3.plot(bounds, bounds, "k--", linewidth=0.8)
            ax3.set_xlabel("Baseline HABRI")
            ax3.set_ylabel(f"HABRI ({current_tag})")
            ax3.spines[["top", "right"]].set_visible(False)
            st.pyplot(fig3, use_container_width=True)
            plt.close(fig3)

            st.dataframe(
                compare.assign(abs_delta=compare["HABRI_delta"].abs())
                .nlargest(20, "abs_delta")
                .drop(columns="abs_delta")
                .reset_index(drop=True)
                .style.background_gradient(subset=["HABRI_delta"], cmap="RdBu_r"),
                use_container_width=True,
            )


st.sidebar.title("HABRI / HABRI-GRID")
product_mode = st.sidebar.radio(
    "Product mode",
    ["HABRI-GRID pilot", "HABRI baseline explorer"],
    index=0,
)
st.sidebar.markdown("---")

if product_mode == "HABRI-GRID pilot":
    render_habri_grid_pilot()
else:
    render_habri_baseline()
