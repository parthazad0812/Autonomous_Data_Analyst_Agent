"""
Integration tests for Upload & Session API endpoints (/api/v1/upload).
"""

import io
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_upload_unsupported_file_format_fails(client: TestClient, auth_headers: dict):
    """Test uploading an unsupported file format (e.g. .txt) returns 400 or 422."""
    file_bytes = io.BytesIO(b"some raw text data")
    files = {"file": ("invalid_file.txt", file_bytes, "text/plain")}

    response = client.post("/api/v1/upload", files=files, headers=auth_headers)
    assert response.status_code in (400, 422)


@patch("app.services.upload_service.upload_file_to_minio")
def test_upload_valid_csv_success(mock_minio, client: TestClient, auth_headers: dict, sample_csv_file: tuple):
    """Test uploading a valid CSV creates an analysis session and dataset profile."""
    mock_minio.return_value = "uploads/test_session_123/sample_data.csv"
    
    filename, file_bytes, content_type = sample_csv_file
    files = {"file": (filename, file_bytes, content_type)}
    data = {"query": "Analyze monthly sales trends"}

    response = client.post("/api/v1/upload", files=files, data=data, headers=auth_headers)
    assert response.status_code in (200, 201)
    res_data = response.json()
    assert "session_id" in res_data
    assert res_data["dataset_filename"] == "sample_data.csv"
    assert "profile" in res_data
    assert res_data["profile"]["rows"] == 4
    assert res_data["profile"]["columns"] == 5


def test_list_user_sessions(client: TestClient, auth_headers: dict):
    """Test listing all analysis sessions for the authenticated user."""
    response = client.get("/api/v1/upload/sessions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_get_nonexistent_session_fails(client: TestClient, auth_headers: dict):
    """Test fetching a non-existent session ID returns 404."""
    response = client.get("/api/v1/upload/sessions/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert response.status_code == 404
