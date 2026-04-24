# scrape_routes.py
# ---------------------------------------------------------------------------
# Script to scrape climbing route data from Mountain Project and store it in a
# PostgreSQL database.  Supports two write modes controlled by the API_URL env var:
#
#   API_URL set   → sends data to the hosted Render API (PUT endpoints)
#   API_URL unset → writes directly to the database via psycopg2
# ---------------------------------------------------------------------------

import os
import re
import time
from urllib.parse import urljoin
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from route_db_connect import get_connection
import tempfile

load_dotenv()

MAX_LOCATION_DEPTH = 10

# Set up Selenium WebDriver
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    # Use a unique temp directory to avoid profile conflicts across concurrent runs
    user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

# Fetch and parse page
def get_soup(url, driver):
    driver.get(url)
    time.sleep(2)
    return BeautifulSoup(driver.page_source, "html.parser")

# Extract breadcrumbs for area/route hierarchy
def extract_breadcrumbs(soup):
    breadcrumbs = []
    for a in soup.select("div.mb-half.small.text-warm a"):
        href = a.get("href", "")
        if "/area/" in href:
            full_url = urljoin("https://www.mountainproject.com", href)
            match = re.search(r"/area/(\d+)", full_url)
            if match:
                breadcrumbs.append({
                    "id": int(match.group(1)),
                    "name": a.text.strip(),
                    "url": full_url
                })
    return breadcrumbs

# Extract current location details
def extract_current_location(soup, fallback_url):
    h1 = soup.find("h1")
    name = h1.text.strip() if h1 else "Unknown"
    canonical = soup.find("link", {"rel": "canonical"})
    url = canonical["href"] if canonical and canonical.has_attr("href") else fallback_url
    match = re.search(r"/area/(\d+)", url)
    loc_id = int(match.group(1)) if match else -1
    return {
        "id": loc_id,
        "name": name,
        "url": url
    }

# Extract GPS coordinates if available
def extract_coordinates(soup):
    gps_row = soup.select_one("tr:has(td:-soup-contains('GPS'))")
    if gps_row:
        tds = gps_row.find_all("td")
        if len(tds) > 1:
            coord_text = tds[1].get_text()
            match = re.search(r"(-?\d+\.\d+),\s*(-?\d+\.\d+)", coord_text)
            if match:
                return float(match.group(1)), float(match.group(2))
    return None, None

# Extract links to sub-areas
def extract_subarea_links(soup):
    return [
        urljoin("https://www.mountainproject.com", a["href"])
        for a in soup.select("div.lef-nav-row a[href*='/area/']")
    ]

# Extract routes listed on the page
def extract_routes(soup):
    routes = []
    table = soup.find("table", id="left-nav-route-table")
    if table:
        for row in table.find_all("tr"):
            link = row.find("a", href=lambda h: h and "/route/" in h)
            rating = row.find("span", class_="rateYDS")
            if link:
                name = link.text.strip()
                url = urljoin("https://www.mountainproject.com", link["href"])
                route_id = int(re.search(r"/route/(\d+)", link["href"]).group(1))
                routes.append({
                    "id": route_id,
                    "name": name,
                    "url": url,
                    "rating": rating.text.strip() if rating else None
                })
    return routes

# Insert location into DB
def insert_location(level, loc_id, name, parent_id, lat, lng, conn):
    if not (0 <= level <= MAX_LOCATION_DEPTH):
        raise ValueError(f"Location level {level} is out of allowed range (0\u2013{MAX_LOCATION_DEPTH})")
    cursor = conn.cursor()
    if level == 0:
        print(f"Inserting into State: {name} (ID: {loc_id})")
        cursor.execute(
            "INSERT INTO State (state_id, state) VALUES (%s, %s) "
            "ON CONFLICT (state_id) DO UPDATE SET state = EXCLUDED.state;",
            (loc_id, name)
        )
    else:
        table = f"SubLocationsLv{level}"
        print(f"Inserting into {table}: {name} (ID: {loc_id}, Parent: {parent_id})")
        cursor.execute(
            f"INSERT INTO {table} (location_id, location_name, parent_id, latitude, longitude) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (location_id) DO UPDATE SET "
            "location_name = EXCLUDED.location_name, parent_id = EXCLUDED.parent_id, "
            f"latitude = COALESCE(EXCLUDED.latitude, {table}.latitude), "
            f"longitude = COALESCE(EXCLUDED.longitude, {table}.longitude);",
            (loc_id, name, parent_id, lat, lng)
        )
    conn.commit()

