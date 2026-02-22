
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

WEEKDAY_TO_INDEX = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

def get_lessons_for_day(weekday_index: int) -> list:
    """Повертає список пар для заданого дня тижня."""
    weekday_name = list(WEEKDAY_TO_INDEX.keys())[weekday_index]
    return [lesson for lesson in SCHEDULE if lesson["weekday"] == weekday_name]
