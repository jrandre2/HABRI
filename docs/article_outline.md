# Article Outline — HABRI (Revised, Apr 2026)
# Hazard-Adjusted Broadband Reliability Index for North Carolina

**Target venue:** *Telecommunications Policy* (Elsevier)
**Format:** ~8,500 words body text; APA 7th citations; 7 figures; 4 tables; supplementary data
**Abstract limit:** 250 words

---

## OUTLINE REVIEW NOTES — READ BEFORE WRITING

The following flags must be resolved before or during drafting. They represent errors in
the prior skeleton draft, corrections required by the new 4-component index, and new content
introduced by the quarterly time series.

### Factual Corrections (prior draft is wrong on these points)

**F1 — Henderson 92nd percentile claim is wrong.**
The draft says "Henderson County's mean HABRI = 0.68, placing it in the 92nd percentile
statewide." This is doubly wrong with the updated index:
- Henderson county MEAN HABRI = 0.491 (17th percentile among county means)
- The correct claim: tract 37089932000 in Henderson County has HABRI = 0.643, placing it
  in the **91.7th percentile** nationally — this is likely the area served by Morris Broadband
- The distinction between county mean and individual high-risk tracts matters and reinforces
  the case for tract-level analysis over county-level

**F2 — Clustering features misdescribed.**
The draft (§4.6) says k-means clusters on "H_E, I_F, C_C." In fact, clustering uses the
raw sub-component indicators: no_vehicle_vuln, disability_vuln, mobile_only_vuln,
tower_density_norm (power axis) and road_fragility, latency_norm (transport axis).
The three sub-index composites are NOT the clustering features.

**F3 — Transport-Fragile profile narrative is wrong.**
The draft describes Transport-Fragile as "isolated mountain communities with single road
corridors." The actual centroid data contradicts this:
- Transport-Fragile has tower_density_norm = 0.131 (the LOWEST of the three — most towers)
- road_fragility = 0.477 (moderate, not "dominant")
- power_z = −0.745, transport_z = +0.003 in z-score space: very low power fragility,
  average transport fragility
The "mountain corridor" narrative actually belongs to Dual-Risk (road_fragility = 0.599,
mobile_only = 0.703, the WNC high-HABRI tracts are overwhelmingly Dual-Risk).
Transport-Fragile should be described as: communities with good cellular tower coverage
but moderate transport dependency, where the transport axis is the dominant (if not
extreme) fragility dimension.

**F4 — Baseline statistics are outdated.**
All numbers should use the 4-component I_F baseline:
- Range: [0.183, 0.820] (was [0.203, 0.818])
- Mean: 0.499 (was 0.495), SD: 0.105 (was 0.106)
- Profile percentages: Power-Dependent 51.1%, Dual-Risk 40.4%, Transport-Fragile 8.5%
- Profile mean sub-indices are all updated (use table below)
- Top county is Bertie (mean HABRI = 0.734), not a WNC county

**F5 — I_F formula is 3-component in the draft, must become 4-component.**
Old: I_F = 0.30·D̃_T + 0.30·Λ̃ + 0.40·R̃_N
New: I_F = 0.25·D̃_T + 0.25·Λ̃ + 0.30·R̃_N + 0.20·G̃
where G̃ = inverted z-score CDF of transmission line density (km/km²) per tract.
Power grid fragility rationale: tracts with little transmission infrastructure depend on
long distribution lines that are more vulnerable to storm damage and cascading outages.

**F6 — Discussion §7.3 violates prose standards.**
The draft directly names `update_ookla_quarterly.py` and `RegionConfig` as a code object.
Both must be rewritten as plain prose: "quarterly automated update procedure" and
"a multi-state parameterization framework" respectively.

**F7 — Future directions are now present results.**
The draft lists power grid integration and time series as future work. Both are complete.
§7.3 must be completely rewritten with genuinely pending items.

**F8 — References require verification before submission.**
The following citations appear in the draft and are UNVERIFIED. Do not include
in final manuscript without checking a bibliographic database:
- Grubesic & Matisziw (2006) — the cited text ("On the use of ZIP codes...") is a
  paper about epidemiological geography, not broadband. This is a citation error.
  Grubesic & Matisziw have broadband-related papers; find the correct one.
- Koulali et al. (2022) — "Post-disaster connectivity using crowdsourced speed test data" —
  may be hallucinated; verify existence before including.
- Reinhart (2019) — "Predictors of broadband adoption in disaster-prone communities" —
  verify existence.
- Powell et al. (2021) — "Rural broadband and natural disaster vulnerability,
  Telecommunications Policy" — verify existence.

### Structural Additions (not in prior draft)

