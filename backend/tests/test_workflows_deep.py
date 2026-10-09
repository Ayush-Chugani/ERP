"""Deep paths of admissions, assessments/results and feedback (every refusal and every branch of the calculations)."""
import datetime as dt
import json

import pytest
from sqlalchemy import text

# ------------------------------------------------------------------------------------------------ admissions


@pytest.fixture()
def pipeline(as_user, db):
    row = db.execute(text(
        "SELECT cs.curriculum_scheme_id, cs.programme_id, cs.effective_from, y.academic_year_id, i.institution_id "
        "FROM curriculum_scheme cs JOIN programme p ON p.programme_id = cs.programme_id AND p.is_active "
        "JOIN academic_year y ON y.status = 'ACTIVE' JOIN department d ON d.department_id = p.department_id "
        "JOIN campus c ON c.campus_id = d.campus_id JOIN institution i ON i.institution_id = c.institution_id WHERE cs.status = 'ACTIVE' LIMIT 1")).first()
    if row is None:
        pytest.skip("no active scheme")
    sem = db.execute(text("SELECT semester_id FROM semester LIMIT 1")).scalar()
    reg = as_user("registrar")
    today = dt.date.today()

    def make(clear=True, select=True):
        applicant = reg.post("/admissions/admission-applicant", json={"first_name": "Pipe", "last_name": "Line", "institution_id": row.institution_id}).json()
        app = reg.post("/admissions/admission-application", json={"admission_applicant_id": applicant["admission_applicant_id"], "programme_id": row.programme_id,
                                                                    "academic_year_id": row.academic_year_id}).json()
        aid = app["application_id"]
        if select:
            for step in ("submit", "start_review", "mark_eligible", "select"):
                assert reg.post(f"/admissions/admission-application/{aid}/actions/{step}").status_code == 200
        if clear and select:
            assert reg.post(f"/admissions/admission-application/{aid}/clearance", json={"reference": "R1"}).status_code == 201
        return aid, applicant["admission_applicant_id"]

    body = {"curriculum_scheme_id": row.curriculum_scheme_id, "admission_semester_id": sem, "admission_date": str(max(row.effective_from, today))}
    return reg, make, body, row


def test_admission_refusals(pipeline, as_user, db):
    reg, make, body, row = pipeline
    aid, _ = make(clear=False, select=True)
    base = f"/admissions/admission-application/{aid}"
    # a student can neither clear nor admit; clearance requires SELECTED
    assert as_user("student").post(f"{base}/clearance", json={"reference": "x"}).status_code in (403, 404)
    draft, _ = make(select=False)
    assert reg.post(f"/admissions/admission-application/{draft}/clearance", json={"reference": "x"}).status_code == 409
    assert reg.post("/admissions/admission-application/99999999/summary").status_code in (404, 405)
    assert reg.get("/admissions/admission-application/99999999/summary").status_code == 404
    summary = reg.get(f"{base}/summary").json()
    assert summary["next_step"] == "record_clearance" and summary["fee_cleared"] is False
    assert reg.get(f"/admissions/admission-application/{draft}/summary").json()["next_step"] is None
    reg.post(f"{base}/clearance", json={"reference": "R2"})
    assert reg.get(f"{base}/summary").json()["next_step"] == "admit"
    # validation of the admit command
    assert reg.post(f"{base}/admit", json={**body, "expected_completion_date": "2000-01-01"}).status_code == 422
    other_scheme = db.execute(text("SELECT curriculum_scheme_id FROM curriculum_scheme WHERE programme_id <> :p LIMIT 1"), {"p": row.programme_id}).scalar()
    if other_scheme:
        assert reg.post(f"{base}/admit", json={**body, "curriculum_scheme_id": other_scheme}).status_code == 422
    assert reg.post(f"{base}/admit", json={**body, "admission_date": "1990-01-01"}).status_code == 409           # scheme not valid then
    assert reg.post(f"{base}/admit", json={**body, "student_id": 99999999}).status_code == 422
    db.execute(text("UPDATE academic_year SET status='PLANNED' WHERE academic_year_id=:y"), {"y": row.academic_year_id})
    db.commit()
    assert reg.post(f"{base}/admit", json=body).status_code == 409                                              # year not active
    db.execute(text("UPDATE academic_year SET status='ACTIVE' WHERE academic_year_id=:y"), {"y": row.academic_year_id})
    db.commit()


