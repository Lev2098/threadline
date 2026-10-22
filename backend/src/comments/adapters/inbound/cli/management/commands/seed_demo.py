"""Demo data for a presentation or video: curated threads on top of an
optional bulk of generated history.

    python manage.py seed_demo --reset --bulk 1000000

``--reset`` wipes ALL comments, uploaded attachments, the search index and the
cache (incl. pending captchas and live WebSocket groups). Local/demo use only.

Curated threads are written through the same domain rules as real posts
(markup validation, sanitizing, image downscaling), with timestamps in the last
hours so they sit on top of the default newest-first table.
"""

from __future__ import annotations

import io
import math
import random
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFilter

from comments.adapters.outbound.media.images import PillowImageProcessor
from comments.adapters.outbound.media.storage import DjangoFileStorage
from comments.adapters.outbound.persistence.models import AttachmentRecord, CommentRecord
from comments.adapters.outbound.sanitizer import Nh3Sanitizer
from comments.adapters.outbound.search.elastic import ElasticsearchSearchIndex
from comments.bootstrap import container
from comments.domain.attachment import IMAGE_MAX_HEIGHT, IMAGE_MAX_WIDTH
from comments.domain.comment import child_path
from comments.domain.markup import CommentText
from comments.domain.values import Email, HomePage, UserName

# --------------------------------------------------------------------------- content


@dataclass
class Post:
    user: str
    text: str
    home: str | None = None
    image: str | None = None  # key of IMAGES
    text_file: tuple[str, str] | None = None  # (file name, content)
    replies: list[Post] = field(default_factory=list)