**S1 — Power grid as new data source** (§3 table and narrative)
**S2 — Power grid in I_F methodology** (§4.4 new subsection)
**S3 — Quarterly time series as a new results section** (§7, new)
**S4 — Recovery monitoring in discussion** (replaces old §7.3 future directions)
**S5 — Geographic narrative must lead with eastern NC** (§5.2)
Eastern NC counties (Bertie, Martin, Jones, Warren) are the top-HABRI counties by mean.
WNC counties are notable for specific high-HABRI tracts driven by I_F, not top-county means.

---

## Title Options

**Recommended:**
"Pre-Disaster Broadband Vulnerability Mapping and Post-Disaster Recovery Monitoring:
The Hazard-Adjusted Broadband Reliability Index for North Carolina"

**Alternative A (original style):**
"A Hazard-Adjusted Broadband Reliability Index for Identifying Communities at Risk of
Connectivity Loss During Natural Disasters: Evidence from North Carolina"

**Alternative B (policy-forward):**
"Mapping Broadband Outage Risk Before Disasters Strike: Development and Hurricane Helene
Validation of the HABRI Index for North Carolina Census Tracts"

*Decision: the recommended title better signals the dual contribution (pre-disaster
prediction + post-disaster monitoring). Alternative A is more conventional for the genre.*

---

## Keywords

broadband resilience; disaster vulnerability; infrastructure fragility; composite index;
Hurricane Helene; North Carolina; telecommunications policy; post-disaster recovery

---

## Abstract (~250 words)

Structure: Problem → Approach → Key results (cross-sectional + validation + time series)
→ Implications

**Content:**
- Problem: Broadband connectivity is critical to disaster response, yet communities most
  exposed to natural hazards frequently have the most fragile communication infrastructure
  and least capacity to absorb disruptions. No publicly reproducible, regularly updatable
  index exists at the census-tract level.
- Approach: HABRI integrates three sub-indices — Hazard Exposure (FEMA NRI, 40%),
  Infrastructure Fragility (cellular tower density, broadband latency, road network
  centrality, and transmission-line density; 35%), Community Coping Capacity (ACS; 25%).
  Applied to all 2,660 NC census tracts.
- Key results: Scores range [0.183, 0.820] (mean = 0.499, SD = 0.105). Validated against
  three Hurricane Helene outage datasets: Ookla latency degradation (ρ = −0.113, p < 0.001,
  n = 2,650), FCC DIRS county outages (ρ = 0.236, p = 0.018, n = 100 counties), and IODA
  BGP telemetry. Quarterly monitoring (Q3 2024 – Q4 2025) reveals incomplete infrastructure
  recovery in WNC: Henderson County's highest-risk tracts remain elevated above pre-storm
  baselines 15 months after Helene. Sensitivity analysis: ρ ≥ 0.87 across five weighting
  schemes.
- Implications: Three vulnerability profiles — Power-Dependent (51%), Dual-Risk (40%),
  Transport-Fragile (9%) — map to distinct interventions. The quarterly update mechanism
  enables HABRI to function as both a pre-disaster targeting tool and a post-disaster
  recovery monitor.

---

## 1. Introduction (~900 words)

### 1.1 Motivation and policy context (~350 words)

- Broadband as critical infrastructure: emergency alerts, damage reporting, FEMA assistance,
  economic recovery — all depend on connectivity during and after disasters
- Rural and low-income communities face compounded vulnerability: disproportionate hazard
  exposure + fragile infrastructure + limited coping capacity
- Hurricane Helene (September 26, 2024) concrete illustration:
  - 21 WNC counties under FCC DIRS activation
  - Morris Broadband (Henderson County): 80-hour BGP blackout beginning September 27
  - Cellular outages left first responders unable to coordinate
  - Post-storm surveys found areas with pre-existing fragility recovered more slowly
- Policy gap: FCC Broadband Data Collection maps coverage, not resilience; SoVI/SVI omit
  communication infrastructure; operator topology data is proprietary
- Investment programs — BEAD, HMGP, BRIC — lack a systematic public-data resilience
  targeting tool at the tract level

### 1.2 Research gap (~300 words)

- Existing broadband indices: Digital Divide Index (Gallardo, 2020), FCC BDCI — neither
  ties to hazard exposure or validates against outage data
- Composite index literature (Cutter et al., 2003; Tate, 2012): well-established for social
  vulnerability; under-applied to communication infrastructure
- Road network centrality applied to transportation vulnerability (Jenelius et al., 2006)
  but not previously to broadband infrastructure
- Ookla data used for coverage mapping but not as a dynamic resilience proxy
- No prior study validates a pre-storm broadband vulnerability score against named-storm
  outage telemetry
- NOTE: Remove Grubesic & Matisziw (2006) citation (wrong paper) — replace with verified
  citation about broadband vulnerability geography

### 1.3 Research questions (~150 words)

Numbered explicitly:
1. Which NC census tracts face the highest broadband outage risk, and which sub-index
   component drives risk in different regions?