def test_admission_links_an_existing_student_and_blocks_conflicts(pipeline, db):
    reg, make, body, row = pipeline
    existing = db.execute(text("SELECT student_id FROM student WHERE institution_id = :i AND student_status = 'APPLICANT' LIMIT 1"), {"i": row.institution_id}).scalar()
    if existing is None:
        existing = db.execute(text("SELECT student_id FROM student WHERE institution_id = :i LIMIT 1"), {"i": row.institution_id}).scalar()
        db.execute(text("UPDATE student SET student_status = 'APPLICANT' WHERE student_id = :s"), {"s": existing})
        db.commit()
    aid, applicant = make()
    ok = reg.post(f"/admissions/admission-application/{aid}/admit", json={**body, "student_id": existing})
    assert ok.status_code in (201, 409)                       # 409 if this student already holds an enrolment for the same year
    if ok.status_code == 201:
        assert db.execute(text("SELECT student_status FROM student WHERE student_id=:s"), {"s": existing}).scalar() == "ACTIVE"
    # an applicant already tied to a different student cannot be linked to another
    aid2, applicant2 = make()
    other = db.execute(text("SELECT student_id FROM student WHERE student_id <> :s LIMIT 1"), {"s": existing}).scalar()
    db.execute(text("UPDATE admission_applicant SET canonical_student_id=:o WHERE admission_applicant_id=:a"), {"o": other, "a": applicant2})
    db.commit()
    assert reg.post(f"/admissions/admission-application/{aid2}/admit", json={**body, "student_id": existing}).status_code == 409
    # an applicant already linked to a student reuses that student record
    again = reg.post(f"/admissions/admission-application/{aid2}/admit", json=body)
    assert again.status_code in (201, 409)


# ------------------------------------------------------------------------------------------ assessments
@pytest.fixture()
def offering(db):
    row = db.execute(text(
        "SELECT e.course_offering_id, e.assessment_event_id, e.assessment_component_id FROM assessment_event e "
        "WHERE e.status = 'CONDUCTED' AND EXISTS (SELECT 1 FROM student_assessment_mark m WHERE m.assessment_event_id = e.assessment_event_id) ORDER BY 1 LIMIT 1")).first()
    if row is None:
        pytest.skip("no conducted assessment")
    return row


@pytest.fixture()
def own_offering(db):
    """An assessment the demo teacher is assigned to (teachers only reach their own papers)."""
    row = db.execute(text(
        "SELECT e.course_offering_id, e.assessment_event_id, e.assessment_component_id FROM assessment_event e "
        "WHERE e.status = 'CONDUCTED' AND EXISTS (SELECT 1 FROM student_assessment_mark m WHERE m.assessment_event_id = e.assessment_event_id) "
        "AND e.course_offering_id IN (SELECT s.course_offering_id FROM course_offering_section s JOIN faculty_course_assignment fa "
        "ON fa.course_offering_section_id = s.course_offering_section_id JOIN person_account_link l ON l.employee_id = fa.employee_id "
        "JOIN user_account u ON u.user_id = l.user_id WHERE u.username = 'teacher') ORDER BY 1 LIMIT 1")).first()
    if row is None:
        pytest.skip("no conducted assessment")
    return row


def regs_of(db, off):
    return [r[0] for r in db.execute(text("SELECT course_registration_id FROM student_course_registration WHERE course_offering_id=:o AND registration_status IN ('REGISTERED','APPROVED','COMPLETED') ORDER BY 1"), {"o": off})]


def test_event_roster_and_marks_branches(as_user, db, own_offering):
    off, event, comp = own_offering
    t = as_user("teacher")
    roster = t.get(f"/assessments/events/{event}/roster").json()
    assert roster["students"] and roster["maximum_marks"] and roster["status"] == "CONDUCTED"
    rs = regs_of(db, off)
    dup = t.put(f"/assessments/events/{event}/marks", json={"marks": [{"course_registration_id": rs[0], "marks_obtained": "1"}, {"course_registration_id": rs[0], "marks_obtained": "2"}]})
    assert dup.status_code == 422
    # insert path: a planned event with no marks becomes CONDUCTED once marks arrive
    planned = db.execute(text("SELECT assessment_event_id FROM assessment_event WHERE course_offering_id=:o AND status='PLANNED' LIMIT 1"), {"o": off}).scalar()
    if planned:
        ok = t.put(f"/assessments/events/{planned}/marks", json={"marks": [{"course_registration_id": rs[0], "marks_obtained": "10"}]})
        assert ok.status_code == 200
        assert db.execute(text("SELECT status FROM assessment_event WHERE assessment_event_id=:e"), {"e": planned}).scalar() == "CONDUCTED"
    db.execute(text("UPDATE assessment_event SET status='PUBLISHED' WHERE assessment_event_id=:e"), {"e": event})
    db.commit()
    closed = t.put(f"/assessments/events/{event}/marks", json={"marks": [{"course_registration_id": rs[0], "marks_obtained": "1"}]})
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "event_closed"


