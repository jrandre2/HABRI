#!/usr/local/bin/python3
"""Build a formal stakeholder PDF report for HABRI with embedded figures."""

from pathlib import Path
from fpdf import FPDF

PROJECT = Path("/Volumes/T9/Projects/HABRI")
DATA = PROJECT / "data" / "processed"
OUTPUT = PROJECT / "docs" / "HABRI_Formal_Report.pdf"


class HABRIReport(FPDF):
    def __init__(self):
        super().__init__()
        font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
        self.add_font("DejaVu", "", font_path)
        self.add_font("DejaVu", "B", font_path)
        self.add_font("DejaVu", "I", font_path)

    def header(self):
        if self.page_no() > 1:
            self.set_font("DejaVu", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "HABRI - Hazard-Adjusted Broadband Reliability Index", align="L")
            self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
            self.line(10, 14, 200, 14)
            self.ln(4)

    def footer(self):
        pass

    def chapter_title(self, title, level=1):
        sizes = {1: 18, 2: 14, 3: 12}
        self.set_font("DejaVu", "B", sizes.get(level, 12))
        self.set_text_color(27, 58, 92)
        self.ln(4 if level == 1 else 2)
        self.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        if level == 1:
            self.set_draw_color(27, 58, 92)
            self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def body_text(self, text):
        self.set_font("DejaVu", "", 10.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def bold_text(self, text):
        self.set_font("DejaVu", "B", 10.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def add_figure(self, filename, caption, width=180):
        path = DATA / filename
        if not path.exists():
            self.body_text(f"[Figure not found: {filename}]")
            return
        # Check if we need a page break — estimate image height
        # Put figure on its own page if large
        if self.get_y() > 140:
            self.add_page()
        x = (210 - width) / 2
        self.image(str(path), x=x, w=width)
        self.ln(3)
        self.set_font("DejaVu", "I", 9)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 4.5, caption, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def add_simple_table(self, headers, rows):
        """Draw a simple table with alternating row colors."""
        n_cols = len(headers)
        col_w = 190 / n_cols
        # Adjust widths for specific tables
        if n_cols == 4 and "Rationale" in headers:
            col_w_list = [35, 30, 15, 110]
        elif n_cols == 4 and "Key Variables" in headers:
            col_w_list = [45, 30, 35, 80]
        elif n_cols == 4 and "Defining Characteristics" in headers:
            col_w_list = [30, 20, 12, 128]
        elif n_cols == 4 and "Interpretation" in headers:
            col_w_list = [35, 40, 15, 100]
        elif n_cols == 3 and "Rationale" in headers:
            col_w_list = [40, 30, 120]
        elif n_cols == 3:
            col_w_list = [50, 70, 70]
        else:
            col_w_list = [col_w] * n_cols

        # Check if table fits on page
        est_height = (len(rows) + 1) * 8
        if self.get_y() + est_height > 260:
            self.add_page()

        # Header
        self.set_font("DejaVu", "B", 9)
        self.set_fill_color(27, 58, 92)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_w_list[i], 7, h, border=1, fill=True, align="C")
        self.ln()

        # Rows
        self.set_font("DejaVu", "", 9)
        self.set_text_color(30, 30, 30)
        for ri, row in enumerate(rows):
            if ri % 2 == 0:
                self.set_fill_color(240, 245, 250)
            else:
                self.set_fill_color(255, 255, 255)
            max_lines = 1
            # Calculate max lines needed
            for ci, val in enumerate(row):
                lines = self.multi_cell(col_w_list[ci], 5, str(val), dry_run=True, output="LINES")
                max_lines = max(max_lines, len(lines))
            row_h = max(7, max_lines * 5)
            y0 = self.get_y()
            for ci, val in enumerate(row):
                x0 = self.get_x()
                self.rect(x0, y0, col_w_list[ci], row_h, style="DF")
                self.set_xy(x0 + 1, y0 + 1)
                self.multi_cell(col_w_list[ci] - 2, 5, str(val))
                self.set_xy(x0 + col_w_list[ci], y0)
            self.set_xy(10, y0 + row_h)
        self.ln(4)


pdf = HABRIReport()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.set_margins(10, 10, 10)

# ═══════════════════════════════════════════════════════════════════════
# TITLE PAGE
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.ln(60)
pdf.set_font("DejaVu", "B", 32)
pdf.set_text_color(27, 58, 92)
pdf.multi_cell(0, 14, "Hazard-Adjusted Broadband\nReliability Index (HABRI)", align="C",
               new_x="LMARGIN", new_y="NEXT")
pdf.ln(8)
pdf.set_font("DejaVu", "", 16)
pdf.set_text_color(68, 68, 68)
pdf.multi_cell(0, 8,
    "Identifying Communities at Risk of Connectivity Loss\n"
    "During Natural Disasters in North Carolina",
    align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(20)
pdf.set_font("DejaVu", "", 14)
pdf.set_text_color(50, 50, 50)
pdf.cell(0, 8, "Jesse R. Andrews", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 8, "Texas Tech University", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(10)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 8, "April 2026", align="C", new_x="LMARGIN", new_y="NEXT")

# ═══════════════════════════════════════════════════════════════════════
# EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("Executive Summary")

pdf.body_text(
    "Broadband internet has become critical infrastructure for emergency communication, "
    "disaster response, and community resilience. Yet the vulnerability of broadband "
    "networks to natural disasters remains poorly quantified, leaving planners and "
    "policymakers without actionable tools to identify at-risk communities before "
    "disasters strike."
)

pdf.body_text(
    "This report introduces the Hazard-Adjusted Broadband Reliability Index (HABRI), "
    "a composite measure that scores every census tract in North Carolina on a 0-to-1 "
    "scale for its risk of broadband service disruption during natural disasters. "
    "HABRI integrates three dimensions of vulnerability: natural hazard exposure "
    "(flooding, hurricanes, and landslides), physical infrastructure fragility "
    "(cell tower density, internet latency, and road network connectivity), and "
    "community coping capacity (income, poverty, disability, vehicle access, and "
    "internet access type)."
)

pdf.body_text(
    "Applied to all 2,660 census tracts across North Carolina's 100 counties, HABRI "
    "identifies three distinct vulnerability profiles: Power-Dependent communities "
    "(51% of tracts), which face moderate hazard exposure but rely on fragile "
    "infrastructure; Dual-Risk communities (40%), which face both high hazard exposure "
    "and weak infrastructure; and Transport-Fragile communities (9%), which have "
    "relatively low hazard exposure but extremely poor road connectivity that impedes "
    "disaster recovery."
)

pdf.body_text(
    "The index was validated against observed broadband outages during Hurricane Helene "
    "(September 2024). Tracts with higher HABRI scores experienced statistically "
    "significant increases in internet latency after the storm. At the county level, "
    "HABRI scores correlated positively with FCC-reported cell site outages. A detailed "
    "case study of Morris Broadband in Henderson County \u2014 where the ISP suffered a "
    "complete 80-hour network blackout \u2014 further confirmed the index's predictive value, "
    "as Henderson County ranks in the 92nd percentile of HABRI scores statewide."
)

# ═══════════════════════════════════════════════════════════════════════
# 1. INTRODUCTION
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("1. Introduction")

pdf.chapter_title("1.1 The Problem", level=2)
pdf.body_text(
    "Natural disasters expose deep inequalities in broadband infrastructure. "
    "When hurricanes, floods, or landslides strike, some communities lose internet "
    "service for hours while others remain disconnected for days or weeks. These "
    "outages are not random \u2014 they concentrate in communities that are already "
    "disadvantaged by geography, infrastructure investment patterns, and "
    "socioeconomic conditions."
)
pdf.body_text(
    "The consequences of prolonged broadband outages during disasters are severe. "
    "Residents cannot receive emergency alerts, access telehealth services, file "
    "insurance claims, or communicate with family members. Schools and businesses "
    "cannot operate remotely. First responders lose coordination capabilities. "
    "In an era when broadband underpins virtually every aspect of disaster response "
    "and recovery, connectivity loss compounds the harm from the disaster itself."
)

pdf.chapter_title("1.2 Why a Composite Index?", level=2)
pdf.body_text(
    "Existing tools for assessing broadband vulnerability tend to examine individual "
    "risk factors in isolation \u2014 mapping flood zones separately from cell tower coverage "
    "separately from income levels. While each factor matters, the interaction among "
    "them determines actual outage risk. A rural mountain community may face moderate "
    "flood risk but extreme infrastructure fragility due to sparse cell towers and "
    "poor road access; conversely, an urban coastal tract may face high hurricane "
    "exposure but have robust, redundant infrastructure."
)
pdf.body_text(
    "HABRI addresses this gap by combining hazard exposure, infrastructure fragility, "
    "and community coping capacity into a single, comparable score. This enables "
    "direct comparisons across geographies and facilitates evidence-based resource "
    "allocation for infrastructure grants, pre-positioned emergency assets, and "
    "long-term resilience investments."
)

pdf.chapter_title("1.3 Study Area", level=2)
pdf.body_text(
    "North Carolina provides an ideal laboratory for this analysis. The state spans "
    "three distinct physiographic regions \u2014 the Appalachian Mountains in the west, "
    "the Piedmont plateau in the center, and the Coastal Plain in the east \u2014 each with "
    "different hazard profiles and infrastructure characteristics. Hurricane Helene's "
    "landfall on September 26, 2024, which caused catastrophic flooding in the western "
    "mountains, provided a natural experiment for validating the index against observed "
    "outage data."
)
pdf.body_text(
    "The analysis covers all 100 North Carolina counties and 2,660 census tracts, "
    "using 2020 Census tract definitions consistent with the American Community "
    "Survey 2018\u20132022 five-year estimates."
)

# ═══════════════════════════════════════════════════════════════════════
# 2. DATA SOURCES
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("2. Data Sources")
pdf.body_text(
    "HABRI integrates six publicly available datasets spanning natural hazard risk, "
    "broadband infrastructure, transportation networks, and demographic characteristics."
)

pdf.add_simple_table(
    ["Dataset", "Source", "Coverage", "Key Variables"],
    [
        ["FEMA NRI v1.20", "FEMA OpenFEMA", "2,660 NC tracts",
         "Inland flooding, hurricane, landslide risk scores"],
        ["Ookla Open Data (Q3\u2013Q4 2024)", "Ookla / AWS S3", "~125K speed tiles",
         "Fixed broadband latency, download/upload speed"],
        ["HIFLD Cellular Towers", "DHS HIFLD", "1,275 NC towers",
         "Tower locations (lat/long)"],
        ["OSM Road Network", "OpenStreetMap / OSMnx", "648K nodes; 1.5M edges",
         "Drive-network topology"],
        ["ACS 2018\u20132022 5-Year", "U.S. Census Bureau", "2,660 tracts",
         "Income, poverty, disability, vehicle, internet"],
        ["FCC DIRS & IODA", "FCC / Georgia Tech", "100 counties / 3 ISPs",
         "Cell site outages; BGP telemetry"],
    ],
)

pdf.chapter_title("2.1 FEMA National Risk Index", level=2)
pdf.body_text(
    "The FEMA National Risk Index (NRI) version 1.20 provides census-tract-level "
    "composite risk scores for 18 natural hazard types. For North Carolina, three "
    "hazards are most relevant to broadband infrastructure: inland flooding (formerly "
    "\"riverine flooding\" in earlier NRI versions), hurricanes, and landslides. Each "
    "NRI composite risk score integrates expected annual loss, social vulnerability, "
    "and community resilience into a single measure."
)

pdf.chapter_title("2.2 Ookla Broadband Performance", level=2)
pdf.body_text(
    "Ookla's Speedtest Intelligence platform publishes quarterly aggregated broadband "
    "performance data as open data on Amazon S3. Each record represents a geographic "
    "tile (roughly 600m x 600m) and reports the median download speed, upload speed, "
    "latency, and number of tests conducted during the quarter. This analysis uses "
    "Q3 2024 (pre-Helene) and Q4 2024 (post-Helene) fixed broadband tiles, comprising "
    "approximately 123,000 and 127,000 tiles respectively."
)

pdf.chapter_title("2.3 HIFLD Cellular Tower Inventory", level=2)
pdf.body_text(
    "The Homeland Infrastructure Foundation-Level Data (HIFLD) program publishes "
    "geolocated cellular tower positions. The NC extract contains 1,275 towers, "
    "spatially joined to census tracts to compute tower density (towers per km\u00b2) "
    "as a proxy for wireless infrastructure redundancy."
)

pdf.chapter_title("2.4 OSM Road Network", level=2)
pdf.body_text(
    "A complete drive-network graph for North Carolina was downloaded from "
    "OpenStreetMap via the OSMnx library (648,424 nodes, 1,528,603 edges). Road "
    "network topology is used to compute betweenness centrality and road density "
    "per tract. Communities served by few, non-redundant roads are harder to reach "
    "for repair crews after a disaster."
)

pdf.chapter_title("2.5 American Community Survey", level=2)
pdf.body_text(
    "Five demographic indicators from the ACS 2018\u20132022 five-year estimates capture "
    "community coping capacity: no-vehicle households, mobile-only internet households, "
    "disability rate, median household income, and poverty rate. These reflect a "
    "community's ability to adapt when primary broadband service is disrupted."
)

# ═══════════════════════════════════════════════════════════════════════
# 3. METHODOLOGY
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("3. Index Construction Methodology")

pdf.chapter_title("3.1 Overall Index Architecture", level=2)
pdf.body_text("HABRI is a weighted composite index comprising three sub-indices:")
pdf.bold_text(
    "HABRI = 0.40 \u00d7 H_E (Hazard Exposure) + 0.35 \u00d7 I_F (Infrastructure Fragility) "
    "+ 0.25 \u00d7 C_C (Coping Capacity Deficit)"
)
pdf.body_text(
    "The weights reflect the relative importance of each dimension: hazard exposure "
    "is the primary driver (a community with no hazard exposure faces minimal outage "
    "risk regardless of infrastructure quality), infrastructure fragility determines "
    "whether hazards translate into actual outages, and community coping capacity "
    "moderates the impact on residents. Higher scores indicate higher risk, yielding "
    "a final HABRI score between 0 (lowest risk) and 1 (highest risk)."
)

pdf.chapter_title("3.2 Normalization", level=2)
pdf.body_text(
    "All component indicators are normalized to a common [0, 1] scale using z-score "
    "standardization followed by conversion to a cumulative distribution function "
    "(CDF) value. Each indicator is centered at its mean and scaled by its standard "
    "deviation to produce a z-score; the z-score is then mapped through the standard "
    "normal CDF, yielding a value between 0 and 1 where 0.5 represents the statewide "
    "average. This approach is robust to outliers and produces a natural probabilistic "
    "interpretation (a score of 0.75 means the tract is more vulnerable than ~75% of "
    "tracts). For indicators where higher values = lower risk (tower density, income), "
    "the z-score is negated before applying the CDF."
)

pdf.chapter_title("3.3 Hazard Exposure (H_E)", level=2)
pdf.body_text(
    "The hazard exposure sub-index combines FEMA NRI composite risk scores for three "
    "hazard types relevant to broadband infrastructure in North Carolina:"
)
pdf.add_simple_table(
    ["Hazard Type", "NRI Column", "Weight", "Rationale"],
    [
        ["Inland Flooding", "IFLD_RISKS", "0.40",
         "Most frequent cause of infrastructure damage in NC"],
        ["Hurricane", "HRCN_RISKS", "0.35",
         "Wind, rain, and storm surge; prolonged outages"],
        ["Landslide", "LNDS_RISKS", "0.25",
         "Western mountains; destroys fiber and access roads"],
    ],
)

pdf.chapter_title("3.4 Infrastructure Fragility (I_F)", level=2)
pdf.body_text(
    "The infrastructure fragility sub-index captures the physical resilience of "
    "broadband and transportation infrastructure:"
)
pdf.add_simple_table(
    ["Component", "Metric", "Weight", "Interpretation"],
    [
        ["Cell Tower Density", "Towers/km\u00b2 (inverted)", "0.30",
         "Fewer towers = less redundancy"],
        ["Broadband Latency", "Median latency (ms)", "0.30",
         "Higher latency = aging/overloaded equipment"],
        ["Road Fragility", "Betweenness + density", "0.40",
         "Poor road access = slower repair response"],
    ],
)
pdf.body_text(
    "Road network fragility is a sub-composite: 60% betweenness centrality "
    "(how critical the tract's roads are to regional connectivity) and 40% inverse "
    "road density. Betweenness centrality is computed using a k=500 random-node "
    "approximation on the full statewide road graph, as exact computation on a "
    "graph with 648,424 nodes is computationally infeasible."
)

pdf.chapter_title("3.5 Community Coping Capacity Deficit (C_C)", level=2)
pdf.body_text(
    "Five ACS indicators, weighted equally at 0.20 each, measure a community's "
    "ability to absorb broadband disruptions:"
)
pdf.add_simple_table(
    ["Indicator", "Direction", "Rationale"],
    [
        ["No-vehicle households", "High = higher risk",
         "Cannot travel to functioning internet"],
        ["Mobile-only internet", "High = higher risk",
         "No wired backup when cell service fails"],
        ["Disability rate", "High = higher risk",
         "Greater dependence on internet-connected services"],
        ["Median household income", "Inverted: low = higher risk",
         "Fewer resources for backup connectivity"],
        ["Poverty rate", "High = higher risk",
         "Economic constraints on adaptation"],
    ],
)

pdf.chapter_title("3.6 Missing Data and Profiling", level=2)
pdf.body_text(
    "Missing indicator values are imputed with the statewide median (48 tracts for "
    "income). No tracts are dropped. After computing sub-indices, k-means clustering "
    "(k=3) identifies three vulnerability profiles based on centroid characteristics: "
    "Power-Dependent, Dual-Risk, and Transport-Fragile."
)

# ═══════════════════════════════════════════════════════════════════════
# 4. RESULTS
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("4. Results")

pdf.chapter_title("4.1 Statewide Score Distribution", level=2)
pdf.body_text(
    "HABRI scores across North Carolina's 2,660 census tracts range from 0.203 to "
    "0.818, with a mean of 0.495 and a standard deviation of 0.106. The distribution "
    "is approximately normal, centered near 0.5 by construction. The interquartile "
    "range spans approximately 0.42 to 0.57."
)

pdf.chapter_title("4.2 Geographic Patterns", level=2)
pdf.body_text(
    "The four-panel map below displays HABRI and its three sub-indices. Hazard "
    "Exposure (H_E) is highest in the Appalachian west (landslide/flood) and Coastal "
    "Plain east (hurricane/flood). Infrastructure Fragility (I_F) is highest in rural "
    "areas statewide; urban centers show low fragility. Coping Capacity Deficit (C_C) "
    "is highest in the eastern Coastal Plain and rural mountain west. The composite "
    "score identifies the highest-risk tracts in two zones: western mountain counties "
    "and portions of the rural eastern Coastal Plain."
)

pdf.add_figure("habri_statewide_4panel.png",
    "Figure 1. Four-panel map of HABRI sub-indices and composite score across all "
    "2,660 North Carolina census tracts. WNC validation counties are outlined.", 185)

pdf.add_page()
pdf.chapter_title("4.3 Vulnerability Profiles", level=2)
pdf.body_text(
    "K-means clustering identified three distinct vulnerability profiles:"
)
pdf.add_simple_table(
    ["Profile", "Count", "Share", "Defining Characteristics"],
    [
        ["Power-Dependent", "1,359", "51%",
         "Moderate hazard; infrastructure fragility is primary risk driver"],
        ["Dual-Risk", "1,075", "40%",
         "Both high hazard exposure and high infrastructure fragility"],
        ["Transport-Fragile", "226", "9%",
         "Lower hazard; extremely poor road connectivity drives risk"],
    ],
)
pdf.body_text(
    "The dominance of the Power-Dependent profile (51%) indicates that infrastructure "
    "fragility \u2014 rather than hazard exposure alone \u2014 is the primary broadband "
    "vulnerability for the majority of NC communities. This has direct policy "
    "implications: infrastructure investment may reduce outage risk for more "
    "communities than hazard mitigation alone."
)
pdf.body_text(
    "Profile assignments remain stable across quarterly updates, as shown below."
)
pdf.add_figure("habri_timeseries_profiles.png",
    "Figure 2. Quarterly distribution of vulnerability profiles across all NC tracts "
    "(Q3 2024 through Q4 2025), showing stability of cluster assignments.", 160)

# ═══════════════════════════════════════════════════════════════════════
# 5. VALIDATION
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("5. Validation Against Hurricane Helene")
pdf.body_text(
    "Hurricane Helene made landfall near Perry, Florida, on September 26, 2024, as a "
    "Category 4 storm before tracking northward through the Appalachian Mountains. "
    "Western North Carolina experienced catastrophic flooding, with some areas "
    "receiving over 20 inches of rain in 48 hours. The storm caused widespread "
    "broadband outages, providing a natural experiment for validation."
)
pdf.body_text(
    "Three independent validation tests were conducted using distinct data sources."
)

pdf.chapter_title("5.1 Ookla Latency Degradation (Tract Level)", level=2)
pdf.body_text(
    "Pre-storm HABRI scores were compared with the change in median broadband latency "
    "between Q3 2024 (pre-Helene) and Q4 2024 (post-Helene) across 2,650 tracts. "
    "The Spearman rank correlation was \u03c1 = \u22120.113 (p < 0.001). Tracts with higher "
    "HABRI scores experienced larger latency increases (greater degradation). When "
    "restricted to western NC, the correlation strengthens to \u03c1 = \u22120.295 (p < 0.001, "
    "n = 130 tracts)."
)
pdf.add_figure("habri_helene_validation_combined.png",
    "Figure 3. HABRI vs. Helene-induced latency degradation. Left: WNC tracts "
    "(\u03c1 = \u22120.295, p < 0.001). Right: eastern TN control region (no significant "
    "correlation).", 170)

pdf.chapter_title("5.2 FCC DIRS County-Level Outages", level=2)
pdf.body_text(
    "FCC Disaster Information Reporting System (DIRS) data records cell site outages "
    "at the county level. Across all 100 NC counties, Spearman \u03c1 = 0.236 (p = 0.018) "
    "between county mean HABRI and FCC-reported outages. All 21 counties with "
    "DIRS-reported outages had mean HABRI scores above the statewide median."
)
pdf.add_figure("fcc_county_validation.png",
    "Figure 4. Left: County mean HABRI vs. FCC cell site outages (\u03c1 = 0.236, "
    "p = 0.018, n = 100). Right: Sub-index decomposition for counties ranked by "
    "outage severity.", 170)

pdf.add_page()
pdf.chapter_title("5.3 IODA ISP Outage Telemetry (Case Study)", level=2)
pdf.body_text(
    "The Internet Outage Detection and Analysis (IODA) platform from Georgia Tech "
    "monitors connectivity via BGP route visibility and active probing. Three WNC "
    "ISPs were examined during the Helene period (September 26 \u2013 October 7, 2024):"
)
pdf.body_text(
    "Morris Broadband (ASN 53488), in Henderson County (92nd percentile HABRI), "
    "experienced a complete BGP blackout. All 24 BGP prefixes became unreachable, "
    "and active probing dropped to zero. The blackout lasted approximately 80 hours."
)
pdf.body_text(
    "Skyline Telephone (ASN 23118) experienced intermittent BGP disruptions but no "
    "complete blackout. Wilkes Communications (ASN 22191) showed minimal disruption, "
    "consistent with its service area's lower HABRI scores."
)
pdf.body_text(
    "The gradient of outage severity \u2014 from complete blackout to minimal disruption \u2014 "
    "aligns with the respective service areas' HABRI scores."
)
pdf.add_figure("ioda_outage_timeseries.png",
    "Figure 5. IODA outage telemetry for three WNC ISPs during Hurricane Helene. "
    "Morris Broadband: complete 80-hour blackout. Skyline: intermittent outages. "
    "Wilkes: minimal disruption.", 175)

pdf.add_page()
pdf.chapter_title("5.4 January 2026 Longitudinal Validation", level=2)
pdf.body_text(
    "HABRI was recomputed using January 2026 Ookla data (hazard and demographic "
    "components held constant). The correlation between baseline HABRI (Q3 2024) and "
    "the absolute latency shift to January 2026 was \u03c1 = 0.15 (p < 0.001, n = 2,649), "
    "confirming persistent degradation in high-risk tracts more than a year after "
    "Hurricane Helene."
)
pdf.add_figure("habri_validation_2026_01.png",
    "Figure 6. Baseline HABRI (left) and Infrastructure Fragility (right) vs. "
    "absolute latency change from Q3 2024 to January 2026.", 170)

pdf.chapter_title("5.5 Western NC Recovery Tracking", level=2)
pdf.body_text(
    "Pre-Helene HABRI scores were plotted against Q4 2025 recomputed scores for WNC "
    "tracts. Points above the diagonal indicate worsened conditions. The majority of "
    "WNC tracts remain above the diagonal, indicating incomplete broadband recovery "
    "more than a year after the storm."
)
pdf.add_figure("habri_recovery_scatter.png",
    "Figure 7. WNC recovery scatter: pre-Helene vs. Q4 2025 HABRI. Points above "
    "the diagonal = worse conditions than before the storm.", 120)

pdf.chapter_title("5.6 Quarterly Trends", level=2)
pdf.body_text(
    "Statewide quarterly trends in mean HABRI and sub-index scores from Q3 2024 "
    "through Q4 2025 show overall stability. This reflects that Helene's damage was "
    "geographically concentrated, and that hazard/demographic sub-indices use fixed "
    "data. Latency is the only time-varying element."
)
pdf.add_figure("habri_timeseries_statewide.png",
    "Figure 8. Statewide quarterly trend in mean HABRI and sub-index scores "
    "(Q3 2024\u2013Q4 2025). Hurricane Helene period highlighted.", 165)

# ═══════════════════════════════════════════════════════════════════════
# 6. SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("6. Sensitivity Analysis")
pdf.body_text(
    "To assess robustness, HABRI was recomputed under five alternative weight "
    "configurations:"
)
pdf.add_simple_table(
    ["Configuration", "H_E", "I_F", "C_C"],
    [
        ["Baseline", "0.40", "0.35", "0.25"],
        ["Equal weights", "0.333", "0.333", "0.333"],
        ["Hazard-dominant", "0.60", "0.25", "0.15"],
        ["Infrastructure-dominant", "0.25", "0.50", "0.25"],
        ["Capacity-dominant", "0.25", "0.25", "0.50"],
        ["Hazard-infra only", "0.50", "0.50", "0.00"],
    ],
)
pdf.body_text(
    "The Spearman rank correlation between the baseline ranking and each alternative "
    "exceeded 0.85 in all cases. The relative ordering of tracts is robust to "
    "substantial weight changes \u2014 the highest-risk communities remain in the upper "
    "quantiles regardless of which dimension is emphasized."
)

# ═══════════════════════════════════════════════════════════════════════
# 7. POLICY IMPLICATIONS
# ═══════════════════════════════════════════════════════════════════════
pdf.chapter_title("7. Policy Implications and Applications")

pdf.chapter_title("7.1 Pre-Disaster Resource Positioning", level=2)
pdf.body_text(
    "Emergency managers can pre-position mobile connectivity assets (satellite "
    "terminals, portable cell towers, Wi-Fi hotspots) in high-HABRI areas before "
    "forecasted storms. Transport-Fragile communities need assets positioned before "
    "road access is lost; Power-Dependent communities benefit most from backup power "
    "for existing towers."
)

pdf.chapter_title("7.2 Infrastructure Grant Prioritization", level=2)
pdf.body_text(
    "State broadband offices administering federal grants (BEAD, Digital Equity Act) "
    "can incorporate HABRI scores into funding criteria to direct investment toward "
    "communities where infrastructure fragility poses the greatest outage risk."
)

pdf.chapter_title("7.3 Utility Planning", level=2)
pdf.body_text(
    "Telecommunications providers and electric utilities can identify where redundant "
    "cell towers, buried fiber, or backup generators would have the greatest impact. "
    "The road fragility component highlights areas where pre-staging equipment is "
    "more effective than post-disaster deployment."
)

pdf.chapter_title("7.4 Longitudinal Monitoring", level=2)
pdf.body_text(
    "The latency component can be updated quarterly using Ookla open data, enabling "
    "ongoing monitoring of whether investments are reducing outage risk. The quarterly "
    "update is automated and requires no additional data licensing."
)

# ═══════════════════════════════════════════════════════════════════════
# 8. LIMITATIONS
# ═══════════════════════════════════════════════════════════════════════
pdf.add_page()
pdf.chapter_title("8. Limitations")

pdf.body_text(
    "Proxy indicators: The index relies on publicly available proxies rather than "
    "direct measures of network topology, equipment age, or power dependency. "
    "Proprietary ISP data would improve precision but is not publicly accessible."
)
pdf.body_text(
    "Sampling bias: Ookla latency data reflects user-initiated speed tests, "
    "introducing selection bias. Tracts with fewer internet users may have fewer "
    "observations. Tile-level medians mitigate noise but do not eliminate the bias."
)
pdf.body_text(
    "Power grid layer: Electric transmission line density and substation data have "
    "been prepared but not yet integrated. Since power outages are the proximate "
    "cause of most broadband outages, this layer would likely improve predictions."
)
pdf.body_text(
    "Temporal currency: ACS demographic data reflects 2018\u20132022 estimates and may "
    "not capture recent population shifts. The FEMA NRI reflects historical hazard "
    "patterns that may evolve with climate change."
)
pdf.body_text(
    "Betweenness approximation: The k=500 random-node approximation introduces "
    "sampling variability, but produces stable results at the tract aggregation "
    "level. Exact computation on the 648,424-node graph is infeasible."
)

# ═══════════════════════════════════════════════════════════════════════
# 9. CONCLUSION
# ═══════════════════════════════════════════════════════════════════════
pdf.chapter_title("9. Conclusion")

pdf.body_text(
    "The Hazard-Adjusted Broadband Reliability Index provides a systematic, "
    "reproducible, and validated approach to identifying communities at risk of "
    "broadband connectivity loss during natural disasters. By integrating hazard "
    "exposure, infrastructure fragility, and community coping capacity into a single "
    "composite measure, HABRI enables direct comparisons across North Carolina's "
    "2,660 census tracts and supports targeted interventions."
)
pdf.body_text(
    "Validation against Hurricane Helene demonstrated that HABRI scores predict "
    "observed broadband outages at multiple scales \u2014 from individual ISP blackouts "
    "to county-level cell site failures to tract-level latency degradation. The "
    "index's robustness to alternative weighting schemes and its stability over "
    "quarterly updates provide confidence in its reliability as a planning tool."
)
pdf.body_text(
    "The identification of three vulnerability profiles \u2014 Power-Dependent, Dual-Risk, "
    "and Transport-Fragile \u2014 offers actionable guidance for policymakers. Different "
    "profiles call for different interventions: infrastructure redundancy for "
    "Power-Dependent communities, comprehensive resilience investment for Dual-Risk "
    "communities, and pre-positioned recovery assets for Transport-Fragile communities."
)
pdf.body_text(
    "As broadband becomes ever more central to disaster response and recovery, tools "
    "like HABRI can help ensure that the communities most at risk of losing "
    "connectivity are identified and supported before the next disaster strikes \u2014 "
    "not after."
)

# ═══════════════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════════════
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdf.output(str(OUTPUT))
print(f"Report saved to {OUTPUT}")
print(f"File size: {OUTPUT.stat().st_size / 1024:.0f} KB")
print(f"Pages: {pdf.pages_count}")