2. Do HABRI scores predict observed connectivity failures during Hurricane Helene?
3. Are results robust to plausible alternative weighting schemes?
4. What distinct vulnerability profiles characterize at-risk communities, and what policy
   interventions does each imply?
5. Can HABRI serve as a post-disaster recovery monitor, and which communities show
   incomplete infrastructure recovery one year after Helene?

### 1.4 Contributions and roadmap (~100 words)

Five explicit contributions:
1. First tract-level index integrating hazard exposure, four-indicator infrastructure
   fragility (including power grid), and coping capacity for broadband outage risk
2. Empirically validated against three independent Hurricane Helene datasets
3. Quarterly update mechanism confirmed through six-quarter panel (Q3 2024 – Q4 2025)
4. Post-disaster recovery monitoring demonstrated with WNC latency trajectory
5. Fully reproducible with open data; extensible to other US states

---

## 2. Background and Related Work (~700 words)

### 2.1 Broadband and disaster resilience (~300 words)

- Multiple disaster phases: pre-disaster warning/preparation; during-event coordination;
  post-disaster damage reporting, FEMA applications, remote work
- Rural compounded vulnerability: hazard exposure + single-ISP dependence + limited backup
  power + weaker economic absorption (Salemink et al., 2017)
- Infrastructure interdependency: cellular base stations require grid power; fiber depends
  on cable-accessible roads; power outages → broadband outages → cascading failures
- Cite: Kellerman (2010); Koulali et al. (2022) [IF VERIFIED]; post-Helene FCC reports

### 2.2 Composite vulnerability indices (~250 words)

- SoVI tradition (Cutter et al., 2003); CDC-SVI (Flanagan et al., 2011); equal-weight
  and data-driven weight variants (Burton, 2010; Spielman et al., 2020; Tate, 2012)
- Key debates: additive vs. multiplicative aggregation; equal vs. elicited weights;
  spatial unit of analysis
- HABRI situates itself in this tradition, adding a communication infrastructure domain

### 2.3 Infrastructure fragility indicators (~150 words)

- Cell tower density (HIFLD): coverage proxy, not previously used as fragility indicator
- Road network betweenness centrality: transportation vulnerability (Jenelius et al., 2006)
- Ookla crowd-sourced performance: coverage mapping, not resilience proxy
- Transmission line density: new addition in HABRI; proxy for grid backbone connectivity

---

## 3. Study Area and Data (~900 words)

### 3.1 Study area (~200 words)

- All 100 NC counties, 2,660 census tracts (2020 boundaries, ACS 2022 5-year)
- Geographic range: coastal plain (hurricane/flood) → piedmont → Appalachians (landslide)
- Hurricane Helene: FL landfall Sep 26, 2024; WNC inland flooding; 21 counties DIRS
- **Figure 1:** NC map with county boundaries, DIRS-activated counties, Helene track

### 3.2 Data sources (~700 words)

**Table 1: Data Sources**

| Source | Dataset | Date | Spatial Resolution | Variables Used |
|---|---|---|---|---|
| FEMA | National Risk Index v1.20 | Dec 2025 | Census tract | IFLD_RISKS, HRCN_RISKS, LNDS_RISKS |
| Ookla | Fixed Network Performance (S3) | Q3 2024 baseline + 5 quarterly updates | ~600 m tile | avg_lat_ms, tests |
| HIFLD | Cellular Towers | 2024 | Point | Tower locations |
| HIFLD | Electric Transmission Lines | 2024 | Polyline | Line length, voltage class |
| OpenStreetMap / OSMnx | Drive network | 2024 | Edge | Betweenness centrality, road density |
| Census ACS 5-year | 2018–2022 | Tract | Income, poverty, disability, vehicle, internet type |
| FCC DIRS | Hurricane Helene reports | Oct 2024 | County | Cell site outage % |
| IODA | ASN outage telemetry | Sep–Oct 2024 | ASN | BGP visibility, active probing |

Narrative notes for each source:
- NRI: v1.20 renamed Riverine Flooding → Inland Flooding (RFLD → IFLD columns); 15 tracts
  had "Insufficient Data" → median imputation
- Ookla: Q3 2024 baseline (123,435 NC tiles); v2024+ uses tile_x/tile_y centroid coords
  (not WKT); test-count-weighted tract aggregation; 28 tracts with no coverage → imputed;
  quarterly S3 downloads for Q4 2024 – Q4 2025 (5 additional quarters)
- HIFLD towers: 1,275 NC locations retrieved via ArcGIS REST API; density computed in
  EPSG:2264 (NC State Plane, US survey feet)
- HIFLD transmission lines: 8,263 in-service segments retrieved via bounding-box spatial
  filter (no state column in service); clipped to tract boundaries; line-km density computed
