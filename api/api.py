# api.py
# ---------------------------------------------------------------------------
# FastAPI application exposing the climbing route scraper as an HTTP microservice.
#
# Scraper endpoints:
#   GET  /health              — liveness probe
#   POST /setup               — initialise (or reset) the database schema
#   POST /scrape              — kick off a background crawl job
#   GET  /status/{task_id}    — poll the status of a crawl job
#
# Data query endpoints:
#   GET  /areas               — list/search areas (optional: level, parent_id, q)
#   GET  /areas/{area_id}     — fetch a single area by ID
#   GET  /areas/{area_id}/routes — all routes whose parent is this area
#   GET  /routes              — list/search routes (optional: parent_id, rating, q, limit)
#   GET  /routes/{route_id}   — fetch a single route by ID
# ---------------------------------------------------------------------------

import uuid
import threading
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, HttpUrl, field_validator
from create_schema import create_schema

app = FastAPI(
    title="Climbing Route Scraper",
    description="Crawls Mountain Project to populate a PostgreSQL database with area and route data.",
    version="1.0.0",
)

# In-process task registry — adequate for a single-worker deployment.
# Replace with Redis / a DB table if you need multi-worker or persistent task history.
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def must_be_mountain_project(cls, v):
        if "mountainproject.com" not in str(v):
            raise ValueError("URL must be a mountainproject.com URL")
        return v


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str = ""


class SetupResponse(BaseModel):
    message: str


class AreaResponse(BaseModel):
    area_id: int
    area_name: str
    level: int
    parent_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AreaUpsertRequest(BaseModel):
    area_name: str
    level: int
    parent_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RouteResponse(BaseModel):
    route_id: int
    route_name: str
    parent_id: Optional[int] = None
    rating: Optional[str] = None


class RouteUpsertRequest(BaseModel):
    route_id: int
    route_name: str
    rating: Optional[str] = None


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _db():
    from route_db_connect import get_connection
    return get_connection()


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_scrape(task_id: str, url: str) -> None:
    with _tasks_lock:
        _tasks[task_id] = {"status": "running", "message": ""}
    try:
        from scrape_routes import crawl_area
        crawl_area(url)
        with _tasks_lock:
            _tasks[task_id] = {"status": "complete", "message": "Scraping finished successfully."}
    except Exception as exc:
        with _tasks_lock:
            _tasks[task_id] = {"status": "failed", "message": str(exc)}


# ---------------------------------------------------------------------------
# Operations endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok"}


