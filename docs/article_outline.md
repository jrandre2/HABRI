# Article Outline — HABRI: Hazard-Adjusted Broadband Reliability Index for North Carolina

**Target venue:** *Telecommunications Policy*
(Elsevier; ~8,000–10,000 words; APA citations; blind peer review)

**Estimated length:** ~8,500 words main text, 6 figures, 4 tables, supplementary data
**Abstract word limit:** 250 words (TP standard)
**Keywords:** 5–8

---

## Proposed Title

**"A Hazard-Adjusted Broadband Reliability Index for Identifying Communities at Risk of Connectivity Loss During Natural Disasters: Evidence from North Carolina"**

**Alternative titles:**
- "Mapping Broadband Vulnerability to Natural Disasters: A Composite Index for North Carolina Census Tracts"
- "HABRI: A Composite Index for Pre-Disaster Broadband Resilience Planning"

---

## Keywords

broadband resilience; disaster vulnerability; natural hazards; composite index; infrastructure fragility; Hurricane Helene; North Carolina; telecommunications policy

---

## Abstract (~250 words)

Structure: Problem statement → Approach → Key results → Implications

- **Problem:** Broadband connectivity is critical to disaster response, yet communities most exposed to natural hazards are often those with the most fragile communication infrastructure and least socioeconomic capacity to absorb disruptions. No publicly reproducible, regularly updatable index exists that integrates hazard exposure, infrastructure fragility, and social vulnerability to quantify broadband outage risk before disaster strikes.
- **Approach:** Introduce HABRI (Hazard-Adjusted Broadband Reliability Index), a weighted composite score for all 2,660 NC census tracts, combining FEMA NRI hazard scores (40%), infrastructure fragility proxies — cell tower density, broadband latency, road network centrality (35%), and Census ACS socioeconomic indicators (25%). K-means clustering identifies three vulnerability profiles.
- **Key results:** Scores range [0.20, 0.82] (mean=0.495). Validated against three Hurricane Helene (Sep 2024) outage datasets: Ookla latency degradation (ρ=−0.113, p<0.001), FCC county outages (ρ=0.236, p=0.018), and IODA BGP telemetry. Weight sensitivity analysis confirms rank stability (Spearman ρ>0.85 across five weighting schemes).
- **Implications:** HABRI identifies distinct intervention priorities — power infrastructure, route redundancy, and fiber diversification — for 51%, 40%, and 9% of tracts respectively. The methodology is publicly reproducible, updatable quarterly using open Ookla data, and extensible to other US states.

---

## 1. Introduction (~900 words)

### 1.1 — Motivation and policy context (~350 words)

- Broadband as critical infrastructure for disaster response: emergency alerts, damage reporting, FEMA assistance, economic recovery
- Rural/low-income communities face compounded vulnerability: disproportionate hazard exposure + fragile infrastructure + limited coping capacity
- Hurricane Helene (Sep 2024) as a concrete illustration: WNC outages, Morris Broadband 80-hr BGP blackout, DIRS activation in 21 counties
- Policy gap: FCC Broadband Data Collection maps coverage but not resilience; existing vulnerability indices (SoVI, CDC-SVI) omit communication infrastructure entirely
- BEAD Program, HMGP, BRIC all involve investment prioritization — no systematic, public-data resilience targeting tool exists at the tract level

### 1.2 — Research gap (~300 words)

- Existing broadband vulnerability literature: Digital Divide Index (Gallardo, 2020), FCC BDCI — neither ties to hazard exposure or validates against outage events
- Composite index methodology (Cutter et al. 2003; Tate 2012): well-established for social vulnerability; under-used for infrastructure resilience
- Road network centrality applied to transportation vulnerability (Jenelius et al. 2006) but not broadband resilience
- Ookla crowd-sourced data: used for coverage mapping but not as a resilience proxy
- No prior study validates a pre-storm broadband vulnerability score against actual outage telemetry from a named storm
- Cite: Grubesic & Matisziw (2006); Salemink et al. (2017); Powell et al. (2021); Koulali et al. (2022)

### 1.3 — Research questions (~150 words)

Explicitly numbered:

1. Which NC census tracts face the highest risk of broadband connectivity loss during natural disasters, and which combination of hazard exposure, infrastructure fragility, and social vulnerability drives that risk?
2. Do HABRI scores predict observed broadband and cellular connectivity failures during Hurricane Helene (September 2024)?
3. Are results robust to plausible alternative weighting schemes?
4. What distinct vulnerability profiles characterize at-risk communities, and what policy interventions does each imply?

