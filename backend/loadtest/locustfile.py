"""Load profile: realistic mix of student / teacher / admin reads. Run: make loadtest (see docs/TESTING.md)."""
import os
import random

from locust import HttpUser, between, task

PASSWORD = os.environ.get("SIMS_LOAD_PASSWORD", "")


class Persona(HttpUser):
    wait_time = between(0.5, 2)
    abstract = True
    username = ""

    def on_start(self):
        self.client.get("/api/v1/auth/csrf")
        csrf = self.client.cookies.get("sims_csrf", "")
        r = self.client.post("/api/v1/auth/login", json={"username": self.username, "password": PASSWORD},
                             headers={"X-CSRF-Token": csrf}, name="/auth/login")
        self.client.headers["Authorization"] = "Bearer " + r.json()["access"]

    @task(5)
    def dashboard(self):
        self.client.get("/api/v1/dashboard", name="/dashboard")

    @task(3)
    def notifications(self):
        self.client.get("/api/v1/notifications", name="/notifications")

    @task(1)
    def me(self):
        self.client.get("/api/v1/auth/me", name="/auth/me")


class Student(Persona):
    username = os.environ.get("SIMS_LOAD_STUDENT", "student")

    @task(4)
    def timetable(self):
        self.client.get("/api/v1/timetable/mine", name="/timetable/mine")

    @task(3)
    def own_records(self):
        self.client.get("/api/v1/people/student", name="/people/student")


class Admin(Persona):
    username = os.environ.get("SIMS_LOAD_ADMIN", "demoadmin")
    weight = 1

    @task(4)
    def browse(self):
        path = random.choice(["people/employee", "people/student", "curriculum/course-catalog", "organization/department"])
        self.client.get(f"/api/v1/{path}?page_size=20", name="/<resource> list")

    @task(1)
    def audit(self):
        self.client.get("/api/v1/security/audit", name="/audit")
