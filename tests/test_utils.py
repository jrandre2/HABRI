"""Unit tests for src/utils.py."""

import numpy as np
import pandas as pd
import pytest
import geopandas as gpd
from shapely.geometry import Point, box
from unittest.mock import patch, MagicMock

from src.utils import (
    ensure_crs,
    get_study_area_bbox,
    min_max_normalize,
    z_score_normalize,
    impute_with_median,
    spatial_join_to_tracts,
    query_arcgis_feature_layer,
    fetch_acs_tract_data,
    fetch_acs_state_tracts,
    fetch_ioda_timeseries,
)
from src.config import CRS_PROJECT, CRS_WGS84


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_series():
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])


@pytest.fixture
def series_with_nan():
    return pd.Series([1.0, np.nan, 3.0, np.nan, 5.0])


@pytest.fixture
def wgs84_points_gdf():
    """Small GeoDataFrame of WGS84 points inside NC.
    Points are placed at tract centroids, not on edges, so within predicate works.
    """
    geoms = [Point(-82.5, 35.5), Point(-79.5, 35.0), Point(-77.0, 34.5)]
    return gpd.GeoDataFrame(
        {"value": [10.0, 20.0, 30.0]},
        geometry=geoms,
        crs=CRS_WGS84,
    )


@pytest.fixture
def nc_tracts_gdf():
    """Minimal census-tract-like GeoDataFrame with three non-overlapping polygons."""
    polys = [
        box(-83.0, 35.0, -82.0, 36.0),
        box(-80.0, 34.5, -79.0, 35.5),
        box(-77.5, 34.0, -76.5, 35.0),
    ]
    return gpd.GeoDataFrame(
        {"GEOID": ["37001", "37002", "37003"]},
        geometry=polys,
        crs=CRS_WGS84,
    )


# ── min_max_normalize ─────────────────────────────────────────────────────────

class TestMinMaxNormalize:
    def test_basic_range(self, simple_series):
        result = min_max_normalize(simple_series)
        assert result.min() == pytest.approx(0.0)
        assert result.max() == pytest.approx(1.0)

    def test_values_monotone(self, simple_series):
        result = min_max_normalize(simple_series)
        assert list(result) == sorted(result.tolist())

    def test_invert(self, simple_series):
        result = min_max_normalize(simple_series, invert=True)
        assert result.min() == pytest.approx(0.0)
        assert result.max() == pytest.approx(1.0)
        assert result.iloc[0] == pytest.approx(1.0)
        assert result.iloc[-1] == pytest.approx(0.0)

    def test_constant_series_returns_half(self):
        s = pd.Series([7.0, 7.0, 7.0])
        result = min_max_normalize(s)
        assert all(result == 0.5)

    def test_two_element(self):
        s = pd.Series([0.0, 10.0])
        result = min_max_normalize(s)
        assert result.tolist() == pytest.approx([0.0, 1.0])

    def test_preserves_index(self):
        s = pd.Series([3.0, 1.0, 2.0], index=[10, 20, 30])
        result = min_max_normalize(s)
        assert result.index.tolist() == [10, 20, 30]

    def test_single_element(self):
        s = pd.Series([42.0])
        result = min_max_normalize(s)
        assert result.iloc[0] == pytest.approx(0.5)


# ── z_score_normalize ─────────────────────────────────────────────────────────

class TestZScoreNormalize:
    def test_output_range(self, simple_series):
        result = z_score_normalize(simple_series)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_mean_maps_to_half(self, simple_series):
        result = z_score_normalize(simple_series)
        # The median value (3.0) should map to 0.5 (mean == median for symmetric series)
        assert result.iloc[2] == pytest.approx(0.5, abs=1e-6)

    def test_invert_flips_ordering(self, simple_series):
        normal = z_score_normalize(simple_series)
        inverted = z_score_normalize(simple_series, invert=True)
        for i in range(len(simple_series)):
            assert inverted.iloc[i] == pytest.approx(1.0 - normal.iloc[i], abs=1e-6)

    def test_constant_series_returns_half(self):
        s = pd.Series([5.0, 5.0, 5.0])
        result = z_score_normalize(s)
        assert all(result == 0.5)

    def test_preserves_index(self):
        s = pd.Series([1.0, 2.0, 3.0], index=["a", "b", "c"])
        result = z_score_normalize(s)
        assert result.index.tolist() == ["a", "b", "c"]

    def test_monotone_increasing(self, simple_series):
        result = z_score_normalize(simple_series)
        assert list(result) == sorted(result.tolist())

    def test_nan_std_returns_half(self):
        # A single-element series has NaN std in pandas
        s = pd.Series([99.0])
        result = z_score_normalize(s)
        assert result.iloc[0] == pytest.approx(0.5)


