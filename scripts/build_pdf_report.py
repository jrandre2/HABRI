#!/usr/bin/env python3
"""Build the HABRI PDF report from the project outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from PIL import Image
from fpdf import FPDF
from scipy.stats import spearmanr


PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data" / "processed"
OUTPUT = PROJECT / "docs" / "HABRI_Formal_Report.pdf"


@dataclass
class DatasetStats:
    label: str
    n_rows: int
    min_score: float
    max_score: float
    mean_score: float
    sd_score: float
    profile_counts: dict[str, int]
    profile_shares: dict[str, float]


@dataclass
class ValidationMetric:
    rho: float
    p_value: float
    n: int


def load_dataset_stats(path: Path, label: str) -> DatasetStats:
    df = pd.read_csv(path, dtype={"GEOID": str})
    habri = pd.to_numeric(df["HABRI"], errors="coerce").dropna()
    counts = (
        df["risk_profile"].value_counts(dropna=False).to_dict()
        if "risk_profile" in df.columns
        else {}
    )
    shares = (
        df["risk_profile"].value_counts(normalize=True, dropna=False).mul(100).to_dict()
        if "risk_profile" in df.columns
        else {}
    )
    return DatasetStats(
        label=label,
        n_rows=len(df),
        min_score=float(habri.min()),
        max_score=float(habri.max()),
        mean_score=float(habri.mean()),
        sd_score=float(habri.std()),
        profile_counts=counts,
        profile_shares=shares,
    )


def pct(stats: DatasetStats, profile: str) -> str:
    return f"{stats.profile_shares.get(profile, 0.0):.1f}%"


def format_p_value(p_value: float) -> str:
    if pd.isna(p_value):
        return "p = N/A"
    if p_value < 0.001:
        return "p < 0.001"
    return f"p = {p_value:.3f}"


def format_metric(metric: ValidationMetric) -> str:
    return f"rho = {metric.rho:.3f}; {format_p_value(metric.p_value)}; n = {metric.n:,}"


def load_validation_context() -> dict[str, object]:
    from compare_helene_nc_tn import (
        ETN_FIPS_5,
        WNC_FIPS_5,
        load_helene_latency_nc,
        load_helene_latency_tn,
        load_nc,
        load_tn,
    )

    def summarize(x: pd.Series, y: pd.Series) -> ValidationMetric:
        rho, p_value = spearmanr(x, y)
        return ValidationMetric(rho=float(rho), p_value=float(p_value), n=int(len(x)))

    def prep_subset(
        gdf: pd.DataFrame, fips_set: set[str], l3: pd.Series, l4: pd.Series
    ) -> pd.DataFrame:
        sub = gdf[gdf["county_fips"].isin(fips_set)].set_index("GEOID")
        df = sub[["HABRI", "I_F", "risk_profile"]].join(l3.rename("lat_q3")).join(l4.rename("lat_q4")).dropna()
        df["lat_delta"] = df["lat_q4"] - df["lat_q3"]
        return df

    nc = load_nc()
    tn = load_tn()
    nc_l3, nc_l4 = load_helene_latency_nc(nc)
    tn_l3, tn_l4 = load_helene_latency_tn(tn)

    nc_statewide = nc[["GEOID", "HABRI"]].set_index("GEOID").join(
        nc_l3.rename("lat_q3")
    ).join(nc_l4.rename("lat_q4")).dropna()
    nc_statewide["lat_delta"] = nc_statewide["lat_q4"] - nc_statewide["lat_q3"]
    wnc = prep_subset(nc, WNC_FIPS_5, nc_l3, nc_l4)
    etn = prep_subset(tn, ETN_FIPS_5, tn_l3, tn_l4)

    jan_summary_path = DATA / "habri_validation_2026_01_summary.csv"
    jan_summary = pd.read_csv(jan_summary_path)
    jan_habri_abs = jan_summary[
        (jan_summary["left_metric"] == "HABRI")
        & (jan_summary["right_metric"] == "latency_abs_delta_ms_vs_q3_2024")
    ].iloc[0]
    jan_if_abs = jan_summary[
        (jan_summary["left_metric"] == "I_F")
        & (jan_summary["right_metric"] == "latency_abs_delta_ms_vs_q3_2024")
    ].iloc[0]

    wnc_profiles = (
        nc[nc["county_fips"].isin(WNC_FIPS_5)]["risk_profile"]
        .value_counts(normalize=True)
        .mul(100)
        .to_dict()
    )
    etn_profiles = (
        tn[tn["county_fips"].isin(ETN_FIPS_5)]["risk_profile"]
        .value_counts(normalize=True)
        .mul(100)
        .to_dict()
    )

    return {
        "nc_statewide_latency": summarize(nc_statewide["HABRI"], nc_statewide["lat_delta"]),
        "wnc_latency": summarize(wnc["HABRI"], wnc["lat_delta"]),
        "etn_latency": summarize(etn["HABRI"], etn["lat_delta"]),
        "jan_habri_abs": ValidationMetric(
            rho=float(jan_habri_abs["spearman_rho"]),
            p_value=float(jan_habri_abs["p_value"]),
            n=int(jan_habri_abs["n"]),
        ),
        "jan_if_abs": ValidationMetric(
            rho=float(jan_if_abs["spearman_rho"]),
            p_value=float(jan_if_abs["p_value"]),
            n=int(jan_if_abs["n"]),
        ),
        "dirs_county": ValidationMetric(rho=0.236, p_value=0.018, n=100),
        "wnc_dual_risk_pct": float(wnc_profiles.get("Dual-Risk", 0.0)),
        "etn_transport_pct": float(etn_profiles.get("Transport-Fragile", 0.0)),
        "ioda_blackout_hours": 80,
    }


class HABRIReport(FPDF):
    primary = (27, 58, 92)
    accent = (204, 102, 119)
    muted = (105, 105, 105)
    body = (35, 35, 35)
    divider = (198, 206, 214)
    header_fill = (27, 58, 92)
    row_fill = (241, 245, 249)

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.alias_nb_pages()
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(14, 18, 14)

    @property
    def content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    @property
    def cover_block_width(self) -> float:
        return min(158.0, self.content_width - 8)

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(8)
        self.set_font("Times", "I", 8)
        self.set_text_color(*self.muted)
        self.cell(
            0,
            4,
            "Hazard-Adjusted Broadband Reliability Index (HABRI)",
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2)

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_draw_color(*self.divider)
        self.line(self.l_margin, self.h - 14, self.w - self.r_margin, self.h - 14)
        self.set_font("Times", "", 8)
        self.set_text_color(*self.muted)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    def cover_title(self, title: str, subtitle: str) -> None:
        self.add_page()
        self.set_fill_color(*self.primary)
        self.rect(0, 0, self.w, 28, style="F")

        block_w = self.cover_block_width
        block_x = (self.w - block_w) / 2

        self.set_xy(block_x, 46)
        self.set_font("Times", "B", 24)
        self.set_text_color(*self.primary)
        self.multi_cell(block_w, 10.5, title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_x(block_x)
        self.set_font("Times", "", 13)
        self.set_text_color(70, 70, 70)
        self.multi_cell(block_w, 6.2, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")

    def cover_scope(self, lines: list[str]) -> None:
        self.ln(10)
        w = self.cover_block_width
        x = (self.w - w) / 2
        y = self.get_y()
        inner_pad = 8
        line_h = 5.4
        box_h = 11 + len(lines) * line_h
        self.set_draw_color(*self.divider)
        self.rect(x, y, w, box_h)
        self.set_xy(x + inner_pad, y + 4.5)
        self.set_font("Times", "B", 10.5)
        self.set_text_color(*self.primary)
        self.multi_cell(w - inner_pad * 2, 5, "Project scope", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Times", "", 10.5)
        self.set_text_color(*self.body)
        for line in lines:
            self.set_x(x + inner_pad)
            self.multi_cell(w - inner_pad * 2, line_h, line, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

    def centered_text(self, text: str, size: float = 12, style: str = "") -> None:
        block_w = self.cover_block_width
        block_x = (self.w - block_w) / 2
        self.set_x(block_x)
        self.set_font("Times", style, size)
        self.set_text_color(*self.body)
        self.multi_cell(block_w, 5.8, text, align="C", new_x="LMARGIN", new_y="NEXT")

    def section_title(self, title: str) -> None:
        if self.get_y() > self.page_break_trigger - 22:
            self.add_page()
        self.set_font("Times", "B", 17)
        self.set_text_color(*self.primary)
        self.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.divider)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def subsection_title(self, title: str) -> None:
        if self.get_y() > self.page_break_trigger - 16:
            self.add_page()
        self.set_font("Times", "B", 13.2)
        self.set_text_color(*self.primary)
        self.multi_cell(0, 6.5, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def paragraph(self, text: str) -> None:
        self.set_font("Times", "", 10.5)
        self.set_text_color(*self.body)
        self.multi_cell(0, 5.7, text, align="J", new_x="LMARGIN", new_y="NEXT")
        self.ln(1.6)

    def strong_paragraph(self, text: str) -> None:
        self.set_font("Times", "B", 10.6)
        self.set_text_color(*self.body)
        self.multi_cell(0, 5.8, text, align="J", new_x="LMARGIN", new_y="NEXT")
        self.ln(1.6)

    def _line_count(self, width: float, text: str, line_height: float) -> int:
        lines = self.multi_cell(width, line_height, text, dry_run=True, output="LINES")
        return max(1, len(lines))

    def add_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths: list[float],
        body_font_size: float = 8.7,
        line_height: float = 4.5,
    ) -> None:
        def draw_header() -> None:
            self.set_font("Times", "B", 8.7)
            self.set_fill_color(*self.header_fill)
            self.set_text_color(255, 255, 255)
            self.set_x(self.l_margin)
            for width, header in zip(col_widths, headers, strict=True):
                self.cell(width, 7, header, border=1, fill=True, align="C")
            self.ln()

        if self.get_y() > self.page_break_trigger - 18:
            self.add_page()
        draw_header()

        self.set_font("Times", "", body_font_size)
        self.set_text_color(*self.body)
        for row_index, row in enumerate(rows):
            max_lines = 1
            for width, value in zip(col_widths, row, strict=True):
                max_lines = max(
                    max_lines,
                    self._line_count(width - 2, str(value), line_height),
                )
            row_height = max(7.2, max_lines * line_height + 2)
            if self.get_y() + row_height > self.page_break_trigger:
                self.add_page()
                draw_header()
                self.set_font("Times", "", body_font_size)
                self.set_text_color(*self.body)

            y0 = self.get_y()
            self.set_fill_color(*(self.row_fill if row_index % 2 == 0 else (255, 255, 255)))
            for width, value in zip(col_widths, row, strict=True):
                x0 = self.get_x()
                self.rect(x0, y0, width, row_height, style="DF")
                self.set_xy(x0 + 1, y0 + 1)
                self.multi_cell(width - 2, line_height, str(value), new_x="LEFT", new_y="TOP")
                self.set_xy(x0 + width, y0)
            self.set_xy(self.l_margin, y0 + row_height)
        self.ln(3)

    def add_figure(self, filename: str, caption: str, width: float = 172) -> None:
        path = DATA / filename
        if not path.exists():
            self.paragraph(f"[Figure not found: {filename}]")
            return

        with Image.open(path) as image:
            image_height = width * (image.height / image.width)

        self.set_font("Times", "I", 9)
        caption_lines = self._line_count(self.content_width, caption, 4.3)
        needed = image_height + caption_lines * 4.3 + 8
        if self.get_y() + needed > self.page_break_trigger:
            self.add_page()

        x = (self.w - width) / 2
        self.image(str(path), x=x, w=width)
        self.ln(2.5)
        self.set_font("Times", "I", 9)
        self.set_text_color(*self.muted)
        self.multi_cell(0, 4.3, caption, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)


def build_report() -> None:
    nc = load_dataset_stats(DATA / "habri_composite.csv", "North Carolina statewide layer")
    tn = load_dataset_stats(DATA / "habri_tn_composite.csv", "Tennessee statewide layer")
    combined = load_dataset_stats(DATA / "habri_nc_tn_standardized.csv", "NC and TN standardized")
    validation = load_validation_context()

    pdf = HABRIReport()

    pdf.cover_title(
        "Hazard-Adjusted Broadband\nReliability Index (HABRI)",
        "North Carolina and Tennessee statewide analyses with a shared regional planning layer",
    )
    pdf.cover_scope(
        [
            f"North Carolina statewide layer: {nc.n_rows:,} tracts across 100 counties",
            f"Tennessee statewide layer: {tn.n_rows:,} tracts across 95 counties",
            f"Shared North Carolina and Tennessee standardized layer: {combined.n_rows:,} tracts on one map scale",
        ]
    )
    pdf.centered_text("Jesse R. Andrews", size=13)
    pdf.centered_text("Texas Tech University", size=11)
    pdf.ln(6)
    pdf.centered_text("April 2026", size=10.5, style="I")

    pdf.add_page()
    pdf.section_title("Executive Summary")
    pdf.paragraph(
        "Broadband service functions as critical disaster infrastructure. When storms, "
        "flooding, and landslides disrupt communications networks, the resulting loss of "
        "connectivity limits emergency alerts, telehealth, insurance claims, logistics, "
        "and household coordination. The planning problem is not only where hazards occur, "
        "but where hazard exposure, fragile infrastructure, and limited coping capacity "
        "combine to produce prolonged outages."
    )
    pdf.paragraph(
        "This report summarizes the HABRI two-state project: a North Carolina statewide "
        f"layer covering {nc.n_rows:,} census tracts, a Tennessee statewide layer covering "
        f"{tn.n_rows:,} tracts, and a shared North Carolina and Tennessee standardized layer covering "
        f"{combined.n_rows:,} tracts for unified regional mapping. The framework combines "
        "hazard exposure, infrastructure fragility, and coping-capacity deficit using seven "
        "public data inputs for index construction and two additional public sources for "
        "event validation."
    )
    pdf.paragraph(
        f"In North Carolina, HABRI scores range from {nc.min_score:.3f} to {nc.max_score:.3f} "
        f"(mean {nc.mean_score:.3f}, SD {nc.sd_score:.3f}). The statewide profile mix is "
        f"{pct(nc, 'Power-Dependent')} Power-Dependent, {pct(nc, 'Dual-Risk')} Dual-Risk, "
        f"and {pct(nc, 'Transport-Fragile')} Transport-Fragile. These high-risk tracts cluster "
        "in the western mountains and the rural eastern Coastal Plain."
    )
    tn_cluster_note = ""
    if tn.profile_counts.get("Dual-Risk", 0) == 0:
        tn_cluster_note = (
            " In Tennessee, the statewide profile distribution is entirely "
            "split between Power-Dependent and Transport-Fragile communities, with no "
            "standalone Dual-Risk cluster occupying its own statewide class."
        )
    pdf.paragraph(
        f"In Tennessee, HABRI scores range from {tn.min_score:.3f} to {tn.max_score:.3f} "
        f"(mean {tn.mean_score:.3f}, SD {tn.sd_score:.3f}). The statewide profile mix is "
        f"{pct(tn, 'Power-Dependent')} Power-Dependent and {pct(tn, 'Transport-Fragile')} "
        f"Transport-Fragile.{tn_cluster_note}"
    )
    pdf.paragraph(
        f"The shared North Carolina and Tennessee standardized layer spans {combined.n_rows:,} tracts and broadens "
        f"the score range to {combined.min_score:.3f}-{combined.max_score:.3f} on a common "
        "scale. That combined layer is appropriate for one regional planning map, but it is "
        "a second-pass standardization of the two completed statewide layers rather than a full "
        "raw-input interstate recomputation."
    )
    pdf.paragraph(
        "Validation against Hurricane Helene remains strongest in Western North Carolina. "
        "Within the WNC focal counties, pre-storm HABRI correlates with Helene-induced "
        "latency degradation (Spearman rho = -0.295, p < 0.001, n = 130). County mean HABRI "
        "also correlates with FCC-reported cell site outages (rho = 0.236, p = 0.018, n = 100), "
        "and IODA telemetry captured Morris Broadband's complete 80-hour blackout in high-risk "
        "Henderson County. A January 2026 validation layer further indicates "
        "persistent degradation in high-risk NC tracts more than a year after the storm."
    )

    pdf.add_page()
    pdf.section_title("1. Introduction")
    pdf.subsection_title("1.1 The planning problem")
    pdf.paragraph(
        "Disaster broadband outages are uneven. Similar storms produce very different outcomes "
        "across communities because outage risk depends on more than hazard location alone. "
        "Communities differ in terrain, network redundancy, power dependence, access for repair "
        "crews, and household capacity to adapt when primary service fails."
    )
    pdf.paragraph(
        "The operational consequence is straightforward: emergency managers and broadband offices "
        "need tract-level intelligence about where connectivity losses are most likely and where "
        "those losses will be hardest to absorb. A county average or a single hazard layer is too "
        "coarse for that task."
    )
    pdf.subsection_title("1.2 Why a composite index")
    pdf.paragraph(
        "HABRI addresses the interaction problem directly. It combines natural hazard exposure, "
        "infrastructure fragility, and community coping-capacity deficit into one score bounded "
        "between 0 and 1. This lets planners compare neighborhoods, identify recurring profile "
        "types, and match different interventions to different failure mechanisms."
    )
    pdf.subsection_title("1.3 Project scope")
    pdf.paragraph(
        "This report presents HABRI as one two-state planning project spanning North Carolina and "
        "Tennessee. It includes a statewide layer for each state and a shared North Carolina and Tennessee standardized "
        "planning layer for cross-state situational awareness. Together these products support both "
        "within-state decision support and one common regional map across both states."
    )

    pdf.add_page()
    pdf.section_title("2. Data Sources")
    pdf.paragraph(
        "The workflow uses seven public datasets to construct the HABRI layers and two "
        "additional public datasets for validation. The same top-level framework is applied in "
        "both states, with state-specific geometry, infrastructure extracts, and latency tiles."
    )
    pdf.add_table(
        ["Dataset", "Role", "Coverage", "Key variables"],
        [
            ["FEMA NRI v1.20", "Hazard exposure", "NC and TN tracts", "Inland flooding, hurricane, landslide risk"],
            ["Ookla fixed broadband", "Observed network performance", "Quarterly tiles, 2024-2026", "Latency, download/upload speed, test counts"],
            ["HIFLD cellular towers", "Wireless redundancy proxy", "Statewide extracts", "Tower location and tract density"],
            ["HIFLD transmission lines", "Power fragility proxy", "Statewide extracts", "Transmission line density by tract"],
            ["OSM road network", "Repair access proxy", "Statewide drive graphs", "Betweenness centrality and road density"],
            ["ACS 2022 5-year", "Coping capacity", "All tracts", "Income, poverty, disability, vehicle access, internet type"],
            ["FCC Broadband Data Collection", "Adaptive infrastructure weighting", "NC and TN fixed-service tracts", "p_wired share of fixed coverage served by wired technologies"],
            ["FCC DIRS", "Validation", "NC county outages", "Cell site outage percentages during Helene"],
            ["IODA", "Validation", "Three WNC ISPs", "BGP visibility and active probing"],
        ],
        [32, 35, 42, 73],
    )
    pdf.subsection_title("2.1 FEMA National Risk Index")
    pdf.paragraph(
        "FEMA NRI provides tract-level composite risk scores for hazards relevant to communications "
        "infrastructure. HABRI uses inland flooding, hurricane, and landslide risk because those "
        "hazards capture the primary pathways by which fiber, power, and access corridors fail in "
        "the Carolinas and Tennessee."
    )
    pdf.subsection_title("2.2 Ookla fixed broadband performance")
    pdf.paragraph(
        "Ookla fixed-network open data provides the only consistently available, tract-scalable, "
        "time-varying performance measure in this workflow. Q3 2024 serves as the pre-Helene "
        "baseline quarter. Q4 2024 captures the storm quarter, and the NC pipeline carries the "
        "latency refresh forward through Q4 2025 plus a January 2026 validation layer."
    )
    pdf.subsection_title("2.3 Infrastructure and power proxies")
    pdf.paragraph(
        "The infrastructure stack uses HIFLD cellular towers, HIFLD electric transmission lines, "
        "and the statewide OpenStreetMap drive network. Together they approximate wireless "
        "redundancy, power dependence, and the accessibility of repair corridors. The road network "
        "is particularly important because wired plant often follows road rights-of-way in the "
        "mountain counties most affected by Helene."
    )
    pdf.subsection_title("2.4 Coping-capacity and weighting inputs")
    pdf.paragraph(
        "ACS 2022 5-year estimates provide the five coping-capacity indicators. FCC Broadband Data "
        "Collection data is used in both state baselines to estimate tract-level wiredness, allowing "
        "the infrastructure index to shift weight toward roads in wired tracts and toward towers in "
        "wireless-dominant tracts."
    )
    pdf.subsection_title("2.5 Validation sources")
    pdf.paragraph(
        "FCC DIRS provides county-level cellular outage reporting for the Helene activation window, "
        "while Georgia Tech's IODA platform provides ISP-level outage telemetry for the WNC case study. "
        "These sources are independent of the HABRI construction inputs and therefore serve as external "
        "validation checks."
    )

    pdf.add_page()
    pdf.section_title("3. Index Construction Methodology")
    pdf.subsection_title("3.1 Overall architecture")
    pdf.strong_paragraph(
        "HABRI is computed as 0.40 times H_E (Hazard Exposure), 0.35 times I_F (Infrastructure Fragility), and 0.25 times C_C (Coping-Capacity Deficit)."
    )
    pdf.paragraph(
        "The top-level weights are unchanged across North Carolina, Tennessee, and the combined "
        "standardized layer. Hazard exposure remains the largest single driver, infrastructure "
        "fragility determines whether hazards translate into real outages, and coping capacity "
        "modulates how severely households experience the resulting service loss."
    )
    pdf.subsection_title("3.2 Normalization and interpretation scope")
    pdf.paragraph(
        "Each statewide layer uses z-score normalization followed by the standard normal cumulative "
        "distribution function. This maps the mean of the chosen normalization universe to 0.5 and "
        "keeps all component scores in [0, 1]. The critical interpretive point is scope: the North "
        "Carolina layer is normalized within North Carolina, the Tennessee layer is normalized within "
        "Tennessee, and the shared North Carolina and Tennessee layer re-standardizes both statewide layers together so one combined map can "
        "be interpreted on a common scale."
    )
    pdf.subsection_title("3.3 Hazard Exposure (H_E)")
    pdf.add_table(
        ["Hazard type", "NRI column", "Weight", "Rationale"],
        [
            ["Inland flooding", "IFLD_RISKS", "0.40", "Primary driver of infrastructure damage in mountain flood events"],
            ["Hurricane", "HRCN_RISKS", "0.35", "Wind, rain, and prolonged outage conditions"],
            ["Landslide", "LNDS_RISKS", "0.25", "Road and buried-fiber disruption in steep terrain"],
        ],
        [34, 32, 20, 96],
    )
    pdf.subsection_title("3.4 Infrastructure Fragility (I_F)")
    pdf.add_table(
        ["Component", "Metric", "Weight", "Role in outage risk"],
        [
            ["Tower density", "Towers per km^2 (inverted)", "0.15-0.40 adaptive", "Low wireless redundancy increases outage risk"],
            ["Latency", "Median fixed latency", "0.25", "Higher initial latency signals weaker network performance"],
            ["Road fragility", "Betweenness and inverse density", "0.15-0.40 adaptive", "Sparse or critical roads slow repair and often co-locate wired plant"],
            ["Power-grid fragility", "Transmission density (inverted)", "0.20", "Sparse backbone transmission raises outage risk from grid failures"],
        ],
        [34, 38, 32, 78],
    )
    pdf.paragraph(
        "In both statewide layers, FCC BDC p_wired shifts tower and road weights linearly. Wired "
        "tracts lean more heavily on the road component because fiber and cable recovery depends on "
        "corridor access; wireless-dominant tracts lean more heavily on the tower component. Latency "
        "and power-grid weights remain fixed at 0.25 and 0.20, respectively."
    )
    pdf.subsection_title("3.5 Coping-Capacity Deficit (C_C)")
    pdf.add_table(
        ["Indicator", "Direction", "Weight", "Why it matters"],
        [
            ["No-vehicle households", "High = higher risk", "0.20", "Limits travel to functioning service or charging access"],
            ["Mobile-only internet", "High = higher risk", "0.20", "Removes wired fallback when cellular service fails"],
            ["Disability rate", "High = higher risk", "0.20", "Raises dependence on internet-connected services"],
            ["Median household income", "Low = higher risk", "0.20", "Reduces capacity to pay for backup connectivity or power"],
            ["Poverty rate", "High = higher risk", "0.20", "Constrains household adaptation and recovery"],
        ],
        [42, 34, 18, 88],
    )
    pdf.subsection_title("3.6 Missing data and profile assignment")
    pdf.paragraph(
        "Missing values are median-imputed so no tract is dropped from the planning surface. After "
        "the three sub-indices are assembled, k-means clustering is applied to identify interpretable "
        "risk profiles. The profile vocabulary is Power-Dependent, Dual-Risk, and Transport-Fragile "
        "when those classes are occupied in a given statewide run."
    )
    pdf.subsection_title("3.7 Shared North Carolina and Tennessee standardization")
    pdf.paragraph(
        "The combined layer is not a simple append of the two statewide layers. It preserves the "
        "original state-local scores in H_E_state, I_F_state, C_C_state, and HABRI_state, then "
        "re-normalizes the three sub-indices across all combined tracts and recomputes HABRI. This "
        "yields one common planning map while retaining the original within-state interpretation."
    )

    pdf.add_page()
    pdf.section_title("4. Results")
    pdf.subsection_title("4.1 North Carolina statewide layer")
    pdf.paragraph(
        f"The North Carolina statewide layer covers {nc.n_rows:,} tracts. HABRI scores range from "
        f"{nc.min_score:.3f} to {nc.max_score:.3f} with mean {nc.mean_score:.3f} and SD "
        f"{nc.sd_score:.3f}. The statewide profile mix is {pct(nc, 'Power-Dependent')} "
        f"Power-Dependent, {pct(nc, 'Dual-Risk')} Dual-Risk, and {pct(nc, 'Transport-Fragile')} "
        "Transport-Fragile. The highest-risk geographies remain concentrated in the western "
        "mountains and the rural eastern Coastal Plain."
    )
    pdf.add_figure(
        "habri_statewide_4panel.png",
        "Figure 1. North Carolina statewide HABRI and the three component sub-indices across all statewide census tracts.",
        width=178,
    )

    pdf.add_page()
    pdf.subsection_title("4.2 Tennessee statewide layer")
    pdf.paragraph(
        f"The Tennessee statewide layer covers {tn.n_rows:,} tracts. HABRI scores range from "
        f"{tn.min_score:.3f} to {tn.max_score:.3f} with mean {tn.mean_score:.3f} and SD "
        f"{tn.sd_score:.3f}. Tennessee's statewide profile mix is {pct(tn, 'Power-Dependent')} "
        f"Power-Dependent and {pct(tn, 'Transport-Fragile')} Transport-Fragile. This suggests that "
        "Tennessee's statewide risk pattern is driven more by infrastructure access and network "
        "redundancy than by a separate statewide Dual-Risk cluster."
    )
    pdf.add_figure(
        "habri_tn_statewide_4panel.png",
        "Figure 2. Tennessee statewide HABRI and sub-index surfaces. Helene focal counties in the northeast are outlined.",
        width=178,
    )

    pdf.add_page()
    pdf.subsection_title("4.3 East Tennessee regional profile map")
    pdf.paragraph(
        "The regional East Tennessee view expands beyond the far northeast corner to cover the broader "
        "East Tennessee grand division while still outlining the narrower Helene focal counties. This "
        "view is useful for understanding how the Tri-Cities corridor, Knoxville-adjacent counties, "
        "and the mountain counties fit into the same profile landscape."
    )
    pdf.add_figure(
        "habri_tn_profiles.png",
        "Figure 3. East Tennessee vulnerability profile map. The broader regional extent is shown, with the narrower Helene focal counties highlighted.",
        width=176,
    )

    pdf.add_page()
    pdf.subsection_title("4.4 Shared North Carolina and Tennessee standardized layer")
    pdf.paragraph(
        f"The combined standardized layer covers {combined.n_rows:,} tracts and uses a shared "
        f"score range of {combined.min_score:.3f} to {combined.max_score:.3f} (mean "
        f"{combined.mean_score:.3f}, SD {combined.sd_score:.3f}). This wider range is expected: "
        "it reflects both states being re-ranked on one common distribution rather than within "
        "their own separate statewide normalizations."
    )
    pdf.paragraph(
        "This combined layer should be used when planners need one map across the broader Appalachia-"
        "to-Coastal corridor. It should not replace the individual state layers for within-state "
        "validation, because the combined product is a second-pass standardization built from the "
        "completed state outputs."
    )
    pdf.add_figure(
        "habri_nc_tn_standardized.png",
        "Figure 4. Shared North Carolina and Tennessee standardized HABRI layer for cross-state planning and visualization.",
        width=176,
    )

    pdf.add_page()
    pdf.subsection_title("4.5 Cross-state profile comparison")
    pdf.paragraph(
        "The profile mix differs materially across the two states. Tennessee carries a much larger "
        "Transport-Fragile share than North Carolina statewide, while the WNC focal counties retain "
        "a larger Dual-Risk concentration than the Eastern Tennessee focal counties. This matters for "
        "planning because the intervention mix shifts with the profile mix."
    )
    pdf.add_figure(
        "habri_wnc_etn_profiles.png",
        "Figure 5. Profile distribution comparison for NC statewide, WNC focal counties, TN statewide, and ETN focal counties.",
        width=176,
    )

    pdf.add_page()
    pdf.section_title("5. Validation and Recovery Monitoring")
    pdf.paragraph(
        "Hurricane Helene provides the core external validation event for HABRI. Western North "
        "Carolina experienced severe flood and landslide impacts, while Eastern Tennessee offers a "
        "useful comparison area for cross-state context."
    )
    pdf.subsection_title("5.1 Validation framework")
    pdf.paragraph(
        "The Helene validation strategy operates at three levels. First, tract-level Ookla fixed-broadband "
        "latency captures whether higher-risk places experienced larger performance shifts during the storm. "
        "Second, FCC DIRS county reports test whether county mean HABRI aligned with observed cellular "
        "infrastructure outages. Third, IODA telemetry provides provider-level outage traces in the hardest-hit "
        "Western North Carolina footprint."
    )
    pdf.add_table(
        ["Source", "Geography", "Metric", "Result", "Interpretation"],
        [
            [
                "Ookla fixed latency",
                "NC statewide tracts",
                "Baseline HABRI vs Q3-to-Q4 2024 latency change",
                format_metric(validation["nc_statewide_latency"]),
                "Statewide signal is modest because most tracts were outside the main impact zone",
            ],
            [
                "Ookla fixed latency",
                "WNC focal tracts",
                "Baseline HABRI vs Q3-to-Q4 2024 latency change",
                format_metric(validation["wnc_latency"]),
                "Strongest tract-level Helene validation in the study area",
            ],
            [
                "Ookla fixed latency",
                "ETN focal tracts",
                "Baseline HABRI vs Q3-to-Q4 2024 latency change",
                format_metric(validation["etn_latency"]),
                "Comparison region shows little raw fixed-broadband degradation signal",
            ],
            [
                "FCC DIRS county outages",
                "NC counties",
                "County mean HABRI vs peak cell site outage percentage",
                format_metric(validation["dirs_county"]),
                "Higher-risk counties had higher reported cellular outage rates",
            ],
            [
                "IODA telemetry",
                "Henderson County ISP footprint",
                "Provider-level outage sequence",
                f"Complete ~{validation['ioda_blackout_hours']}-hour blackout",
                "Morris Broadband failed in a high-risk service area",
            ],
            [
                "January 2026 validation layer",
                "NC tracts",
                "Baseline HABRI vs absolute latency shift from Q3 2024",
                format_metric(validation["jan_habri_abs"]),
                "Higher baseline risk remained associated with later network degradation",
            ],
            [
                "January 2026 validation layer",
                "NC tracts",
                "Baseline I_F vs absolute latency shift from Q3 2024",
                format_metric(validation["jan_if_abs"]),
                "Infrastructure fragility retains standalone predictive value",
            ],
        ],
        [24, 25, 43, 34, 56],
        body_font_size=7.7,
        line_height=4.0,
    )
    pdf.paragraph(
        f"WNC and ETN are both Appalachian comparison areas, but they are not compositionally identical. "
        f"In the focal counties, WNC is {validation['wnc_dual_risk_pct']:.1f}% Dual-Risk while ETN is "
        f"{validation['etn_transport_pct']:.1f}% Transport-Fragile. That makes ETN a useful cross-state "
        "comparison area rather than a second interchangeable validation sample."
    )
    pdf.add_figure(
        "habri_wnc_etn_map.png",
        "Figure 6. HABRI comparison map for the Western North Carolina and Eastern Tennessee Helene focal counties.",
        width=176,
    )
    pdf.add_figure(
        "habri_wnc_etn_profiles.png",
        "Figure 7. Risk profile comparison for NC statewide, WNC focal counties, TN statewide, and ETN focal counties.",
        width=160,
    )
    pdf.subsection_title("5.2 Tract-level latency degradation")
    pdf.paragraph(
        "Across all NC tracts with coverage in both quarters, pre-storm HABRI correlates with "
        f"Q3-to-Q4 2024 latency change ({format_metric(validation['nc_statewide_latency'])}). Within the "
        f"WNC focal counties the relationship strengthens substantially ({format_metric(validation['wnc_latency'])}). "
        f"In the ETN focal counties, the same raw-millisecond comparison is near zero "
        f"({format_metric(validation['etn_latency'])}), reinforcing that the clearest Helene fixed-broadband "
        "degradation signal was concentrated in WNC."
    )
    pdf.add_figure(
        "habri_helene_validation_combined.png",
        "Figure 8. HABRI versus Helene-induced latency degradation in WNC and ETN focal counties.",
        width=170,
    )
    pdf.subsection_title("5.3 FCC county-level outages")
    pdf.paragraph(
        "County mean HABRI correlates positively with FCC DIRS cell site outages in North Carolina "
        f"({format_metric(validation['dirs_county'])}). Counties with observed outage activity during the "
        "Helene activation window sit disproportionately above the statewide HABRI median."
    )
    pdf.add_figure(
        "fcc_county_validation.png",
        "Figure 9. County mean HABRI versus FCC-reported cell site outages, plus sub-index decomposition for counties ranked by outage severity.",
        width=170,
    )

    pdf.add_page()
    pdf.subsection_title("5.4 IODA ISP case study")
    pdf.paragraph(
        "IODA telemetry adds provider-level validation. Morris Broadband in Henderson County suffered "
        f"a complete {validation['ioda_blackout_hours']}-hour blackout during the Helene window. Skyline Telephone showed intermittent "
        "degradation, while Wilkes Communications showed comparatively limited disruption. The gradient "
        "of outage severity aligns with the relative HABRI exposure of the providers' service areas."
    )
    pdf.add_figure(
        "ioda_outage_timeseries.png",
        "Figure 10. IODA telemetry for three WNC providers during Hurricane Helene. Morris Broadband shows the clearest complete outage signal.",
        width=176,
    )

    pdf.add_page()
    pdf.subsection_title("5.5 January 2026 validation layer")
    pdf.paragraph(
        "The January 2026 validation layer recomputes HABRI using updated latency while holding hazard "
        "and demographic inputs fixed. Baseline HABRI correlates with the absolute latency shift to "
        f"January 2026 ({format_metric(validation['jan_habri_abs'])}), while baseline Infrastructure Fragility "
        f"also remains significant ({format_metric(validation['jan_if_abs'])}). This indicates that high-risk "
        "tracts remained more degraded than low-risk tracts more than a year after Helene."
    )
    pdf.add_figure(
        "habri_validation_2026_01.png",
        "Figure 11. Baseline HABRI and Infrastructure Fragility versus January 2026 latency shift in North Carolina.",
        width=170,
    )
    pdf.subsection_title("5.6 Recovery tracking")
    pdf.paragraph(
        "The WNC recovery scatter shows that the storm effect is persistent and geographically "
        "concentrated. Most North Carolina tracts were outside the direct impact zone, but many "
        "tracts in the western mountain counties remain above their pre-storm HABRI conditions."
    )
    pdf.add_figure(
        "habri_recovery_scatter.png",
        "Figure 12. WNC recovery scatter comparing pre-Helene HABRI to the Q4 2025 recomputed layer.",
        width=122,
    )

    pdf.add_page()
    pdf.section_title("6. Sensitivity Analysis")
    pdf.paragraph(
        "To assess ranking robustness, the North Carolina statewide layer was recomputed under five "
        "alternative weight configurations. In every case, the Spearman rank correlation with the "
        "reference configuration exceeded 0.85. "
        "This indicates that the broad ordering of the highest-risk tracts is stable to substantial "
        "reweighting of the three top-level pillars."
    )
    pdf.add_table(
        ["Configuration", "H_E", "I_F", "C_C"],
        [
            ["Baseline", "0.40", "0.35", "0.25"],
            ["Equal weights", "0.333", "0.333", "0.333"],
            ["Hazard-dominant", "0.60", "0.25", "0.15"],
            ["Infrastructure-dominant", "0.25", "0.50", "0.25"],
            ["Capacity-dominant", "0.25", "0.25", "0.50"],
            ["Hazard and infrastructure only", "0.50", "0.50", "0.00"],
        ],
        [64, 22, 22, 22],
    )

    pdf.add_page()
    pdf.section_title("7. Policy Implications")
    pdf.subsection_title("7.1 Pre-disaster resource positioning")
    pdf.paragraph(
        "High-HABRI communities are strong candidates for pre-positioned satellite terminals, "
        "portable towers, charging resources, and field communications kits. Transport-Fragile "
        "areas benefit most when those assets are staged before roads fail."
    )
    pdf.subsection_title("7.2 Infrastructure grant prioritization")
    pdf.paragraph(
        "State broadband offices can use HABRI to supplement grant criteria for middle-mile "
        "hardening, redundant routing, backup generation, and transport corridor resilience. "
        "The profile framework helps distinguish where fiber routing, wireless redundancy, or "
        "household resilience support will have the highest payoff."
    )
    pdf.subsection_title("7.3 Utility and power planning")
    pdf.paragraph(
        "The power-grid component makes HABRI directly relevant to electric utility coordination. "
        "Sparse transmission access raises communications outage risk because grid loss is often the "
        "proximate cause of tower and headend failure."
    )
    pdf.subsection_title("7.4 Interstate coordination")
    pdf.paragraph(
        "The Tennessee statewide layer and the shared North Carolina and Tennessee standardized layer support a broader Appalachian "
        "planning frame. Interstate mutual-aid planning, corridor hardening, and cross-border logistics "
        "benefit from one regional picture rather than separate state maps."
    )
    pdf.subsection_title("7.5 Longitudinal monitoring")
    pdf.paragraph(
        "Because latency can be refreshed from new Ookla releases, HABRI can function as an ongoing "
        "monitoring layer rather than a one-time assessment. The versioned refresh path is implemented "
        "for North Carolina."
    )

    pdf.add_page()
    pdf.section_title("8. Limitations and Next Steps")
    pdf.paragraph(
        "HABRI relies on public proxies rather than proprietary carrier topology, generator "
        "inventory, and network management data. That is a practical strength for reproducibility, "
        "but it places a ceiling on precision."
    )
    pdf.paragraph(
        "Ookla latency is observational rather than administratively complete. Tile-level aggregation "
        "reduces noise, but user-initiated test behavior still introduces sampling bias."
    )
    pdf.paragraph(
        "The shared North Carolina and Tennessee map is a second-pass standardization of completed state outputs. It is "
        "appropriate for unified mapping and planning, but a publication-grade interstate comparison "
        "would ideally rebuild both states jointly from harmonized raw inputs."
    )
    pdf.paragraph(
        "Both statewide layers use FCC BDC to adapt tower and road weights by tract-level "
        "wiredness from the same December 31, 2024 filing. That makes the North Carolina and "
        "Tennessee state layers methodologically symmetric before the shared re-standardization step."
    )
    pdf.paragraph(
        "Temporal currency also varies by component. Hazard and demographic layers are slower moving, "
        "while latency is quarterly or versioned. This is acceptable for operational planning, but it "
        "means the composite blends inputs with different refresh cadences."
    )
    pdf.paragraph(
        "Road betweenness remains an approximation based on k = 500 sampled paths. That is a deliberate "
        "tradeoff for tractable statewide computation."
    )

    pdf.add_page()
    pdf.section_title("9. Conclusion")
    pdf.paragraph(
        "HABRI provides a two-state planning stack spanning North Carolina and Tennessee. The "
        "project includes one statewide layer for each state and a shared North Carolina and Tennessee standardized layer "
        "that supplies one common map for interstate situational awareness."
    )
    pdf.paragraph(
        "Infrastructure fragility is modeled as a four-component system that includes power-grid "
        "fragility, while both statewide layers adjust tower-versus-road dependence using tract-level "
        "broadband composition. Together these elements let HABRI capture both network access risk "
        "and utility dependence in one tract-level measure."
    )
    pdf.paragraph(
        "For practitioners, the message is operational: use the state layers for within-state "
        "decision support and validation, and use the shared standardized layer when one regional map "
        "is needed across both states. Together these products provide a defensible open-data framework "
        "for prioritizing broadband resilience investment before the next major disaster."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    print(f"Report saved to {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size / 1024:.0f} KB")
    print(f"Pages: {pdf.pages_count}")


if __name__ == "__main__":
    build_report()