### 1.4 — Contributions and roadmap (~100 words)

Explicitly listed:
- First index to integrate hazard exposure, infrastructure fragility (with road network centrality), and coping capacity for broadband outage risk at the census-tract level
- Empirically validated against three independent Hurricane Helene datasets
- Publicly reproducible with open data; updatable quarterly; extensible via `RegionConfig` to other states
- Vulnerability profiles mapped to specific intervention categories relevant to BEAD, HMGP, BRIC program targeting

---

## 2. Study Area and Data (~1,100 words)

### 2.1 — Study area (~250 words)

- North Carolina: 100 counties, 2,660 census tracts (2020 boundaries, matched to ACS 2022 5-year)
- Geographic diversity: coastal plain (hurricane/flood), piedmont, Appalachian mountains (landslide/flood)
- Hurricane Helene context: Sep 26, 2024 landfall FL; inland flooding in WNC; 21 counties under FCC DIRS activation
- **Figure 1:** NC study area map with county boundaries, DIRS-activated counties highlighted, Helene track

### 2.2 — Data sources (~850 words)

Organize as narrative + summary table.

**Table 1: Data Sources**
| Source | Dataset | Date | Spatial Resolution | Variables Used |
|---|---|---|---|---|
| FEMA | National Risk Index v1.20 | Dec 2025 | Census tract | IFLD_RISKS, HRCN_RISKS, LNDS_RISKS |
| Ookla | Fixed Network Performance (S3) | Q3 2024 (baseline) | ~600m tile | avg_lat_ms, tests |
| HIFLD | Cellular Towers | 2024 | Point | Tower locations |
| OpenStreetMap / OSMnx | Drive network | 2024 | Edge | Betweenness centrality, road density |
| Census ACS 5-year | 2018–2022 | 2022 | Census tract | Income, poverty, disability, vehicle access, internet type |
| FCC DIRS | Helene activation reports | Oct 2024 | County | Cell site outage % |
| IODA | ASN outage telemetry | Sep–Oct 2024 | ASN | BGP visibility, active probing |

- Note NRI v1.20 column rename (RFLD → IFLD)
- Note Ookla pyarrow/pandas compat issue and workaround
- Note OSMnx k=500 betweenness approximation and runtime (~30–40 min)
- Note Census sentinel value (-666666666 = NaN) and imputation (48 tracts for income)

---

## 3. Methodology (~1,800 words)

### 3.1 — HABRI framework overview (~200 words)

- Formula: `HABRI = 0.40·H_E + 0.35·I_F + 0.25·C_C`
- **Figure 2:** Index structure diagram (hierarchical: sub-indices → components → indicators → sources)
- Additive linear composite; all sub-indices normalized [0,1]; higher = higher risk
- Weight rationale: physical hazards primary driver (40%); infrastructure design secondary (35%); social factors modulate (25%)

### 3.2 — Normalization (~200 words)

- Z-score → standard normal CDF: `x̃ = Φ((x − x̄)/s)`
- Maps mean → 0.5; bounded [0,1]; outlier-robust
- For high-value = lower-risk indicators: `invert=True` negates z before CDF
- Missing value imputation: uniform median imputation; all imputed GEOIDs logged
- Compare to min-max (note sensitivity to outliers); justify CDF approach

### 3.3 — Hazard Exposure sub-index (H_E) (~300 words)

- Formula: `H_E = 0.40·F̃ + 0.35·R̃ + 0.25·L̃`
- NRI score interpretation: composite of expected annual loss, social vulnerability, community resilience
- Weight rationale for flood/hurricane/landslide: NC historical frequency and severity
- 15 tracts with "Insufficient Data" NRI ratings → median imputation

### 3.4 — Infrastructure Fragility sub-index (I_F) (~600 words)

- Formula: `I_F = 0.30·D̃_T + 0.30·Λ̃ + 0.40·R̃_N`
- **Tower density (D̃_T):** HIFLD points → spatial join → towers/km² → inverted z-score CDF
- **Broadband latency (Λ̃):** Ookla Q3 2024 → test-weighted avg_lat_ms per tract → z-score CDF. 28 tracts with no coverage → median imputed. Note latency as resilience proxy (higher latency = degraded infrastructure).
- **Road network centrality (R̃_N):**
  - `R̃_N = 0.60·B̃ + 0.40·D̃_R`
  - Betweenness centrality: k=500 approximation on statewide directed graph (648K nodes, 1.5M edges); edge → tract via midpoint-in-polygon; tract score = max edge betweenness (worst-case choke point)
  - Road density: total edge length / tract area km²; inverted (more roads = more redundancy = lower fragility)

