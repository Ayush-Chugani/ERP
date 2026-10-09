"""Staff-activity workflow: staff draft and submit their own records, reviewers verify and approve them."""
import pytest

AWARD = {"activity_title": "Best Teacher 2026", "start_date": "2026-01-10", "end_date": "2026-01-10",
         "award_name": "Best Teacher", "award_date": "2026-01-10", "currency_code": "INR"}


@pytest.fixture()
def teacher(as_user):
    return as_user("teacher")


def test_staff_creates_and_submits_own_activity(teacher):
    me = teacher.get("/auth/me").json()
    assert me["employee_ids"], "teacher persona must be linked to an employee"
    r = teacher.post("/awards/staff-award", json=AWARD)
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["workflow_status"] == "DRAFT" and row["employee_id"] == me["employee_ids"][0]
    assert {a["name"] for a in row["actions"]} == {"submit", "withdraw"}
    aid = row["staff_activity_id"]
    # drafts are editable
    assert teacher.patch(f"/awards/staff-award/{aid}", json={"award_name": "Best Teacher (Dept)"}).status_code == 200
    # a staff member cannot approve or verify (reviewer actions)
    assert teacher.post(f"/awards/staff-award/{aid}/actions/approve").status_code in (403, 409)
    r = teacher.post(f"/awards/staff-award/{aid}/actions/submit")
    assert r.status_code == 200 and r.json()["workflow_status"] == "SUBMITTED"
    # submitted records are locked
    assert teacher.patch(f"/awards/staff-award/{aid}", json={"award_name": "Tampered"}).status_code == 409
    assert teacher.delete(f"/awards/staff-award/{aid}").status_code == 409


def test_full_review_chain_and_audit(teacher, as_user, db):
    aid = teacher.post("/awards/staff-award", json=AWARD).json()["staff_activity_id"]
    teacher.post(f"/awards/staff-award/{aid}/actions/submit")
    hod = as_user("hod")
    row = hod.get(f"/awards/staff-award/{aid}").json()
    assert {a["name"] for a in row["actions"]} >= {"review", "verify", "return", "reject"}
    # cannot approve before verification
    assert hod.post(f"/awards/staff-award/{aid}/actions/approve").status_code == 409
    # returning needs remarks
    assert hod.post(f"/awards/staff-award/{aid}/actions/return").status_code == 422
    r = hod.post(f"/awards/staff-award/{aid}/actions/return", json={"remarks": "Attach the certificate"})
    assert r.json()["workflow_status"] == "RETURNED"
    assert teacher.patch(f"/awards/staff-award/{aid}", json={"award_name": "Best Teacher 2026"}).status_code == 200
    teacher.post(f"/awards/staff-award/{aid}/actions/submit")
    assert hod.post(f"/awards/staff-award/{aid}/actions/verify").json()["workflow_status"] == "VERIFIED"
    done = hod.post(f"/awards/staff-award/{aid}/actions/approve", json={"remarks": "Well deserved"}).json()
    assert done["workflow_status"] == "APPROVED" and done["approved_at"] and done["approval_remarks"] == "Well deserved"
    assert done["actions"] == []
    history = [h for (h,) in db.execute(__import__("sqlalchemy").text(
        "SELECT to_status FROM status_history WHERE entity_type='staff_award' AND entity_id=:i ORDER BY status_history_id"),
        {"i": str(aid)})]
    assert history == ["SUBMITTED", "RETURNED", "SUBMITTED", "VERIFIED", "APPROVED"]


def test_cannot_review_own_record(as_user):
    admin = as_user("demoadmin")
    # a reviewer who is also the owner is stopped by the self-review guard
    hod = as_user("hod")
    emp = hod.get("/auth/me").json()["employee_ids"]
    if not emp:
        pytest.skip("hod persona is not linked to an employee")
    aid = hod.post("/awards/staff-award", json=AWARD).json()["staff_activity_id"]
    hod.post(f"/awards/staff-award/{aid}/actions/submit")
    assert hod.post(f"/awards/staff-award/{aid}/actions/verify").status_code == 403
    assert admin.post(f"/awards/staff-award/{aid}/actions/verify").status_code == 200  # a different reviewer can


def test_staff_cannot_spoof_ownership_or_organisation(teacher, as_user):
    reg = as_user("registrar")
    other = next(e for e in reg.get("/people/employee?page_size=100").json()["results"]
                 if e["employee_id"] not in teacher.get("/auth/me").json()["employee_ids"])
    body = {**AWARD, "employee_id": other["employee_id"]}
    assert teacher.post("/awards/staff-award", json=body).status_code == 403
    mine = teacher.post("/awards/staff-award", json={**AWARD, "institution_id": 999, "department_id": 12345})
    assert mine.status_code == 201
    assert mine.json()["institution_id"] != 999


def test_staff_only_see_their_own_records(teacher, as_user):
    teacher.post("/awards/staff-award", json=AWARD)
    mine = {r["employee_id"] for r in teacher.get("/awards/staff-award?page_size=100").json()["results"]}
    assert len(mine) == 1
    everyone = {r["employee_id"] for r in as_user("registrar").get("/awards/staff-award?page_size=100").json()["results"]}
    assert len(everyone) >= len(mine)


def test_withdraw_then_delete(teacher):
    aid = teacher.post("/awards/staff-award", json=AWARD).json()["staff_activity_id"]
    assert teacher.post(f"/awards/staff-award/{aid}/actions/withdraw").json()["workflow_status"] == "WITHDRAWN"
    assert teacher.delete(f"/awards/staff-award/{aid}").status_code == 204
    assert teacher.get(f"/awards/staff-award/{aid}").status_code == 404
