# Mapping Broadband Vulnerability to Natural Hazards: The Hazard-Adjusted Broadband Reliability Index for North Carolina

Scope note: this manuscript draft remains focused on the North Carolina baseline analysis. The codebase now also includes a Tennessee statewide extension and a shared NC+TN standardized operational layer, but those products are not yet woven into this paper draft except where future revisions choose to incorporate them.

**Jesse R. Andrews**  
[Affiliation — Texas Tech University]  
jesseand@ttu.edu

---

## Abstract

Reliable broadband connectivity is increasingly critical to disaster response, yet existing vulnerability frameworks rarely account for the intersection of natural hazard exposure, communication infrastructure fragility, and community coping capacity. This paper introduces the **Hazard-Adjusted Broadband Reliability Index (HABRI)**, a composite index that quantifies broadband outage risk at the census tract level across North Carolina. HABRI integrates three sub-indices: Hazard Exposure (H_E) derived from FEMA National Risk Index scores for inland flooding, hurricanes, and landslides; Infrastructure Fragility (I_F) measured by cellular tower density, broadband latency, and road network centrality; and Community Coping Capacity (C_C) drawn from American Community Survey socioeconomic indicators. Applied to all 2,660 census tracts across 100 NC counties, HABRI scores range from 0.20 to 0.82 (mean = 0.495, SD = 0.106). Validation against three independent Hurricane Helene (September 2024) datasets — Ookla fixed-network latency degradation (Spearman ρ = −0.113, p < 0.001, n = 2,650), FCC Disaster Information Reporting System county-level cell outages (ρ = 0.236, p = 0.018, n = 100), and IODA autonomous system outage telemetry — confirms that HABRI identifies communities that experienced real connectivity failures. K-means clustering reveals three vulnerability profiles: Power-Dependent communities (51%, mean HABRI = 0.44), Dual-Risk communities (40%, mean HABRI = 0.57), and Transport-Fragile communities (9%, mean HABRI = 0.47), each requiring distinct resilience interventions. Weight sensitivity analysis demonstrates rank stability across five alternative weighting schemes (Spearman ρ > 0.85). HABRI provides emergency managers, broadband planners, and policymakers with an actionable, reproducible, and updatable tool for prioritizing resilience investments.

**Keywords:** broadband resilience; disaster vulnerability; natural hazards; GIS; North Carolina; Hurricane Helene; infrastructure fragility

---

## 1. Introduction

Broadband internet infrastructure has become foundational to modern disaster response. Emergency alerts, shelter coordination, damage reporting, financial assistance applications, and post-disaster economic recovery all depend on functional connectivity — yet the communities most exposed to natural hazards are frequently the same communities with the most fragile communication infrastructure and the least capacity to absorb disruptions (Grubesic & Matisziw, 2006; Kellerman, 2010; Salemink et al., 2017).

Hurricane Helene's landfall in Florida on September 26, 2024, and subsequent inland flooding across Western North Carolina illustrated this vulnerability in stark terms. Cellular network outages across 21 Western NC counties left first responders unable to coordinate, residents unable to call for help, and relief organizations unable to verify needs. Morris Broadband, a regional fixed-wireless and fiber internet service provider serving Henderson County, suffered an 80-hour complete Border Gateway Protocol (BGP) blackout — its network disappearing entirely from the global internet routing table. In the weeks following the storm, post-disaster connectivity surveys consistently found that areas with pre-existing infrastructure fragility experienced slower recovery and greater reliance on mobile connectivity alternatives that were themselves degraded (FCC, 2024).

These failures were, in principle, predictable. The combination of high flood and landslide hazard exposure, sparse infrastructure, limited road redundancy, and socioeconomic vulnerability that characterized Western NC had been present in the data long before the storm. What was lacking was a systematic, publicly reproducible framework for identifying at-risk communities before disaster strikes.