THREADS: list[Post] = [
    Post(
        "Taras",
        'Запустили <strong>Threadline</strong> — коментарі, де відповіді ростуть гілками на будь-яку глибину, а нові повідомлення з’являються наживо.\n\nПишіть, що думаєте, і тисніть «Відповісти» на будь-якому коментарі. Код і документація — <a href="https://example.com/threadline" title="Документація">тут</a>.',
        home="https://example.com/taras",
        replies=[
            Post(
                "Olena",
                "Виглядає дуже охайно! Нитки між відповідями — супер ідея, одразу видно, хто кому відповідає.",
                replies=[
                    Post("Taras", "Дякую! Найбільше часу пішло саме на них — щоб і на телефоні читалося."),
                    Post("Maksym", "Підтверджую, на телефоні все зручно. Навіть глибокі гілки."),
                ],
            ),
            Post(
                "Andrii",
                "А під навантаженням як? Скільки витримає?",
                replies=[
                    Post(
                        "Taras",
                        "Тестували на <strong>1 000 000</strong> коментарів: p95 — 16 мс на ~180 запитів/с, а в стрес-тесті 580 запитів/с без жодної помилки.",
                        replies=[Post("Andrii", "Серйозно. Дякую за цифри!")],
                    )
                ],
            ),
        ],
    ),
    Post(
        "Olena",
        "Карпати сьогодні о шостій ранку. Знято на телефон, без фільтрів. Натисніть на фото — відкриється більше.",
        image="mountains",
        replies=[
            Post(
                "Iryna",
                "Неймовірні кольори! Це Говерла?",
                replies=[
                    Post(
                        "Olena",
                        "Ні, Петрос — вид з Заросляка. Говерла правіше, в кадр не влізла.",
                        replies=[Post("Iryna", "Додаю в список на літо!")],
                    )
                ],
            ),
            Post("Bohdan", "Заздрю білою заздрістю. Скільки йти до такої точки?"),
        ],
    ),
    Post(
        "Dmytro",
        "Як ви робите пагінацію на мільйоні рядків? У нас <code>OFFSET 300000</code> вже думає по пів секунди.",
        replies=[
            Post(
                "Kateryna",
                "Два варіанти: keyset-пагінація (<code>WHERE id &lt; :last</code>) або deferred join — спершу вибираєте лише id з вузького індексу, потім рядки за id.",
                replies=[
                    Post(
                        "Dmytro",
                        "Спробував deferred join з частковим індексом — ось результат, різниця вражає.",
                        image="chart",
                    )
                ],
            ),
            Post(
                "Serhii",
                "І не забудьте про <i>index-only scan</i>: для індексу по <code>lower(username)</code> додайте <code>INCLUDE (username)</code>.",
            ),
        ],
    ),
    Post(
        "Anna",
        "Как вы тестируете WebSocket под нагрузкой? Интересует, сколько соединений держит один процесс.",
        replies=[
            Post(
                "Roman",
                "Мы гоняли 5000 соединений на один процесс uvicorn: доставка без потерь, задержка растёт примерно линейно. Дальше просто добавляем реплики.",
            ),
            Post(
                "Polina", "Плюс обязательно проверьте массовое переподключение после рестарта — это самое интересное."
            ),
        ],
    ),
    Post(
        "Iryna",
        "Ділюся нашим чеклістом перед релізом — може, комусь знадобиться. Файл нижче.",
        text_file=(
            "release-checklist.txt",
            "Чекліст перед релізом\n\n"
            "1. Усі тести зелені: unit, integration, e2e.\n"
            "2. Міграції перевірені на копії продакшн-бази.\n"
            "3. Є план відкату (і він перевірений).\n"
            "4. Метрики й алерти на нові ендпоінти.\n"
            "5. Feature flag для ризикових змін.\n"
            "6. Changelog і повідомлення для підтримки.\n"
            "7. Реліз не в п’ятницю ввечері :)\n",
        ),
        replies=[Post("Oleh", "Пункт 7 — найважливіший. Дякую!")],
    ),
    Post(
        "Maksym",
        "Зробив маленьку анімацію завантаження для свого проєкту. GIF зберігає анімацію навіть після зменшення.",
        image="loader",
        replies=[Post("Sofiia", "Гіпнотизує :) Можна поділитися кодом?")],
    ),
    Post(
        "Viktoriia",
        "Вічне питання: табуляція чи пробіли?",
        replies=[
            Post(
                "Pavlo",
                "Пробіли. Код виглядає однаково всюди.",
                replies=[
                    Post(
                        "Viktoriia",
                        "Але табуляція дає кожному обрати ширину відступу!",
                        replies=[
                            Post(
                                "Pavlo",
                                "А потім вирівнювання в рядках з’їжджає в половини команди.",
                                replies=[
                                    Post(
                                        "Artem",
                                        "Давайте просто погодимося на автоформатер і закриємо тему.",
                                        replies=[
                                            Post(
                                                "Viktoriia",
                                                "Тобто… пробіли? 😄",
                                                replies=[
                                                    Post(
                                                        "Artem",
                                                        "Тобто те, що вирішить <code>ruff format</code>.",
                                                        replies=[Post("Pavlo", "Найкраща відповідь у цій гілці.")],
                                                    )
                                                ],
                                            )
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    ),
    Post(
        "Kateryna",
        "Порадьте книжку на вихідні — щось не про роботу.",
        replies=[
            Post("Natalia", "<i>«Тигролови»</i> Багряного. Перечитую раз на кілька років."),
            Post("Yaroslav", "<i>«Сто років самотності»</i> — якщо ще не читали."),
            Post("Liliia", "Будь-що з Террі Пратчетта. Гарантовано підніме настрій."),
        ],
    ),
    Post(
        "Roman",
        "Утренний кофе: френч-пресс или эспрессо? Я пока за френч-пресс — проще и вкуснее.",
        replies=[Post("Daria", "Аэропресс! Компромисс между ними.")],
    ),
    Post(
        "Andrii",
        "Шпалери для робочого столу, які згенерував кодом на Python. Хвилі на 20 рядків Pillow.",
        image="waves",
        home="https://example.com/andrii",
        replies=[],
    ),
    Post(
        "Sofiia",
        "Перший коментар у новій гілці — хто наступний?",
        replies=[],
    ),
    Post(
        "Oksana",
        "Кілька думок після року віддаленої роботи.\n\nПерше: окреме місце для роботи важливіше за дорогий стілець.\n\nДруге: зустрічі без порядку денного — найбільший поглинач часу.\n\nТретє: <strong>писати</strong> зрозуміло — це суперсила.",
        replies=[
            Post("Denys", "Третє — на всі сто. Гарний текст економить три зустрічі."),
            Post(
                "Alina",
                "А як боретеся з відчуттям ізоляції?",
                replies=[Post("Oksana", "Коворкінг двічі на тиждень і спільні обіди з командою.")],
            ),
        ],
    ),
]


# --------------------------------------------------------------------------- images


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        k = y / (h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bottom, strict=True)))
    return img


def _mountains() -> bytes:
    w, h = 1600, 1000
    img = _gradient((w, h), (255, 170, 120), (110, 74, 200))
    draw = ImageDraw.Draw(img)
    draw.ellipse((1050, 210, 1250, 410), fill=(255, 230, 170))
    rng = random.Random(7)  # noqa: S311 - art, not crypto
    layers = [((92, 60, 150), 560), ((70, 45, 120), 650), ((48, 32, 92), 760), ((30, 22, 64), 860)]
    for colour, base in layers:
        points = [(0, h)]
        x = 0
        while x <= w:
            points.append((x, base - rng.randint(0, 180)))
            x += rng.randint(90, 180)
        points += [(w, base - 60), (w, h)]
        draw.polygon(points, fill=colour)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def _waves() -> bytes:
    w, h = 1920, 1080
    img = _gradient((w, h), (20, 18, 52), (60, 30, 120))
    draw = ImageDraw.Draw(img)
    for i in range(14):
        colour = (110 + i * 8, 80 + i * 6, 255 - i * 6)
        pts = [(x, h * 0.35 + i * 38 + 60 * math.sin(x / 210 + i * 0.5)) for x in range(0, w + 20, 20)]
        draw.line(pts, fill=colour, width=6)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def _chart() -> bytes:
    w, h = 1200, 800
    img = Image.new("RGB", (w, h), (247, 247, 253))
    draw = ImageDraw.Draw(img)
    draw.line([(120, 680), (1120, 680)], fill=(180, 180, 210), width=3)
    bars = [("OFFSET", 1700, (232, 70, 124)), ("deferred join", 94, (109, 74, 255)), ("index-only", 45, (18, 184, 134))]
    for i, (_, ms, colour) in enumerate(bars):
        left = 220 + i * 300
        height = max(12, int(560 * ms / 1700))
        draw.rounded_rectangle((left, 680 - height, left + 180, 680), radius=18, fill=colour)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def _loader() -> bytes:
    frames = []
    for f in range(18):
        frame = Image.new("RGB", (480, 360), (241, 242, 251))
        draw = ImageDraw.Draw(frame)
        for i in range(10):
            angle = 2 * math.pi * i / 10
            size = 10 + 14 * ((i + f) % 10) / 9
            cx, cy = 240 + 90 * math.cos(angle), 180 + 90 * math.sin(angle)
            draw.ellipse((cx - size, cy - size, cx + size, cy + size), fill=(109, 74, 255) if i % 2 else (61, 220, 168))
        frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:], duration=60, loop=0)
    return out.getvalue()


IMAGES = {
    "mountains": ("karpaty.jpg", _mountains),
    "waves": ("waves.png", _waves),
    "chart": ("pagination.png", _chart),
    "loader": ("loader.gif", _loader),
}


# --------------------------------------------------------------------------- command


class Command(BaseCommand):
    help = "Curated demo threads on top of optional generated history. --reset wipes all comments first."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset", action="store_true", help="Delete ALL comments, attachments, index and cache first."
        )
        parser.add_argument("--bulk", type=int, default=0, help="Generated older comments to add (e.g. 1000000).")
        parser.add_argument("--yes", action="store_true", help="Don't ask for confirmation of --reset.")

    def handle(self, *args: Any, **opts: Any) -> None:
        if opts["reset"]:
            if not opts["yes"] and input("Delete ALL comments, attachments and search data? [y/N] ").lower() != "y":
                raise CommandError("Aborted.")
            self._reset()
        if opts["bulk"]:
            self.stdout.write(f"Generating {opts['bulk']:,} older comments…")
            call_command("seed_comments", count=opts["bulk"], batch=10_000, until_days_ago=1, stdout=self.stdout)

        self.sanitizer = Nh3Sanitizer()
        self.images = PillowImageProcessor()
        self.storage = DjangoFileStorage()
        now = timezone.now()
        created = 0
        # The first thread is the newest, so it is the first row of the table.
        for index, post in enumerate(reversed(THREADS)):
            root_time = now - timedelta(minutes=(len(THREADS) - index) * 23 + 6)
            created += self._insert(post, None, root_time, iter(range(1, 1000)))
        cache.delete_many(["roots:ver", "roots:count"])
        self.stdout.write(self.style.SUCCESS(f"Created {len(THREADS)} demo threads ({created} comments)."))

        search_index = container().search_index
        if isinstance(search_index, ElasticsearchSearchIndex):
            self.stdout.write("Indexing for search…")
            call_command("search_reindex", stdout=self.stdout)

    # -- helpers ---------------------------------------------------------------

    def _insert(self, post: Post, parent: CommentRecord | None, root_time: datetime, tick: Any) -> int:
        when = root_time if parent is None else root_time + timedelta(seconds=40 * next(tick))
        name = UserName(post.user).value
        text = CommentText.parse(post.text)
        with transaction.atomic():
            record = CommentRecord.objects.create(
                parent=parent,
                username=name,
                email=Email(f"{name.lower()}@example.com").value,
                home_page=HomePage(post.home).value if post.home else "",
                text_source=text.source,
                text_html=self.sanitizer.clean(text.html),
                client_id="demo",
                ip="127.0.0.1",
                user_agent="seed_demo",
                created_at=when,
            )
            root_id = parent.root_id if parent else record.id
            record.root_id = root_id
            record.path = child_path(parent.path if parent else "", record.id)
            CommentRecord.objects.filter(pk=record.pk).update(root_id=root_id, path=record.path)
            if parent:
                CommentRecord.objects.filter(pk=root_id).update(replies_count=F("replies_count") + 1)
            self._attach(record, post)
        root_time = root_time if parent else when
        return 1 + sum(self._insert(reply, record, root_time, tick) for reply in post.replies)

    def _attach(self, record: CommentRecord, post: Post) -> None:
        if post.image:
            name, render = IMAGES[post.image]
            processed = self.images.fit(render(), IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT)
            ext = "jpg" if processed.format.value == "jpeg" else processed.format.value
            path = self.storage.save(f"demo-{record.id}.{ext}", processed.content)
            AttachmentRecord.objects.create(
                comment=record,
                kind="image",
                file=path,
                original_name=name,
                size=len(processed.content),
                width=processed.width,
                height=processed.height,
            )
        if post.text_file:
            name, content = post.text_file
            data = content.encode()
            path = self.storage.save(f"demo-{record.id}.txt", data)
            AttachmentRecord.objects.create(comment=record, kind="text", file=path, original_name=name, size=len(data))

    def _reset(self) -> None:
        self.stdout.write("Resetting: comments, attachments, search index, cache…")
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE comment_attachments, comments RESTART IDENTITY CASCADE")
        else:
            AttachmentRecord.objects.all().delete()
            CommentRecord.objects.all().delete()
        shutil.rmtree(Path(settings.MEDIA_ROOT) / "attachments", ignore_errors=True)
        index = container().search_index
        if isinstance(index, ElasticsearchSearchIndex):
            index.reset()
        # Comment ids restart from 1, so every cached thread/page must go.
        cache.clear()
