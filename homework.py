
import json
import os

HOMEWORK_FILE = "homework.json"
HOMEWORK = {}

def load_homework() -> None:

    global HOMEWORK
    if os.path.exists(HOMEWORK_FILE):
        with open(HOMEWORK_FILE, "r", encoding="utf-8") as file:
            HOMEWORK = json.load(file)

def save_homework() -> None:

    with open(HOMEWORK_FILE, "w", encoding="utf-8") as file:
        json.dump(HOMEWORK, file, ensure_ascii=False, indent=4)
