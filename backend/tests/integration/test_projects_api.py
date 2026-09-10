from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_project(client: TestClient) -> None:
    create_response = client.post("/projects", json={"name": "RAG Demo", "slug": "rag-demo"})
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["slug"] == "rag-demo"

    get_response = client.get(f"/projects/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "RAG Demo"


def test_create_project_duplicate_slug_conflicts(client: TestClient) -> None:
    client.post("/projects", json={"name": "RAG Demo", "slug": "rag-demo"})
    response = client.post("/projects", json={"name": "RAG Demo 2", "slug": "rag-demo"})
    assert response.status_code == 409
