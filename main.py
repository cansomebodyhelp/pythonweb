from fastapi import FastAPI, Depends
import os
from fastapi.responses import HTMLResponse
from sqlalchemy.sql import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, Time
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from pydantic import BaseModel
# Створення об`єкта застосунку
app = FastAPI(
    title="Розклад руху поїздів",
    description="Це API для управління розкладом поїздів.",
    version="1.0.0"
)

# Підключення к БД
DATABASE_URL = "mysql+asyncmy://root:root@localhost/schedule"

# Створення асинхроного двигуна
engine = create_async_engine(DATABASE_URL, echo=True)


Base = declarative_base()

# Створення фабрики сесій
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# Приклад залежності для сесій
async def get_db():
    async with async_session() as session:
        yield session

# Таблиця Train
class Train(Base):
    __tablename__ = "train"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)
    records = relationship("Record", back_populates="train")

# Таблиця Station
class Station(Base):
    __tablename__ = "station"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    platform = Column(String(20), nullable=False)
    departure_records = relationship("Record", back_populates="departure_station",
                                     foreign_keys='Record.departure_station_id')
    arrival_records = relationship("Record", back_populates="arrival_station", foreign_keys='Record.arrival_station_id')

# Таблиця Record
class Record(Base):
    __tablename__ = "record"
    id = Column(Integer, primary_key=True, index=True)
    train_id = Column(Integer, ForeignKey("train.id"), nullable=False)
    departure_station_id = Column(Integer, ForeignKey("station.id"), nullable=False)
    arrival_station_id = Column(Integer, ForeignKey("station.id"), nullable=False)
    departure_time = Column(Time, nullable=False)
    arrival_time = Column(Time, nullable=False)

    # Створені зв'язки для поєднання станцій та потягів в записах
    train = relationship("Train", back_populates="records")
    departure_station = relationship("Station", back_populates="departure_records", foreign_keys=[departure_station_id])
    arrival_station = relationship("Station", back_populates="arrival_records", foreign_keys=[arrival_station_id])

# Функція для перероблення формата часу
def parse_time(time_str: str) -> datetime.time:
    return datetime.strptime(time_str, "%H:%M").time()

# Створюємо таблиці в бд(1 раз)
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Шаблони для jinja2
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, "templates")
env = Environment(loader=FileSystemLoader(template_dir))

# Код нижче витягує дані з бд та передає на html сторінку
@app.get("/", response_class=HTMLResponse)
async def read_root(db: AsyncSession = Depends(get_db)):
    query = text("""
        SELECT
            r.id,
            t.name AS train_name,
            ds.name AS departure_station_name,
            asn.name AS arrival_station_name,
            r.departure_time,
            r.arrival_time
        FROM record r
        JOIN train t ON r.train_id = t.id
        JOIN station ds ON r.departure_station_id = ds.id
        JOIN station asn ON r.arrival_station_id = asn.id
    """)
    result = await db.execute(query)
    records = result.fetchall()

    formatted_records = []
    for record in records:
        formatted_records.append({
            "train_name": record.train_name,
            "departure_station_name": record.departure_station_name,
            "arrival_station_name": record.arrival_station_name,
            "departure_time": record.departure_time,
            "arrival_time": record.arrival_time,
        })

    template = env.get_template("index.html")
    return HTMLResponse(content=template.render(records=formatted_records))

# Ендпоінти для роботи з поїздами
@app.post("/trains/")
async def create_train(name: str, train_type: str, db=Depends(get_db)):
    new_train = Train(name=name, type=train_type)
    db.add(new_train)
    await db.commit()
    return {"id": new_train.id, "name": new_train.name, "type": new_train.type}

@app.delete("/trains/{train_id}")
async def delete_train(train_id: int, db=Depends(get_db)):
    train = await db.get(Train, train_id)
    if train:
        await db.delete(train)
        await db.commit()
        return {"message": "Train deleted successfully"}
    return {"message": "Train not found"}, 404

# модель оновлення даних поїзду
class TrainUpdate(BaseModel):
    name: str
    type: str

@app.put("/trains/{train_id}")
async def update_train(train_id: int, train_update: TrainUpdate, db=Depends(get_db)):
    # пошук поїзду через id
    train = await db.get(Train, train_id)
    if train:
        # оновлення даних поїзду
        train.name = train_update.name
        train.type = train_update.type
        await db.commit()
        return {
            "id": train.id,
            "name": train.name,
            "type": train.type
        }
    return {"message": f"Train with ID {train_id} not found"}, 404

@app.get("/trains/")
async def get_trains(db=Depends(get_db)):
    trains = await db.execute(Train.__table__.select())
    trains_list = trains.fetchall()
    return [{"id": train.id, "name": train.name, "type": train.type} for train in trains_list]

# Ендпоінти для роботи зі станціями
@app.post("/stations/")
async def create_station(name: str, platform: str, db=Depends(get_db)):
    new_station = Station(name=name, platform=platform)
    db.add(new_station)
    await db.commit()
    return {"id": new_station.id, "name": new_station.name, "platform": new_station.platform}

@app.delete("/stations/{station_id}")
async def delete_station(station_id: int, db=Depends(get_db)):
    station = await db.get(Station, station_id)
    if station:
        await db.delete(station)
        await db.commit()
        return {"message": "Station deleted successfully"}
    return {"message": "Station not found"}, 404

@app.get("/stations/")
async def get_stations(db=Depends(get_db)):
    stations = await db.execute(Station.__table__.select())
    stations_list = stations.fetchall()
    return [{"id": station.id, "name": station.name, "platform": station.platform} for station in stations_list]

# Модель створення запису про рух потягу
class RecordCreate(BaseModel):
    train_id: int
    departure_station_id: int
    arrival_station_id: int
    departure_time: str
    arrival_time: str

@app.post("/records/")
async def create_record(record: RecordCreate, db=Depends(get_db)):
    dep_time = parse_time(record.departure_time)
    arr_time = parse_time(record.arrival_time)

    new_record = Record(
        train_id=record.train_id,
        departure_station_id=record.departure_station_id,
        arrival_station_id=record.arrival_station_id,
        departure_time=dep_time,
        arrival_time=arr_time
    )
    db.add(new_record)
    await db.commit()
    return {
        "id": new_record.id,
        "train_id": new_record.train_id,
        "departure_station_id": new_record.departure_station_id,
        "arrival_station_id": new_record.arrival_station_id,
        "departure_time": new_record.departure_time,
        "arrival_time": new_record.arrival_time,
    }

@app.delete("/records/{record_id}/")
async def delete_record(record_id: int, db=Depends(get_db)):
    record = await db.get(Record, record_id)
    if record:
        await db.delete(record)
        await db.commit()
        return {"message": "Record deleted successfully"}
    return {"message": "Record not found"}