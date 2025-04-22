import datetime
import asyncio

from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uvicorn

# ======================
# Настройка подключения к БД
# ======================
DATABASE_URL = "postgresql://postgres:0000@localhost:5432/LoggingMicroservice"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


# ======================
# Определение моделей БД
# ======================
class Event(Base):
    __tablename__ = "events"
    event_id = Column("event_id", Integer, primary_key=True, index=True)
    subsystem_id = Column("subsystem_id", Integer, nullable=False)
    user_id = Column("user_id", Integer, nullable=False)
    event_name = Column("event_name", String, nullable=False)
    comment = Column("comment", String, nullable=True)
    date = Column("date", Date, default=datetime.date.today)
    status = Column("status", Integer, nullable=False)
    priority = Column("priority", Integer, nullable=False)


class Subsystem(Base):
    __tablename__ = "subsystems"
    subsystem_id = Column("subsystem_id", Integer, primary_key=True, index=True)
    subsystem_name = Column("subsystem_name", String, nullable=False)
    type = Column("type", Integer, nullable=False)


class User(Base):
    __tablename__ = "users"
    user_id = Column("user_id", Integer, primary_key=True, index=True)
    login = Column("login", String, nullable=False)
    role = Column("role", Integer, nullable=False)  # Например, 1 - Administrator, 2 - User


Base.metadata.create_all(bind=engine)


# ======================
# Инициализация FastAPI приложения
# ======================
app = FastAPI(title="Микросервис мониторинга и логгирования событий")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class EventCreate(BaseModel):
    subsystem_id: int
    user_id: int
    event_name: str
    comment: str = None
    date: datetime.date = None
    status: int
    priority: int


# ======================
# Менеджер WebSocket-соединений
# ======================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)


# ======================
# Эндпоинты для работы с событиями
# Сделаны асинхронными для корректного выполнения background задач
# ======================
@app.get("/events")
def read_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    return events


@app.get("/events/{event_id}")
def read_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    return event


@app.post("/events")
async def create_event(event: EventCreate, db: Session = Depends(get_db)):
    db_event = Event(
        subsystem_id=event.subsystem_id,
        user_id=event.user_id,
        event_name=event.event_name,
        comment=event.comment,
        date=event.date if event.date else datetime.date.today(),
        status=event.status,
        priority=event.priority
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # Теперь вызов background задачи выполняется внутри работающего event loop
    asyncio.create_task(manager.broadcast(f"Новое событие: {db_event.event_name}"))
    return db_event


@app.put("/events/{event_id}")
async def update_event(event_id: int, updated_event: EventCreate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    event.subsystem_id = updated_event.subsystem_id
    event.user_id = updated_event.user_id
    event.event_name = updated_event.event_name
    event.comment = updated_event.comment
    event.date = updated_event.date if updated_event.date else event.date
    event.status = updated_event.status
    event.priority = updated_event.priority

    db.commit()

    asyncio.create_task(manager.broadcast(f"Обновлено событие: {event.event_name}"))
    return event


@app.delete("/events/{event_id}")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    db.delete(event)
    db.commit()

    asyncio.create_task(manager.broadcast(f"Удалено событие: {event.event_name}"))
    return {"detail": "Событие удалено"}


@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