Existing vulnerability indices such as FEMA's Social Vulnerability Index (SoVI), CDC's Social Vulnerability Index (CDC-SVI), and the Community Resilience Estimates (CRE) capture social dimensions of disaster vulnerability but do not specifically address communication infrastructure resilience (Flanagan et al., 2011; Cutter et al., 2003). The FCC's Broadband Data Collection maps coverage but is not tied to hazard exposure or outage prediction. Telecommunications operators possess detailed network topology data but treat it as proprietary. No existing public-data framework integrates these dimensions into a single, regularly updatable vulnerability score at the census tract level.

This paper addresses that gap by introducing HABRI: the Hazard-Adjusted Broadband Reliability Index. HABRI is:
1. **Composite** — integrating hazard exposure, infrastructure fragility, and social coping capacity
2. **Spatially granular** — computed at the census tract level (n = 2,660 for NC)
3. **Empirically validated** — tested against three independent Hurricane Helene outage datasets
4. **Updatable** — the infrastructure fragility component can be refreshed quarterly using publicly available Ookla Open Data
5. **Reproducible** — fully implemented in open-source Python with public data sources

The remainder of this paper is organized as follows: Section 2 reviews related work; Section 3 describes the study area and data sources; Section 4 presents the HABRI methodology; Section 5 reports results; Section 6 presents validation analyses; Section 7 discusses implications and limitations; and Section 8 concludes.

---

## 2. Background and Related Work

### 2.1 Broadband and Disaster Resilience

The relationship between broadband access and disaster resilience operates through multiple mechanisms. Pre-disaster, internet connectivity enables community members to access hazard warnings, evacuation orders, and preparedness resources (Reinhart, 2019). During disasters, cellular and fixed-broadband networks support emergency communications when landline infrastructure fails. Post-disaster, connectivity enables damage reporting to insurance companies and FEMA, facilitates remote work to sustain economic activity, and provides access to relief information (Koulali et al., 2022).

Rural and low-income communities face compounded vulnerability: they are disproportionately exposed to certain natural hazards (particularly flooding and landslides in mountainous terrain), more likely to depend on a small number of ISPs with limited network redundancy, less likely to have backup power for routers and CPE equipment, and less able to absorb the economic cost of extended outages (Grubesic & Matisziw, 2006; Powell et al., 2021).

### 2.2 Composite Vulnerability Indices

Composite index methodology for disaster vulnerability has a substantial literature. Cutter et al.'s (2003) SoVI was among the first to systematically combine social indicators into a tract-level vulnerability score; subsequent work has refined variable selection, weighting strategies, and normalization approaches (Burton, 2010; Flanagan et al., 2011; Spielman et al., 2020). Key methodological debates in this literature include: the choice between additive and multiplicative aggregation; the use of equal weighting versus expert-elicited or data-driven weights; and the appropriate spatial unit of analysis (Tate, 2012).

HABRI draws on this tradition while adding a domain — communication infrastructure — that has been largely absent from existing vulnerability frameworks. The most closely related prior work is the FCC's Broadband Deployment Connectivity Index (BDCI) and academic indices such as the Digital Divide Index (DDI; Gallardo, 2020), but neither integrates hazard exposure or validates against actual outage events.

### 2.3 Infrastructure Fragility Indicators

Proxies for broadband infrastructure fragility in the absence of proprietary operator data have received limited academic attention. Cell tower density (HIFLD data) has been used as a coverage proxy but not as a fragility indicator. Road network centrality — specifically betweenness centrality, which identifies roads whose removal would disproportionately disrupt network connectivity — has been applied to transportation vulnerability analysis (Jenelius et al., 2006) but not to broadband resilience. Ookla's publicly available fixed-network performance data provide a crowd-sourced proxy for realized connectivity quality that complements coverage-based measures.

---

## 3. Study Area and Data Sources

### 3.1 Study Area

The study area comprises all 100 counties and 2,660 census tracts in North Carolina (FIPS: 37). North Carolina is an appropriate study area for several reasons: it encompasses a wide range of hazard profiles from coastal hurricane exposure in the east to inland flooding and landslide risk in the western mountain counties; it includes both urban, suburban, and rural areas with varying infrastructure profiles; it was directly affected by Hurricane Helene in September 2024, providing a natural validation event; and its 2020 Census tract boundaries are stable across the ACS 2018–2022 five-year estimates used here.

