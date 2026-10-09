"""Anonymous course feedback: a student's answers are stored without any link to the student; a keyed fingerprint in a
separate ledger only prevents the same registration from answering the same target twice."""
import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import active_principal
from app.config import get_settings
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.security import new_token
from app.db.session import get_db
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry
from app.services import audit

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questionnaire_item_id: int
    numeric_score: Decimal | None = None
    text_response: str | None = Field(default=None, max_length=4000)
    choice_ids: list[int] = Field(default_factory=list, max_length=20)


class RespondIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_offering_id: int
    faculty_assignment_id: int | None = None
    answers: list[Answer] = Field(min_length=1, max_length=100)


def _fingerprint(cycle_key: str, cycle_id: int, registration_id: int, faculty_id: int | None) -> str:
    secret = (get_settings().secret_key + cycle_key).encode()
    return hmac.new(secret, f"{cycle_id}|{registration_id}|{faculty_id or 0}".encode(), hashlib.sha256).hexdigest()


def _student_registrations(db: Session, principal: Principal, offering_id: int) -> list[int]:
    if not principal.student_ids:
        return []
    return [r[0] for r in db.execute(text(
        "SELECT r.course_registration_id FROM student_course_registration r "
        "JOIN student_term_registration t ON t.term_registration_id = r.term_registration_id "
        "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
        "WHERE r.course_offering_id = :o AND e.student_id = ANY(:s) AND r.registration_status IN ('REGISTERED','APPROVED','COMPLETED')"),
        {"o": offering_id, "s": list(principal.student_ids)})]