def seed_external(db, off, comp_type="EXTERNAL_EXAM"):
    cid = db.execute(text("INSERT INTO assessment_component (component_code, component_name, component_type, maximum_marks, weightage_percent, is_mandatory, actor_id, course_offering_id, version) "
                          "VALUES ('EXT','External','" + comp_type + "', 100, 100, true, 1, :o, 1) RETURNING assessment_component_id"), {"o": off}).scalar()
    eid = db.execute(text("INSERT INTO assessment_event (assessment_component_id, course_offering_id, policy_id, attempt_number, event_title, assessment_date, maximum_marks, details, status, roster, actor_id, version) "
                          "SELECT :c, :o, (SELECT id FROM assessment_policy WHERE course_offering_id=:o LIMIT 1), 1, 'End exam', CURRENT_DATE, 100, '', 'CONDUCTED', '[]'::jsonb, 1, 1 RETURNING assessment_event_id"), {"c": cid, "o": off}).scalar()
    return cid, eid


def put_mark(db, event, reg, status="PRESENT", marks=None):
    db.execute(text("INSERT INTO student_assessment_mark (assessment_event_id, course_registration_id, course_offering_id, attendance_status, marks_obtained, remarks, actor_id, evaluated_at, version, updated_at) "
                    "SELECT :e, :r, course_offering_id, :s, :m, '', 1, now(), 1, now() FROM assessment_event WHERE assessment_event_id=:e"), {"e": event, "r": reg, "s": status, "m": marks})


def test_result_calculation_every_branch(as_user, db, offering):
    off, event, comp = offering
    rs = regs_of(db, off)
    assert len(rs) >= 5
    ex = as_user("examcell")
    assert as_user("registrar").post(f"/assessments/offerings/{off}/calculate-results").status_code == 403
    assert as_user("student").post(f"/assessments/offerings/{off}/calculate-results").status_code in (403, 404)
    cid, ext = seed_external(db, off)
    put_mark(db, ext, rs[0], "PRESENT", 90)            # internal + external
    put_mark(db, ext, rs[1], "ABSENT")                  # absent -> zero
    put_mark(db, ext, rs[2], "EXEMPTED")                # excluded event
    put_mark(db, ext, rs[3], "MALPRACTICE")             # withheld
    # rs[4] has no external mark at all -> incomplete
    db.commit()
    r = ex.post(f"/assessments/offerings/{off}/calculate-results")
    assert r.status_code == 200 and r.json()["calculated"] >= 5
    res = {x["course_registration_id"]: x for x in ex.get("/assessments/student-course-result?page_size=100").json()["results"]}
    assert res[rs[3]]["result_status"] == "WITHHELD" and res[rs[3]]["state"] == "WITHHELD"
    assert res[rs[0]]["external_marks"] is not None and res[rs[0]]["internal_marks"] is not None
    assert res[rs[4]]["result_status"] == "INCOMPLETE"
    assert res[rs[1]]["result_status"] in ("FAIL", "PASS")
    # only external marks (internal component removed) and no marks at all
    db.execute(text("DELETE FROM student_assessment_mark WHERE assessment_event_id IN (SELECT assessment_event_id FROM assessment_event WHERE assessment_component_id=:c)"), {"c": comp})
    db.execute(text("UPDATE assessment_event SET status='CANCELLED' WHERE assessment_component_id=:c"), {"c": comp})
    db.commit()
    assert ex.post(f"/assessments/offerings/{off}/calculate-results").status_code == 200
    res = {x["course_registration_id"]: x for x in ex.get("/assessments/student-course-result?page_size=100").json()["results"]}
    assert res[rs[0]]["total_marks"] is not None
    db.execute(text("UPDATE assessment_event SET status='CANCELLED' WHERE course_offering_id=:o"), {"o": off})
    db.commit()
    assert ex.post(f"/assessments/offerings/{off}/calculate-results").status_code == 200
    again = {x["course_registration_id"]: x for x in ex.get("/assessments/student-course-result?page_size=100").json()["results"]}
    assert again[rs[0]]["result_status"] == "INCOMPLETE"
    db.execute(text("DELETE FROM student_course_result WHERE course_registration_id IN (SELECT course_registration_id FROM student_course_registration WHERE course_offering_id=:o)"), {"o": off})
    db.execute(text("DELETE FROM student_assessment_mark WHERE course_offering_id=:o"), {"o": off})
    db.execute(text("DELETE FROM assessment_event WHERE course_offering_id=:o"), {"o": off})
    db.execute(text("DELETE FROM assessment_policy WHERE course_offering_id=:o"), {"o": off})
    db.commit()
    gone = ex.post(f"/assessments/offerings/{off}/calculate-results")
    assert gone.status_code == 409 and gone.json()["error"]["code"] == "no_policy"