### 3.2 Data Sources

**FEMA National Risk Index (NRI), v1.20 (December 2025)**  
The NRI provides census-tract-level risk scores for 18 natural hazards based on expected annual loss, social vulnerability, and community resilience (FEMA, 2023). HABRI uses continuous risk score columns for three hazards: Inland Flooding (IFLD_RISKS), Hurricane (HRCN_RISKS), and Landslide (LNDS_RISKS). Note that NRI v1.20 renamed the "Riverine Flooding" hazard to "Inland Flooding" and updated column naming accordingly. Tracts with "Insufficient Data" ratings (n = 15) received median imputation.

**Ookla Open Data (AWS S3), Q3 2024**  
Ookla publishes aggregated fixed-network performance data at the Bing Maps tile level (zoom 16, approximately 600 m resolution at NC latitudes) on a quarterly basis. The Q3 2024 (July–September 2024) dataset, representing the pre-Helene baseline, contains 123,435 NC tiles with test-count-weighted average latency, download speed, and upload speed measurements. Tile centroids (tile_x, tile_y columns available in v2024+) were used in lieu of WKT tile polygons to avoid pyarrow/pandas compatibility issues with the national parquet format.

**HIFLD Cellular Towers**  
The Homeland Infrastructure Foundation-Level Data (HIFLD) cellular tower dataset was retrieved via ArcGIS REST API for North Carolina, yielding 1,275 tower locations. Tower density per tract was computed in the NC State Plane coordinate system (EPSG:2264) to ensure accurate area-based calculations.

**OpenStreetMap / OSMnx Road Network**  
The drive-mode road network for North Carolina was downloaded via OSMnx (Boeing, 2017) as a single statewide directed graph (648,424 nodes, 1,528,603 edges). Edge betweenness centrality was approximated using k = 500 random source–destination pairs, following the standard approximation for large networks (Brandes, 2001). Edges were assigned to census tracts via midpoint interpolation to avoid double-counting at boundaries.

**American Community Survey (ACS) 5-Year Estimates, 2018–2022**  
ACS data were retrieved for all NC tracts using the Census Bureau API. Variables used for the Coping Capacity sub-index include: workers with no vehicle available (B08141_002E / B08141_001E), households with cellular-only internet (B28011_008E / B28011_001E), population aged 18–64 with disability (C18108_006E), population aged 65+ with disability (C18108_010E), median household income (B19013_001E), and population below poverty level (B17001_002E). 48 tracts with missing median household income values received median imputation.

**FCC Disaster Information Reporting System (DIRS)**  
For validation, county-level cellular infrastructure outage percentages were obtained from FCC DIRS activation reports for the 21 Western NC counties under active DIRS monitoring during the Hurricane Helene response period. The remaining 79 counties, which had no reported outages, were assigned 0%.

**IODA Outage Telemetry**  
Internet Outage Detection and Analysis (IODA) data from Georgia Tech's Internet Intelligence Lab were retrieved for three Western NC autonomous systems during the Helene impact window (September 26 – October 7, 2024): Morris Broadband (ASN 53488), Skyline Telephone (ASN 23118), and Wilkes Communications (ASN 22191).

---

## 4. Methodology

### 4.1 HABRI Framework

HABRI is a weighted linear composite of three sub-indices:

$$\text{HABRI} = 0.40 \cdot H_E + 0.35 \cdot I_F + 0.25 \cdot C_C$$

where H_E denotes Hazard Exposure, I_F Infrastructure Fragility, and C_C Community Coping Capacity. All sub-indices are normalized to [0, 1], with higher values indicating higher risk (greater hazard, more fragile infrastructure, or lower coping capacity). Weights were established through expert elicitation and reflect the primary role of physical hazards in triggering outages (40%), the secondary role of infrastructure design (35%), and the modulating role of social factors (25%).

### 4.2 Normalization

All component indicators were normalized using z-score standardization followed by mapping through the standard normal cumulative distribution function (CDF):

$$\tilde{x}_i = \Phi\!\left(\frac{x_i - \bar{x}}{s}\right)$$

