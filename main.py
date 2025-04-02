# Імпорт необхідних бібліотек
from fastapi import FastAPI, Depends, Form, HTTPException  # Основа FastAPI + форми та обробка помилок
from pymongo import MongoClient  # Клієнт для роботи з MongoDB
from fastapi.responses import HTMLResponse  # Для відправки HTML-відповідей
import os  # Для роботи з файловою системою
from jinja2 import Environment, FileSystemLoader, select_autoescape  # Шаблонізатор HTML
from datetime import datetime  # Робота з часом
from bson import ObjectId  # Робота з ObjectId MongoDB
from typing import Optional  # Типізація (не використовується безпосередньо в цьому коді)

# Ініціалізація FastAPI додатку з метаданими
app = FastAPI(
    title="Розклад руху поїздів",
    description="Це API для управління розкладом поїздів з використанням MongoDB",
    version="1.0.1"
)

# Функція для підключення до MongoDB
def get_db_connection():
    # Створюємо клієнт для підключення до MongoDB на локальному сервері
    client = MongoClient("mongodb://localhost:27017/")
    # Обираємо базу даних "train_schedule"
    db = client["train_schedule"]
    return db  # Повертаємо об'єкт бази даних

# Функція для перетворення рядка часу у форматі "HH:MM" у об'єкт time
def parse_time(time_str: str) -> datetime.time:
    return datetime.strptime(time_str, "%H:%M").time()

# Налаштування Jinja2 для рендерингу HTML шаблонів
env = Environment(
    loader=FileSystemLoader('.'),  # Шукаємо шаблони в поточній директорії
    autoescape=select_autoescape(['html'])  # Автоматичне екранування HTML
)

# Головний ендпоінт, який повертає HTML сторінку з розкладом
@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Отримуємо підключення до бази даних
    db = get_db_connection()

    # Отримуємо список усіх поїздів
    trains = list(db.trains.find({}))
    # Форматуємо дані поїздів для шаблону
    formatted_trains = [{"id": str(train["_id"]), "name": train["name"]} for train in trains]

    # Отримуємо список усіх станцій
    stations = list(db.stations.find({}))
    # Форматуємо дані станцій для шаблону
    formatted_stations = [{"id": str(station["_id"]), "name": station["name"]} for station in stations]

    # Агрегаційний запит для отримання розкладу з пов'язаними даними
    pipeline = [
        {
            "$lookup": {  # Об'єднуємо записи з колекцією поїздів
                "from": "trains",
                "localField": "train_id",  # Поле в поточній колекції
                "foreignField": "_id",  # Поле в колекції trains
                "as": "train"  # Назва масиву для результатів
            }
        },
        # Аналогічний lookup для станції відправлення
        {
            "$lookup": {
                "from": "stations",
                "localField": "departure_station_id",
                "foreignField": "_id",
                "as": "departure_station"
            }
        },
        # Аналогічний lookup для станції прибуття
        {
            "$lookup": {
                "from": "stations",
                "localField": "arrival_station_id",
                "foreignField": "_id",
                "as": "arrival_station"
            }
        },
        # Розгортаємо масив train (перетворюємо з масиву з одного елемента в об'єкт)
        {
            "$unwind": "$train"
        },
        # Аналогічно для станцій
        {
            "$unwind": "$departure_station"
        },
        {
            "$unwind": "$arrival_station"
        },
        # Вибірка потрібних полів для фінального результату
        {
            "$project": {
                "_id": 1,  # Включаємо поле _id
                "train_name": "$train.name",  # Беремо назву поїзда
                "departure_station_name": "$departure_station.name",  # Назва станції відправлення
                "arrival_station_name": "$arrival_station.name",  # Назва станції прибуття
                "departure_time": 1,  # Час відправлення
                "arrival_time": 1  # Час прибуття
            }
        }
    ]

    # Виконуємо агрегаційний запит
    records = list(db.records.aggregate(pipeline))

    # Форматуємо записи для шаблону
    formatted_records = []
    for record in records:
        formatted_records.append({
            "id": str(record["_id"]),  # Конвертуємо ObjectId у рядок
            "train_name": record["train_name"],
            "departure_station_name": record["departure_station_name"],
            "arrival_station_name": record["arrival_station_name"],
            "departure_time": record["departure_time"],
            "arrival_time": record["arrival_time"],
        })

    # Рендеримо HTML шаблон з отриманими даними
    template = env.get_template('index.html')
    return HTMLResponse(content=template.render(
        records=formatted_records,
        trains=formatted_trains,
        stations=formatted_stations
    ))

# Ендпоінт для створення нового поїзда (POST-запит)
@app.post("/trains/")
async def create_train(name: str = Form(...), train_type: str = Form(...)):
    db = get_db_connection()  # Підключаємось до БД
    # Готуємо дані для нового поїзда
    train_data = {
        "name": name,
        "type": train_type
    }
    # Вставляємо новий документ у колекцію trains
    result = db.trains.insert_one(train_data)
    # Повертаємо успішний результат з ID нового поїзда
    return {"message": "Train added successfully", "id": str(result.inserted_id)}

