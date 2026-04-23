# tests/test_scrape_routes.py
# Unit tests for the HTML-parsing and DB-insertion functions in scrape_routes.py.
# All DB and WebDriver interactions are mocked — no live network or database needed.

import pytest
from unittest.mock import MagicMock, patch, call

from scrape_routes import (
    extract_breadcrumbs,
    extract_current_location,
    extract_coordinates,
    extract_routes,
    extract_subarea_links,
    insert_location,
    insert_routes,
    MAX_LOCATION_DEPTH,
)
from tests.conftest import make_soup


# ---------------------------------------------------------------------------
# extract_breadcrumbs
# ---------------------------------------------------------------------------

class TestExtractBreadcrumbs:
    def test_returns_both_entries(self, breadcrumb_soup):
        result = extract_breadcrumbs(breadcrumb_soup)
        assert len(result) == 2

    def test_first_entry_name_and_id(self, breadcrumb_soup):
        result = extract_breadcrumbs(breadcrumb_soup)
        assert result[0]["name"] == "California"
        assert result[0]["id"] == 105907743

    def test_second_entry_name_and_id(self, breadcrumb_soup):
        result = extract_breadcrumbs(breadcrumb_soup)
        assert result[1]["name"] == "Yosemite Valley"
        assert result[1]["id"] == 105948977

    def test_url_is_absolute(self, breadcrumb_soup):
        result = extract_breadcrumbs(breadcrumb_soup)
        assert result[0]["url"].startswith("https://www.mountainproject.com")

    def test_empty_when_no_breadcrumb_div(self, empty_soup):
        assert extract_breadcrumbs(empty_soup) == []

    def test_ignores_non_area_links(self):
        html = """
        <div class="mb-half small text-warm">
          <a href="/route/12345/some-route">A Route</a>
        </div>
        """
        result = extract_breadcrumbs(make_soup(html))
        assert result == []


# ---------------------------------------------------------------------------
# extract_current_location
# ---------------------------------------------------------------------------

class TestExtractCurrentLocation:
    def test_extracts_name_from_h1(self, current_location_soup):
        result = extract_current_location(current_location_soup, "fallback")
        assert result["name"] == "El Capitan"

    def test_extracts_id_from_canonical(self, current_location_soup):
        result = extract_current_location(current_location_soup, "fallback")
        assert result["id"] == 105833381

    def test_url_comes_from_canonical(self, current_location_soup):
        result = extract_current_location(current_location_soup, "fallback")
        assert "el-capitan" in result["url"]

    def test_falls_back_to_provided_url_when_no_canonical(self, empty_soup):
        fallback = "https://www.mountainproject.com/area/999/test-area"
        result = extract_current_location(empty_soup, fallback)
        assert result["url"] == fallback
        assert result["id"] == 999

    def test_name_is_unknown_when_no_h1(self, empty_soup):
        result = extract_current_location(empty_soup, "https://www.mountainproject.com/area/1/x")
        assert result["name"] == "Unknown"


# ---------------------------------------------------------------------------
# extract_coordinates
# ---------------------------------------------------------------------------

class TestExtractCoordinates:
    def test_parses_latitude(self, coordinates_soup):
        lat, _ = extract_coordinates(coordinates_soup)
        assert lat == pytest.approx(37.7341)

    def test_parses_longitude(self, coordinates_soup):
        _, lng = extract_coordinates(coordinates_soup)
        assert lng == pytest.approx(-119.6379)

    def test_returns_none_when_no_gps_row(self, empty_soup):
        lat, lng = extract_coordinates(empty_soup)
        assert lat is None
        assert lng is None

    def test_returns_none_when_gps_row_has_no_coords(self):
        html = "<table><tr><td>GPS</td><td>No coordinates available</td></tr></table>"
        lat, lng = extract_coordinates(make_soup(html))
        assert lat is None
        assert lng is None

    def test_handles_negative_coordinates(self):
        html = "<table><tr><td>GPS</td><td>-33.8688, -70.6693</td></tr></table>"
        lat, lng = extract_coordinates(make_soup(html))
        assert lat == pytest.approx(-33.8688)
        assert lng == pytest.approx(-70.6693)


# ---------------------------------------------------------------------------
# extract_routes
# ---------------------------------------------------------------------------

class TestExtractRoutes:
    def test_returns_two_routes(self, routes_soup):
        assert len(extract_routes(routes_soup)) == 2

    def test_first_route_name(self, routes_soup):
        assert extract_routes(routes_soup)[0]["name"] == "The Nose"

    def test_first_route_id(self, routes_soup):
        assert extract_routes(routes_soup)[0]["id"] == 106261520

    def test_first_route_rating(self, routes_soup):
        assert extract_routes(routes_soup)[0]["rating"] == "5.9"

    def test_second_route_rating(self, routes_soup):
        assert extract_routes(routes_soup)[1]["rating"] == "5.11a"

    def test_route_url_is_absolute(self, routes_soup):
        url = extract_routes(routes_soup)[0]["url"]
        assert url.startswith("https://www.mountainproject.com/route/")

    def test_empty_when_no_table(self, empty_soup):
        assert extract_routes(empty_soup) == []

    def test_none_rating_when_no_yds_span(self):
        html = """
        <table id="left-nav-route-table">
          <tr><td><a href="/route/999/unnamed">Unnamed</a></td></tr>
        </table>
        """
        routes = extract_routes(make_soup(html))
        assert routes[0]["rating"] is None