def test_term_result_statuses_publication_and_transcript(as_user, db, offering):
    off, event, comp = offering
    ex = as_user("examcell")
    ex.post(f"/assessments/offerings/{off}/calculate-results")
    tid = db.execute(text("SELECT term_registration_id FROM student_course_registration WHERE course_offering_id=:o LIMIT 1"), {"o": off}).scalar()
    assert as_user("registrar").post(f"/assessments/term-registrations/{tid}/calculate-term-result").status_code == 403
    empty = db.execute(text("SELECT term_registration_id FROM student_term_registration t WHERE NOT EXISTS (SELECT 1 FROM student_course_registration r WHERE r.term_registration_id = t.term_registration_id) LIMIT 1")).scalar()
    if empty:
        assert ex.post(f"/assessments/term-registrations/{empty}/calculate-term-result").status_code == 409
    db.execute(text("DELETE FROM student_course_result x USING student_course_registration r WHERE x.course_registration_id = r.course_registration_id "
                    "AND r.term_registration_id = :t AND x.student_course_result_id = (SELECT min(student_course_result_id) FROM student_course_result y "
                    "JOIN student_course_registration z USING (course_registration_id) WHERE z.term_registration_id = :t)"), {"t": tid})
    db.commit()
    incomplete = ex.post(f"/assessments/term-registrations/{tid}/calculate-term-result").json()
    assert incomplete["result_status"] == "INCOMPLETE"
    db.execute(text("INSERT INTO student_course_result (course_registration_id, attempt_number, grade_letter, credits_earned, result_status, state, evidence, remarks, actor_id, policy_id, version, updated_at) "
                    "SELECT r.course_registration_id, 1, 'A', 0, 'PASS', 'CALCULATED', '{}'::jsonb, '', 1, (SELECT id FROM assessment_policy LIMIT 1), 1, now() "
                    "FROM student_course_registration r WHERE r.term_registration_id = :t AND NOT EXISTS (SELECT 1 FROM student_course_result x WHERE x.course_registration_id = r.course_registration_id)"), {"t": tid})
    db.commit()
    for status, expected in (("FAIL", "FAIL"), ("WITHHELD", "WITHHELD"), ("PASS", "PASS")):
        db.execute(text("UPDATE student_course_result SET result_status=CAST(:s AS varchar), grade_point=CASE WHEN CAST(:s AS varchar)='PASS' THEN 8 ELSE 0 END WHERE course_registration_id IN "
                        "(SELECT course_registration_id FROM student_course_registration WHERE term_registration_id=:t)"), {"s": status, "t": tid})
        db.commit()
        body = ex.post(f"/assessments/term-registrations/{tid}/calculate-term-result").json()
        assert body["result_status"] == expected, body
        if status == "PASS":
            assert body["sgpa"] is not None and body["cgpa"] is not None
    # recalculation updates the same row; published results are protected
    first = ex.post(f"/assessments/term-registrations/{tid}/calculate-term-result")
    assert first.status_code == 200
    term_result = ex.get(f"/assessments/student-term-result?term_registration_id={tid}").json()["results"][0]
    assert ex.post(f"/assessments/student-term-result/{term_result['student_term_result_id']}/actions/publish").status_code == 200
    blocked = ex.post(f"/assessments/term-registrations/{tid}/calculate-term-result")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "published"
    # transcript lists published course results
    for x in ex.get("/assessments/student-course-result?page_size=100").json()["results"]:
        ex.post(f"/assessments/student-course-result/{x['student_course_result_id']}/actions/publish")
    sid = db.execute(text("SELECT e.student_id FROM student_term_registration t JOIN student_programme_enrolment e USING (enrolment_id) WHERE t.term_registration_id=:t"), {"t": tid}).scalar()
    tr = ex.get(f"/assessments/transcript/{sid}").json()
    assert tr["terms"] and tr["terms"][0]["courses"] and {"course_code", "grade_letter", "credits"} <= set(tr["terms"][0]["courses"][0])