- OSMnx: single statewide graph (648,424 nodes, 1,528,603 edges); k=500 betweenness
  approximation (~30–40 min); edge → tract via midpoint-in-polygon; tract score = max
  edge betweenness
- ACS: statewide single API call; sentinel −666666666 = NaN; 48 tracts imputed for income
- FCC DIRS: 21 counties activated; 79 counties assigned 0%
- IODA: three WNC ISPs; Sep 26 – Oct 7, 2024 window

---

## 4. Methodology (~1,600 words)

### 4.1 HABRI framework overview (~150 words)

$$\text{HABRI} = 0.40 \cdot H_E + 0.35 \cdot I_F + 0.25 \cdot C_C$$

- Weighted linear composite; all sub-indices [0,1]; higher = higher risk
- Weight rationale: physical hazards primary driver (40%); infrastructure secondary (35%);
  social factors modulate but don't dominate (25%)
- **Figure 2:** Index structure diagram — hierarchical: HABRI → sub-indices →
  components → indicators → sources. MUST show 4 I_F components.

### 4.2 Normalization (~200 words)

$$\tilde{x}_i = \Phi\!\left(\frac{x_i - \bar{x}}{s}\right)$$

- Z-score → standard normal CDF; maps mean → 0.5; bounded [0,1]; outlier-robust
- For high-value = low-risk indicators (tower density, road density, income,
  transmission line density): z negated before CDF (higher normalized score = more fragile)
- Missing data: median imputation; all imputed GEOIDs logged for transparency
- Brief comparison to min-max (sensitive to outliers); justify CDF approach

### 4.3 Hazard Exposure sub-index (H_E) (~200 words)

$$H_E = 0.40 \cdot \tilde{F} + 0.35 \cdot \tilde{R} + 0.25 \cdot \tilde{L}$$

- F̃ = Inland Flooding (NRI v1.20: IFLD_RISKS), R̃ = Hurricane (HRCN_RISKS),
  L̃ = Landslide (LNDS_RISKS)
- NRI scores: composite of expected annual loss, social vulnerability, community resilience
- Weight rationale: historical NC hazard frequency and severity record
- Note NRI column rename (RFLD → IFLD in v1.20); 15 tracts imputed

### 4.4 Infrastructure Fragility sub-index (I_F) (~600 words)

$$I_F = 0.25 \cdot \tilde{D}_T + 0.25 \cdot \tilde{\Lambda} + 0.30 \cdot \tilde{R}_N + 0.20 \cdot \tilde{G}$$

Previous 3-component formulation used 0.30/0.30/0.40 without power grid.

**Cellular tower density (D̃_T):**
HIFLD points → spatial join to census tracts → towers per km² → inverted z-score CDF.
Few towers → high fragility. 1,275 NC towers; area computation in EPSG:2264.

**Broadband latency (Λ̃):**
Ookla Q3 2024 → test-count-weighted average latency per tract → z-score CDF.
Higher latency indicates degraded connectivity quality and correlates with infrastructure
age and congestion. 28 tracts imputed for no Ookla coverage.

**Road network fragility (R̃_N):**
$$\tilde{R}_N = 0.60 \cdot \tilde{B} + 0.40 \cdot \tilde{D}_R$$
B̃ = max edge betweenness centrality (k=500 approximation); D̃_R = inverted road density.
Betweenness identifies tracts whose access requires traversal of a critical single route
(choke-point dependency); road density captures redundancy.
Edge → tract assignment via midpoint-in-polygon; boundary-crossing edges counted once.

**Power grid fragility (G̃):** ← NEW
HIFLD electric transmission line density (km of in-service lines per km² of tract area),
inverted z-score CDF. High density → low fragility (strong grid backbone); zero or sparse
lines → high fragility because the tract relies on long distribution lines more susceptible
to storm damage and extended outage.
2,052 of 2,660 tracts contain at least one transmission segment; remaining 608 tracts
(primarily small urban) received median imputation.
Rationale: transmission line density provides a publicly available, spatially explicit
proxy for grid backbone access that complements cellular tower density as an infrastructure
fragility indicator.

### 4.5 Community Coping Capacity sub-index (C_C) (~250 words)

$$C_C = 0.20 \cdot \tilde{V} + 0.20 \cdot \tilde{M} + 0.20 \cdot \tilde{\Delta} + 0.20 \cdot \tilde{Y} + 0.20 \cdot \tilde{P}$$

- Ṽ = no-vehicle rate; M̃ = mobile-only internet rate; Δ̃ = disability rate;
  Ỹ = inverted income; P̃ = poverty rate
- Equal weights: absence of prior empirical evidence for differential importance
- All computed as rates from ACS denominators; 48 tracts imputed for income
- Rationale for each indicator: discuss each in 1–2 sentences

### 4.6 Vulnerability profiling (~200 words)