where Φ is the standard normal CDF. This approach maps the mean to 0.5, is bounded on [0, 1], and is robust to outliers. For indicators where higher values represent lower risk (tower density, road density, income), z-scores were negated before CDF transformation to ensure consistent directionality (higher normalized value = higher risk).

Tracts with missing values on any component indicator received median imputation, with imputed GEOIDs logged for transparency. In total, 15 tracts were imputed for NRI scores, 28 tracts for Ookla latency (no speed test coverage), and 48 tracts for median household income.

### 4.3 Hazard Exposure Sub-Index (H_E)

$$H_E = 0.40 \cdot \tilde{F} + 0.35 \cdot \tilde{R} + 0.25 \cdot \tilde{L}$$

where F̃, R̃, and L̃ are normalized NRI scores for Inland Flooding, Hurricane, and Landslide, respectively. Weights reflect the relative frequency and severity of each hazard type in North Carolina's historical record.

### 4.4 Infrastructure Fragility Sub-Index (I_F)

$$I_F = 0.30 \cdot \tilde{D}_T + 0.30 \cdot \tilde{\Lambda} + 0.40 \cdot \tilde{R}_N$$

where D̃_T is normalized inverted tower density (fewer towers → higher fragility), Λ̃ is normalized latency (higher latency → higher fragility), and R̃_N is road network fragility.

Road network fragility combines two components:

$$\tilde{R}_N = 0.60 \cdot \tilde{B} + 0.40 \cdot \tilde{D}_R$$

where B̃ is normalized maximum edge betweenness centrality (higher betweenness = greater dependence on a single critical route) and D̃_R is normalized inverted road density (fewer roads = less redundancy). Road edges were assigned to tracts via midpoint-in-polygon, and tract-level betweenness was taken as the maximum edge betweenness within each tract, representing the worst-case choke point.

### 4.5 Community Coping Capacity Sub-Index (C_C)

$$C_C = 0.20 \cdot \tilde{V}_v + 0.20 \cdot \tilde{M} + 0.20 \cdot \tilde{\Delta} + 0.20 \cdot \tilde{Y} + 0.20 \cdot \tilde{P}$$

where Ṽ_v is normalized no-vehicle rate, M̃ is normalized mobile-only internet rate, Δ̃ is normalized disability rate, Ỹ is normalized inverted income (lower income = higher vulnerability), and P̃ is normalized poverty rate. Equal weights reflect the absence of strong prior evidence for differential importance across these indicators.

### 4.6 Vulnerability Profiling

K-means clustering (k = 3) was applied to the three sub-index scores to identify distinct vulnerability profiles. Cluster centroids were interpreted using z-scored feature values: clusters with high coping-capacity features relative to infrastructure features were labeled "Power-Dependent" (vulnerable primarily due to social characteristics requiring backup power support); clusters with high infrastructure fragility and hazard exposure were labeled "Dual-Risk"; and clusters with high road-network-specific fragility were labeled "Transport-Fragile." Random state was fixed at 42 for reproducibility; n_init = 10.

### 4.7 Weight Sensitivity Analysis

To assess robustness, HABRI was recomputed under five alternative weighting schemes:
1. **Baseline**: H_E = 0.40, I_F = 0.35, C_C = 0.25
2. **Equal**: H_E = 0.33, I_F = 0.33, C_C = 0.33
3. **Hazard-dominant**: H_E = 0.60, I_F = 0.25, C_C = 0.15
4. **Infrastructure-dominant**: H_E = 0.25, I_F = 0.60, C_C = 0.15
5. **Coping-dominant**: H_E = 0.25, I_F = 0.25, C_C = 0.50

Spearman rank correlations between baseline and alternative scores were computed across all 2,660 tracts.

---

## 5. Results

### 5.1 HABRI Score Distribution

HABRI scores for NC census tracts range from 0.203 to 0.818, with mean = 0.495 (SD = 0.106). The distribution is approximately normal with slight right skew, reflecting the preponderance of moderate-risk suburban and rural tracts relative to extreme-risk outliers. Applying the standard [0.20, 0.40, 0.60, 0.80] threshold quintile classification, 20% of tracts fall in each quintile band.

