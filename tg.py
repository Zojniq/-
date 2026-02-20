import asyncio
from datetime import datetime, time, timedelta
import os  # Додано для роботи зі змінними середовища
import logging  # Додано для логування

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton  # Додано імпорт клавіатури
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,  # Додано для обробки callback'ів
)

# === СЮДИ ВСТАВ СВІЙ ТОКЕН БОТА ===
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === СЮДИ ВСТАВ СВІЙ chat_id (можна поки залишити None, тоді збережеться зі /start) ===
MY_CHAT_ID = None  # або одразу твій чат id, наприклад 123456789

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# РОЗКЛАД ПАР:
# Щоб змінити розклад, просто додай/видали елементи в цьому списку.
# weekday: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
# time: "HH:MM" (24-годинний формат)
SCHEDULE = [
    # Понеділок
    {
        "weekday": "Monday",
        "time": "08:15",
        "subject": "Програмування",
        "room": "313",
    },
    {
        "weekday": "Monday",
        "time": "17:45",
        "subject": "Графові алгоритми",
        "room": "313",
    },
    # Вівторок
    {
        "weekday": "Tuesday",
        "time": "14:35",
        "subject": "Математика",
        "room": "234",
    },
    {
        "weekday": "Tuesday",
        "time": "16:10",  # Друга пара підряд
        "subject": "Математика",
        "room": "234",
    },
    # Середа
    {
        "weekday": "Wednesday",
        "time": "09:50",
        "subject": "Веб технології",
        "room": "134",
    },
    {
        "weekday": "Wednesday",
        "time": "12:15",
        "subject": "Веб технології",
        "room": "356",
    },
    {
        "weekday": "Wednesday",
        "time": "13:50",
        "subject": "Лінукс",
        "room": "135",
    },
    # Четвер
    {
        "weekday": "Thursday",
        "time": "11:25",
        "subject": "Програмування",
        "room": "135",
    },
    {
        "weekday": "Thursday",
        "time": "13:50",
        "subject": "Позашкільна чинність",
        "room": "135",
    },
    # П'ятниця
    {
        "weekday": "Friday",
        "time": "07:30",
        "subject": "Графові алгоритми",
        "room": "313",
    },
]

# Мапа назв днів тижня на індекси JobQueue (0 = Monday, 6 = Sunday)
WEEKDAY_TO_INDEX = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# Словник для зберігання ДЗ
HOMEWORK = {}

def parse_time_str(t: str) -> time:
    """Парсимо 'HH:MM' у datetime.time."""
    hour, minute = map(int, t.split(":"))
    return time(hour=hour, minute=minute)