K-means clustering (k=3) on six sub-component indicators: no_vehicle_vuln,
disability_vuln, mobile_only_vuln, tower_density_norm (power-dependence axis) and
road_fragility, latency_norm (transport-fragility axis). StandardScaler normalization
before fitting. n_init=10, random_state=42.

Cluster labeling is deterministic and based on centroid z-score positions:
- Dual-Risk: cluster with highest combined (power_z + transport_z)
- Transport-Fragile: of the remaining two, the cluster with highest (transport_z − power_z)
- Power-Dependent: the remaining cluster

DESCRIBE EACH PROFILE ACCURATELY based on centroid data (see §5.3):
- Power-Dependent: high tower fragility (few towers), high disability, low latency,
  low road centrality — intervention is backup power
- Dual-Risk: high mobile-only rate (0.703), high road centrality (0.599), high latency
  (0.572), high income vulnerability — the WNC storm impact profile; comprehensive intervention
- Transport-Fragile: low tower fragility (many towers — 0.131), moderate road centrality
  (0.477), moderate latency, above-average income vulnerability — intervention is
  reducing transport dependencies

### 4.7 Weight sensitivity analysis (~200 words)

Five schemes (Table 3). Spearman ρ computed against baseline across all 2,660 tracts.
Use actual computed values: equal=0.9819, hazard-dominant=0.9517,
infrastructure-dominant=0.9327, coping-dominant=0.8728.

---

## 5. Cross-Sectional Results (~1,100 words)

### 5.1 HABRI score distribution (~250 words)

- Range [0.183, 0.820]; mean=0.499 (SD=0.105)
- Approximately normal, slight right skew
- Quintile cut points: Very Low <0.405, Low 0.405–0.471, Moderate 0.471–0.530,
  High 0.530–0.591, Very High >0.591
- Sub-index means: H_E=0.501 (SD=0.194), I_F=0.502 (SD=0.106), C_C=0.491 (SD=0.165)
- **Figure 3:** Four-panel map (H_E, I_F, C_C, HABRI), Natural Breaks, 5 classes

### 5.2 Geographic patterns (~450 words)

LEAD with eastern NC — this is the high-mean-HABRI region:

**Eastern NC (hazard + poverty driven):** The highest county-mean HABRI scores in the
state are in northeastern and southeastern coastal counties — Bertie (0.734), Martin
(0.701), Jones (0.684), Warren (0.675), Bladen (0.670). These counties combine very
high flood and hurricane hazard exposure (H_E) with severe socioeconomic vulnerability
(low income, high poverty, high disability rates). Bertie County's mean HABRI of 0.734
reflects the highest flood risk in the state alongside among the highest poverty and
disability rates. These communities represent the index's "compound vulnerability" case.

**Western NC (infrastructure fragility driven):** WNC counties do not rank among the
highest by county mean HABRI, but contain the highest-HABRI individual tracts in the
state. Mitchell County (mean 0.626, 86th percentile), Yancey (0.604, 72nd percentile),
and Haywood (0.560, 46th percentile) score high on I_F driven by road network centrality
and latency. The highest individual tract in WNC — Henderson County tract 37089932000
(HABRI=0.643, 91.7th percentile nationally) — exemplifies this pattern: high road
betweenness centrality reflecting single-corridor mountain access, combined with high
hazard exposure and latency. That Henderson County's county MEAN is only at the 17th
percentile (mean=0.491) while containing a 91.7th-percentile tract underscores the value
of tract-level over county-level analysis. County averages obscure localized choke-points.

**Urban cores:** Mecklenburg, Wake, Forsyth, Guilford — lowest two HABRI quintiles.
High road density (redundancy) + strong infrastructure + greater economic capacity offsets
non-trivial hazard exposure. Lowest-HABRI tracts are dense urban cores.

### 5.3 Vulnerability profiles (~300 words)

**Table 2: Vulnerability Profiles**

| Profile | N | % | HABRI | H_E | I_F | C_C | tower_dn | latency | road_frag | mobile_only | income_vuln |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Power-Dependent | 1,359 | 51.1 | 0.446 | 0.459 | 0.456 | 0.412 | 0.587 | 0.386 | 0.369 | 0.297 | 0.424 |
| Dual-Risk | 1,075 | 40.4 | 0.569 | 0.545 | 0.582 | 0.591 | 0.563 | 0.572 | 0.599 | 0.703 | 0.668 |
| Transport-Fragile | 226 | 8.5 | 0.480 | 0.542 | 0.398 | 0.494 | 0.131 | 0.463 | 0.477 | 0.467 | 0.546 |

Profile descriptions (write accurately, not from prior narrative):
- Power-Dependent: many tracts with sparse cellular towers (high tower fragility), high
  disability rates, but low latency and low road centrality. These communities are
  fragile primarily because infrastructure depends on grid power they may lack.