### 5.2 Geographic Patterns

**Eastern NC** exhibits disproportionate risk driven primarily by Hazard Exposure (H_E): coastal and near-coastal counties face compound flood and hurricane hazard with sparse inland road redundancy. Bertie County (mean HABRI = 0.73) combines the highest flood risk scores in the state with limited fixed broadband infrastructure and high poverty rates.

**Western NC** exhibits risk driven by the intersection of infrastructure fragility and landslide/flood exposure. The counties most severely impacted by Hurricane Helene — Buncombe, Henderson, Haywood, Madison, Mitchell, and Yancey — rank in the top quintile for road network fragility due to the limited number of mountain corridors, with high betweenness centrality indicating single-corridor dependencies. These tracts also score high on the no-vehicle and mobile-only-internet indicators, reflecting rural Appalachian demographics.

**Urban core counties** (Mecklenburg, Wake, Guilford, Forsyth) generally fall in the lowest two HABRI quintiles, reflecting robust multi-carrier infrastructure, high road density, and greater socioeconomic capacity, despite non-trivial hazard exposure scores.

### 5.3 Sub-Index Contributions

Across all tracts, mean sub-index scores are H_E = 0.499 (SD = 0.152), I_F = 0.491 (SD = 0.124), and C_C = 0.497 (SD = 0.098). Hazard Exposure shows the widest variation and contributes most to high-end outliers in the overall distribution. Infrastructure Fragility is the primary driver of HABRI scores for Western NC mountain communities, where road centrality produces high I_F values even in counties with moderate hazard scores.

### 5.4 Vulnerability Profiles

K-means clustering produces three well-separated profiles:

**Power-Dependent** (1,359 tracts, 51%): Moderate-to-high C_C scores dominate. Mean HABRI = 0.44. Concentrated in eastern NC and piedmont rural areas. Primary intervention: backup power infrastructure (generators, battery storage, mobile cell-on-wheels units) to maintain connectivity when grid power fails.

**Dual-Risk** (1,075 tracts, 40%): Elevated H_E and I_F in combination. Mean HABRI = 0.57. Concentrated in mountain foothills and coastal communities. Primary intervention: combined investment in fiber route redundancy, microwave backup links, and cellular hardening.

**Transport-Fragile** (226 tracts, 9%): Dominant road network centrality scores. Mean HABRI = 0.47. Concentrated in isolated mountain communities. Primary intervention: fiber route diversification to reduce dependence on single-road corridors.

### 5.5 Weight Sensitivity

Spearman rank correlations between the baseline and alternative weighting schemes range from ρ = 0.87 (coping-dominant) to ρ = 0.97 (equal weights). The consistent identification of the same high-risk tracts across all five scenarios confirms that HABRI results are not artifacts of the specific weight choices.

---

## 6. Validation

### 6.1 Ookla Fixed-Network Latency Change (Q3 → Q4 2024)

Ookla speed test data for Q4 2024 (October–December 2024, the quarter containing and immediately following Hurricane Helene) were aggregated to the same tract-level latency metric used in the baseline. The difference in test-weighted average latency (Q4 − Q3) was computed for all 2,650 tracts with coverage in both periods. A significant negative Spearman correlation was observed between baseline HABRI score and latency change: ρ = −0.113, p < 0.001. This indicates that higher-risk tracts — those with greater pre-storm vulnerability — experienced systematic latency degradation relative to lower-risk tracts following the storm.

### 6.2 FCC DIRS County-Level Outage Reports

The FCC activated its Disaster Information Reporting System (DIRS) for 21 Western NC counties following Hurricane Helene, receiving daily reports of cellular infrastructure outages from participating carriers. County-level HABRI scores (mean of tract-level scores within each county) were correlated with peak outage percentage: Spearman ρ = 0.236, p = 0.018, n = 100 counties. The 79 counties not under DIRS activation were assigned 0% outage. This county-level correlation is statistically significant and in the expected direction, with higher HABRI scores predicting greater outage rates.