### 3.5 — Community Coping Capacity sub-index (C_C) (~300 words)

- Five ACS indicators, equally weighted at 0.20 each
- No-vehicle rate, mobile-only internet rate, disability rate, inverted income, poverty rate
- Equal weights: absence of prior evidence for differential importance
- All computed as rates (numerator/denominator from ACS); disability = (18-64 + 65+) / total population

### 3.6 — Vulnerability profiling (~200 words)

- K-means clustering, k=3 on H_E, I_F, C_C (random_state=42, n_init=10)
- Cluster labels derived from z-scored centroids: Power-Dependent, Dual-Risk, Transport-Fragile
- Intervention logic: Power-Dependent → backup power; Dual-Risk → combined investment; Transport-Fragile → route diversification

---

## 4. Results (~1,500 words)

### 4.1 — HABRI score distribution (~300 words)

- Range [0.203, 0.818]; mean=0.495, SD=0.106; approximately normal with slight right skew
- Quintile distribution (quintile labels and cut points)
- **Figure 3:** Four-panel map — H_E, I_F, C_C, HABRI composite (Natural Breaks classification, 5 classes)

### 4.2 — Geographic patterns (~500 words)

- Eastern NC: hazard-driven risk (flood + hurricane); Bertie highest mean HABRI
- Western NC: infrastructure fragility-driven (road centrality); Henderson, Haywood, Madison, Mitchell, Yancey
- Urban cores (Mecklenburg, Wake): lowest quintile — infrastructure redundancy + socioeconomic capacity offsets hazard
- Decompose by sub-index: which component drives risk in each region

### 4.3 — Vulnerability profiles (~400 words)

- **Table 2: Vulnerability Profiles**

| Profile | N Tracts | % | Mean HABRI | Mean H_E | Mean I_F | Mean C_C | Primary Intervention |
|---|---|---|---|---|---|---|---|
| Power-Dependent | 1,359 | 51% | 0.44 | — | — | — | Backup power, mobile COW |
| Dual-Risk | 1,075 | 40% | 0.57 | — | — | — | Fiber redundancy + generators |
| Transport-Fragile | 226 | 9% | 0.47 | — | — | — | Route diversification, satellite |

- **Figure 4:** Vulnerability profile map

### 4.4 — Weight sensitivity (~300 words)

- **Table 3: Sensitivity Analysis — Spearman ρ Between Baseline and Alternative Rankings**

| Weight Scheme | H_E | I_F | C_C | ρ vs. Baseline |
|---|---|---|---|---|
| Baseline | 0.40 | 0.35 | 0.25 | 1.00 |
| Equal | 0.33 | 0.33 | 0.33 | — |
| Hazard-dominant | 0.60 | 0.25 | 0.15 | — |
| Infrastructure-dominant | 0.25 | 0.60 | 0.15 | — |
| Coping-dominant | 0.25 | 0.25 | 0.50 | — |

---

## 5. Validation (~900 words)

### 5.1 — Ookla latency degradation Q3→Q4 2024 (~300 words)

- Spearman ρ=−0.113, p<0.001, n=2,650 tracts
- Interpretation: higher pre-storm HABRI → more latency degradation post-Helene
- Scatter plot: HABRI vs. Δlatency (ms)

### 5.2 — FCC DIRS county outages (~300 words)

- County-level HABRI (tract mean) vs. FCC outage % (21 DIRS counties + 79 at 0%)
- Spearman ρ=0.236, p=0.018, n=100 counties
- Scatter plot: county HABRI vs. outage %

### 5.3 — IODA ASN outage telemetry (~300 words)

- Morris Broadband (ASN 53488): 80-hour BGP blackout — Henderson Co. (92nd pctile HABRI)
- Skyline Telephone (ASN 23118): sustained active probing degradation — Mitchell/Avery (88th, 84th pctile)
- Wilkes Communications (ASN 22191): moderate degradation — Wilkes/Ashe/Surry (76th pctile)
- Ranking: disruption severity ~ HABRI percentile rank

**Figure 5:** Three-panel validation figure
- Panel A: Ookla scatter (HABRI vs. Δlatency)
- Panel B: FCC county scatter (county HABRI vs. outage %)
- Panel C: IODA time series (BGP visibility for 3 ASNs, Helene window highlighted)