# Ендпоінт для видалення поїзда (DELETE-запит)
@app.delete("/trains/{train_id}")
async def delete_train(train_id: str):
    db = get_db_connection()
    try:
        # Конвертуємо рядковий ID у ObjectId
        obj_id = ObjectId(train_id)
    except:
        # Якщо конвертація не вдалась - повертаємо помилку
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Видаляємо поїзд за ID
    result = db.trains.delete_one({"_id": obj_id})
    if result.deleted_count == 1:  # Якщо видалено 1 документ
        return {"message": "Train deleted successfully"}
    else:  # Якщо документ не знайдено
        raise HTTPException(status_code=404, detail="Train not found")

# Ендпоінт для оновлення інформації про поїзд (PUT-запит)
@app.put("/trains/{train_id}")
async def update_train(train_id: str, name: str = Form(...), train_type: str = Form(...)):
    db = get_db_connection()
    try:
        obj_id = ObjectId(train_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Оновлюємо дані поїзда за допомогою оператора $set
    result = db.trains.update_one(
        {"_id": obj_id},  # Критерій пошуку
        {"$set": {"name": name, "type": train_type}}  # Нові значення
    )

    if result.modified_count == 1:  # Якщо оновлено 1 документ
        return {"message": "Train updated successfully"}
    else:  # Якщо документ не знайдено
        raise HTTPException(status_code=404, detail="Train not found")

# Ендпоінт для отримання списку всіх поїздів (GET-запит)
@app.get("/trains/")
async def get_trains():
    db = get_db_connection()
    # Отримуємо всі документи з колекції trains
    trains = list(db.trains.find({}))
    # Форматуємо результат (конвертуємо ObjectId у рядок)
    return [{"id": str(train["_id"]), "name": train["name"], "type": train["type"]} for train in trains]

# Ендпоінт для створення нової станції (POST-запит)
@app.post("/stations/")
async def create_station(name: str = Form(...), platform: str = Form(...)):
    db = get_db_connection()
    # Готуємо дані для нової станції
    station_data = {
        "name": name,
        "platform": platform
    }
    # Вставляємо новий документ у колекцію stations
    result = db.stations.insert_one(station_data)
    # Повертаємо успішний результат з ID нової станції
    return {"message": "Station added successfully", "id": str(result.inserted_id)}

# Ендпоінт для видалення станції (DELETE-запит)
@app.delete("/stations/{station_id}")
async def delete_station(station_id: str):
    db = get_db_connection()
    try:
        obj_id = ObjectId(station_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Видаляємо станцію за ID
    result = db.stations.delete_one({"_id": obj_id})
    if result.deleted_count == 1:
        return {"message": "Station deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Station not found")

# Ендпоінт для отримання списку всіх станцій (GET-запит)
@app.get("/stations/")
async def get_stations():
    db = get_db_connection()
    # Отримуємо всі документи з колекції stations
    stations = list(db.stations.find({}))
    # Форматуємо результат (конвертуємо ObjectId у рядок)
    return [{"id": str(station["_id"]), "name": station["name"], "platform": station["platform"]}
            for station in stations]

# Ендпоінт для створення нового запису розкладу (POST-запит)
@app.post("/records/")
async def create_record(
    train_id: str = Form(...),
    departure_station_id: str = Form(...),
    arrival_station_id: str = Form(...),
    departure_time: str = Form(...),
    arrival_time: str = Form(...),
):
    try:
        # Парсимо час з рядків
        dep_time = parse_time(departure_time)
        arr_time = parse_time(arrival_time)

        # Конвертуємо рядкові ID у ObjectId
        train_obj_id = ObjectId(train_id)
        dep_station_obj_id = ObjectId(departure_station_id)
        arr_station_obj_id = ObjectId(arrival_station_id)
    except Exception as e:
        # Логуємо помилку та повертаємо HTTP 400 у разі проблем
        print("Error parsing input:", e)
        raise HTTPException(status_code=400, detail=f"Invalid input format: {e}")

    db = get_db_connection()

    # Готуємо дані для нового запису розкладу
    record_data = {
        "train_id": train_obj_id,
        "departure_station_id": dep_station_obj_id,
        "arrival_station_id": arr_station_obj_id,
        "departure_time": dep_time.strftime("%H:%M"),  # Зберігаємо час у форматі рядка
        "arrival_time": arr_time.strftime("%H:%M")
    }

    # Вставляємо новий документ у колекцію records
    result = db.records.insert_one(record_data)
    # Повертаємо успішний результат з ID нового запису
    return {"message": "Record added successfully", "id": str(result.inserted_id)}

# Ендпоінт для видалення запису розкладу (DELETE-запит)
@app.delete("/records/{record_id}/")
async def delete_record(record_id: str):
    db = get_db_connection()
    try:
        obj_id = ObjectId(record_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Видаляємо запис розкладу за ID
    result = db.records.delete_one({"_id": obj_id})
    if result.deleted_count == 1:
        return {"message": "Record deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Record not found")