# HABRI Stakeholder Outreach Templates

Scope note: these templates are intentionally North Carolina-facing. They describe the NC baseline product for state and federal stakeholders and do not automatically mention the Tennessee extension or the shared NC+TN standardized layer unless you customize the message.

Tailored messages for the three primary audiences. Personalize the bracketed fields before sending.

---

## 1. NC Division of Emergency Management (NCEM)

**To:** [Director / Deputy Director, NCEM]  
**Subject:** Pre-Disaster Broadband Vulnerability Mapping Tool for NC Emergency Preparedness

Dear [Name],

I am writing to share a research tool that may be directly useful to NCEM's preparedness planning and post-disaster communications operations: the Hazard-Adjusted Broadband Reliability Index (HABRI), a publicly available, census-tract-level broadband outage risk model for all 100 NC counties.

HABRI was developed at [Texas Tech University] and validated against Hurricane Helene outage data from three independent sources — Ookla fixed-network performance measurements, FCC Disaster Information Reporting System reports, and Internet Outage Detection and Analysis (IODA) telemetry. The validation found that HABRI correctly identified the counties and providers that experienced the most severe connectivity failures during Helene, including the 80-hour complete network blackout suffered by Morris Broadband in Henderson County.

**What HABRI provides:**

- Risk scores for all 2,660 NC census tracts, combining FEMA NRI hazard exposure, cellular tower density, broadband latency, road network centrality, electric transmission grid exposure, and ACS socioeconomic vulnerability
- Three vulnerability profiles (*Power-Dependent*, *Dual-Risk*, *Transport-Fragile*) with distinct recommended interventions
- An interactive web map and downloadable data for integration into existing planning tools
- A quarterly update mechanism tied to Ookla's public speed-test data

**Potential applications for NCEM:**
- Pre-positioning mobile connectivity assets (cell-on-wheels, portable satellite terminals) before forecast events in highest-HABRI tracts
- Informing the prioritization of HMGP broadband resilience projects
- Identifying communities where "last mile" satellite backup would provide the greatest marginal resilience benefit

The full dataset, methodology, and code are available at: https://github.com/jrandre2/HABRI  
An interactive map is available at: https://jrandre2.github.io/HABRI/

I would welcome the opportunity to present these findings to your planning staff and to discuss how HABRI might be integrated into NCEM's preparedness workflows. Please feel free to contact me at jesseand@ttu.edu.

Sincerely,  
Jesse R. Andrews  
[Title], Texas Tech University

---

## 2. NC Department of Information Technology — Broadband Infrastructure Office

**To:** [Director, NCDIT Broadband Infrastructure Office]  
**Subject:** Research Tool for Identifying Disaster-Vulnerable Broadband Communities in NC

Dear [Name],

As your office continues to implement North Carolina's BEAD Program broadband expansion, I wanted to share a complementary research tool focused on a dimension of broadband equity that is often overlooked in coverage-based analyses: resilience to natural disaster.

HABRI (Hazard-Adjusted Broadband Reliability Index) provides a systematic, data-driven ranking of all 2,660 NC census tracts by their risk of losing broadband connectivity during a natural disaster. Rather than measuring whether broadband *exists* in a community, HABRI assesses whether it is likely to *survive* a flood, hurricane, or landslide event.

The distinction matters for BEAD implementation in two ways:

First, **infrastructure design choices** in high-HABRI areas should prioritize physical resilience — underground conduit, diversified fiber routes, backup power — even at higher upfront cost. HABRI identifies the specific tracts where these investments are most justified.

Second, **provider selection criteria** in high-HABRI areas could reasonably weight network hardening and disaster response plans more heavily. Transport-Fragile communities (those with high road-network centrality scores) may be candidates for satellite-first or satellite-supplemental deployment strategies, given that terrestrial route dependencies are inherently difficult to eliminate.

HABRI draws on FEMA's National Risk Index, HIFLD cellular infrastructure data, Ookla broadband performance data, and Census ACS demographics — all public sources your team may already use.

**Attachments / Links:**
- Project overview and interactive map: https://jrandre2.github.io/HABRI/
- Full data and methodology: https://github.com/jrandre2/HABRI
- Methodology documentation: [GitHub link to docs/METHODOLOGY.md]

I would be glad to provide a county-level briefing or to generate a custom HABRI report for any specific county or region of interest. Please reach out at jesseand@ttu.edu.

Best regards,  
Jesse R. Andrews  
[Title], Texas Tech University

---

## 3. NC Office of Recovery and Resiliency (NCORR)

**To:** [Director, NCORR]  
**Subject:** Broadband Resilience Research Relevant to Helene Recovery and Future Mitigation

