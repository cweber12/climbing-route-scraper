# tests/test_api.py
# Tests for the FastAPI endpoints.
# No live DB or WebDriver is started — crawl_area is mocked throughout.

from fastapi.testclient import TestClient
from unittest.mock import patch

from api import app, _tasks

client = TestClient(app, raise_server_exceptions=False)

VALID_URL = "https://www.mountainproject.com/area/105792216/nevermind-wall"


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self):
        assert client.get("/health").status_code == 200

    def test_body_is_ok(self):
        assert client.get("/health").json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /setup
# ---------------------------------------------------------------------------

class TestSetupEndpoint:
    def test_returns_200_on_success(self):
        with patch("api.create_schema"):
            response = client.post("/setup")
        assert response.status_code == 200

    def test_message_mentions_initialised(self):
        with patch("api.create_schema"):
            data = client.post("/setup").json()
        assert "initialised" in data["message"]

    def test_reset_true_message_mentions_reset(self):
        with patch("api.create_schema"):
            data = client.post("/setup?reset=true").json()
        assert "reset" in data["message"]

    def test_returns_500_when_schema_raises(self):
        with patch("api.create_schema", side_effect=Exception("DB down")):
            response = client.post("/setup")
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /scrape
# ---------------------------------------------------------------------------

class TestScrapeEndpoint:
    def test_returns_202_for_valid_url(self):
        with patch("api._run_scrape"):
            response = client.post("/scrape", json={"url": VALID_URL})
        assert response.status_code == 202

    def test_response_contains_task_id(self):
        with patch("api._run_scrape"):
            data = client.post("/scrape", json={"url": VALID_URL}).json()
        assert "task_id" in data

    def test_status_is_queued(self):
        with patch("api._run_scrape"):
            data = client.post("/scrape", json={"url": VALID_URL}).json()
        assert data["status"] == "queued"

    def test_rejects_non_mountainproject_url(self):
        response = client.post("/scrape", json={"url": "https://www.example.com/area/1/foo"})
        assert response.status_code == 422

    def test_rejects_malformed_url(self):
        assert client.post("/scrape", json={"url": "not-a-url"}).status_code == 422

    def test_rejects_missing_url_field(self):
        assert client.post("/scrape", json={}).status_code == 422

    def test_different_tasks_have_unique_ids(self):
        with patch("api._run_scrape"):
            id1 = client.post("/scrape", json={"url": VALID_URL}).json()["task_id"]
            id2 = client.post("/scrape", json={"url": VALID_URL}).json()["task_id"]
        assert id1 != id2


# ---------------------------------------------------------------------------
# GET /status/{task_id}
# ---------------------------------------------------------------------------

class TestStatusEndpoint:
    def test_returns_404_for_unknown_task(self):
        assert client.get("/status/does-not-exist").status_code == 404

    def test_returns_queued_status_immediately_after_submit(self):
        with patch("api._run_scrape"):
            task_id = client.post("/scrape", json={"url": VALID_URL}).json()["task_id"]
        response = client.get(f"/status/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_returns_complete_status(self):
        task_id = "test-complete-task"
        _tasks[task_id] = {"status": "complete", "message": "Done"}
        response = client.get(f"/status/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "complete"
        del _tasks[task_id]

    def test_returns_failed_status_with_message(self):
        task_id = "test-failed-task"
        _tasks[task_id] = {"status": "failed", "message": "Connection refused"}
        data = client.get(f"/status/{task_id}").json()
        assert data["status"] == "failed"
        assert "Connection refused" in data["message"]
        del _tasks[task_id]

    def test_task_id_echoed_in_response(self):
        task_id = "echo-test"
        _tasks[task_id] = {"status": "running", "message": ""}
        assert client.get(f"/status/{task_id}").json()["task_id"] == task_id
        del _tasks[task_id]