- Dual-Risk: highest HABRI (0.569). Very high mobile-only internet rate (0.703) signals
  communities where most households rely on cellular data — these are simultaneously
  most fragile (high road centrality, high latency) and most dependent on connectivity
  quality. The mountain communities most severely affected by Helene predominate here.
- Transport-Fragile: despite good cellular tower coverage (tower_density_norm=0.131,
  lowest fragility from towers), moderate road centrality becomes the defining fragility
  dimension. Above-average income vulnerability (0.546) compounds the risk.

**Figure 4:** Vulnerability profile map

### 5.4 Weight sensitivity (~100 words)

Table 3. Rho values: equal=0.982, hazard-dominant=0.952, infra-dominant=0.933,
coping-dominant=0.873. The coping-dominant scheme produces the greatest deviation
(ρ=0.873) — expected, since C_C indicators are most weakly correlated with
infrastructure indicators in this sample.

---

## 6. Validation Against Hurricane Helene (~900 words)

### 6.1 Ookla fixed-network latency change (~300 words)

- Q3→Q4 2024 latency difference per tract
- Spearman ρ = −0.113, p < 0.001, n = 2,650
- Negative ρ: higher pre-storm HABRI → more post-storm latency degradation
- Panel A of Figure 5

### 6.2 FCC DIRS county-level outages (~300 words)

- County HABRI (tract mean) vs. peak cell outage %
- ρ = 0.236, p = 0.018, n = 100
- 21 activated counties + 79 at 0%; note design conservatism (bimodal distribution)
- Panel B of Figure 5

### 6.3 IODA autonomous system telemetry (~300 words)

Write accurately based on data (correct from prior draft):
- Morris Broadband (ASN 53488, Henderson County): 80-hour BGP blackout from Sep 27.
  Service area encompasses Henderson tract 37089932000 (HABRI=0.643, 91.7th pctile).
  Note: Henderson county MEAN HABRI is moderate (0.491); the extreme outage reflects
  concentration of risk in a specific high-HABRI tract, not county-wide severity.
  This reinforces the case for tract-level vs. county-level targeting.
- Skyline Telephone (ASN 23118, Mitchell/Avery): sustained active probing degradation
  ~120 hours; Mitchell county at 86th percentile (HABRI=0.626)
- Wilkes Communications (ASN 22191, Wilkes/Ashe/Surry): moderate degradation consistent
  with less direct storm impact; counties at ~60th–70th percentile
- Qualitative result: outage severity ~ HABRI percentile ranking

### 6.4 Component-level validation: road network proxy (~200 words)

The road network fragility component (R̃_N) rests on an assumption that wired broadband
infrastructure is physically co-located with road rights-of-way, such that roads with high
betweenness centrality carry critical last-mile fiber or cable. This assumption was tested
directly by comparing road_fragility correlations with post-Helene latency degradation
separately for Ookla fixed-network (type=fixed: fiber, cable, DSL) and mobile/cellular
(type=mobile) tiles.

- If the road ROW assumption holds, road_fragility should predict fixed degradation more
  than mobile, since cellular infrastructure follows tower placement rather than road corridors
- If the correlation is equal for both, it suggests geographic confounding (remote = both bad
  roads and bad broadband), not a road-mediated mechanism

Results (WNC tracts, n=130):

- Fixed broadband: road_fragility ρ = −0.287, p < 0.001
- Mobile/cellular: road_fragility ρ = +0.078, p = 0.38 (not significant; sign reversed)
- Fixed/mobile ratio: 3.69×

The sign reversal for mobile is consistent with cellular failures occurring through distinct
mechanisms (power loss at towers, backhaul path diversity) unrelated to road-corridor damage.
Statewide, both correlations are near-zero — road fragility is a disaster-specific signal in
topographically complex terrain, not a general broadband predictor.

This result upgrades the road proxy from an unverified theoretical assumption to an
empirically supported methodological choice.

**Table 4: Validation Summary**
| Dataset | Metric | n | ρ | p |
|---|---|---|---|---|
| Ookla Q3→Q4 2024 (fixed) | Δ latency_norm | 2,650 tracts | −0.113 | <0.001 |
| Ookla Q3→Q4 2024 (fixed, WNC) | Δ latency_norm × road_fragility | 130 tracts | −0.287 | <0.001 |
| Ookla Q3→Q4 2024 (mobile, WNC) | Δ latency_norm × road_fragility | 130 tracts | +0.078 | 0.38 |
| FCC DIRS | County cell outage % | 100 counties | 0.236 | 0.018 |
| IODA BGP | Qualitative ASN ranking | 3 ASNs | — | — |

**Figure 5:** Three-panel validation