Dear [Name],

In the context of NCORR's ongoing Hurricane Helene recovery work and long-term community resilience planning, I am writing to share research that may help inform where broadband infrastructure investments will generate the greatest resilience return.

Following Helene, our research team applied the Hazard-Adjusted Broadband Reliability Index (HABRI) to validate whether pre-storm data could have identified the communities that experienced the most severe connectivity failures. The results are striking: the Western NC communities most severely impacted by Helene-related broadband outages — Henderson, Haywood, Madison, Mitchell, and Yancey counties — rank in the 84th–92nd percentile statewide on HABRI's Infrastructure Fragility sub-index, which captures road network centrality and broadband latency even before the storm made landfall.

This suggests that HABRI could serve as a targeting tool for proactive resilience investment ahead of future events, complementing NCORR's current disaster recovery programming with a forward-looking, pre-disaster vulnerability lens.

**Key findings for Western NC:**
- 226 NC census tracts classified as *Transport-Fragile* — communities where a single mountain corridor carries both the road network and the fiber infrastructure serving the community
- Morris Broadband (Henderson County, ASN 53488) experienced an 80-hour complete network blackout during Helene; the specific tract served by Morris (37089932000) has a HABRI score in the 92nd percentile statewide
- The correlation between pre-storm HABRI scores and Helene cell outage rates (FCC DIRS data) is statistically significant: Spearman ρ = 0.236, p = 0.018

**Suggested NCORR applications:**
- Use HABRI's *Transport-Fragile* profile to identify communities eligible for a "fiber route diversification" grant category
- Apply HABRI scores as a supplemental eligibility or priority factor for broadband resilience components of CDBG-DR allocations
- Use the quarterly HABRI refresh to track whether Helene-impacted communities have recovered their pre-storm infrastructure fragility scores

All data and documentation are freely available:
- Interactive map: https://jrandre2.github.io/HABRI/
- Data and code: https://github.com/jrandre2/HABRI

I would welcome the opportunity to brief your team and to discuss how HABRI might complement NCORR's current planning and investment frameworks. I can be reached at jesseand@ttu.edu.

With appreciation for NCORR's work in supporting Helene-affected communities,

Jesse R. Andrews  
[Title], Texas Tech University

---

## 4. FEMA Region 4

**To:** [Regional Administrator, FEMA Region 4 — Atlanta]  
**Subject:** Census-Tract-Level Broadband Outage Risk Model for NC — Potential Application to BRIC and HMGP Programs

Dear [Name],

I am a researcher at Texas Tech University developing tools to improve pre-disaster identification of communities at risk of broadband connectivity loss during natural hazard events. I am writing to bring to your attention a completed index — the Hazard-Adjusted Broadband Reliability Index (HABRI) — that may be relevant to FEMA Region 4's BRIC and Hazard Mitigation Grant Program administration in North Carolina.

HABRI integrates FEMA's own National Risk Index with infrastructure fragility indicators (HIFLD cellular tower data, Ookla broadband performance, and road network centrality) and Census ACS socioeconomic indicators to produce a composite outage risk score for each of North Carolina's 2,660 census tracts. The index has been validated against Hurricane Helene outage data with statistically significant results across three independent datasets.

Of particular relevance to HMGP subapplication review: HABRI's *Transport-Fragile* cluster identifies 226 NC census tracts where a single road corridor effectively functions as both the transportation network and the conduit for fiber infrastructure — the exact conditions that caused extended post-Helene outages in mountain communities. These communities have well-documented, quantifiable infrastructure fragility that is amenable to targeted mitigation investment.

HABRI also provides a repeatable pre/post comparison framework: by running the index before and after a mitigation project (e.g., installation of a redundant fiber route), evaluators can measure the reduction in Infrastructure Fragility scores, providing a quantitative indicator for benefit-cost analyses.

The project is fully open-source and documented at https://github.com/jrandre2/HABRI. I would welcome the opportunity to discuss potential applications within Region 4's programs at your convenience.

Respectfully,  
Jesse R. Andrews  
[Title], Texas Tech University  
jesseand@ttu.edu

---

## Sending checklist

Before sending each message:
- [ ] Confirm recipient name and title
- [ ] Add your current title/position
- [ ] Verify GitHub Pages site is live (https://jrandre2.github.io/HABRI/)
- [ ] Attach the `habri_4panel_preview.jpg` image as a visual reference
- [ ] Attach or link the `habri_profiles_preview.jpg` vulnerability profile chart
- [ ] For NCEM/NCORR: attach the `ioda_outage_timeseries.png` showing the Morris Broadband blackout
