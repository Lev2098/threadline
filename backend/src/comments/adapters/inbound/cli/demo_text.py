"""Plausible Ukrainian / Russian comment text for generated data.

Sentences are assembled from small phrase banks, so a million rows read like
real discussions (questions, opinions, replies) instead of word salad, while
staying fully deterministic for a given random seed.
"""

from __future__ import annotations

import random

FIRST_NAMES = [
    "Olena",
    "Taras",
    "Iryna",
    "Andrii",
    "Sofiia",
    "Dmytro",
    "Nadiia",
    "Bohdan",
    "Oksana",
    "Maksym",
    "Yuliia",
    "Serhii",
    "Kateryna",
    "Oleh",
    "Mariia",
    "Roman",
    "Anastasiia",
    "Ihor",
    "Viktoriia",
    "Pavlo",
    "Anna",
    "Artem",
    "Daria",
    "Mykola",
    "Khrystyna",
    "Vlad",
    "Polina",
    "Denys",
    "Alina",
    "Yaroslav",
    "Natalia",
    "Kyrylo",
    "Svitlana",
    "Volodymyr",
    "Liliia",
    "Oleksii",
    "Tetiana",
    "Stepan",
    "Inna",
    "Danylo",
]
DOMAINS = ["example.com", "example.org", "example.net", "mail.example.com"]

TOPICS_UK = {
    "tech": [
        "перехід на Vue 3",
        "кешування в Redis",
        "WebSocket у продакшні",
        "індекси в PostgreSQL",
        "чисту архітектуру",
        "код-рев'ю в команді",
        "тестування під навантаженням",
        "Docker для локальної розробки",
        "черги на RabbitMQ",
        "пошук через Elasticsearch",
        "типізацію в Python",
        "мікросервіси",
    ],
    "life": [
        "ранкові пробіжки",
        "подорож Карпатами",
        "книжку про звички",
        "домашню каву",
        "навчання англійської",
        "роботу віддалено",
        "велосипед у місті",
        "фотографію на телефон",
        "настільні ігри",
        "вихідні без гаджетів",
    ],
}
TOPICS_RU = {
    "tech": [
        "переход на TypeScript",
        "кэширование страниц",
        "очереди задач",
        "мониторинг сервиса",
        "миграции базы",
        "нагрузочное тестирование",
        "ревью архитектуры",
        "CI для монорепозитория",
        "SSR для SEO",
    ],
    "life": ["утренний кофе", "поход в горы", "чтение по вечерам", "спорт после работы", "путешествие поездом"],
}

ROOT_UK = [
    "Хто вже пробував {t}? Поділіться досвідом: що спрацювало, а що ні.",
    "Думаю спробувати {t}, але сумніваюся. З чого порадите почати?",
    "Нарешті спробував {t} — результат кращий, ніж очікував. Розповім деталі в коментарях.",
    "Питання до спільноти про {t}: варто чи ні? Цікаво почути різні думки.",
    "Пів року тому взявся за {t}. Головний висновок: <strong>регулярність важливіша за інтенсивність</strong>.",
    "Чи варто витрачати час на {t}, якщо дедлайни горять? Мені здається, що так.",
    "Зібрав нотатки про {t}. Якщо цікаво — питайте, відповім на все.",
]
ROOT_RU = [
    "Кто-нибудь уже пробовал {t}? Поделитесь опытом, пожалуйста.",
    "Есть сомнения про {t}: стоит ли оно потраченного времени?",
    "Неделю назад попробовал {t} — пока всё нравится, но есть вопросы.",
    "Вопрос к сообществу про {t}: да или нет? Хочется услышать разные мнения.",
]
REPLY_UK = [
    "Повністю погоджуюся. У нас було так само, особливо на старті.",
    "А я б зробив інакше: спершу маленький експеримент, потім рішення.",
    "Дякую, корисно! Збережу собі.",
    "Можете розповісти детальніше про перший тиждень?",
    "Головне — не кидати після перших труднощів. Перевірено.",
    "Ми спробували, але повернулися назад. Не все так однозначно.",
    "Цікаво, а як це виглядає через рік?",
    "Плюсую. Ще б додав: варто одразу записувати результати.",
    "У мене схожий досвід, тільки зайняло вдвічі більше часу.",
    "Гарне питання. Я б почав із <i>найпростішого</i> варіанту.",
    "Підтримую, але з одним застереженням: усе залежить від команди.",
    "Спасибі за розгорнуту відповідь, тепер зрозуміло.",
]
REPLY_RU = [
    "Согласен, у нас было то же самое.",
    "А я бы начал с малого и посмотрел на результат.",
    "Спасибо, очень полезно!",
    "Можно подробнее? Интересно, как вы это измеряли.",
    "Пробовали, но вернулись обратно. Не всё так просто.",
    "Плюсую. И обязательно записывать выводы.",
]


def username(rng: random.Random) -> str:
    name = rng.choice(FIRST_NAMES)
    style = rng.random()
    if style < 0.4:
        return name
    if style < 0.8:
        return f"{name}{rng.randint(1, 99)}"
    return f"{name}{rng.choice('KMSTOPRV')}"


def email(rng: random.Random, name: str) -> str:
    return f"{name.lower()}@{rng.choice(DOMAINS)}"


def root_text(rng: random.Random) -> str:
    if rng.random() < 0.8:
        topics, templates = TOPICS_UK, ROOT_UK
    else:
        topics, templates = TOPICS_RU, ROOT_RU
    topic = rng.choice(topics[rng.choice(list(topics))])
    return rng.choice(templates).format(t=topic)


def reply_text(rng: random.Random) -> str:
    return rng.choice(REPLY_UK if rng.random() < 0.8 else REPLY_RU)