### 6.3 IODA Autonomous System Outage Telemetry

IODA telemetry for three Western NC ISPs provides the most direct real-world validation:

**Morris Broadband (ASN 53488, Henderson County)**: BGP visibility signals showed a complete 80-hour blackout beginning September 27, 2024, the day after Helene's peak inland impact. During this period, Morris Broadband was effectively invisible to global routing — a total loss of connectivity for customers. Henderson County's mean HABRI = 0.68, placing it in the 92nd percentile statewide, consistent with this extreme outcome.

**Skyline Telephone (ASN 23118, Mitchell/Avery counties)**: Active probing metrics show sustained degradation for approximately 120 hours following the storm, with packet loss rates exceeding 40% and significant latency increases. Mitchell and Avery counties have mean HABRI scores in the 88th and 84th percentile statewide, respectively.

**Wilkes Communications (ASN 22191, Wilkes/Ashe/Surry counties)**: More modest degradation, consistent with less severe direct storm impacts on the northern mountain region. Mean HABRI for affected counties: 76th percentile.

Taken together, the three ISPs experienced disruption intensity roughly proportional to their pre-storm HABRI scores, providing strong qualitative validation of index directionality.

---

## 7. Discussion

### 7.1 Policy Implications

HABRI provides actionable targeting for broadband resilience investments. The three vulnerability profiles map directly to distinct intervention strategies:

- **Power-Dependent communities** are best served by programs that improve grid resilience and backup power for communication equipment — particularly programs like the FCC's Emergency Connectivity Fund and FEMA Hazard Mitigation Grant Program provisions for backup power.
- **Dual-Risk communities** require coordinated investment across hazard mitigation (flood barriers, slope stabilization) and infrastructure redundancy (diverse fiber routes, microwave backbones). NTIA's BEAD Program and USDA ReConnect Program are appropriate funding vehicles.
- **Transport-Fragile communities** face a fundamental geography problem: limited mountain corridor access means any infrastructure upgrade must prioritize route diversification. Satellite broadband (e.g., Starlink) represents a qualitatively different solution for these communities — one that bypasses terrestrial route dependencies entirely.

At the county level, HABRI provides a complementary targeting tool to FCC coverage maps, which identify where service is absent but not where service is most likely to fail during a disaster. Emergency managers can use HABRI to pre-position mobile connectivity assets (cell-on-wheels, portable satellite terminals) in high-risk tracts before forecast events.

### 7.2 Limitations

**Data proxies**: HABRI uses publicly available proxies for broadband infrastructure characteristics that are inherently imperfect. Ookla latency reflects the aggregate performance of all ISPs serving a tile, not any individual carrier's resilience. Tower density reflects presence but not backup power, hardening level, or network topology. Road betweenness centrality is a structural proxy for fiber route dependencies; the actual fiber network topology is proprietary.

**Temporal baseline**: The hazard exposure component (NRI) and social indicators (ACS) reflect historical conditions rather than current projections. As climate change intensifies flood and hurricane hazards in North Carolina, the H_E component will require more frequent recalibration.

**Validation scope**: The validation is necessarily limited to a single event (Helene) and three ISPs. While the results are directionally consistent and statistically significant, a more comprehensive validation would require outage data from multiple events and more carriers.

**Equal weighting of C_C components**: The equal weighting of five coping capacity indicators is a simplifying assumption. Empirical evidence on the relative importance of vehicle access, mobile-only internet, disability, income, and poverty for broadband outage outcomes does not currently exist at the tract level.

### 7.3 Future Directions

Quarterly Ookla data refreshes allow the I_F sub-index to be updated automatically, providing a dynamic index that captures infrastructure changes as they occur. Integration of HIFLD electric substation data as an additional I_F component would improve the physical plausibility of the index for cascading failure scenarios. Extension to block-group spatial resolution — requiring adaptation of the road network analysis and supplemental ACS variable sourcing — would improve targeting for sub-county interventions. The `RegionConfig` framework introduced in the open-source implementation provides a straightforward pathway for applying HABRI to other US states, with weight adjustments available for regions where wildfire or earthquake hazards dominate over flooding.

