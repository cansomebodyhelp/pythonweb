from fastapi import FastAPI, Depends, Form, HTTPException  # Імпортуємо необхідні модулі з FastAPI
import psycopg2  # Імпортуємо psycopg2 для роботи з PostgreSQL
from fastapi.responses import HTMLResponse  # Імпортуємо клас для відповіді у вигляді HTML
import os  # Імпортуємо для роботи з операційною системою (використовуємо для шляху до шаблонів)
from jinja2 import Environment, FileSystemLoader  # Імпортуємо Jinja2 для рендерингу HTML-шаблонів
from datetime import datetime  # Імпортуємо для роботи з датами та часом

# Ініціалізація додатка FastAPI з основними параметрами
app = FastAPI(
    title="Розклад руху поїздів",  # Заголовок додатку
    description="Це API для управління розкладом поїздів.",  # Опис додатку
    version="1.0.1"  # Версія додатку
)

# Функція для встановлення з'єднання з базою даних PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        dbname="train_schedule",  # Назва бази даних
        host="localhost",         # Адреса сервера бази даних
        user="user",              # Ім'я користувача для підключення
        password="123",           # Пароль для підключення
        port="5432"               # Порт для підключення
    )
    return conn  # Повертаємо з'єднання з базою даних

# Функція для парсингу часу з рядка у форматі "HH:MM"
def parse_time(time_str: str) -> datetime.time:
    return datetime.strptime(time_str, "%H:%M").time()  # Перетворюємо рядок в об'єкт типу time

# Підключення Jinja2 для рендерингу HTML-шаблонів
base_dir = os.path.dirname(os.path.abspath(__file__))  # Отримуємо абсолютний шлях до поточного файлу
template_dir = os.path.join(base_dir, "templates")     # Шлях до директорії з шаблонами
env = Environment(loader=FileSystemLoader(template_dir))  # Створюємо середовище для рендерингу шаблонів

# Ендпоінт для отримання головної сторінки, яка містить розклад поїздів
@app.get("/", response_class=HTMLResponse)
async def read_root():
    query = """
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
    """  # SQL-запит для отримання розкладу руху поїздів

    # Підключення до бази даних та виконання запиту
    conn = get_db_connection()
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    cur.execute(query)  # Виконуємо запит
    records = cur.fetchall()  # Отримуємо всі результати запиту
    conn.close()  # Закриваємо з'єднання з базою даних

    formatted_records = []  # Список для відформатованих записів
    for record in records:
        # Форматуємо отримані дані для зручності використання у шаблоні
        formatted_records.append({
            "id": record[0],  # Додаємо id запису
            "train_name": record[1],
            "departure_station_name": record[2],
            "arrival_station_name": record[3],
            "departure_time": record[4],
            "arrival_time": record[5],
        })

    template = env.get_template("index.html")  # Завантажуємо шаблон HTML
    return HTMLResponse(content=template.render(records=formatted_records))  # Рендеримо шаблон та повертаємо відповідь

# Ендпоінт для створення нового поїзда
@app.post("/trains/")
async def create_train(name: str = Form(...), train_type: str = Form(...)):
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "INSERT INTO train (name, type) VALUES (%s, %s) RETURNING id, name, type"  # Запит для додавання поїзда
    cur.execute(query, (name, train_type))  # Виконуємо запит з параметрами
    new_train = cur.fetchone()  # Отримуємо дані нового поїзда
    conn.commit()  # Зберігаємо зміни в базі
    conn.close()  # Закриваємо з'єднання
    return {"message": "Train added successfully"}

# Ендпоінт для видалення поїзда за його ID
@app.delete("/trains/{train_id}")
async def delete_train(train_id: int):
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "DELETE FROM train WHERE id = %s RETURNING id"  # Запит для видалення поїзда за ID
    cur.execute(query, (train_id,))  # Виконуємо запит
    deleted_train = cur.fetchone()  # Отримуємо ID видаленого поїзда
    conn.commit()  # Зберігаємо зміни
    conn.close()  # Закриваємо з'єднання

    if deleted_train:
        return {"message": "Train deleted successfully"}  # Повертаємо успішне повідомлення
    else:
        raise HTTPException(status_code=404, detail="Train not found")  # Повертаємо помилку, якщо поїзд не знайдений

# Ендпоінт для оновлення інформації про поїзд
@app.put("/trains/{train_id}")
async def update_train(train_id: int, name: str = Form(...), train_type: str = Form(...)):
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "UPDATE train SET name = %s, type = %s WHERE id = %s RETURNING id, name, type"  # Запит для оновлення поїзда
    cur.execute(query, (name, train_type, train_id))  # Виконуємо запит
    updated_train = cur.fetchone()  # Отримуємо оновлені дані поїзда
    conn.commit()  # Зберігаємо зміни
    conn.close()  # Закриваємо з'єднання

    if updated_train:
        return {"id": updated_train[0], "name": updated_train[1], "type": updated_train[2]}  # Повертаємо оновлену інформацію
    else:
        raise HTTPException(status_code=404, detail="Train not found")  # Повертаємо помилку, якщо поїзд не знайдений

