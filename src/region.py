"""HABRI RegionConfig — parameterize the index for any US state.

Usage
-----
from src.region import RegionConfig, NC_CONFIG

# Use the built-in NC config (identical to the hardcoded constants in config.py)
cfg = NC_CONFIG

# Build a config for another state
wa_config = RegionConfig(
    state_name="Washington",
    state_fips="53",
    county_fips={...},         # name → 3-digit FIPS
    crs_project="EPSG:2855",   # NAD83 / Washington North
    sqft_per_sqkm=None,        # set if CRS is in feet; None for metre CRS
    # Override hazard weights for a wildfire-prone state
    hazard_weights={"wildfire": 0.50, "earthquake": 0.30, "flood": 0.20},
    nri_score_cols={
        "WFIR_RISKS": "Wildfire Risk Score",
        "ERQK_RISKS": "Earthquake Risk Score",
        "IFLD_RISKS": "Inland Flooding Risk Score",
    },
)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.config import (
    CRS_PROJECT,
    COUNTY_FIPS,
    NRI_SCORE_COLS,
    SQFT_PER_SQKM,
    STATE_FIPS,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_HE_FLOOD,
    W_HE_HURRICANE,
    W_HE_LANDSLIDE,
    W_IF_LATENCY,
    W_IF_ROAD_CENTRALITY,
    W_IF_TOWER_DENSITY,
    W_INFRA_FRAGILITY,
    W_ROAD_BETWEENNESS,
    W_ROAD_DENSITY,
    WNC_COUNTY_FIPS,
)


@dataclass
class RegionConfig:
    """All region-specific parameters needed to run HABRI for a US state.

    The default values mirror the North Carolina baseline. Override individual
    fields to adapt the index to a different state or hazard profile.

    Parameters
    ----------
    state_name : str
        Human-readable state name (e.g., "North Carolina").
    state_fips : str
        2-digit FIPS code (e.g., "37").
    county_fips : dict[str, str]
        Mapping of county name → 3-digit FIPS code for all counties in the study.
    crs_project : str
        EPSG code for the state-plane or local projected CRS (used for distance
        and area calculations). E.g., "EPSG:2264" for NC.
    sqft_per_sqkm : float | None
        Conversion factor from the CRS's area unit to km². Supply when the CRS
        uses US survey feet (10,763,910.4 sqft/km²). Set None for metre-based CRS
        (conversion is then 1,000,000 m²/km²).
    w_hazard_exposure : float
        Top-level weight for the Hazard Exposure sub-index (default 0.40).
    w_infra_fragility : float
        Top-level weight for the Infrastructure Fragility sub-index (default 0.35).
    w_coping_capacity : float
        Top-level weight for the Community Coping Capacity sub-index (default 0.25).
    hazard_weights : dict[str, float]
        Internal weights for hazard components (must sum to 1.0).
        Keys are short names; values are fractional weights.
        Default: {"flood": 0.40, "hurricane": 0.35, "landslide": 0.25}.
    nri_score_cols : dict[str, str]
        Mapping of NRI column name → human-readable label for each hazard.
        Override to substitute different NRI hazard types (e.g., wildfire, earthquake).
    w_if_tower_density : float
        Weight for cellular tower density within I_F (default 0.30).
    w_if_latency : float
        Weight for broadband latency within I_F (default 0.30).
    w_if_road_centrality : float
        Weight for road network centrality within I_F (default 0.40).
    w_road_betweenness : float
        Internal weight for betweenness centrality within the road component (default 0.60).
    w_road_density : float
        Internal weight for road density within the road component (default 0.40).
    focal_county_fips : dict[str, str]
        Optional subset of counties for validation / case studies. E.g., the
        6 Western NC counties used for the Helene IODA validation.
    acs_year : int
        ACS 5-year vintage to use (default 2022, which uses 2020 Census tracts).
    """

    state_name: str
    state_fips: str
    county_fips: dict[str, str]
    crs_project: str

    # Area unit conversion
    sqft_per_sqkm: Optional[float] = SQFT_PER_SQKM

    # Top-level weights
    w_hazard_exposure: float = W_HAZARD_EXPOSURE
    w_infra_fragility: float = W_INFRA_FRAGILITY
    w_coping_capacity: float = W_COPING_CAPACITY

    # Hazard sub-weights (must sum to 1.0; keys are short names for logging)
    hazard_weights: dict[str, float] = field(
        default_factory=lambda: {
            "flood": W_HE_FLOOD,
            "hurricane": W_HE_HURRICANE,
            "landslide": W_HE_LANDSLIDE,
        }
    )

    # NRI score columns for the chosen hazards
    nri_score_cols: dict[str, str] = field(
        default_factory=lambda: dict(NRI_SCORE_COLS)
    )

    # Infrastructure Fragility weights
    w_if_tower_density: float = W_IF_TOWER_DENSITY
    w_if_latency: float = W_IF_LATENCY
    w_if_road_centrality: float = W_IF_ROAD_CENTRALITY

    # Road network internal weights
    w_road_betweenness: float = W_ROAD_BETWEENNESS
    w_road_density: float = W_ROAD_DENSITY

    # Optional: subset counties for validation
    focal_county_fips: dict[str, str] = field(default_factory=dict)

    # Census ACS vintage
    acs_year: int = 2022

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def county_fips_list(self) -> list[str]:
        """3-digit FIPS codes for all study counties."""
        return list(self.county_fips.values())

    @property
    def county_fips_full(self) -> list[str]:
        """Full 5-digit state+county FIPS (e.g., '37021')."""
        return [f"{self.state_fips}{c}" for c in self.county_fips_list]

    @property
    def sqm_per_sqkm(self) -> float:
        """Square metres per km² (always 1,000,000; useful for metre-CRS states)."""
        return 1_000_000.0

    @property
    def area_divisor(self) -> float:
        """CRS-native area units per km² (feet or metres depending on CRS)."""
        return self.sqft_per_sqkm if self.sqft_per_sqkm is not None else self.sqm_per_sqkm

    # ── Validation ────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        top_total = self.w_hazard_exposure + self.w_infra_fragility + self.w_coping_capacity
        if abs(top_total - 1.0) > 1e-6:
            raise ValueError(
                f"Top-level weights must sum to 1.0 (got {top_total:.4f}). "
                f"w_hazard_exposure={self.w_hazard_exposure}, "
                f"w_infra_fragility={self.w_infra_fragility}, "
                f"w_coping_capacity={self.w_coping_capacity}"
            )

        hazard_total = sum(self.hazard_weights.values())
        if abs(hazard_total - 1.0) > 1e-6:
            raise ValueError(
                f"hazard_weights must sum to 1.0 (got {hazard_total:.4f})."
            )

        if len(self.hazard_weights) != len(self.nri_score_cols):
            raise ValueError(
                f"hazard_weights has {len(self.hazard_weights)} entries but "
                f"nri_score_cols has {len(self.nri_score_cols)}. They must match."
            )

        if_total = self.w_if_tower_density + self.w_if_latency + self.w_if_road_centrality
        if abs(if_total - 1.0) > 1e-6:
            raise ValueError(
                f"Infrastructure Fragility weights must sum to 1.0 (got {if_total:.4f})."
            )

        road_total = self.w_road_betweenness + self.w_road_density
        if abs(road_total - 1.0) > 1e-6:
            raise ValueError(
                f"Road sub-weights must sum to 1.0 (got {road_total:.4f})."
            )

    def summary(self) -> str:
        lines = [
            f"RegionConfig: {self.state_name} (FIPS {self.state_fips})",
            f"  Counties: {len(self.county_fips)}",
            f"  CRS: {self.crs_project}",
            f"  Top weights: H_E={self.w_hazard_exposure:.0%}  "
            f"I_F={self.w_infra_fragility:.0%}  C_C={self.w_coping_capacity:.0%}",
            f"  Hazard components: "
            + ", ".join(f"{k}={v:.0%}" for k, v in self.hazard_weights.items()),
            f"  I_F components: tower={self.w_if_tower_density:.0%}  "
            f"latency={self.w_if_latency:.0%}  road={self.w_if_road_centrality:.0%}",
            f"  ACS year: {self.acs_year}",
        ]
        return "\n".join(lines)


# ── Built-in configs ──────────────────────────────────────────────────────────

NC_CONFIG = RegionConfig(
    state_name="North Carolina",
    state_fips=STATE_FIPS,
    county_fips=COUNTY_FIPS,
    crs_project=CRS_PROJECT,
    sqft_per_sqkm=SQFT_PER_SQKM,
    focal_county_fips=WNC_COUNTY_FIPS,
)

# Template for a Pacific Northwest state (wildfire + earthquake hazards)
# Un-comment and populate county_fips to use:
#
# WA_CONFIG = RegionConfig(
#     state_name="Washington",
#     state_fips="53",
#     county_fips={...},
#     crs_project="EPSG:2855",   # NAD83 / Washington North (feet)
#     sqft_per_sqkm=SQFT_PER_SQKM,
#     hazard_weights={"wildfire": 0.45, "earthquake": 0.35, "flood": 0.20},
#     nri_score_cols={
#         "WFIR_RISKS": "Wildfire Risk Score",
#         "ERQK_RISKS": "Earthquake Risk Score",
#         "IFLD_RISKS": "Inland Flooding Risk Score",
#     },
# )