# --------------------------------------------------------------------------------------------- feedback
@pytest.fixture()
def open_cycle(db):
    row = db.execute(text("SELECT feedback_cycle_id, questionnaire_id FROM feedback_cycle LIMIT 1")).first()
    if row is None:
        pytest.skip("no cycle")
    db.execute(text("UPDATE feedback_cycle SET status='OPEN', start_at=now()-interval '1 day', end_at=now()+interval '3 day', key_fingerprint='k', "
                    "allow_text_review=false, minimum_cohort=2 WHERE feedback_cycle_id=:c"), {"c": row[0]})
    db.execute(text("DELETE FROM feedback_questionnaire_item WHERE questionnaire_id=:q"), {"q": row[1]})
    rating = db.execute(text("INSERT INTO feedback_question (question_text, response_type, is_active, rating_min, rating_max, rating_step, actor_id, feedback_category_id, version) "
                             "SELECT 'Rate the course', 'RATING', true, 1, 5, 1, 1, feedback_category_id, 1 FROM feedback_question_category LIMIT 1 RETURNING feedback_question_id")).scalar()
    choice_q = db.execute(text("INSERT INTO feedback_question (question_text, response_type, is_active, actor_id, feedback_category_id, version) "
                               "SELECT 'Pick one', 'SINGLE_CHOICE', true, 1, feedback_category_id, 1 FROM feedback_question_category LIMIT 1 RETURNING feedback_question_id")).scalar()
    db.execute(text("INSERT INTO feedback_choice (choice_text, score, display_order, is_active, actor_id, feedback_question_id, version) VALUES ('Yes', 1, 1, true, 1, :q, 1)"), {"q": choice_q})
    text_q = db.execute(text("INSERT INTO feedback_question (question_text, response_type, is_active, text_limit, actor_id, feedback_category_id, version) "
                             "SELECT 'Comments', 'TEXT', true, 20, 1, feedback_category_id, 1 FROM feedback_question_category LIMIT 1 RETURNING feedback_question_id")).scalar()
    ids = {}
    for order, (name, q, req) in enumerate((("rating", rating, True), ("choice", choice_q, False), ("text", text_q, False)), start=1):
        ids[name] = db.execute(text("INSERT INTO feedback_questionnaire_item (questionnaire_id, feedback_question_id, display_order, is_required) VALUES (:z, :q, :n, :r) RETURNING questionnaire_item_id"),
                               {"z": row[1], "q": q, "n": order, "r": req}).scalar()
    choice_id = db.execute(text("SELECT feedback_choice_id FROM feedback_choice WHERE feedback_question_id=:q"), {"q": choice_q}).scalar()
    db.commit()
    return row[0], ids, choice_id


def student_of_course(db):
    return db.execute(text(
        "SELECT u.username, r.course_offering_id FROM student_course_registration r JOIN student_term_registration t USING (term_registration_id) "
        "JOIN student_programme_enrolment e USING (enrolment_id) JOIN person_account_link l ON l.student_id = e.student_id JOIN user_account u ON u.user_id = l.user_id "
        "WHERE r.registration_status IN ('REGISTERED','APPROVED') ORDER BY r.course_registration_id LIMIT 1")).first()