@router.get("/pending")
def pending(principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Open feedback cycles with the courses the signed-in student has not yet reviewed."""
    if not principal.student_ids:
        return {"results": []}
    rows = db.execute(text(
        "SELECT c.feedback_cycle_id, c.cycle_name, c.end_at, c.key_fingerprint, o.course_offering_id, o.offering_code, "
        "cat.course_title, r.course_registration_id FROM feedback_cycle c "
        "JOIN programme_term_offering p ON p.academic_term_id = c.academic_term_id AND (c.programme_id IS NULL OR p.programme_id = c.programme_id) "
        "JOIN student_term_registration t ON t.programme_term_offering_id = p.programme_term_offering_id "
        "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
        "JOIN student_course_registration r ON r.term_registration_id = t.term_registration_id "
        "JOIN course_offering o ON o.course_offering_id = r.course_offering_id "
        "JOIN course_catalog cat ON cat.course_id = o.course_id "
        "WHERE c.status = 'OPEN' AND now() BETWEEN c.start_at AND c.end_at AND e.student_id = ANY(:s) "
        "AND r.registration_status IN ('REGISTERED','APPROVED','COMPLETED') ORDER BY c.end_at, cat.course_title"),
        {"s": list(principal.student_ids)}).all()
    out = []
    for r in rows:
        fp = _fingerprint(r.key_fingerprint, r.feedback_cycle_id, r.course_registration_id, None)
        done = db.execute(text("SELECT 1 FROM feedback_ledger WHERE fingerprint = :f"), {"f": fp}).first()
        if not done:
            out.append({"cycle_id": r.feedback_cycle_id, "cycle_name": r.cycle_name, "closes_at": r.end_at,
                        "course_offering_id": r.course_offering_id, "course": r.course_title, "offering_code": r.offering_code})
    return {"results": out}


@router.get("/cycles/{cycle_id}/form")
def form(cycle_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    cycle = db.execute(text("SELECT feedback_cycle_id, cycle_name, questionnaire_id, status, allow_text_review FROM feedback_cycle "
                            "WHERE feedback_cycle_id = :c"), {"c": cycle_id}).first()
    if cycle is None or cycle.status != "OPEN":
        raise NotFound("This feedback cycle is not open.")
    items = db.execute(text(
        "SELECT i.questionnaire_item_id, i.is_required, q.question_text, q.response_type, q.rating_min, q.rating_max, "
        "q.rating_step, q.text_limit, i.feedback_question_id FROM feedback_questionnaire_item i "
        "JOIN feedback_question q ON q.feedback_question_id = i.feedback_question_id "
        "WHERE i.questionnaire_id = :q AND q.is_active ORDER BY i.display_order"), {"q": cycle.questionnaire_id}).mappings().all()
    out = []
    for it in items:
        choices = db.execute(text("SELECT feedback_choice_id, choice_text FROM feedback_choice WHERE feedback_question_id = :q "
                                  "AND is_active ORDER BY display_order"), {"q": it["feedback_question_id"]}).all()
        out.append({**{k: it[k] for k in it if k != "feedback_question_id"},
                    "choices": [{"id": c[0], "text": c[1]} for c in choices]})
    return {"cycle_id": cycle_id, "cycle_name": cycle.cycle_name, "allow_text": cycle.allow_text_review, "items": out}


@router.post("/cycles/{cycle_id}/respond", status_code=201)
def respond(cycle_id: int, body: RespondIn, request: Request, principal: Principal = Depends(active_principal),
            db: Session = Depends(get_db)):
    if not principal.student_ids:
        raise Forbidden("Only students can submit feedback.")
    cycle = db.execute(text(
        "SELECT feedback_cycle_id, questionnaire_id, status, start_at, end_at, key_fingerprint, allow_text_review "
        "FROM feedback_cycle WHERE feedback_cycle_id = :c FOR SHARE"), {"c": cycle_id}).first()
    if cycle is None:
        raise NotFound()
    now = datetime.now(UTC)
    if cycle.status != "OPEN" or not (cycle.start_at <= now <= cycle.end_at):
        raise Conflict("This feedback cycle is not currently open.", code="cycle_closed")
    regs = _student_registrations(db, principal, body.course_offering_id)
    if not regs:
        raise Forbidden("You are not registered for this course.")
    items = {r[0]: r for r in db.execute(text(
        "SELECT i.questionnaire_item_id, i.is_required, q.response_type, q.rating_min, q.rating_max, q.text_limit, q.feedback_question_id "
        "FROM feedback_questionnaire_item i JOIN feedback_question q ON q.feedback_question_id = i.feedback_question_id "
        "WHERE i.questionnaire_id = :q"), {"q": cycle.questionnaire_id})}
    answered = {a.questionnaire_item_id for a in body.answers}
    if len(answered) != len(body.answers) or not answered <= set(items):
        raise Invalid("Answers must refer to distinct items of this questionnaire.")
    required = {k for k, v in items.items() if v.is_required}
    if not required <= answered:
        raise Invalid("Some required questions were not answered.", details={"missing": sorted(required - answered)})
    for a in body.answers:
        it = items[a.questionnaire_item_id]
        if a.numeric_score is not None and it.rating_min is not None and not (it.rating_min <= a.numeric_score <= it.rating_max):
            raise Invalid("A rating is outside the allowed range.", details={"questionnaire_item_id": [a.questionnaire_item_id]})
        if a.text_response and not cycle.allow_text_review:
            raise Invalid("Free-text comments are not enabled for this cycle.")
        if a.text_response and it.text_limit and len(a.text_response) > it.text_limit:
            raise Invalid("A comment is longer than the limit.")
    registration_id = regs[0]
    fp = _fingerprint(cycle.key_fingerprint, cycle_id, registration_id, body.faculty_assignment_id)
    digest = hashlib.sha256(json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    receipt = new_token(12)
    try:
        with db.begin_nested():
            db.execute(text("INSERT INTO feedback_ledger (cycle_id, fingerprint, request_digest, receipt) "
                            "VALUES (:c, :f, :d, :r)"), {"c": cycle_id, "f": fp, "d": digest, "r": receipt})
    except IntegrityError:
        raise Conflict("You have already submitted feedback for this course.", code="already_submitted") from None
    response_id = db.execute(text(
        "INSERT INTO feedback_response (feedback_cycle_id, course_offering_id, faculty_assignment_id, target_key, "
        "response_token, submitted_at) VALUES (:c, :o, :f, :t, :tok, now()) RETURNING feedback_response_id"),
        {"c": cycle_id, "o": body.course_offering_id, "f": body.faculty_assignment_id,
         "t": f"{body.course_offering_id}:{body.faculty_assignment_id or 0}", "tok": new_token(12)}).scalar_one()
    for a in body.answers:
        item_id = db.execute(text(
            "INSERT INTO feedback_response_item (feedback_response_id, questionnaire_item_id, numeric_score, text_response) "
            "VALUES (:r, :i, :n, :t) RETURNING feedback_response_item_id"),
            {"r": response_id, "i": a.questionnaire_item_id, "n": a.numeric_score, "t": a.text_response}).scalar_one()
        for cid in a.choice_ids:
            db.execute(text("INSERT INTO feedback_response_item_choice (feedback_response_item_id, feedback_choice_id) "
                            "VALUES (:i, :c)"), {"i": item_id, "c": cid})
    # Audit records the act of submitting but deliberately not who answered what.
    audit.record(db, None, action="feedback_submitted", module="FEEDBACK", resource="feedback_cycle", record_id=cycle_id,
                 request_id=request.state.request_id, ip=None)
    db.commit()
    return {"receipt": receipt}


@router.get("/cycles/{cycle_id}/results")
def results(cycle_id: int, course_offering_id: int | None = Query(default=None),
            principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Aggregated ratings per question. Cohorts smaller than the cycle's minimum are suppressed to protect anonymity."""
    spec = build_registry()["feedback_cycle"]
    cycle = crud.get_one(db, spec, principal, cycle_id, "READ")
    if cycle.result_visibility == "HIDDEN" and not principal.is_superuser:
        raise Forbidden("Results for this cycle are hidden.")
    params = {"c": cycle_id, "o": course_offering_id}
    cohort = db.execute(text("SELECT count(*) FROM feedback_response WHERE feedback_cycle_id = :c AND (CAST(:o AS bigint) IS NULL OR course_offering_id = :o)"),
                        params).scalar()
    if cohort < cycle.minimum_cohort:
        return {"cycle_id": cycle_id, "responses": cohort, "suppressed": True, "minimum_cohort": cycle.minimum_cohort, "items": []}
    rows = db.execute(text(
        "SELECT q.question_text, count(ri.numeric_score) AS n, avg(ri.numeric_score) AS mean FROM feedback_response r "
        "JOIN feedback_response_item ri ON ri.feedback_response_id = r.feedback_response_id "
        "JOIN feedback_questionnaire_item i ON i.questionnaire_item_id = ri.questionnaire_item_id "
        "JOIN feedback_question q ON q.feedback_question_id = i.feedback_question_id "
        "WHERE r.feedback_cycle_id = :c AND (CAST(:o AS bigint) IS NULL OR r.course_offering_id = :o) "
        "GROUP BY q.question_text, i.display_order ORDER BY i.display_order"), params).all()
    return {"cycle_id": cycle_id, "responses": cohort, "suppressed": False,
            "items": [{"question": r[0], "answers": r[1], "mean": round(float(r[2]), 2) if r[2] is not None else None}
                      for r in rows]}


def open_cycle_hook(db: Session, principal: Principal, obj) -> None:
    """Opening a cycle fixes the secret used to fingerprint submissions (never changed while the cycle lives)."""
    if not obj.key_fingerprint:
        obj.key_fingerprint = new_token(24)
