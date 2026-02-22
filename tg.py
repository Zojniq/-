print("=== TG.PY STARTED ===")
from datetime import datetime, time, timedelta
import os
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from schedule import SCHEDULE, WEEKDAY_TO_INDEX, get_lessons_for_day
from homework import HOMEWORK, load_homework, save_homework


BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Змінна середовища BOT_TOKEN не встановлена. Будь ласка, додайте її до вашого середовища.")

MY_CHAT_ID = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

REMINDER_INTERVAL = 15

MAIN_MENU_BUTTONS = [
    ["▶️ Старт", "⏹ Стоп"],
    ["📚 ДЗ", "📝 Список ДЗ"],
    ["📅 Розклад", "⚙️ Нагадування"],
]

def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text) for text in row] for row in MAIN_MENU_BUTTONS],
        resize_keyboard=True,
    )


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

    text = f"Час йти в універ! Через {REMINDER_INTERVAL} хв починається {subject} в кабінеті {room}."
    await context.bot.send_message(chat_id=chat_id, text=text)


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REMINDER_INTERVAL

    try:
        new_interval = int(context.args[0])
        if new_interval <= 0:
            raise ValueError
        REMINDER_INTERVAL = new_interval
        await update.message.reply_text(f"✅ Інтервал нагадувань змінено на {REMINDER_INTERVAL} хвилин.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Вкажіть коректний інтервал у хвилинах. Наприклад: /remind 10")


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

        dt_dummy = datetime.combine(datetime.today(), lesson_time) - timedelta(minutes=REMINDER_INTERVAL)
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

    try:
        validate_schedule(SCHEDULE)
    except ValueError as e:
        logger.error(f"Помилка в розкладі: {e}")
        await update.message.reply_text("❌ Помилка в розкладі. Поправ код.")
        return

    remove_jobs_for_chat(context.application, MY_CHAT_ID)
    schedule_jobs_for_chat(context.application, MY_CHAT_ID)

    await update.message.reply_text(
        f"👋 Привіт! Нагадуватиму за {REMINDER_INTERVAL} хв до початку пар.\n"
        "Використовуй меню нижче.",
        reply_markup=build_main_keyboard(),
    )
    await update.message.reply_text("✅ Розклад нагадувань налаштовано!")
    logger.info(f"Розклад налаштовано для chat_id={MY_CHAT_ID}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global MY_CHAT_ID

    chat_id = update.effective_chat.id

    if MY_CHAT_ID is not None and chat_id != MY_CHAT_ID:
        await update.message.reply_text("У тебе немає активних нагадувань або ти не головний користувач бота.")
        return

    remove_jobs_for_chat(context.application, chat_id)
    await update.message.reply_text("✅ Всі нагадування скасовано.", reply_markup=build_main_keyboard())
    logger.info(f"Нагадування скасовано для chat_id={chat_id}")


async def homework_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subjects = sorted({lesson["subject"] for lesson in SCHEDULE})
    keyboard = [[InlineKeyboardButton(subj, callback_data=subj)] for subj in subjects]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📘 Оберіть предмет для додавання ДЗ:", reply_markup=reply_markup)


async def homework_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    subject = query.data
    context.user_data["selected_subject"] = subject
    await query.edit_message_text(f"Введіть ДЗ для предмета: {subject}")


async def save_homework_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subject = context.user_data.get("selected_subject")
    if not subject:
        await update.message.reply_text("Спочатку оберіть предмет через /homework.")
        return

    homework_text = update.message.text
    HOMEWORK[subject] = homework_text
    save_homework()
    await update.message.reply_text(f"✅ ДЗ для '{subject}' збережено: {homework_text}")


async def list_homework(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    load_homework()
    if not HOMEWORK:
        await update.message.reply_text("ДЗ ще не додано.")
        return

    text = "📋 Ваші ДЗ:\n" + "\n".join([f"📌 {subject}: {hw}" for subject, hw in HOMEWORK.items()])
    await update.message.reply_text(text)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [KeyboardButton("🚀 /start"), KeyboardButton("🛑 /stop")],
        [KeyboardButton("📚 /homework"), KeyboardButton("📝 /listhw")],
        [KeyboardButton("🔙 /menu")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("🔧 Панель керування:", reply_markup=reply_markup)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_index = datetime.today().weekday()
    lessons = get_lessons_for_day(today_index)

    if not lessons:
        await update.message.reply_text("📅 Сьогодні пар немає!")
        return

    text = "📅 <b>Розклад на сьогодні:</b>\n" + "\n".join(
        [f"🕒 {lesson['time']} | {lesson['subject']} | ауд. {lesson['room']}" for lesson in lessons]
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def tomorrow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tomorrow_index = (datetime.today().weekday() + 1) % 7
    lessons = get_lessons_for_day(tomorrow_index)

    if not lessons:
        await update.message.reply_text("📅 Завтра пар немає!")
        return

    text = "📅 <b>Розклад на завтра:</b>\n" + "\n".join(
        [f"🕒 {lesson['time']} | {lesson['subject']} | ауд. {lesson['room']}" for lesson in lessons]
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "📅 <b>Розклад на тиждень:</b>\n"
    for weekday_index, weekday_name in enumerate(WEEKDAY_TO_INDEX.keys()):
        lessons = get_lessons_for_day(weekday_index)
        if lessons:
            text += "\n<b>{}:</b>\n".format(weekday_name) + "\n".join(
                [f"🕒 {lesson['time']} | {lesson['subject']} | ауд. {lesson['room']}" for lesson in lessons]
            ) + "\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def main_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    if text == "▶️ Старт":
        await start_command(update, context)
    elif text == "⏹ Стоп":
        await stop_command(update, context)
    elif text == "📚 ДЗ":
        await homework_menu(update, context)
    elif text == "📝 Список ДЗ":
        await list_homework(update, context)
    elif text == "📅 Розклад":
        await schedule_menu(update, context)
    elif text == "⚙️ Нагадування":
        await update.message.reply_text("Використовуй команду: /remind 5")
    else:
        await save_homework_command(update, context)


def main() -> None:
    from telegram.ext import MessageHandler, filters

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
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("tomorrow", tomorrow_command))
    app.add_handler(CommandHandler("week", week_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CallbackQueryHandler(homework_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_router))

    load_homework()
    logger.info("Бот запущено")
    app.run_polling()


if __name__ == "__main__":
    main()
