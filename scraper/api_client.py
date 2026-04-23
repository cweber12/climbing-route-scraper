# api_client.py
# ---------------------------------------------------------------------------
# HTTP client used by the local scraper to write data to the hosted Render API.
#
# When API_URL is set in .env this is used instead of direct DB writes.
# This means only the Render service (not the local machine) needs database
# credentials — the scraper only needs the API URL.
# ---------------------------------------------------------------------------

import httpx


class ApiWriter:
    """Writes area and route data to the hosted API via HTTP PUT requests."""

    def __init__(self, api_url: str):
        self._base = api_url.rstrip("/")
        # Reuse a single httpx client for connection pooling across the crawl
        self._client = httpx.Client(timeout=30.0)

    def upsert_area(self, level: int, loc_id: int, name: str, parent_id, lat, lng) -> None:
        payload = {
            "area_name": name,
            "level": level,
            "parent_id": parent_id,
            "latitude": lat,
            "longitude": lng,
        }
        url = f"{self._base}/areas/{loc_id}"
        print(f"PUT {url}  ({name})")
        response = self._client.put(url, json=payload)
        response.raise_for_status()

    def upsert_routes(self, routes: list[dict], parent_id: int) -> None:
        if not routes:
            return
        payload = [
            {"route_id": r["id"], "route_name": r["name"], "rating": r.get("rating")}
            for r in routes
        ]
        url = f"{self._base}/areas/{parent_id}/routes"
        print(f"PUT {url}  ({len(routes)} routes)")
        response = self._client.put(url, json=payload)
        response.raise_for_status()

    def close(self) -> None:
        self._client.close()