# ── impute_with_median ────────────────────────────────────────────────────────

class TestImputeWithMedian:
    def test_fills_nan_with_median(self):
        df = pd.DataFrame({
            "GEOID": ["001", "002", "003", "004", "005"],
            "value": [1.0, np.nan, 3.0, np.nan, 5.0],
        })
        result_df, imputed = impute_with_median(df, "value")
        assert result_df["value"].isna().sum() == 0
        # Median of [1, 3, 5] = 3.0
        assert result_df.loc[result_df["GEOID"] == "002", "value"].iloc[0] == pytest.approx(3.0)
        assert result_df.loc[result_df["GEOID"] == "004", "value"].iloc[0] == pytest.approx(3.0)

    def test_returns_imputed_geoids(self):
        df = pd.DataFrame({
            "GEOID": ["001", "002", "003"],
            "value": [1.0, np.nan, 3.0],
        })
        _, imputed = impute_with_median(df, "value")
        assert imputed == ["002"]

    def test_no_nans_returns_empty_list(self):
        df = pd.DataFrame({
            "GEOID": ["001", "002"],
            "value": [1.0, 2.0],
        })
        _, imputed = impute_with_median(df, "value")
        assert imputed == []

    def test_no_geoid_column(self):
        df = pd.DataFrame({"score": [1.0, np.nan, 3.0]})
        result_df, imputed = impute_with_median(df, "score")
        assert result_df["score"].isna().sum() == 0
        assert imputed == []

    def test_modifies_inplace_and_returns(self):
        df = pd.DataFrame({
            "GEOID": ["001"],
            "value": [np.nan],
        })
        result_df, _ = impute_with_median(df, "value")
        # Returned df should be same object
        assert result_df is df

    def test_all_nan_imputes_nan_median(self):
        df = pd.DataFrame({
            "GEOID": ["001", "002"],
            "value": [np.nan, np.nan],
        })
        # median of all-NaN is NaN, so values stay NaN
        result_df, imputed = impute_with_median(df, "value")
        # fillna(NaN) leaves NaN in place
        assert len(imputed) == 2


# ── ensure_crs ────────────────────────────────────────────────────────────────

class TestEnsureCrs:
    def test_no_op_when_crs_matches(self, wgs84_points_gdf):
        result = ensure_crs(wgs84_points_gdf, CRS_WGS84)
        assert result.crs.to_epsg() == 4326
        # Should be the same object (no reprojection needed)
        assert result is wgs84_points_gdf

    def test_reprojects_to_target(self, wgs84_points_gdf):
        result = ensure_crs(wgs84_points_gdf, CRS_PROJECT)
        assert result.crs.to_epsg() == 2264

    def test_raises_without_crs(self):
        gdf = gpd.GeoDataFrame({"a": [1]}, geometry=[Point(0, 0)])
        with pytest.raises(ValueError, match="no CRS set"):
            ensure_crs(gdf)

    def test_preserves_row_count(self, wgs84_points_gdf):
        result = ensure_crs(wgs84_points_gdf, CRS_PROJECT)
        assert len(result) == len(wgs84_points_gdf)

    def test_default_target_is_project_crs(self, wgs84_points_gdf):
        result = ensure_crs(wgs84_points_gdf)
        assert result.crs.to_epsg() == 2264


# ── get_study_area_bbox ───────────────────────────────────────────────────────

