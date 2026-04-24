# tests/conftest.py
# Shared fixtures for the test suite.

import pytest
from bs4 import BeautifulSoup


BREADCRUMB_HTML = """
<html><body>
<div class="mb-half small text-warm">
  <a href="/area/105907743/california">California</a>
  <span>&rsaquo;</span>
  <a href="/area/105948977/yosemite-valley">Yosemite Valley</a>
</div>
</body></html>
"""

CURRENT_LOCATION_HTML = """
<html>
<head>
  <link rel="canonical" href="https://www.mountainproject.com/area/105833381/el-capitan"/>
</head>
<body>
  <h1>El Capitan</h1>
</body>
</html>
"""

COORDINATES_HTML = """
<html><body>
<table>
  <tr><td>GPS</td><td>37.7341, -119.6379</td></tr>
</table>
</body></html>
"""

ROUTES_HTML = """
<html><body>
<div class="lef-nav-row">
  <a href="/route/106261520/the-nose">The Nose</a>
  <span class="rateYDS">5.9</span>
</div>
<div class="lef-nav-row">
  <a href="/route/106261521/zodiac">Zodiac</a>
  <span class="rateYDS">5.11a</span>
</div>
</body></html>
"""

SUBAREA_HTML = """
<html><body>
<div class="lef-nav-row"><a href="/area/105833381/el-capitan">El Capitan</a></div>
<div class="lef-nav-row"><a href="/area/105924807/half-dome">Half Dome</a></div>
</body></html>
"""


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


@pytest.fixture
def breadcrumb_soup():
    return make_soup(BREADCRUMB_HTML)


@pytest.fixture
def current_location_soup():
    return make_soup(CURRENT_LOCATION_HTML)


@pytest.fixture
def coordinates_soup():
    return make_soup(COORDINATES_HTML)


@pytest.fixture
def routes_soup():
    return make_soup(ROUTES_HTML)


@pytest.fixture
def subarea_soup():
    return make_soup(SUBAREA_HTML)


@pytest.fixture
def empty_soup():
    return make_soup("<html><body></body></html>")


@pytest.fixture
def mock_conn(mocker):
    conn = mocker.MagicMock()
    cursor = mocker.MagicMock()
    conn.cursor.return_value = cursor
    return conn