def test_feedback_validation_branches(as_user, db, open_cycle):
    cycle, ids, choice = open_cycle
    row = student_of_course(db)
    s = as_user(row.username)
    url = f"/feedback/cycles/{cycle}/respond"
    base = {"course_offering_id": row.course_offering_id}
    ok_answer = {"questionnaire_item_id": ids["rating"], "numeric_score": "4"}
    assert as_user("registrar").get("/feedback/pending").json() == {"results": []}
    assert s.post(url, json={**base, "answers": [{"questionnaire_item_id": ids["choice"], "choice_ids": [choice]}]}).status_code == 422       # required missing
    assert s.post(url, json={**base, "answers": [ok_answer, ok_answer]}).status_code == 422                                                       # duplicate item
    assert s.post(url, json={**base, "answers": [{"questionnaire_item_id": 99999999, "numeric_score": "1"}]}).status_code == 422                  # foreign item
    assert s.post(url, json={**base, "answers": [{"questionnaire_item_id": ids["rating"], "numeric_score": "9"}]}).status_code == 422             # out of range
    assert s.post(url, json={**base, "answers": [ok_answer, {"questionnaire_item_id": ids["text"], "text_response": "nice"}]}).status_code == 422   # text off
    db.execute(text("UPDATE feedback_cycle SET allow_text_review=true WHERE feedback_cycle_id=:c"), {"c": cycle})
    db.commit()
    assert s.post(url, json={**base, "answers": [ok_answer, {"questionnaire_item_id": ids["text"], "text_response": "x" * 50}]}).status_code == 422   # too long
    full = s.post(url, json={**base, "answers": [ok_answer, {"questionnaire_item_id": ids["choice"], "choice_ids": [choice]},
                                                   {"questionnaire_item_id": ids["text"], "text_response": "short"}]})
    assert full.status_code == 201 and full.json()["receipt"]
    db.execute(text("UPDATE feedback_cycle SET end_at = now() - interval '1 hour' WHERE feedback_cycle_id=:c"), {"c": cycle})
    db.commit()
    late = s.post(url, json={**base, "answers": [ok_answer]})
    assert late.status_code == 409 and late.json()["error"]["code"] == "cycle_closed"
    assert s.post("/feedback/cycles/99999999/respond", json={**base, "answers": [ok_answer]}).status_code == 404
    db.execute(text("UPDATE feedback_cycle SET status='CLOSED' WHERE feedback_cycle_id=:c"), {"c": cycle})
    db.commit()
    assert s.get(f"/feedback/cycles/{cycle}/form").status_code == 404


def test_feedback_results_and_visibility(as_user, db, open_cycle):
    cycle, ids, choice = open_cycle
    admin = as_user("demoadmin")
    for i in range(3):
        rid = db.execute(text("INSERT INTO feedback_response (feedback_cycle_id, target_key, response_token, submitted_at) VALUES (:c, 'k', :t, now()) RETURNING feedback_response_id"), {"c": cycle, "t": f"t{i}"}).scalar()
        db.execute(text("INSERT INTO feedback_response_item (feedback_response_id, questionnaire_item_id, numeric_score) VALUES (:r, :i, :s)"), {"r": rid, "i": ids["rating"], "s": 3 + i % 2})
    db.commit()
    body = admin.get(f"/feedback/cycles/{cycle}/results").json()
    assert body["suppressed"] is False and body["responses"] == 3 and body["items"][0]["mean"] is not None
    db.execute(text("UPDATE feedback_cycle SET result_visibility='HIDDEN' WHERE feedback_cycle_id=:c"), {"c": cycle})
    db.commit()
    assert as_user("registrar").get(f"/feedback/cycles/{cycle}/results").status_code == 403
    assert admin.get(f"/feedback/cycles/{cycle}/results").status_code == 200       # super administrators always may


def test_opening_a_cycle_fixes_its_key(as_user, db):
    cycle = db.execute(text("SELECT feedback_cycle_id FROM feedback_cycle LIMIT 1")).scalar()
    db.execute(text("UPDATE feedback_cycle SET status='SCHEDULED', key_fingerprint='' WHERE feedback_cycle_id=:c"), {"c": cycle})
    db.commit()
    r = as_user("demoadmin").post(f"/feedback/feedback-cycle/{cycle}/actions/open")
    assert r.status_code == 200
    assert db.execute(text("SELECT length(key_fingerprint) FROM feedback_cycle WHERE feedback_cycle_id=:c"), {"c": cycle}).scalar() >= 20
    assert json.dumps(r.json())


def test_non_students_cannot_see_pending_feedback_form_data(as_user):
    assert as_user("teacher").get("/feedback/pending").json() == {"results": []}