- Panel A: Ookla scatter (HABRI vs. Δlatency, all tracts)
- Panel B: FCC county scatter
- Panel C: IODA time series (BGP visibility, three ASNs, Helene window)

*Note: road proxy validation (§6.4) is a separate figure — see road_proxy_validation.png.
Consider whether to include as Panel D or as a supplementary figure.*

---

## 7. Quarterly Monitoring and Post-Disaster Recovery (~700 words)

*This section is entirely new. It demonstrates HABRI as a recovery monitoring tool,
not just a pre-disaster risk score.*

### 7.1 Quarterly update methodology (~150 words)

- Only the latency component of I_F varies by quarter (Ookla data refreshes quarterly)
- Tower density, road fragility, power grid fragility, H_E, and C_C remain at baseline
  until those source datasets update
- Q3 2024 (baseline, pre-Helene) through Q4 2025: six quarters
- Q4 2024 = post-Helene Ookla data; captures the actual outage in the latency metric

### 7.2 Statewide trend (~100 words)

- Statewide mean HABRI is stable (0.4985–0.4987 across six quarters) — expected, since
  Helene affected a small fraction of NC's 2,660 tracts
- The value of the time series lies at the county and tract level, not statewide

### 7.3 WNC county recovery trajectories (~350 words)

**Figure 6:** WNC county quarterly HABRI trends, Q3 2024 – Q4 2025, vs. NC statewide mean

Key county-level findings:
- Mitchell (+0.023 impact, still +0.012 above baseline at Q4 2025) — largest absolute
  impact and slowest proportional recovery; 86th percentile county
- Yancey (+0.022 impact, +0.008 above baseline at Q4 2025)
- Henderson (+0.017 impact, +0.014 above baseline at Q4 2025) — incomplete recovery
  despite being only the 17th-percentile county overall; driven by specific high-HABRI tracts
- Madison (+0.007 impact, essentially recovered at Q4 2025: −0.002 vs. baseline)
- Buncombe (+0.014 impact, still +0.007 above baseline)

Recovery metric: latency_norm change tells the infrastructure story most directly.
Henderson latency_norm: 0.530 (Q3 2024 baseline) → 0.723 (Q4 2024, +0.193) →
0.692 (Q4 2025, still +0.162 above pre-storm level). One year after Helene, latency
has not returned to baseline — indicating persistent infrastructure degradation or
changed traffic patterns post-storm.

Recovery by profile (WNC tracts only):
- Power-Dependent WNC tracts (n=46): impact +0.020, still +0.012 above baseline at Q4 2025
- Dual-Risk WNC tracts (n=67): impact +0.009, still +0.009 above baseline (no recovery)
- Transport-Fragile WNC tracts (n=19): impact +0.013, nearly recovered at Q4 2025 (+0.003)
Dual-Risk tracts show the least proportional recovery — consistent with compound fragility
making infrastructure restoration harder.

### 7.4 Implications for recovery monitoring (~100 words)

- HABRI time series identifies communities requiring ongoing monitoring, not one-time assessment
- Counties where HABRI remains elevated > 12 months post-event are candidates for
  long-term infrastructure resilience investment, not just emergency repair
- The quarterly cadence aligns with FCC reporting periods and HMGP project cycles

---

## 8. Discussion (~1,100 words)

### 8.1 Policy implications (~500 words)

*BEAD Program:*
HABRI as supplemental targeting criterion — not just where broadband is absent, but
where broadband is most likely to fail. Transport-Fragile tracts: satellite-first or
satellite-supplemental deployment. Dual-Risk tracts: physical hardening requirements in
grant conditions. Power-Dependent tracts: backup power provisions in project designs.

*HMGP/BRIC:*
HABRI I_F scores as quantitative pre/post benefit metric for HMGP subapplications
(e.g., redundant fiber route reduces I_F → measurable resilience gain). The quarterly
update mechanism enables project impact tracking.

*DIRS pre-positioning:*
Emergency managers can use HABRI quintile maps to pre-position mobile connectivity
assets (cell-on-wheels, portable satellite terminals) in highest-HABRI tracts before
forecast events. The DIRS analysis confirms that pre-storm HABRI scores predict which
counties will experience outages.

*Recovery policy:*
The incomplete recovery finding (WNC Dual-Risk tracts still elevated at Q4 2025)
provides evidence for sustained investment in post-disaster connectivity infrastructure —
not just emergency response, but long-term resilience building.

*Regulatory angle:*
FCC should incorporate resilience indicators alongside coverage in reporting requirements.
Current data collection identifies service availability, not service survivability.

### 8.2 Limitations (~350 words)

- Proxy limitations: Ookla = aggregate ISP performance, not individual operator; tower
  count ≠ hardening or backup power; road centrality validated as a proxy for wired fiber
  topology in mountainous terrain (§6.4) but not for flat or urban terrain; transmission
  line density ≠ grid hardening or substation backup
