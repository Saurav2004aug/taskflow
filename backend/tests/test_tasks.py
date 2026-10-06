from datetime import date, timedelta

from base import ApiTestCase


class TestCrud(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.h = self.register()

    def test_create_defaults_and_location(self):
        r = self.client.post("/api/tasks", json={"title": "  Write resume  "}, headers=self.h)
        self.assertEqual(r.status_code, 201)
        t = r.get_json()
        self.assertEqual((t["title"], t["status"], t["priority"], t["description"], t["due_date"]),
                         ("Write resume", "todo", "medium", "", None))
        self.assertEqual(r.headers["Location"], f"/api/tasks/{t['id']}")

    def test_new_tasks_go_to_bottom_of_their_column(self):
        a = self.create(self.h, title="a")
        b = self.create(self.h, title="b")
        c = self.create(self.h, title="c", status="done")
        self.assertLess(a["position"], b["position"])
        self.assertEqual(c["position"], 1.0)  # first card in the 'done' column

    def test_validation(self):
        bad = [{}, {"title": ""}, {"title": "x" * 201}, {"title": "ok", "status": "blocked"},
               {"title": "ok", "priority": "urgent"}, {"title": "ok", "due_date": "31/12/2026"},
               {"title": "ok", "position": "first"}, {"title": "ok", "position": True},
               {"title": "ok", "description": 42}]
        for body in bad:
            with self.subTest(body=body):
                r = self.client.post("/api/tasks", json=body, headers=self.h)
                self.assertEqual(r.status_code, 422)
                self.assertIn("fields", r.get_json())

    def test_patch_is_partial(self):
        t = self.create(self.h, title="Keep", priority="high", description="details")
        r = self.client.patch(f"/api/tasks/{t['id']}", json={"due_date": "2030-05-01"}, headers=self.h)
        body = r.get_json()
        self.assertEqual((body["title"], body["priority"], body["description"], body["due_date"]),
                         ("Keep", "high", "details", "2030-05-01"))
        self.assertGreaterEqual(body["updated_at"], t["updated_at"])

    def test_put_replaces(self):
        t = self.create(self.h, title="Old", priority="high", description="x", due_date="2030-01-01")
        body = self.client.put(f"/api/tasks/{t['id']}", json={"title": "New"}, headers=self.h).get_json()
        self.assertEqual((body["title"], body["priority"], body["description"], body["due_date"]),
                         ("New", "medium", "", None))

    def test_moving_to_another_column_appends_to_its_bottom(self):
        self.create(self.h, title="d1", status="done")
        t = self.create(self.h, title="mover")
        moved = self.client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}, headers=self.h).get_json()
        self.assertEqual((moved["status"], moved["position"]), ("done", 2.0))

    def test_drag_drop_between_two_cards_uses_fractional_position(self):
        a = self.create(self.h, title="a")
        b = self.create(self.h, title="b")
        c = self.create(self.h, title="c")
        mid = (a["position"] + b["position"]) / 2
        self.client.patch(f"/api/tasks/{c['id']}", json={"position": mid}, headers=self.h)
        order = [t["title"] for t in self.client.get("/api/tasks?status=todo", headers=self.h).get_json()["tasks"]]
        self.assertEqual(order, ["a", "c", "b"])

    def test_delete(self):
        t = self.create(self.h)
        self.assertEqual(self.client.delete(f"/api/tasks/{t['id']}", headers=self.h).status_code, 204)
        self.assertEqual(self.client.delete(f"/api/tasks/{t['id']}", headers=self.h).status_code, 404)
        self.assertEqual(self.client.get(f"/api/tasks/{t['id']}", headers=self.h).status_code, 404)

    def test_empty_patch_rejected(self):
        t = self.create(self.h)
        self.assertEqual(self.client.patch(f"/api/tasks/{t['id']}", json={}, headers=self.h).status_code, 400)