class TestGetStudyAreaBbox:
    def test_returns_four_values(self, nc_tracts_gdf):
        bbox = get_study_area_bbox(nc_tracts_gdf)
        assert len(bbox) == 4

    def test_wgs84_output(self, nc_tracts_gdf):
        minx, miny, maxx, maxy = get_study_area_bbox(nc_tracts_gdf, CRS_WGS84)
        # NC is roughly -84 to -75 lon, 33.8 to 36.6 lat
        assert -90 <= minx <= 0
        assert -90 <= miny <= 90
        assert minx < maxx
        assert miny < maxy

    def test_bbox_ordering(self, nc_tracts_gdf):
        minx, miny, maxx, maxy = get_study_area_bbox(nc_tracts_gdf)
        assert minx < maxx
        assert miny < maxy

    def test_already_correct_crs(self, nc_tracts_gdf):
        """If input is already in WGS84 and we request WGS84, no reprojection."""
        bbox1 = get_study_area_bbox(nc_tracts_gdf, CRS_WGS84)
        bbox2 = get_study_area_bbox(nc_tracts_gdf, CRS_WGS84)
        assert bbox1 == bbox2


# ── spatial_join_to_tracts ────────────────────────────────────────────────────

class TestSpatialJoinToTracts:
    def test_counts_points_per_tract(self, wgs84_points_gdf, nc_tracts_gdf):
        # Each point should fall in exactly one tract
        result = spatial_join_to_tracts(
            wgs84_points_gdf,
            nc_tracts_gdf,
            agg_dict={"value": "count"},
        )
        assert "GEOID" in result.columns
        assert "value" in result.columns
        assert len(result) == len(nc_tracts_gdf)

    def test_sums_values_per_tract(self, wgs84_points_gdf, nc_tracts_gdf):
        result = spatial_join_to_tracts(
            wgs84_points_gdf,
            nc_tracts_gdf,
            agg_dict={"value": "sum"},
        )
        non_null = result["value"].dropna()
        assert non_null.sum() == pytest.approx(60.0)  # 10 + 20 + 30

    def test_preserves_all_tracts_with_left_join(self, nc_tracts_gdf):
        """Tracts with no points should have NaN, not be dropped."""
        # Create a point that falls only in one tract
        single_point = gpd.GeoDataFrame(
            {"value": [99.0]},
            geometry=[Point(-82.5, 35.5)],
            crs=CRS_WGS84,
        )
        result = spatial_join_to_tracts(
            single_point, nc_tracts_gdf, agg_dict={"value": "sum"}
        )
        assert len(result) == 3
        # Two tracts should have NaN
        assert result["value"].isna().sum() == 2


# ── query_arcgis_feature_layer ────────────────────────────────────────────────

class TestQueryArcgisFeatureLayer:
    def _make_mock_response(self, features, total=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"features": features}
        return mock_resp

    def _make_feature(self, lon, lat, **props):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        }

    @patch("src.utils.requests.get")
    def test_returns_geodataframe(self, mock_get):
        features = [self._make_feature(-82.0, 35.5, name="TowerA")]
        mock_get.return_value = self._make_mock_response(features)
        result = query_arcgis_feature_layer("https://fake.url/query")
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1

    @patch("src.utils.requests.get")
    def test_empty_response_returns_empty_gdf(self, mock_get):
        mock_get.return_value = self._make_mock_response([])
        result = query_arcgis_feature_layer("https://fake.url/query")
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 0

    @patch("src.utils.requests.get")
    def test_paginates_when_full_page(self, mock_get):
        """Should make a second request if first page is exactly max_records.
        Loop stops when a page returns fewer features than max_records — no
        extra empty-page request is needed.
        """
        page1 = [self._make_feature(-82.0, 35.5, id=i) for i in range(3)]
        page2 = [self._make_feature(-79.0, 35.0, id=10)]  # 1 < max_records → stop

        mock_get.side_effect = [
            self._make_mock_response(page1),
            self._make_mock_response(page2),
        ]

        result = query_arcgis_feature_layer("https://fake.url/query", max_records=3)
        assert len(result) == 4
        assert mock_get.call_count == 2

    @patch("src.utils.requests.get")
    def test_result_crs_is_wgs84(self, mock_get):
        features = [self._make_feature(-82.0, 35.5, name="TowerA")]
        mock_get.return_value = self._make_mock_response(features)
        result = query_arcgis_feature_layer("https://fake.url/query")
        assert result.crs.to_epsg() == 4326