# ---------------------------------------------------------------------------
# extract_subarea_links
# ---------------------------------------------------------------------------

class TestExtractSubareaLinks:
    def test_returns_two_links(self, subarea_soup):
        assert len(extract_subarea_links(subarea_soup)) == 2

    def test_links_are_absolute(self, subarea_soup):
        links = extract_subarea_links(subarea_soup)
        assert all(l.startswith("https://www.mountainproject.com") for l in links)

    def test_contains_expected_slugs(self, subarea_soup):
        links = extract_subarea_links(subarea_soup)
        slugs = " ".join(links)
        assert "el-capitan" in slugs
        assert "half-dome" in slugs

    def test_empty_when_no_nav_rows(self, empty_soup):
        assert extract_subarea_links(empty_soup) == []


# ---------------------------------------------------------------------------
# insert_location
# ---------------------------------------------------------------------------

class TestInsertLocation:
    def test_level_0_inserts_into_state(self, mock_conn):
        insert_location(0, 105907743, "California", None, None, None, mock_conn)
        sql = mock_conn.cursor().execute.call_args[0][0]
        assert "State" in sql
        mock_conn.commit.assert_called_once()

    def test_level_1_inserts_into_sublocationslv1(self, mock_conn):
        insert_location(1, 105948977, "Yosemite", 105907743, 37.73, -119.63, mock_conn)
        sql = mock_conn.cursor().execute.call_args[0][0]
        assert "SubLocationsLv1" in sql
        assert "ON CONFLICT" in sql
        mock_conn.commit.assert_called_once()

    def test_coordinates_passed_as_separate_floats(self, mock_conn):
        insert_location(2, 1, "Test Area", 2, 37.0, -119.0, mock_conn)
        params = mock_conn.cursor().execute.call_args[0][1]
        assert 37.0 in params
        assert -119.0 in params

    def test_null_coordinates_when_none(self, mock_conn):
        insert_location(1, 1, "No Coords", 2, None, None, mock_conn)
        params = mock_conn.cursor().execute.call_args[0][1]
        # params = (loc_id, name, parent_id, lat, lng) — both coords should be None
        assert params[-1] is None
        assert params[-2] is None

    def test_raises_for_level_above_max(self, mock_conn):
        with pytest.raises(ValueError, match="out of allowed range"):
            insert_location(MAX_LOCATION_DEPTH + 1, 1, "Too Deep", 2, None, None, mock_conn)

    def test_raises_for_negative_level(self, mock_conn):
        with pytest.raises(ValueError):
            insert_location(-1, 1, "Invalid", None, None, None, mock_conn)


# ---------------------------------------------------------------------------
# insert_routes
# ---------------------------------------------------------------------------

class TestInsertRoutes:
    def test_executes_once_per_route(self, mock_conn):
        routes = [
            {"id": 1, "name": "Route A", "rating": "5.9"},
            {"id": 2, "name": "Route B", "rating": "5.10a"},
        ]
        insert_routes(routes, parent_id=100, conn=mock_conn)
        assert mock_conn.cursor().execute.call_count == 2

    def test_commits_once_after_all_inserts(self, mock_conn):
        insert_routes([{"id": 1, "name": "X", "rating": "5.8"}], 100, mock_conn)
        mock_conn.commit.assert_called_once()

    def test_empty_list_does_not_execute(self, mock_conn):
        insert_routes([], parent_id=100, conn=mock_conn)
        mock_conn.cursor().execute.assert_not_called()

    def test_passes_rating_to_query(self, mock_conn):
        insert_routes([{"id": 1, "name": "Rated", "rating": "5.12d"}], 100, mock_conn)
        params = mock_conn.cursor().execute.call_args[0][1]
        assert "5.12d" in params


# ---------------------------------------------------------------------------
# crawl_area integration (driver + DB mocked)
# ---------------------------------------------------------------------------

class TestCrawlArea:
    def test_driver_created_and_quit_exactly_once(self, mocker):
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.mountainproject.com/area/1/test"
        mock_driver.page_source = """
        <html>
          <head><link rel="canonical" href="https://www.mountainproject.com/area/1/test"/></head>
          <body><h1>Test Area</h1></body>
        </html>
        """
        mocker.patch("scrape_routes.get_driver", return_value=mock_driver)
        mocker.patch("scrape_routes.get_connection", return_value=MagicMock())

        from scrape_routes import crawl_area
        crawl_area("https://www.mountainproject.com/area/1/test")

        mock_driver.quit.assert_called_once()

    def test_each_url_visited_only_once(self, mocker):
        """A URL that appears in multiple sub-area lists should only be fetched once."""
        call_count = {}

        def fake_get(url):
            call_count[url] = call_count.get(url, 0) + 1

        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.mountainproject.com/area/1/root"
        mock_driver.page_source = """
        <html>
          <head><link rel="canonical" href="https://www.mountainproject.com/area/1/root"/></head>
          <body><h1>Root</h1></body>
        </html>
        """
        mock_driver.get.side_effect = fake_get
        mocker.patch("scrape_routes.get_driver", return_value=mock_driver)
        mocker.patch("scrape_routes.get_connection", return_value=MagicMock())

        from scrape_routes import crawl_area
        crawl_area("https://www.mountainproject.com/area/1/root")

        root_url = "https://www.mountainproject.com/area/1/root"
        assert call_count.get(root_url, 0) == 1
