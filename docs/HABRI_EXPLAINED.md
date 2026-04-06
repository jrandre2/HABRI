HABRI: Hazard-Adjusted Broadband Reliability Index


What HABRI Is

HABRI is a composite risk score that identifies which communities in North Carolina are most likely to lose phone and internet service during a natural disaster. It produces a score between 0 and 1 for each census tract in the state, where higher scores indicate greater risk of prolonged communications failure. The index covers all 100 NC counties (2,660 tracts) and is designed to be replicable for any US state using the same freely available federal data sources.


What Goes Into It

The index integrates five public datasets:

- FEMA National Risk Index: Flood, hurricane, and landslide risk scores computed at the tract level for the entire US. These are FEMA's own composite estimates of expected annual loss, exposure, and community resilience for each hazard type.

- HIFLD Cellular Tower Locations: Point locations of cell towers from the Homeland Infrastructure Foundation-Level Data program. Used to measure tower density per tract -- areas with fewer towers have less network redundancy.

- Ookla Speedtest Data: Crowdsourced broadband performance measurements aggregated into geographic tiles. We use average latency (response time in milliseconds) as an indicator of network health. Higher baseline latency suggests infrastructure that is already under strain and more likely to degrade under disaster conditions.

- OpenStreetMap Road Network: The complete drivable road graph for North Carolina (648,000+ nodes, 1.5 million+ road segments). We compute betweenness centrality -- a network science measure of how critical each road segment is as a transportation chokepoint. Roads that carry a disproportionate share of all shortest paths between locations are single points of failure. When they wash out, the fiber and cable lines that follow road corridors go with them.

- US Census American Community Survey: Demographic indicators including households without vehicle access, mobile-only internet subscribers, disability prevalence, median household income, and poverty rates. These capture a community's capacity to adapt when communications infrastructure fails.


How the Score Is Calculated

HABRI combines three sub-indices, each measuring a distinct dimension of risk:

Hazard Exposure (40% of score) draws on three FEMA NRI risk scores weighted by their relevance to communications infrastructure damage in NC: inland flooding (40%), hurricanes (35%), and landslides (25%). Flooding was the primary driver of infrastructure destruction during Hurricane Helene. Hurricanes cause widespread wind damage to towers and power lines. Landslides sever roads and the buried fiber routes that follow them.

Infrastructure Fragility (35% of score) measures the physical vulnerability of the communications network through three indicators: cell tower scarcity (30%), broadband latency (30%), and road network bottlenecks (40%). The road component uses betweenness centrality to identify tracts whose connectivity depends on a small number of critical road segments. The tower and latency components capture wireless and wireline network resilience respectively.

Coping Capacity Deficit (25% of score) uses five equally weighted Census indicators to measure how well a community can adapt when service goes down: no-vehicle rate, mobile-only internet rate, disability prevalence, median household income (inverted -- lower income means higher vulnerability), and poverty rate. A community where residents cannot drive to find a signal, have no fixed broadband fallback, or lack financial resources to purchase backup power is meaningfully more affected by the same outage.

Each indicator is normalized within the study area using z-scores mapped through the standard normal CDF, which produces values bounded between 0 and 1 with the statewide mean at 0.5. This approach is more robust to outliers than simple min-max scaling and preserves the relative spacing of the underlying distributions. Missing values are imputed with the study area median. The three sub-indices are then combined using the weights above into the final HABRI score.


Validation

The index was validated against three independent sources of real outage data from Hurricane Helene (September 2024):

- FCC cell site outage reports for 21 western NC counties under DIRS activation correlated significantly with county-level HABRI scores (Spearman rho = 0.236, p = 0.018, n = 100 counties).

- Ookla latency degradation from Q3 to Q4 2024 showed a significant association with HABRI, with the Infrastructure Fragility sub-index as the strongest predictor (rho = -0.216, p < 0.001).

- IODA internet outage monitoring confirmed that three WNC ISPs experienced outages consistent with HABRI geographic risk patterns, including an 80-hour complete BGP withdrawal for Morris Broadband in Henderson County.