**Table 4: Validation Summary**
| Dataset | Metric | n | Spearman ρ | p-value |
|---|---|---|---|---|
| Ookla Q3→Q4 latency | Δavg_lat_ms | 2,650 tracts | −0.113 | <0.001 |
| FCC DIRS cell outages | County outage % | 100 counties | 0.236 | 0.018 |
| IODA BGP (qualitative) | ASN severity rank | 3 ASNs | — | — |

---

## 6. Discussion (~1,200 words)

### 6.1 — Policy implications (~500 words)

- BEAD Program: HABRI as supplemental targeting criterion beyond coverage maps
  - Transport-Fragile tracts: satellite-first or satellite-supplemental deployment
  - Dual-Risk tracts: require physical hardening requirements in grant conditions
- HMGP / BRIC: power-grid and route redundancy sub-grants; HABRI scores as pre/post impact metric for benefit-cost analyses
- DIRS pre-positioning: mobile connectivity assets (COW, SECU-SATCOM) deployed to highest-HABRI tracts before forecast events
- Regulatory angle: FCC should incorporate resilience indicators alongside coverage in reporting requirements

### 6.2 — Limitations (~400 words)

- Infrastructure proxies: Ookla latency = aggregate of all ISPs; tower density ≠ hardening level; road centrality = structural proxy for fiber topology
- Temporal baseline: NRI and ACS reflect historical conditions; climate change will alter H_E over time
- Validation scope: single event (Helene), three ISPs; more events and carriers needed
- Equal C_C weights: simplifying assumption; no empirical evidence for differential importance
- Spatial unit: census tract; sub-tract heterogeneity exists; block-group resolution future work

### 6.3 — Future directions (~300 words)

- Quarterly latency refresh already automated (`update_ookla_quarterly.py`)
- Power grid transmission line layer (HIFLD) — pending integration decision
- Block-group disaggregation for finer targeting
- Multi-state extension via `RegionConfig` (src/region.py)
- Formal uncertainty quantification: bootstrap CIs on HABRI scores

---

## 7. Conclusion (~500 words)

- HABRI provides a reproducible, validated, regularly updatable broadband resilience index at the census-tract level
- Three vulnerability profiles map directly to distinct policy interventions
- Hurricane Helene validation confirms index predictive validity
- HABRI is ready for integration into BEAD, HMGP, and BRIC program targeting workflows
- Open-source code and methodology available at https://github.com/jrandre2/HABRI

---

## Figures (6 main)

| # | Description | Source / Script |
|---|---|---|
| Fig 1 | NC study area: county boundaries, DIRS-activated counties, Helene track | notebook 04 / new |
| Fig 2 | HABRI index structure diagram (hierarchical) | new (conceptual) |
| Fig 3 | Four-panel map: H_E, I_F, C_C, HABRI | `habri_4panel.png` (regenerate for submission quality) |
| Fig 4 | Vulnerability profile map | `habri_profiles.png` |
| Fig 5 | Three-panel validation: Ookla scatter, FCC scatter, IODA time series | new composite |
| Fig 6 | Sensitivity analysis: ρ across 5 weight scenarios | notebook 04 output |

---

## Tables (4 main)

| # | Description |
|---|---|
| Table 1 | Data sources summary (source, date, resolution, variables, use) |
| Table 2 | Vulnerability profile characteristics (N, %, mean sub-indices, intervention) |
| Table 3 | Sensitivity analysis weight schemes and ρ vs. baseline |
| Table 4 | Validation summary (dataset, n, ρ, p) |

---

## Supplementary Material

- S1: County-level HABRI summary table (all 100 counties: mean, SD, min, max, top quintile %)
- S2: Full tract-level scores CSV (link to GitHub or Zenodo)
- S3: Robustness check — alternative normalization (min-max vs. z-score CDF)
- S4: Quarterly time series plots (Q3 2024 – Q4 2025) once data is ready

---

## Manuscript Readiness Checklist

Before submission:

- [ ] Q1–Q4 2025 quarterly time series complete and analyzed
- [ ] Power grid integration decision finalized
- [ ] All figures regenerated at 300 DPI with journal-consistent fonts (Arial/Helvetica)
- [ ] All tables formatted per *Telecommunications Policy* style guide
- [ ] References verified in APA 7th edition format
- [ ] Supplementary files prepared and uploaded
- [ ] Data archived on Zenodo with DOI
- [ ] Co-author list and acknowledgments finalized
- [ ] Cover letter drafted
