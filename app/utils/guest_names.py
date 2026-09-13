import secrets

# (noun, grammatical gender) pairs; adjectives are picked from the matching-gender
# list below so the generated nickname agrees in gender (e.g. "Неопознанная Капибара",
# "Тихий Бобр") the same way the product design's placeholder names do.
_ANIMALS: list[tuple[str, str]] = [
    ("Капибара", "f"),
    ("Бобр", "m"),
    ("Ёж", "m"),
    ("Лис", "m"),
    ("Кит", "m"),
    ("Лось", "m"),
    ("Снегирь", "m"),
    ("Барсук", "m"),
    ("Сурок", "m"),
    ("Сова", "f"),
    ("Лиса", "f"),
    ("Пантера", "f"),
]

_ADJECTIVES_M: list[str] = [
    "Тихий", "Яркий", "Быстрый", "Синий", "Добрый",
    "Пёстрый", "Смелый", "Ловкий", "Весёлый", "Хитрый",
]

_ADJECTIVES_F: list[str] = [
    "Неопознанная", "Тихая", "Яркая", "Быстрая",
    "Смелая", "Ловкая", "Весёлая", "Хитрая",
]


def generate_guest_nickname() -> str:
    """Generate a random "Adjective Animal" nickname for guest accounts, e.g. "Неопознанная Капибара"."""
    animal, gender = secrets.choice(_ANIMALS)
    adjectives = _ADJECTIVES_F if gender == "f" else _ADJECTIVES_M
    adjective = secrets.choice(adjectives)
    return f"{adjective} {animal}"
