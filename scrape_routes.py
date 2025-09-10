import os
import re
import time
from urllib.parse import urljoin
import pymysql
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from route_db_connect import get_connection
import tempfile

load_dotenv()

START_URL = "https://www.mountainproject.com/area/105792216/nevermind-wall"
visited = set()

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    # Use a unique temp directory for user data
    user_data_dir = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

def get_soup(url, driver):
    driver.get(url)
    time.sleep(2)
    return BeautifulSoup(driver.page_source, "html.parser")

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

def extract_subarea_links(soup):
    return [
        urljoin("https://www.mountainproject.com", a["href"])
        for a in soup.select("div.lef-nav-row a[href*='/area/']")
    ]

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

def insert_location(level, loc_id, name, parent_id, lat, lng, conn):
    cursor = conn.cursor()
    if level == 0:
        print(f"Inserting into State: {name} (ID: {loc_id})")
        cursor.execute("""INSERT INTO State (state_id, state) VALUES (%s, %s)
                          ON DUPLICATE KEY UPDATE state = VALUES(state);""", (loc_id, name))
    else:
        print(f"Inserting into SubLocationsLv{level}: {name} (ID: {loc_id}, Parent: {parent_id})")
        cursor.execute(f"""INSERT INTO SubLocationsLv{level} (location_id, location_name, parent_id, coordinates)
                           VALUES (%s, %s, %s, ST_PointFromText(%s))
                           ON DUPLICATE KEY UPDATE location_name = VALUES(location_name),
                                                   parent_id = VALUES(parent_id);""",
                       (loc_id, name, parent_id, f"POINT({lng} {lat})" if lat and lng else None))
    conn.commit()

def insert_routes(routes, parent_id, conn):
    cursor = conn.cursor()
    for r in routes:
        print(f"Inserting route: {r['name']} (ID: {r['id']})")
        cursor.execute("""INSERT INTO Routes (route_id, route_name, parent_id, rating)
                          VALUES (%s, %s, %s, %s)
                          ON DUPLICATE KEY UPDATE route_name = VALUES(route_name), rating = VALUES(rating);""",
                       (r['id'], r['name'], parent_id, r['rating']))
    conn.commit()

def crawl_area(url):
    driver = get_driver()
    conn = get_connection()

    try:
        soup = get_soup(url, driver)
        if not soup:
            return

        current = extract_current_location(soup, driver.current_url)
        breadcrumbs = extract_breadcrumbs(soup)
        hierarchy = breadcrumbs + [current]

        for i, entry in enumerate(hierarchy):
            if entry["id"] in visited:
                continue
            sub_soup = get_soup(entry["url"], driver)
            if not sub_soup:
                continue
            lat, lng = extract_coordinates(sub_soup)
            parent_id = hierarchy[i - 1]["id"] if i > 0 else None
            insert_location(i, entry["id"], entry["name"], parent_id, lat, lng, conn)
            visited.add(entry["id"])

        # Insert routes in the main area
        if current["id"] not in visited:
            lat, lng = extract_coordinates(soup)
            parent_id = breadcrumbs[-1]["id"] if breadcrumbs else None
            insert_location(len(breadcrumbs), current["id"], current["name"], parent_id, lat, lng, conn)
            visited.add(current["id"])

        routes = extract_routes(soup)
        if routes:
            insert_routes(routes, current["id"], conn)

        # Recurse through sub-areas
        for sub_url in extract_subarea_links(soup):
            crawl_area(sub_url)

    finally:
        driver.quit()
        conn.close()
        print("Scraping complete.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scrape_routes.py <START_URL>")
        print("Please provide exactly one argument: the start URL.")
    else:
        crawl_area(sys.argv[1])