# ── fetch_acs_tract_data ──────────────────────────────────────────────────────

class TestFetchAcsTractData:
    def _make_census_response(self, rows):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = rows
        return mock_resp

    @patch("src.utils.requests.get")
    def test_constructs_geoid(self, mock_get):
        header = ["NAME", "B01003_001E", "state", "county", "tract"]
        data = [header, ["Tract 1", "1500", "37", "021", "000100"]]
        mock_get.return_value = self._make_census_response(data)

        result = fetch_acs_tract_data(["B01003_001E"], "37", "021")
        assert "GEOID" in result.columns
        assert result["GEOID"].iloc[0] == "37021000100"

    @patch("src.utils.requests.get")
    def test_converts_to_numeric(self, mock_get):
        header = ["NAME", "B01003_001E", "state", "county", "tract"]
        data = [header, ["Tract 1", "2500", "37", "021", "000100"]]
        mock_get.return_value = self._make_census_response(data)

        result = fetch_acs_tract_data(["B01003_001E"], "37", "021")
        assert result["B01003_001E"].dtype in (np.float64, np.int64, float)

    @patch("src.utils.requests.get")
    def test_sentinel_becomes_nan(self, mock_get):
        header = ["NAME", "B19013_001E", "state", "county", "tract"]
        data = [header, ["Tract 1", "-666666666", "37", "021", "000100"]]
        mock_get.return_value = self._make_census_response(data)

        result = fetch_acs_tract_data(["B19013_001E"], "37", "021")
        assert pd.isna(result["B19013_001E"].iloc[0])


# ── fetch_acs_state_tracts ────────────────────────────────────────────────────

class TestFetchAcsStateTracts:
    @patch("src.utils.requests.get")
    def test_uses_wildcard_county(self, mock_get):
        header = ["NAME", "B01003_001E", "state", "county", "tract"]
        data = [
            header,
            ["Tract A", "1000", "37", "001", "000100"],
            ["Tract B", "2000", "37", "003", "000200"],
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = data
        mock_get.return_value = mock_resp

        result = fetch_acs_state_tracts(["B01003_001E"], "37")
        assert len(result) == 2
        # Verify the API was called once (wildcard, not per-county loop)
        assert mock_get.call_count == 1

    @patch("src.utils.requests.get")
    def test_geoid_is_11_digits(self, mock_get):
        header = ["NAME", "B01003_001E", "state", "county", "tract"]
        data = [header, ["Tract A", "1000", "37", "001", "000100"]]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = data
        mock_get.return_value = mock_resp

        result = fetch_acs_state_tracts(["B01003_001E"], "37")
        geoid = result["GEOID"].iloc[0]
        assert len(geoid) == 11


# ── fetch_ioda_timeseries ─────────────────────────────────────────────────────

class TestFetchIodaTimeseries:
    @patch("src.utils.requests.get")
    def test_parses_response_to_dataframe(self, mock_get):
        mock_payload = {
            "data": [
                [
                    {
                        "from": 1727308800,
                        "step": 300,
                        "values": [100.0, 95.0, 90.0],
                        "entityCode": "53488",
                        "entityName": "Morris Broadband",
                        "datasource": "bgp",
                    }
                ]
            ]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        result = fetch_ioda_timeseries("asn", "53488", 1727308800, 1727395200)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "datetime" in result.columns
        assert "value" in result.columns
        assert "entityCode" in result.columns

    @patch("src.utils.requests.get")
    def test_empty_data_returns_empty_dataframe(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_get.return_value = mock_resp

        result = fetch_ioda_timeseries("asn", "99999", 0, 1)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch("src.utils.requests.get")
    def test_datetime_column_is_utc(self, mock_get):
        mock_payload = {
            "data": [
                [
                    {
                        "from": 1727308800,
                        "step": 3600,
                        "values": [1.0],
                        "entityCode": "53488",
                        "entityName": "Test",
                        "datasource": "bgp",
                    }
                ]
            ]
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        result = fetch_ioda_timeseries("asn", "53488", 0, 1)
        assert str(result["datetime"].dt.tz) == "UTC"