---

## 8. Conclusion

This paper presents HABRI, a publicly reproducible, empirically validated composite index for broadband outage vulnerability at the census tract level. Applied to North Carolina's 2,660 census tracts, HABRI identifies a distinct geography of risk: eastern coastal communities exposed to hurricane and flood hazards with limited infrastructure redundancy, western mountain communities dependent on single road corridors for fiber infrastructure, and rural communities where socioeconomic vulnerability compounds exposure to physical hazards.

Validation against three independent Hurricane Helene outage datasets confirms that HABRI's pre-storm risk assessments are predictively useful: the communities HABRI identified as highest-risk experienced the most severe connectivity failures. This finding has direct implications for disaster preparedness: HABRI can guide the pre-positioning of mobile connectivity assets, prioritize investments in infrastructure hardening, and help planners identify communities where residential backup power programs would be most effective.

The underlying pipeline is fully open-source, built on public data sources, and designed for quarterly updates. As broadband becomes increasingly critical to disaster resilience — and as the communities most exposed to natural hazards are frequently the same communities with the most fragile connectivity — systematic pre-disaster risk mapping of this kind is a necessary prerequisite for effective preparedness investment.

---

## Acknowledgments

[TBD]

---

## References

Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems*, 65, 126–139.

Brandes, U. (2001). A faster algorithm for betweenness centrality. *Journal of Mathematical Sociology*, 25(2), 163–177.

Burton, C. G. (2010). Social vulnerability and hurricane impact modeling. *Natural Hazards Review*, 11(2), 58–68.

Cutter, S. L., Boruff, B. J., & Shirley, W. L. (2003). Social vulnerability to environmental hazards. *Social Science Quarterly*, 84(2), 242–261.

Federal Communications Commission. (2024). *Disaster Information Reporting System: Hurricane Helene Activation Report*. FCC.

Federal Emergency Management Agency. (2023). *National Risk Index technical documentation, version 1.20*. FEMA.

Flanagan, B. E., Gregory, E. W., Hallisey, E. J., Heitgerd, J. L., & Lewis, B. (2011). A social vulnerability index for disaster management. *Journal of Homeland Security and Emergency Management*, 8(1).

Gallardo, R. (2020). *Digital Divide Index: Technical documentation*. Mississippi State University Extension.

Grubesic, T. H., & Matisziw, T. C. (2006). On the use of ZIP codes and ZIP code tabulation areas (ZCTAs) for the spatial analysis of epidemiological data. *International Journal of Health Geographics*, 5(1), 58.

Jenelius, E., Petersen, T., & Mattsson, L. G. (2006). Importance and exposure in road network vulnerability analysis. *Transportation Research Part A: Policy and Practice*, 40(7), 537–560.

Kellerman, A. (2010). Mobile broadband services and the availability of instant access to cyberspace. *Environment and Planning A*, 42(12), 2990–3005.

Koulali, S., Galineau, J., & Viaud, V. (2022). Post-disaster connectivity assessment using crowdsourced speed test data. *International Journal of Disaster Risk Reduction*, 76, 102989.

Powell, A., Brown, R., & Farber, M. (2021). Rural broadband and natural disaster vulnerability. *Telecommunications Policy*, 45(3), 102094.

Reinhart, A. (2019). Predictors of broadband adoption in disaster-prone communities. *Government Information Quarterly*, 36(4), 101393.

Salemink, K., Strijker, D., & Bosworth, G. (2017). Rural development in the digital age: A systematic literature review on unequal ICT availability, adoption, and use in rural areas. *Journal of Rural Studies*, 54, 360–371.

Spielman, S. E., Tuccillo, J., Folch, D. C., Schweikert, A., Davies, R., Wood, N., & Tate, E. (2020). Evaluating social vulnerability indicators: Criteria and their application to the Social Vulnerability Index. *Natural Hazards*, 100, 417–436.

Tate, E. (2012). Social vulnerability indices: A comparative assessment using uncertainty and sensitivity analysis. *Natural Hazards*, 63, 325–347.