def validate_schedule(schedule: list) -> None:
    """Перевіряє коректність розкладу."""
    for lesson in schedule:
        if "weekday" not in lesson or "time" not in lesson or "subject" not in lesson or "room" not in lesson:
            raise ValueError(f"Некоректний запис у розкладі: {lesson}")
        if lesson["weekday"] not in WEEKDAY_TO_INDEX:
            raise ValueError(f"Некоректний день тижня: {lesson['weekday']}")
        try:
            parse_time_str(lesson["time"])
        except ValueError:
            raise ValueError(f"Некоректний час: {lesson['time']}")

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Функція, яку викликає JobQueue, щоб надіслати нагадування."""
    data = context.job.data
    chat_id = data["chat_id"]
    subject = data["subject"]
    room = data["room"]

    text = f"Час йти в універ! Через 15 хв починається {subject} в кабінеті {room}."
    await context.bot.send_message(chat_id=chat_id, text=text)

def schedule_jobs_for_chat(application: Application, chat_id: int) -> None:
    """
    Планує всі нагадування згідно з розкладом для конкретного chat_id.
    Викликається, коли користувач робить /start.
    """
    job_queue = application.job_queue

    for i, lesson in enumerate(SCHEDULE):
        weekday_name = lesson["weekday"]
        lesson_time_str = lesson["time"]
        subject = lesson["subject"]
        room = lesson["room"]

        if weekday_name not in WEEKDAY_TO_INDEX:
            continue  # якщо день введений з помилкою

        weekday_index = WEEKDAY_TO_INDEX[weekday_name]

        # Час пари
        lesson_time = parse_time_str(lesson_time_str)

        # Час нагадування: T = час пари - 15 хвилин
        dt_dummy = datetime.combine(datetime.today(), lesson_time) - timedelta(minutes=15)
        reminder_time = time(hour=dt_dummy.hour, minute=dt_dummy.minute)

        # Унікальне ім'я job для можливого видалення
        job_name = f"reminder_{chat_id}_{weekday_index}_{i}"

        # Плануємо job, який буде спрацьовувати щотижня в потрібний день та час
        job_queue.run_daily(
            callback=reminder_callback,
            time=reminder_time,
            days=(weekday_index,),
            data={
                "chat_id": chat_id,
                "subject": subject,
                "room": room,
            },
            name=job_name,
        )

def remove_jobs_for_chat(application: Application, chat_id: int) -> None:
    """
    Видаляє всі job'и, пов'язані з цим chat_id (створені в schedule_jobs_for_chat).
    Викликається, коли користувач робить /stop.
    """
    job_queue = application.job_queue
    current_jobs = job_queue.jobs()  # отримаємо всі job'и

    for job in current_jobs:
        # Наші job'и називаємо як "reminder_{chat_id}_..."
        if job.name and job.name.startswith(f"reminder_{chat_id}_"):
            job.schedule_removal()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start:
    - вітає користувача
    - зберігає chat_id
    - запускає планування всіх майбутніх нагадувань
    - додає панель із кнопками біля поля вводу тексту
    """
    global MY_CHAT_ID

    chat_id = update.effective_chat.id
    if MY_CHAT_ID is None:
        MY_CHAT_ID = chat_id

    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/stop")],
        [KeyboardButton("/homework"), KeyboardButton("/listhw")],
        [KeyboardButton("/menu")],  # Додано кнопку для повернення до меню
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привіт! Я буду надсилати нагадування за 15 хвилин до початку пар.",
        reply_markup=reply_markup,  # Додає панель із кнопками
    )

    try:
        validate_schedule(SCHEDULE)  # Перевірка розкладу
    except ValueError as e:
        logger.error(f"Помилка в розкладі: {e}")
        await update.message.reply_text("Помилка в розкладі. Зверніться до адміністратора.")
        return

    remove_jobs_for_chat(context.application, MY_CHAT_ID)
    schedule_jobs_for_chat(context.application, MY_CHAT_ID)

    await update.message.reply_text("Розклад нагадувань налаштовано!")
    logger.info(f"Розклад налаштовано для chat_id={MY_CHAT_ID}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /stop:
    - відміняє всі заплановані нагадування для цього chat_id
    """
    global MY_CHAT_ID

    chat_id = update.effective_chat.id

    # Якщо хочеш, можна дозволити /stop працювати лише для конкретного MY_CHAT_ID
    if MY_CHAT_ID is not None and chat_id != MY_CHAT_ID:
        await update.message.reply_text("У тебе немає активних нагадувань або ти не головний користувач бота.")
        return

    remove_jobs_for_chat(context.application, chat_id)
    await update.message.reply_text("Всі нагадування скасовано.")
    logger.info(f"Нагадування скасовано для chat_id={chat_id}")

async def homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /homework:
    - Відображає меню з унікальними предметами для вибору.
    """
    subjects = sorted({lesson["subject"] for lesson in SCHEDULE})  # Унікальні предмети
    keyboard = [[InlineKeyboardButton(subj, callback_data=subj)] for subj in subjects]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть предмет:", reply_markup=reply_markup)

async def homework_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обробляє вибір предмета для запису ДЗ.
    """
    query = update.callback_query
    await query.answer()
    subject = query.data
    context.user_data["selected_subject"] = subject
    await query.edit_message_text(f"Введіть ДЗ для предмета: {subject}")

async def save_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Зберігає ДЗ для вибраного предмета.
    """
    subject = context.user_data.get("selected_subject")
    if not subject:
        await update.message.reply_text("Спочатку оберіть предмет через /homework.")
        return

    homework_text = update.message.text
    HOMEWORK[subject] = homework_text
    await update.message.reply_text(f"ДЗ для '{subject}' збережено: {homework_text}")

async def list_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /listhw:
    - Відображає список усіх збережених ДЗ.
    """
    if not HOMEWORK:
        await update.message.reply_text("ДЗ ще не додано.")
        return

    text = "Ваші ДЗ:\n" + "\n".join([f"{subject}: {hw}" for subject, hw in HOMEWORK.items()])
    await update.message.reply_text(text)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /menu:
    - показує панель керування з основними кнопками біля поля вводу тексту.
    """
    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/stop")],
        [KeyboardButton("/homework"), KeyboardButton("/listhw")],
        [KeyboardButton("/menu")],  # Додано кнопку для повернення до меню
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Панель керування:", reply_markup=reply_markup)

def main() -> None:
    from telegram.ext import MessageHandler, filters  # імпорт тут ок

    app: Application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("homework", homework_menu))
    app.add_handler(CommandHandler("listhw", list_homework))
    app.add_handler(CommandHandler("menu", menu_command))  # Зареєстровано хендлер для /menu
    app.add_handler(CallbackQueryHandler(homework_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_homework))

    logger.info("Бот запущено")
    app.run_polling()  # БЕЗ await

if __name__ == "__main__":
    main()