# Insert routes into DB
def insert_routes(routes, parent_id, conn):
    cursor = conn.cursor()
    for r in routes:
        print(f"Inserting route: {r['name']} (ID: {r['id']})")
        cursor.execute(
            "INSERT INTO Routes (route_id, route_name, parent_id, rating) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (route_id) DO UPDATE SET "
            "route_name = EXCLUDED.route_name, rating = EXCLUDED.rating;",
            (r['id'], r['name'], parent_id, r['rating'])
        )
    conn.commit()


class DatabaseWriter:
    """Writes directly to PostgreSQL via an open psycopg2 connection."""

    def __init__(self, conn):
        self._conn = conn

    def upsert_area(self, level, loc_id, name, parent_id, lat, lng):
        insert_location(level, loc_id, name, parent_id, lat, lng, self._conn)

    def upsert_routes(self, routes, parent_id):
        insert_routes(routes, parent_id, self._conn)


# Internal recursive crawler — shares a single driver and writer across all calls
def _crawl(url, driver, writer, visited_ids, visited_urls):
    if url in visited_urls:
        return
    visited_urls.add(url)

    soup = get_soup(url, driver)
    if not soup:
        return

    current = extract_current_location(soup, driver.current_url)
    breadcrumbs = extract_breadcrumbs(soup)
    hierarchy = breadcrumbs + [current]

    # Insert all ancestor hierarchy levels (breadcrumbs) if not already visited
    for i, entry in enumerate(hierarchy):
        if entry["id"] in visited_ids:
            continue
        # Reuse the already-fetched soup for the current page to avoid a redundant fetch
        sub_soup = soup if entry["url"] == url else get_soup(entry["url"], driver)
        if not sub_soup:
            continue
        lat, lng = extract_coordinates(sub_soup)
        parent_id = hierarchy[i - 1]["id"] if i > 0 else None
        level = min(i, MAX_LOCATION_DEPTH)
        writer.upsert_area(level, entry["id"], entry["name"], parent_id, lat, lng)
        visited_ids.add(entry["id"])

    # Insert the current area if not already inserted via breadcrumb loop
    if current["id"] not in visited_ids:
        lat, lng = extract_coordinates(soup)
        parent_id = breadcrumbs[-1]["id"] if breadcrumbs else None
        level = min(len(breadcrumbs), MAX_LOCATION_DEPTH)
        writer.upsert_area(level, current["id"], current["name"], parent_id, lat, lng)
        visited_ids.add(current["id"])

    routes = extract_routes(soup)
    if routes:
        writer.upsert_routes(routes, current["id"])

    # Recurse into sub-areas, sharing the same driver and writer
    for sub_url in extract_subarea_links(soup):
        _crawl(sub_url, driver, writer, visited_ids, visited_urls)

# Public entry point — picks write mode based on API_URL env var
def crawl_area(url):
    api_url = os.getenv("API_URL", "").strip()
    driver = get_driver()

    if api_url:
        from api_client import ApiWriter
        writer = ApiWriter(api_url)
        conn = None
        print(f"Write mode: API  →  {api_url}")
    else:
        conn = get_connection()
        writer = DatabaseWriter(conn)
        print("Write mode: direct database")

    try:
        _crawl(url, driver, writer, visited_ids=set(), visited_urls=set())
    finally:
        driver.quit()
        if conn:
            conn.close()
        if api_url:
            writer.close()
        print("Scraping complete.")

# Start crawling from the provided URL
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scrape_routes.py <START_URL>")
        print("Please provide exactly one argument: the start URL.")
        sys.exit(1)
    url = sys.argv[1]
    if "mountainproject.com" not in url:
        print("Error: URL must be a mountainproject.com URL")
        sys.exit(1)
    crawl_area(url)


