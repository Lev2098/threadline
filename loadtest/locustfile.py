"""Load profile for "1,000,000 comments, 100,000 users per day".

100k daily users x ~20 requests = 2M requests/day = ~23 req/s on average.
Traffic is bursty, so we design for a 10x peak (~250 req/s) and check that
p95 latency stays under 200 ms with a 95/5 read/write mix.

Run (see docs/loadtest.md):
    docker compose -f docker-compose.yml -f docker-compose.loadtest.yml up -d --build
    docker compose -f docker-compose.yml -f docker-compose.loadtest.yml run --rm locust
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, events, tag, task

CAPTCHA_ANSWER = os.environ.get("LOADTEST_CAPTCHA_ANSWER", "loadtest")
ORDERINGS = ["-created_at", "created_at", "username", "-username", "email", "-email"]
WORDS = "architecture hexagon cache queue index replica latency thread reply comment".split()


class Visitor(HttpUser):
    """A reader who sometimes writes; weights mirror a typical comments page."""

    wait_time = between(0.5, 3)

    def on_start(self) -> None:
        token = self.client.post("/api/v1/session", name="POST /session").json()["token"]
        self.client.headers["Authorization"] = f"Bearer {token}"
        self.root_ids: list[int] = []
        self.pages = 1

    def _remember(self, payload: dict) -> None:
        self.pages = max(1, payload.get("pages", 1))
        ids = [c["id"] for c in payload.get("items", [])]
        if ids:
            self.root_ids = ids

    @tag("read")
    @task(40)
    def first_page(self) -> None:
        with self.client.get("/api/v1/comments", name="GET /comments?page=1", catch_response=True) as r:
            if r.ok:
                self._remember(r.json())

    @tag("read")
    @task(15)
    def sorted_page(self) -> None:
        ordering = random.choice(ORDERINGS)
        page = random.randint(1, min(self.pages, 10))
        self.client.get(f"/api/v1/comments?ordering={ordering}&page={page}", name="GET /comments?ordering&page<=10")

    @tag("read")
    @task(5)
    def deep_page(self) -> None:
        # Uncached deep OFFSET in any ordering: exercises the deferred join over
        # the partial (index-only) indexes.
        page = random.randint(1, self.pages)
        ordering = random.choice(ORDERINGS)
        self.client.get(f"/api/v1/comments?ordering={ordering}&page={page}", name="GET /comments?page=deep")

    @tag("read")
    @task(25)
    def open_thread(self) -> None:
        if self.root_ids:
            root = random.choice(self.root_ids)
            self.client.get(f"/api/v1/comments/{root}/thread", name="GET /comments/:id/thread")

    @tag("read")
    @task(5)
    def search(self) -> None:
        self.client.get(f"/api/v1/comments/search?q={random.choice(WORDS)}", name="GET /comments/search")

    @tag("write")
    @task(5)
    def post_comment(self) -> None:
        captcha = self.client.get("/api/v1/captcha", name="GET /captcha").json()
        data = {
            "username": f"Load{random.randint(1, 99_999)}",
            "email": "load@example.com",
            "text": " ".join(random.sample(WORDS, 6)) + " <i>load</i>",
            "captcha_key": captcha["key"],
            "captcha": CAPTCHA_ANSWER,
        }
        if self.root_ids and random.random() < 0.7:
            data["parent_id"] = str(random.choice(self.root_ids))
        self.client.post("/api/v1/comments", data=data, name="POST /comments")


@events.quitting.add_listener
def assert_slo(environment, **_kwargs) -> None:  # noqa: ANN001
    """Fail the run (exit code 1) when the SLO is missed, so CI can gate on it."""
    stats = environment.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    if stats.fail_ratio > 0.01 or p95 > 200:
        print(f"SLO MISSED: fail_ratio={stats.fail_ratio:.2%} p95={p95}ms")
        environment.process_exit_code = 1
    else:
        print(f"SLO OK: fail_ratio={stats.fail_ratio:.2%} p95={p95}ms rps={stats.total_rps:.0f}")
        environment.process_exit_code = 0