- Temporal baseline: NRI (historical conditions), ACS (2018–2022) — does not capture
  climate trajectory; H_E recalibration needed as climate projections improve
- Validation scope: single event (Helene), three ISPs, one state — more events and carriers
  needed for generalizability
- Equal C_C weights: simplifying assumption; no empirical evidence yet on relative
  importance for broadband outcomes specifically
- Spatial unit: census tract; sub-tract heterogeneity (e.g., Morris Broadband covering
  only rural parts of Henderson County); block-group disaggregation is future work
- Latency as recovery proxy: latency changes capture infrastructure quality but are
  influenced by traffic patterns; post-Helene network reconfiguration could affect readings

### 8.3 Future directions (~250 words)

- Multi-event validation: Tropical Storm Debby (2024), Florence (2018) if data available;
  western wildfires for other-state applications
- Block-group spatial resolution: requires subdivision of road network analysis
- Formal uncertainty quantification: bootstrap confidence intervals on HABRI tract scores
- Multi-state application: the multi-state parameterization framework already implemented
  provides a pathway; requires state-specific weight calibration and validation events
- Carrier-level outage data: if FCC or carriers release more granular DIRS data,
  tract-level ISP-specific validation would substantially strengthen the index
- Climate-adjusted H_E: FEMA NRI does not yet incorporate forward-looking hazard projections;
  integration of NOAA climate scenarios would improve H_E long-run validity

---

## 9. Conclusion (~450 words)

- HABRI provides a reproducible, validated, quarterly-updatable broadband resilience index
- Two uses confirmed: pre-disaster risk identification and post-disaster recovery monitoring
- Three vulnerability profiles map directly to distinct policy interventions
- Hurricane Helene validation confirms predictive validity across three independent datasets
- One year after Helene, Dual-Risk WNC tracts show the least recovery — consistent with
  compound fragility and requiring sustained investment attention
- Open-source, public-data, extensible methodology available at github.com/jrandre2/HABRI
- As broadband becomes critical infrastructure for disaster resilience, systematic
  pre-disaster vulnerability mapping is a necessary prerequisite for effective
  preparedness investment

---

## Figures (7)

| # | Description | File / Status |
|---|---|---|
| 1 | NC study area: county boundaries, DIRS-activated counties, Helene track | regenerate |
| 2 | Index structure diagram — hierarchical, 4 I_F components | new (conceptual) |
| 3 | Four-panel baseline map: H_E, I_F, C_C, HABRI (Natural Breaks, 5 classes) | `habri_4panel.png` — regenerate at 300 DPI |
| 4 | Vulnerability profile map | `habri_profiles.png` — regenerate at 300 DPI |
| 5 | Three-panel validation: Ookla scatter, FCC scatter, IODA time series | composite — new |
| 6 | WNC quarterly recovery: county-level HABRI trend Q3 2024 – Q4 2025 | `habri_timeseries_wnc.png` — polish for publication |
| 7 | Weight sensitivity: ρ across 5 schemes (bar or table-figure) | notebook 04 — regenerate |

---

## Tables (4)

| # | Description |
|---|---|
| 1 | Data sources (source, dataset, date, resolution, variables, use) — add HIFLD transmission lines |
| 2 | Vulnerability profiles (N, %, mean HABRI, H_E, I_F, C_C, key sub-components, intervention) |
| 3 | Sensitivity analysis (5 weight schemes, ρ vs. baseline) |
| 4 | Validation summary (dataset, metric, n, ρ, p) |

---

## Supplementary Material

- S1: County-level HABRI summary (all 100 counties: mean, SD, min, max, top-quintile %)
- S2: Full tract-level scores (link to GitHub/Zenodo)
- S3: Quarterly HABRI summary by WNC county (Q3 2024 – Q4 2025)
- S4: Robustness check — alternative normalization (min-max vs. z-score CDF comparison)
- S5: Power grid fragility layer methodology and tract coverage statistics

---

## Submission Checklist (to complete before first draft is finalized)

- [ ] Verify all four flagged references (F8 above) before including in manuscript
- [ ] Replace Grubesic & Matisziw (2006) with correct broadband-vulnerability citation
- [ ] Figure 1 needs to be created (currently does not exist as a file)
- [ ] Figure 2 needs to be created (conceptual diagram)
- [ ] Figures 3 and 4 need regeneration at 300 DPI with submission-quality fonts
- [ ] Figure 5 needs to be assembled as a composite three-panel
- [ ] Figure 6 (WNC recovery) needs publication polish (font size, labels)
- [ ] Archive dataset on Zenodo, obtain DOI
- [ ] Co-author list and CRediT statement finalized
- [ ] Highlights drafted (3–5 bullets, ≤85 characters each)
- [ ] Cover letter drafted emphasizing policy relevance for TP readership