@app.post("/setup", response_model=SetupResponse, tags=["Operations"])
def setup_database(reset: bool = Query(default=False, description="Drop and recreate all tables")):
    """
    Initialise the database schema.  
    Pass `?reset=true` to drop existing tables first (**destructive**).
    """
    try:
        create_schema(reset=reset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schema setup failed: {exc}")
    action = "reset and recreated" if reset else "initialised"
    return SetupResponse(message=f"Database schema {action} successfully.")


# ---------------------------------------------------------------------------
# Scraper endpoints
# ---------------------------------------------------------------------------

@app.post("/scrape", response_model=TaskResponse, status_code=202, tags=["Scraper"])
def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Submit a crawl job for the given Mountain Project URL.  
    Returns a `task_id` you can poll via `GET /status/{task_id}`.
    """
    task_id = str(uuid.uuid4())
    with _tasks_lock:
        _tasks[task_id] = {"status": "queued", "message": ""}
    background_tasks.add_task(_run_scrape, task_id, str(request.url))
    return TaskResponse(task_id=task_id, status="queued")


@app.get("/status/{task_id}", response_model=TaskResponse, tags=["Scraper"])
def get_status(task_id: str):
    """
    Poll the status of a previously submitted crawl job.
    """
    with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return TaskResponse(task_id=task_id, **task)


# ---------------------------------------------------------------------------
# Data query endpoints
# ---------------------------------------------------------------------------

@app.get("/areas", response_model=list[AreaResponse], tags=["Data"])
def list_areas(
    level: Optional[int] = Query(default=None, ge=0, le=10, description="Filter by hierarchy level (0=state)"),
    parent_id: Optional[int] = Query(default=None, description="Filter by parent area ID"),
    q: Optional[str] = Query(default=None, description="Case-insensitive name search"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """
    Query areas from all hierarchy levels via the `all_areas` view.
    """
    sql = "SELECT area_id, area_name, level, parent_id, latitude, longitude FROM all_areas WHERE TRUE"
    params: list = []

    if level is not None:
        sql += " AND level = %s"
        params.append(level)
    if parent_id is not None:
        sql += " AND parent_id = %s"
        params.append(parent_id)
    if q:
        sql += " AND LOWER(area_name) LIKE %s"
        params.append(f"%{q.lower()}%")

    sql += " ORDER BY level, area_name LIMIT %s"
    params.append(limit)

    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [AreaResponse(**row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/areas/{area_id}", response_model=AreaResponse, tags=["Data"])
def get_area(area_id: int):
    """
    Fetch a single area by its Mountain Project ID.
    """
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT area_id, area_name, level, parent_id, latitude, longitude "
                "FROM all_areas WHERE area_id = %s LIMIT 1",
                (area_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Area {area_id} not found.")
        return AreaResponse(**row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/areas/{area_id}/routes", response_model=list[RouteResponse], tags=["Data"])
def get_area_routes(area_id: int):
    """
    Return all routes whose direct parent is the given area.
    """
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT route_id, route_name, parent_id, rating FROM Routes WHERE parent_id = %s ORDER BY route_name",
                (area_id,),
            )
            rows = cur.fetchall()
        return [RouteResponse(**row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/routes", response_model=list[RouteResponse], tags=["Data"])
def list_routes(
    parent_id: Optional[int] = Query(default=None, description="Filter by parent area ID"),
    rating: Optional[str] = Query(default=None, description="Exact rating filter (e.g. 5.10a)"),
    q: Optional[str] = Query(default=None, description="Case-insensitive name search"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """
    Query routes with optional filters.
    """
    sql = "SELECT route_id, route_name, parent_id, rating FROM Routes WHERE TRUE"
    params: list = []

    if parent_id is not None:
        sql += " AND parent_id = %s"
        params.append(parent_id)
    if rating:
        sql += " AND rating = %s"
        params.append(rating)
    if q:
        sql += " AND LOWER(route_name) LIKE %s"
        params.append(f"%{q.lower()}%")

    sql += " ORDER BY route_name LIMIT %s"
    params.append(limit)

    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [RouteResponse(**row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/routes/{route_id}", response_model=RouteResponse, tags=["Data"])
def get_route(route_id: int):
    """
    Fetch a single route by its Mountain Project ID.
    """
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT route_id, route_name, parent_id, rating FROM Routes WHERE route_id = %s LIMIT 1",
                (route_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Route {route_id} not found.")
        return RouteResponse(**row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write endpoints (called by the local scraper via api_client.py)
# ---------------------------------------------------------------------------

@app.put("/areas/{area_id}", response_model=AreaResponse, tags=["Write"])
def upsert_area(area_id: int, body: AreaUpsertRequest):
    """
    Upsert a single area (insert or update on conflict).
    Called by the local scraper for each area discovered during a crawl.
    """
    conn = _db()
    try:
        with conn.cursor() as cur:
            if body.level == 0:
                cur.execute(
                    "INSERT INTO State (state_id, state) VALUES (%s, %s) "
                    "ON CONFLICT (state_id) DO UPDATE SET state = EXCLUDED.state;",
                    (area_id, body.area_name),
                )
            else:
                table = f"SubLocationsLv{body.level}"
                cur.execute(
                    f"INSERT INTO {table} (location_id, location_name, parent_id, latitude, longitude) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (location_id) DO UPDATE SET "
                    "location_name = EXCLUDED.location_name, parent_id = EXCLUDED.parent_id;",
                    (area_id, body.area_name, body.parent_id, body.latitude, body.longitude),
                )
        conn.commit()
        return AreaResponse(
            area_id=area_id,
            area_name=body.area_name,
            level=body.level,
            parent_id=body.parent_id,
            latitude=body.latitude,
            longitude=body.longitude,
        )
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.put("/areas/{area_id}/routes", response_model=list[RouteResponse], tags=["Write"])
def upsert_routes(area_id: int, routes: list[RouteUpsertRequest]):
    """
    Batch upsert routes belonging to a given area.
    Called by the local scraper after processing each area page.
    """
    if not routes:
        return []
    conn = _db()
    try:
        with conn.cursor() as cur:
            for r in routes:
                cur.execute(
                    "INSERT INTO Routes (route_id, route_name, parent_id, rating) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (route_id) DO UPDATE SET "
                    "route_name = EXCLUDED.route_name, rating = EXCLUDED.rating;",
                    (r.route_id, r.route_name, area_id, r.rating),
                )
        conn.commit()
        return [
            RouteResponse(route_id=r.route_id, route_name=r.route_name, parent_id=area_id, rating=r.rating)
            for r in routes
        ]
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()