class TestIsolation(ApiTestCase):
    """The most important security property: users only ever see their own data."""

    def test_users_cannot_touch_each_others_tasks(self):
        alice = self.register(email="alice@example.com")
        bob = self.register(email="bob@example.com")
        secret = self.create(alice, title="Alice's secret plan")

        for method, kwargs in (("get", {}), ("patch", {"json": {"title": "hacked"}}),
                               ("put", {"json": {"title": "hacked"}}), ("delete", {})):
            with self.subTest(method=method):
                r = getattr(self.client, method)(f"/api/tasks/{secret['id']}", headers=bob, **kwargs)
                self.assertEqual(r.status_code, 404)  # 404, not 403: don't reveal it exists

        self.assertEqual(self.client.get("/api/tasks", headers=bob).get_json()["total"], 0)
        self.assertEqual(self.client.get("/api/tasks/stats", headers=bob).get_json()["total"], 0)
        still = self.client.get(f"/api/tasks/{secret['id']}", headers=alice).get_json()
        self.assertEqual(still["title"], "Alice's secret plan")

    def test_deleting_a_user_deletes_their_tasks(self):
        from app import db
        h = self.register()
        self.create(h)
        with db.get_conn() as conn:
            conn.execute("DELETE FROM users")
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM tasks").fetchone()["n"], 0)


class TestListing(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.h = self.register()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        in_3_days = (date.today() + timedelta(days=3)).isoformat()
        self.create(self.h, title="Buy milk", priority="low", status="done")
        self.create(self.h, title="Fix login bug", priority="high", description="JWT expiry edge case")
        self.create(self.h, title="Write blog post", due_date=yesterday)
        self.create(self.h, title="Plan sprint", priority="high", status="in_progress", due_date=in_3_days)
        self.create(self.h, title="Discount 50% banner")

    def list(self, **params):
        r = self.client.get("/api/tasks", query_string=params, headers=self.h)
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()

    def titles(self, **params):
        return [t["title"] for t in self.list(**params)["tasks"]]

    def test_filters(self):
        self.assertEqual(self.list(status="done")["total"], 1)
        self.assertEqual(self.list(priority="high")["total"], 2)
        self.assertEqual(self.titles(overdue="true"), ["Write blog post"])

    def test_search_title_and_description_case_insensitive(self):
        self.assertEqual(self.titles(q="BLOG"), ["Write blog post"])
        self.assertEqual(self.titles(q="jwt"), ["Fix login bug"])

    def test_search_treats_wildcards_literally(self):
        self.assertEqual(self.titles(q="50%"), ["Discount 50% banner"])
        self.assertEqual(self.titles(q="%"), ["Discount 50% banner"])
        self.assertEqual(self.titles(q="_"), [])

    def test_sorting(self):
        self.assertEqual(set(self.titles(sort="-priority")[:2]), {"Fix login bug", "Plan sprint"})
        self.assertEqual(self.titles(sort="-priority")[-1], "Buy milk")
        self.assertEqual(self.titles(sort="due_date")[:2], ["Write blog post", "Plan sprint"])
        self.assertEqual(self.titles(sort="-due_date")[:2], ["Plan sprint", "Write blog post"])  # NULLs stay last
        names = self.titles(sort="title")
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_pagination(self):
        p1, p2 = self.list(per_page=3, page=1), self.list(per_page=3, page=2)
        self.assertEqual((p1["total"], p1["total_pages"], len(p1["tasks"]), len(p2["tasks"])), (5, 2, 3, 2))
        self.assertEqual(len({t["id"] for t in p1["tasks"] + p2["tasks"]}), 5)

    def test_bad_params(self):
        for params in ({"status": "x"}, {"priority": "x"}, {"sort": "id; DROP TABLE tasks"},
                       {"page": "a"}, {"page": "0"}, {"per_page": "1000"}, {"page": "99999999999999999999"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/tasks", query_string=params, headers=self.h).status_code, 400)

    def test_stats(self):
        s = self.client.get("/api/tasks/stats", headers=self.h).get_json()
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["by_status"], {"todo": 3, "in_progress": 1, "done": 1})
        self.assertEqual((s["high_priority_open"], s["overdue"], s["due_this_week"]), (2, 1, 1))
        self.assertEqual(s["completion_rate"], 0.2)


class TestApiRateLimit(ApiTestCase):
    def test_per_user_limit(self):
        self.app.config["API_RATE_CAPACITY"] = 5
        self.setUp()  # rebuild limiters with the small capacity
        a, b = self.register(email="a@x.com"), self.register(email="b@x.com")
        codes = [self.client.get("/api/tasks", headers=a).status_code for _ in range(7)]
        self.assertEqual(codes, [200] * 5 + [429] * 2)
        self.assertEqual(self.client.get("/api/tasks", headers=b).status_code, 200)  # other users unaffected
        self.app.config["API_RATE_CAPACITY"] = 120
