from datetime import datetime, time, timedelta
import os
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MY_CHAT_ID = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SCHEDULE = [
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
    {
        "weekday": "Tuesday",
        "time": "14:35",
        "subject": "Математика",
        "room": "234",
    },
    {
        "weekday": "Tuesday",
        "time": "16:10",
        "subject": "Математика",
        "room": "234",
    },
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
    {
        "weekday": "Friday",
        "time": "07:30",
        "subject": "Графові алгоритми",
        "room": "313",
    },
]

WEEKDAY_TO_INDEX = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

HOMEWORK = {}

def parse_time_str(t: str) -> time:
    hour, minute = map(int, t.split(":"))
    return time(hour=hour, minute=minute)

def validate_schedule(schedule: list) -> None:
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
    data = context.job.data
    chat_id = data["chat_id"]
    subject = data["subject"]
    room = data["room"]

    text = f"Час йти в універ! Через 15 хв починається {subject} в кабінеті {room}."
    await context.bot.send_message(chat_id=chat_id, text=text)

def schedule_jobs_for_chat(application: Application, chat_id: int) -> None:
    job_queue = application.job_queue

    for i, lesson in enumerate(SCHEDULE):
        weekday_name = lesson["weekday"]
        lesson_time_str = lesson["time"]
        subject = lesson["subject"]
        room = lesson["room"]

        if weekday_name not in WEEKDAY_TO_INDEX:
            continue

        weekday_index = WEEKDAY_TO_INDEX[weekday_name]
        lesson_time = parse_time_str(lesson_time_str)
        dt_dummy = datetime.combine(datetime.today(), lesson_time) - timedelta(minutes=15)
        reminder_time = time(hour=dt_dummy.hour, minute=dt_dummy.minute)
        job_name = f"reminder_{chat_id}_{weekday_index}_{i}"
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
    job_queue = application.job_queue
    current_jobs = job_queue.jobs()

    for job in current_jobs:
        if job.name and job.name.startswith(f"reminder_{chat_id}_"):
            job.schedule_removal()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global MY_CHAT_ID

    chat_id = update.effective_chat.id
    if MY_CHAT_ID is None:
        MY_CHAT_ID = chat_id

    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/stop")],
        [KeyboardButton("/homework"), KeyboardButton("/listhw")],
        [KeyboardButton("/menu")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привіт! Я буду надсилати нагадування за 15 хвилин до початку пар.",
        reply_markup=reply_markup,
    )

    try:
        validate_schedule(SCHEDULE)
    except ValueError as e:
        logger.error(f"Помилка в розкладі: {e}")
        await update.message.reply_text("Помилка в розкладі. Зверніться до адміністратора.")
        return

    remove_jobs_for_chat(context.application, MY_CHAT_ID)
    schedule_jobs_for_chat(context.application, MY_CHAT_ID)

    await update.message.reply_text("Розклад нагадувань налаштовано!")
    logger.info(f"Розклад налаштовано для chat_id={MY_CHAT_ID}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global MY_CHAT_ID

    chat_id = update.effective_chat.id

    if MY_CHAT_ID is not None and chat_id != MY_CHAT_ID:
        await update.message.reply_text("У тебе немає активних нагадувань або ти не головний користувач бота.")
        return

    remove_jobs_for_chat(context.application, chat_id)
    await update.message.reply_text("Всі нагадування скасовано.")
    logger.info(f"Нагадування скасовано для chat_id={chat_id}")

async def homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subjects = sorted({lesson["subject"] for lesson in SCHEDULE})
    keyboard = [[InlineKeyboardButton(subj, callback_data=subj)] for subj in subjects]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть предмет:", reply_markup=reply_markup)

async def homework_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    subject = query.data
    context.user_data["selected_subject"] = subject
    await query.edit_message_text(f"Введіть ДЗ для предмета: {subject}")

async def save_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subject = context.user_data.get("selected_subject")
    if not subject:
        await update.message.reply_text("Спочатку оберіть предмет через /homework.")
        return

    homework_text = update.message.text
    HOMEWORK[subject] = homework_text
    await update.message.reply_text(f"ДЗ для '{subject}' збережено: {homework_text}")

async def list_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not HOMEWORK:
        await update.message.reply_text("ДЗ ще не додано.")
        return

    text = "Ваші ДЗ:\n" + "\n".join([f"{subject}: {hw}" for subject, hw in HOMEWORK.items()])
    await update.message.reply_text(text)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/stop")],
        [KeyboardButton("/homework"), KeyboardButton("/listhw")],
        [KeyboardButton("/menu")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Панель керування:", reply_markup=reply_markup)

def main() -> None:
    from telegram.ext import MessageHandler, filters

    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN environment variable")

    app: Application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("homework", homework_menu))
    app.add_handler(CommandHandler("listhw", list_homework))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CallbackQueryHandler(homework_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_homework))

    logger.info("Бот запущено")
    app.run_polling()

if __name__ == "__main__":
    main()
