"""Integration tests for catalog reactive filtering endpoint and empty-state metadata (HU-10)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.challenge.main import app
from src.core.database import get_db
from src.models.challenge import Challenge

client = TestClient(app)


def create_sample_challenge(title: str = "Route Optimizer", status: str = "OPEN") -> Challenge:
    """Helper to instantiate mock Challenge ORM instance."""
    return Challenge(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        title=title,
        description="Optimize delivery routes using heuristics.",
        business_process="Supply Chain Logistics",
        status=status,
        difficulty_level="INTERMEDIATE",
        modality="REMOTE",
        min_semester=7,
        economic_sector="Logistics & Transport",
        required_skills=["Python", "Optimization"],
        knowledge_areas=["Operations Research"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_db_session():
    """Override get_db FastAPI dependency with AsyncMock."""
    mock_session = AsyncMock()

    async def _get_db_override():
        yield mock_session

    app.dependency_overrides[get_db] = _get_db_override
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


def test_catalog_endpoint_success_with_results(mock_db_session):
    """Verify catalog endpoint returns paginated items when matches are found."""
    sample = create_sample_challenge()

    with patch(
        "src.repositories.catalog_repository.CatalogRepository.filter_catalog",
        new=AsyncMock(return_value=([sample], 1)),
    ):
        response = client.get("/api/v1/challenges/catalog?q=Route&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["page"] == 1
        assert data["limit"] == 10
        assert data["pages"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Route Optimizer"
        assert data["empty_state"] is None


def test_catalog_endpoint_root_alias(mock_db_session):
    """Verify /challenges and /challenges/catalog are both accessible."""
    with patch(
        "src.repositories.catalog_repository.CatalogRepository.filter_catalog",
        new=AsyncMock(return_value=([], 0)),
    ), patch(
        "src.repositories.catalog_repository.CatalogRepository.count_active_challenges",
        new=AsyncMock(return_value=15),
    ):
        res1 = client.get("/challenges/catalog")
        assert res1.status_code == 200

        res2 = client.get("/challenges")
        assert res2.status_code == 200


def test_catalog_endpoint_empty_state_metadata(mock_db_session):
    """Verify empty_state metadata is populated with applied filters when zero matches occur."""
    with patch(
        "src.repositories.catalog_repository.CatalogRepository.filter_catalog",
        new=AsyncMock(return_value=([], 0)),
    ), patch(
        "src.repositories.catalog_repository.CatalogRepository.count_active_challenges",
        new=AsyncMock(return_value=25),
    ):
        response = client.get(
            "/api/v1/challenges/catalog"
            "?q=NonExistent"
            "&sector=Health"
            "&modality=REMOTE"
            "&difficulty=ADVANCED"
            "&skill=Rust"
            "&knowledge_area=Biomedical"
            "&min_semester=9"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["items"] == []
        assert data["pages"] == 1
        assert data["empty_state"] is not None

        empty_state = data["empty_state"]
        assert empty_state["code"] == "NO_MATCHING_CHALLENGES"
        assert "No challenges match" in empty_state["message"]
        assert empty_state["suggested_reset"] is True
        assert empty_state["total_active_challenges"] == 25

        query_params = empty_state["query_params"]
        assert query_params["q"] == "NonExistent"
        assert query_params["economic_sector"] == "Health"
        assert query_params["modality"] == "REMOTE"
        assert query_params["difficulty_level"] == "ADVANCED"
        assert query_params["skill"] == "Rust"
        assert query_params["knowledge_area"] == "Biomedical"
        assert query_params["min_semester"] == 9


def test_catalog_param_aliases(mock_db_session):
    """Verify parameter aliases (sector -> economic_sector, difficulty -> difficulty_level, page_size -> limit)."""
    with patch(
        "src.repositories.catalog_repository.CatalogRepository.filter_catalog",
        new=AsyncMock(return_value=([], 0)),
    ) as mock_filter, patch(
        "src.repositories.catalog_repository.CatalogRepository.count_active_challenges",
        new=AsyncMock(return_value=5),
    ):
        response = client.get(
            "/api/v1/challenges/catalog"
            "?sector=Finance"
            "&difficulty=BEGINNER"
            "&max_semester=8"
            "&page_size=20"
        )
        assert response.status_code == 200
        mock_filter.assert_called_once()
        _, kwargs = mock_filter.call_args

        assert kwargs["economic_sector"] == "Finance"
        assert kwargs["difficulty_level"] == "BEGINNER"
        assert kwargs["min_semester"] == 8
        assert kwargs["limit"] == 20


def test_catalog_pagination_calculation(mock_db_session):
    """Verify total pages calculation across various total counts."""
    with patch(
        "src.repositories.catalog_repository.CatalogRepository.filter_catalog",
        new=AsyncMock(return_value=([create_sample_challenge()], 35)),
    ):
        response = client.get("/api/v1/challenges/catalog?page=2&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 35
        assert data["page"] == 2
        assert data["limit"] == 10
        assert data["pages"] == 4  # 35 / 10 = 3.5 -> 4 pages


def test_catalog_validation_errors():
    """Verify FastAPI query validation rejects invalid categorical values and page bounds."""
    # Invalid modality
    res1 = client.get("/api/v1/challenges/catalog?modality=INVALID_MODALITY")
    assert res1.status_code == 422

    # Invalid difficulty
    res2 = client.get("/api/v1/challenges/catalog?difficulty=SUPER_HARD")
    assert res2.status_code == 422

    # Page < 1
    res3 = client.get("/api/v1/challenges/catalog?page=0")
    assert res3.status_code == 422

    # Limit > 100
    res4 = client.get("/api/v1/challenges/catalog?limit=101")
    assert res4.status_code == 422

    # Semester > 10
    res5 = client.get("/api/v1/challenges/catalog?min_semester=11")
    assert res5.status_code == 422