# Ендпоінт для отримання всіх поїздів
@app.get("/trains/")
async def get_trains():
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "SELECT id, name, type FROM train"  # Запит для отримання списку всіх поїздів
    cur.execute(query)  # Виконуємо запит
    trains = cur.fetchall()  # Отримуємо всі результати
    conn.close()  # Закриваємо з'єднання
    return [{"id": train[0], "name": train[1], "type": train[2]} for train in trains]  # Повертаємо список поїздів

# Ендпоінт для створення нової станції
@app.post("/stations/")
async def create_station(name: str = Form(...), platform: str = Form(...)):
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "INSERT INTO station (name, platform) VALUES (%s, %s) RETURNING id, name, platform"  # Запит для додавання станції
    cur.execute(query, (name, platform))  # Виконуємо запит з параметрами
    new_station = cur.fetchone()  # Отримуємо дані нової станції
    conn.commit()  # Зберігаємо зміни в базі
    conn.close()  # Закриваємо з'єднання
    return {"id": new_station[0], "name": new_station[1], "platform": new_station[2]}  # Повертаємо інформацію про нову станцію

# Ендпоінт для видалення станції за її ID
@app.delete("/stations/{station_id}")
async def delete_station(station_id: int):
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "DELETE FROM station WHERE id = %s RETURNING id"  # Запит для видалення станції за ID
    cur.execute(query, (station_id,))  # Виконуємо запит
    deleted_station = cur.fetchone()  # Отримуємо ID видаленої станції
    conn.commit()  # Зберігаємо зміни
    conn.close()  # Закриваємо з'єднання

    if deleted_station:
        return {"message": "Station deleted successfully"}  # Повертаємо успішне повідомлення
    else:
        raise HTTPException(status_code=404, detail="Station not found")  # Повертаємо помилку, якщо станція не знайдена

# Ендпоінт для отримання всіх станцій
@app.get("/stations/")
async def get_stations():
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "SELECT id, name, platform FROM station"  # Запит для отримання списку всіх станцій
    cur.execute(query)  # Виконуємо запит
    stations = cur.fetchall()  # Отримуємо всі результати
    conn.close()  # Закриваємо з'єднання
    return [{"id": station[0], "name": station[1], "platform": station[2]} for station in stations]  # Повертаємо список станцій

# Ендпоінт для створення нового запису про розклад
@app.post("/records/")
async def create_record(
        train_id: int = Form(...),  # ID поїзда
        departure_station_id: int = Form(...),  # ID станції відправлення
        arrival_station_id: int = Form(...),  # ID станції прибуття
        departure_time: str = Form(...),  # Час відправлення
        arrival_time: str = Form(...),  # Час прибуття
):
    dep_time = parse_time(departure_time)  # Перетворюємо час відправлення в тип datetime
    arr_time = parse_time(arrival_time)  # Перетворюємо час прибуття в тип datetime

    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = """
        INSERT INTO record (train_id, departure_station_id, arrival_station_id, departure_time, arrival_time)
        VALUES (%s, %s, %s, %s, %s) RETURNING id, train_id, departure_station_id, arrival_station_id, departure_time, arrival_time
    """  # Запит для додавання нового запису в розклад
    cur.execute(query, (train_id, departure_station_id, arrival_station_id, dep_time, arr_time))  # Виконуємо запит
    new_record = cur.fetchone()  # Отримуємо дані нового запису
    conn.commit()  # Зберігаємо зміни в базі
    conn.close()  # Закриваємо з'єднання

    return {
        "id": new_record[0],  # Повертаємо інформацію про новий запис
        "train_id": new_record[1],
        "departure_station_id": new_record[2],
        "arrival_station_id": new_record[3],
        "departure_time": new_record[4],
        "arrival_time": new_record[5],
    }

# Ендпоінт для видалення запису за його ID
@app.delete("/records/{record_id}/")
async def delete_record(record_id: int):
    conn = get_db_connection()  # Підключення до бази даних
    cur = conn.cursor()  # Створюємо курсор для виконання запиту
    query = "DELETE FROM record WHERE id = %s RETURNING id"  # Запит для видалення запису за ID
    cur.execute(query, (record_id,))  # Виконуємо запит
    deleted_record = cur.fetchone()  # Отримуємо ID видаленого запису
    conn.commit()  # Зберігаємо зміни
    conn.close()  # Закриваємо з'єднання

    if deleted_record:
        return {"message": "Record deleted successfully"}  # Повертаємо успішне повідомлення
    else:
        raise HTTPException(status_code=404, detail="Record not found")  # Повертаємо помилку, якщо запис не знайдений
