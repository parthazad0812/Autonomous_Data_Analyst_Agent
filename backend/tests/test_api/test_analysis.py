"""
Integration tests for Analysis API endpoints (/api/v1/analysis).
"""

from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.session import AnalysisSession
from app.models.user import User


def test_get_analysis_status(client: TestClient, auth_headers: dict, test_user: User, db_session: Session):
    """Test retrieving status for a valid analysis session."""
    session = AnalysisSession(
        user_id=test_user.id,
        dataset_filename="sales_data.csv",
        dataset_path="uploads/session_1/sales_data.csv",
        dataset_rows=100,
        dataset_columns=10,
        status="pending",
        user_query="Find correlations",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    response = client.get(f"/api/v1/analysis/{session.id}/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == str(session.id)
    assert data["status"] == "pending"
    assert data["dataset_filename"] == "sales_data.csv"


def test_get_analysis_steps_empty(client: TestClient, auth_headers: dict, test_user: User, db_session: Session):
    """Test retrieving steps for a new analysis returns an empty list."""
    session = AnalysisSession(
        user_id=test_user.id,
        dataset_filename="test.csv",
        dataset_path="uploads/s2/test.csv",
        status="pending",
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(f"/api/v1/analysis/{session.id}/steps", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_analysis_findings_empty(client: TestClient, auth_headers: dict, test_user: User, db_session: Session):
    """Test retrieving findings returns an empty list when none exist yet."""
    session = AnalysisSession(
        user_id=test_user.id,
        dataset_filename="test.csv",
        dataset_path="uploads/s3/test.csv",
        status="pending",
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(f"/api/v1/analysis/{session.id}/findings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []
