"""Anonymous feedback: eligibility, one-response-per-course, no link between student and answers, small-cohort suppression."""
import pytest
from sqlalchemy import text


@pytest.fixture()
def cycle(db):
    row = db.execute(text(
        "SELECT c.feedback_cycle_id, c.questionnaire_id, c.academic_term_id FROM feedback_cycle c LIMIT 1")).first()
    if row is None:
        pytest.skip("no feedback cycle in demo data")
    db.execute(text("UPDATE feedback_cycle SET status='OPEN', start_at = now() - interval '1 day', "
                    "end_at = now() + interval '5 day', key_fingerprint = 'test-key', allow_text_review = true, "
                    "minimum_cohort = 2 WHERE feedback_cycle_id = :c"), {"c": row[0]})
    n = db.execute(text("SELECT count(*) FROM feedback_questionnaire_item WHERE questionnaire_id = :q"), {"q": row[1]}).scalar()
    if n == 0:
        # one rating question so the questionnaire can be answered
        qid = db.execute(text("SELECT feedback_question_id FROM feedback_question LIMIT 1")).scalar()
        db.execute(text("INSERT INTO feedback_questionnaire_item (questionnaire_id, feedback_question_id, display_order, is_required) "
                        "VALUES (:q, :f, 1, true)"), {"q": row[1], "f": qid})
    db.flush()
    return row[0]


def _student_with_course(db):
    return db.execute(text(
        "SELECT u.username, r.course_offering_id FROM student_course_registration r "
        "JOIN student_term_registration t USING (term_registration_id) JOIN student_programme_enrolment e USING (enrolment_id) "
        "JOIN person_account_link l ON l.student_id = e.student_id JOIN user_account u ON u.user_id = l.user_id "
        "WHERE r.registration_status IN ('REGISTERED','APPROVED') ORDER BY r.course_registration_id LIMIT 1")).first()


def test_student_submits_once_and_stays_anonymous(as_user, cycle, db):
    row = _student_with_course(db)
    assert row, "needs a registered student with a login"
    student = as_user(row.username)
    form = student.get(f"/feedback/cycles/{cycle}/form").json()
    assert form["items"]
    answers = []
    for it in form["items"]:
        a = {"questionnaire_item_id": it["questionnaire_item_id"]}
        if it["response_type"] in ("RATING", "SCALE") or it["rating_min"] is not None:
            a["numeric_score"] = str(it["rating_max"] or 5)
        elif it["choices"]:
            a["choice_ids"] = [it["choices"][0]["id"]]
        else:
            a["text_response"] = "Good"
        answers.append(a)
    body = {"course_offering_id": row.course_offering_id, "answers": answers}
    first = student.post(f"/feedback/cycles/{cycle}/respond", json=body)
    assert first.status_code == 201, first.text
    assert first.json()["receipt"]
    again = student.post(f"/feedback/cycles/{cycle}/respond", json=body)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_submitted"
    # the stored response carries no student identity
    cols = {c for (c,) in db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='feedback_response'"))}
    assert not {"student_id", "user_id", "term_registration_id"} & cols or db.execute(text(
        "SELECT count(*) FROM feedback_response WHERE term_registration_id IS NOT NULL AND feedback_cycle_id=:c"), {"c": cycle}).scalar() == 0
    pending = student.get("/feedback/pending").json()["results"]
    assert all(p["course_offering_id"] != row.course_offering_id or p["cycle_id"] != cycle for p in pending)


def test_only_registered_students_can_respond(as_user, cycle, db):
    row = _student_with_course(db)
    other = as_user("teacher")
    r = other.post(f"/feedback/cycles/{cycle}/respond", json={"course_offering_id": row.course_offering_id,
                                                              "answers": [{"questionnaire_item_id": 1, "numeric_score": "3"}]})
    assert r.status_code == 403
    student = as_user(row.username)
    wrong = student.post(f"/feedback/cycles/{cycle}/respond", json={"course_offering_id": 99999999,
                                                                    "answers": [{"questionnaire_item_id": 1, "numeric_score": "3"}]})
    assert wrong.status_code == 403


def test_small_cohorts_are_suppressed(as_user, cycle):
    admin = as_user("demoadmin")
    r = admin.get(f"/feedback/cycles/{cycle}/results")
    assert r.status_code == 200
    body = r.json()
    assert body["suppressed"] is True or body["responses"] >= 2
