import pytest
import datetime
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app, Base, get_db, Event, User

# Задайте строку подключения к тестовой базе PostgreSQL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:0000@localhost:5432/LoggingMicroservice")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаём таблицы в тестовой базе данных (если они ещё не созданы)
Base.metadata.create_all(bind=engine)

# Переопределяем зависимость для получения сессии БД в приложении
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def run_around_tests():
    # Перед каждым тестом очищаем таблицы и создаём тестового пользователя
    db = TestingSessionLocal()
    # Очищаем таблицы
    db.query(Event).delete()
    db.query(User).delete()
    # Создаем тестового пользователя
    test_user = User(user_id=1, login="testuser", role=2)
    db.add(test_user)
    db.commit()
    db.close()
    yield
    # После теста можно добавить очистку, если потребуется

def test_get_events_empty():
    response = client.get("/events")
    assert response.status_code == 200
    # При пустой таблице список событий должен быть пустым
    assert response.json() == []

def test_create_event():
    event_data = {
        "subsystem_id": 1,
        "user_id": 1,
        "event_name": "Test Event",
        "comment": "This is a test event",
        "status": 0,
        "priority": 1
    }
    response = client.post("/events", json=event_data)
    assert response.status_code == 200
    data = response.json()
    assert data["event_name"] == "Test Event"
    assert data["comment"] == "This is a test event"
    # Проверяем наличие поля date (формат ISO)
    assert "date" in data

def test_get_event_by_id():
    event_data = {
        "subsystem_id": 1,
        "user_id": 1,
        "event_name": "GetById Event",
        "comment": "Retrieve by id",
        "status": 0,
        "priority": 1
    }
    post_response = client.post("/events", json=event_data)
    event_id = post_response.json()["event_id"]

    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == event_id
    assert data["event_name"] == "GetById Event"

def test_update_event():
    event_data = {
        "subsystem_id": 1,
        "user_id": 1,
        "event_name": "Initial Event",
        "comment": "Initial comment",
        "status": 0,
        "priority": 1
    }
    post_response = client.post("/events", json=event_data)
    event_id = post_response.json()["event_id"]

    updated_data = {
        "subsystem_id": 2,
        "user_id": 1,
        "event_name": "Updated Event",
        "comment": "Updated comment",
        "date": datetime.date.today().isoformat(),
        "status": 1,
        "priority": 2
    }
    response = client.put(f"/events/{event_id}", json=updated_data)
    assert response.status_code == 200
    data = response.json()
    assert data["event_name"] == "Updated Event"
    assert data["subsystem_id"] == 2
    assert data["status"] == 1
    assert data["priority"] == 2

def test_delete_event():
    event_data = {
        "subsystem_id": 1,
        "user_id": 1,
        "event_name": "Delete Event",
        "comment": "To be deleted",
        "status": 0,
        "priority": 1
    }
    post_response = client.post("/events", json=event_data)
    event_id = post_response.json()["event_id"]

    response = client.delete(f"/events/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["detail"] == "Событие удалено"

    # Проверяем, что событие больше не доступно
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 404

def test_get_users():
    response = client.get("/users")
    assert response.status_code == 200
    data = response.json()
    # Проверяем, что тестовый пользователь присутствует
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "login" in data[0]
