"""Assessments and results: marks entry, grade calculation from the offering's policy, term (SGPA/CGPA) results."""
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import active_principal, client_ip
from app.core.errors import Conflict, Forbidden, Invalid
from app.db.session import get_db
from app.rbac.engine import Principal
from app.resources import crud
from app.resources.registry import build_registry
from app.services import audit

router = APIRouter(prefix="/assessments", tags=["Assessments and results"])
D = Decimal
TWO = D("0.01")
ExamStatus = Literal["PRESENT", "ABSENT", "EXEMPTED", "MALPRACTICE"]


class MarkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_registration_id: int
    attendance_status: ExamStatus = "PRESENT"
    marks_obtained: D | None = Field(default=None, ge=0, max_digits=7, decimal_places=2)
    remarks: str = Field(default="", max_length=500)


class MarksIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    marks: list[MarkIn] = Field(min_length=1, max_length=1000)


def q2(x: D) -> D:
    return x.quantize(TWO, rounding=ROUND_HALF_UP)


@router.get("/events/{event_id}/roster")
def event_roster(event_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Students registered for the event's course with any marks already entered (for the marks-entry screen)."""
    event = crud.get_one(db, build_registry()["assessment_event"], principal, event_id, "READ")
    rows = db.execute(text(
        "SELECT r.course_registration_id, st.student_id, st.display_name, st.student_number, m.attendance_status, "
        "m.marks_obtained, m.remarks FROM student_course_registration r "
        "JOIN student_term_registration t ON t.term_registration_id = r.term_registration_id "
        "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id JOIN student st ON st.student_id = e.student_id "
        "LEFT JOIN student_assessment_mark m ON m.course_registration_id = r.course_registration_id AND m.assessment_event_id = :e "
        "WHERE r.course_offering_id = :o AND r.registration_status IN ('REGISTERED','APPROVED','COMPLETED') "
        "ORDER BY st.display_name"), {"e": event_id, "o": event.course_offering_id}).mappings().all()
    return {"assessment_event_id": event_id, "title": event.event_title, "maximum_marks": event.maximum_marks,
            "status": event.status, "students": [dict(r) for r in rows]}


@router.put("/events/{event_id}/marks")
def enter_marks(event_id: int, body: MarksIn, request: Request, principal: Principal = Depends(active_principal),
                db: Session = Depends(get_db)):
    spec = build_registry()["assessment_event"]
    event = crud.get_one(db, spec, principal, event_id, "UPDATE", lock=True)
    if event.status not in ("PLANNED", "CONDUCTED"):
        raise Conflict("Marks can only be entered while the assessment is planned or conducted.", code="event_closed")
    regs = {r[0] for r in db.execute(text(
        "SELECT course_registration_id FROM student_course_registration WHERE course_offering_id = :o "
        "AND registration_status IN ('REGISTERED','APPROVED','COMPLETED')"), {"o": event.course_offering_id})}
    seen: set[int] = set()
    for m in body.marks:
        if m.course_registration_id in seen:
            raise Invalid(f"Registration {m.course_registration_id} appears more than once.")
        seen.add(m.course_registration_id)
        if m.course_registration_id not in regs:
            raise Invalid(f"Registration {m.course_registration_id} does not belong to this course.",
                          details={"course_registration_id": [str(m.course_registration_id)]})
        if m.attendance_status == "PRESENT":
            if m.marks_obtained is None:
                raise Invalid("Marks are required for students who attended.",
                              details={"marks_obtained": [str(m.course_registration_id)]})
            if m.marks_obtained > event.maximum_marks:
                raise Invalid(f"Marks cannot exceed the maximum of {event.maximum_marks}.",
                              details={"marks_obtained": [str(m.course_registration_id)]})
        elif m.marks_obtained not in (None, D(0)):
            raise Invalid("Marks must be empty for absent, exempted or malpractice entries.")
    for m in body.marks:
        existing = db.execute(text("SELECT student_assessment_mark_id FROM student_assessment_mark "
                                   "WHERE assessment_event_id = :e AND course_registration_id = :r FOR UPDATE"),
                              {"e": event_id, "r": m.course_registration_id}).scalar()
        args = {"e": event_id, "r": m.course_registration_id, "o": event.course_offering_id,
                "s": m.attendance_status, "m": m.marks_obtained if m.attendance_status == "PRESENT" else None,
                "rm": m.remarks, "u": principal.user_id}
        if existing:
            db.execute(text("UPDATE student_assessment_mark SET attendance_status=:s, marks_obtained=:m, remarks=:rm, "
                            "actor_id=:u, evaluated_at=now(), version=version+1, updated_at=now() "
                            "WHERE student_assessment_mark_id=:id"), {**args, "id": existing})
        else:
            db.execute(text(
                "INSERT INTO student_assessment_mark (assessment_event_id, course_registration_id, course_offering_id, "
                "attendance_status, marks_obtained, remarks, actor_id, evaluated_at, version, updated_at) "
                "VALUES (:e, :r, :o, :s, :m, :rm, :u, now(), 1, now())"), args)
    if event.status == "PLANNED":
        db.execute(text("UPDATE assessment_event SET status = 'CONDUCTED', version = version + 1 WHERE assessment_event_id = :e"),
                   {"e": event_id})
    audit.record(db, principal, action="enter_marks", module="ASSESSMENT", resource="assessment_event",
                 record_id=event_id, after={"students": len(body.marks)}, request_id=request.state.request_id,
                 ip=client_ip(request))
    db.commit()
    return {"assessment_event_id": event_id, "saved": len(body.marks)}


def _grade(db: Session, scale_id: int, pct: D):
    return db.execute(text(
        "SELECT grade_letter, grade_point, result_status FROM grade_rule WHERE grade_scale_id = :s "
        "AND :p >= minimum_percentage AND :p <= maximum_percentage ORDER BY minimum_percentage DESC LIMIT 1"),
        {"s": scale_id, "p": pct}).first()


def _component_pct(rows: list[tuple[D, D]], best_n: int) -> D:
    """Mean of the best ``best_n`` event percentages for one component."""
    pcts = sorted((m / mx * 100 for m, mx in rows if mx), reverse=True)[:max(best_n, 1)]
    return sum(pcts, D(0)) / len(pcts) if pcts else D(0)


@router.post("/offerings/{offering_id}/calculate-results")
def calculate_results(offering_id: int, request: Request, principal: Principal = Depends(active_principal),
                      db: Session = Depends(get_db)):
    """Compute grades for every registration of a course offering from conducted assessment marks."""
    ospec = build_registry()["course_offering"]
    crud.get_one(db, ospec, principal, offering_id, "READ")
    if not (principal.is_superuser or principal.can("RESULT", "STUDENT_COURSE_RESULT", "CREATE")
            or principal.can("RESULT", "STUDENT_COURSE_RESULT", "UPDATE")):
        raise Forbidden()
    policy = db.execute(text("SELECT id, rules, grade_scale_id FROM assessment_policy WHERE course_offering_id = :o "
                             "ORDER BY number DESC LIMIT 1"), {"o": offering_id}).first()
    if policy is None:
        raise Conflict("No assessment policy is defined for this course offering.", code="no_policy")
    rules = policy.rules
    iw, ew = D(str(rules.get("internal_weight", 100))), D(str(rules.get("external_weight", 0)))
    min_i, min_e = D(str(rules.get("minimum_internal", 0))), D(str(rules.get("minimum_external", 0)))
    best_n = int(rules.get("best_n", 1))
    credit_statuses = set(rules.get("credit_statuses", ["PASS"]))
    credits = db.execute(text(
        "SELECT c.credits FROM course_offering o JOIN course_catalog c ON c.course_id = o.course_id "
        "WHERE o.course_offering_id = :o"), {"o": offering_id}).scalar() or D(0)
    comps = db.execute(text(
        "SELECT assessment_component_id, component_type, COALESCE(weightage_percent, 0) FROM assessment_component "
        "WHERE course_offering_id = :o"), {"o": offering_id}).all()
    kind = {c[0]: ("external" if any(w in c[1].upper() for w in ("EXTERNAL", "END", "SEMESTER", "EXAM")) and
                   "INTERNAL" not in c[1].upper() else "internal") for c in comps}
    weight = {c[0]: D(c[2]) for c in comps}
    regs = [r[0] for r in db.execute(text(
        "SELECT course_registration_id FROM student_course_registration WHERE course_offering_id = :o "
        "AND registration_status IN ('REGISTERED','APPROVED','COMPLETED') ORDER BY 1"), {"o": offering_id})]
    done = skipped = 0
    for reg in regs:
        rows = db.execute(text(
            "SELECT e.assessment_component_id, e.assessment_event_id, e.maximum_marks, m.attendance_status, m.marks_obtained "
            "FROM assessment_event e LEFT JOIN student_assessment_mark m ON m.assessment_event_id = e.assessment_event_id "
            "AND m.course_registration_id = :r WHERE e.course_offering_id = :o AND e.status IN ('CONDUCTED','PUBLISHED')"),
            {"r": reg, "o": offering_id}).all()
        existing = db.execute(text("SELECT student_course_result_id, state FROM student_course_result "
                                   "WHERE course_registration_id = :r AND attempt_number = 1 FOR UPDATE"), {"r": reg}).first()
        if existing and existing.state == "PUBLISHED":
            skipped += 1
            continue
        blocked = any(r.attendance_status == "MALPRACTICE" for r in rows)
        by_comp: dict[int, list[tuple[D, D]]] = {}
        missing = False
        for r in rows:
            if r.attendance_status == "EXEMPTED":
                continue
            if r.attendance_status is None:
                missing = True
                continue
            by_comp.setdefault(r.assessment_component_id, []).append(
                (D(0) if r.attendance_status == "ABSENT" or r.marks_obtained is None else D(r.marks_obtained), D(r.maximum_marks)))
        scores: dict[str, tuple[D, D]] = {}
        for k in ("internal", "external"):
            cids = [c for c in by_comp if kind.get(c) == k]
            if cids:
                total_w = sum(weight[c] for c in cids) or D(len(cids))
                pct = sum(_component_pct(by_comp[c], best_n) * ((weight[c] or D(1)) / total_w) for c in cids)
                scores[k] = (pct, total_w)
        if blocked:
            status, grade, gp, total, internal_m, external_m, pct = "WITHHELD", "", None, None, None, None, D(0)
            state = "WITHHELD"
        elif not scores:
            status, grade, gp, total, internal_m, external_m, pct = "INCOMPLETE", "", None, None, None, None, D(0)
            state = "CALCULATED"
        else:
            state = "CALCULATED"
            internal_pct = scores.get("internal", (D(0), D(0)))[0]
            external_pct = scores.get("external", (D(0), D(0)))[0]
            if "external" in scores and "internal" in scores:
                internal_m, external_m = q2(internal_pct * iw / 100), q2(external_pct * ew / 100)
                pct = q2(internal_m + external_m)
            elif "internal" in scores:
                internal_m, external_m = q2(internal_pct * iw / 100) if iw else None, None
                pct = q2(internal_pct)
            else:
                internal_m, external_m = None, q2(external_pct * ew / 100)
                pct = q2(external_pct)
            total = pct
            rule = _grade(db, policy.grade_scale_id, pct) if policy.grade_scale_id else None
            grade, gp = (rule.grade_letter, rule.grade_point) if rule else (rules.get("failure_grade", "F"), D(0))
            status = rule.result_status if rule else ("PASS" if pct >= 40 else "FAIL")
            if (internal_m is not None and "internal" in scores and iw and internal_m < min_i) or \
                    (external_m is not None and "external" in scores and external_m < min_e):
                status, grade, gp = "FAIL", rules.get("failure_grade", "F"), D(0)
            if missing and status == "PASS":
                status = "INCOMPLETE"
        earned = credits if status in credit_statuses else D(0)
        evidence = {"policy": policy.id, "components": {k: float(v[0]) for k, v in scores.items()}, "percentage": float(pct)}
        args = {"r": reg, "im": internal_m, "em": external_m, "tm": total, "g": grade, "gp": gp, "ce": earned,
                "st": status, "state": state, "ev": json.dumps(evidence), "pol": policy.id,
                "u": principal.user_id, "w": state == "WITHHELD"}
        if existing:
            db.execute(text(
                "UPDATE student_course_result SET internal_marks=:im, external_marks=:em, total_marks=:tm, grade_letter=:g, "
                "grade_point=:gp, credits_earned=:ce, result_status=:st, state=:state, evidence=CAST(:ev AS jsonb), "
                "policy_id=:pol, actor_id=:u, is_withheld=:w, result_date=CURRENT_DATE, version=version+1, updated_at=now() "
                "WHERE student_course_result_id=:id"), {**args, "id": existing.student_course_result_id})
        else:
            db.execute(text(
                "INSERT INTO student_course_result (course_registration_id, attempt_number, internal_marks, external_marks, "
                "total_marks, grade_letter, grade_point, credits_earned, result_status, state, evidence, policy_id, actor_id, "
                "is_withheld, result_date, remarks, version, updated_at) VALUES (:r, 1, :im, :em, :tm, :g, :gp, :ce, :st, "
                ":state, CAST(:ev AS jsonb), :pol, :u, :w, CURRENT_DATE, '', 1, now())"), args)
        done += 1
    audit.record(db, principal, action="calculate_results", module="RESULT", resource="course_offering",
                 record_id=offering_id, after={"calculated": done, "skipped_published": skipped},
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    return {"course_offering_id": offering_id, "calculated": done, "skipped_published": skipped}


@router.post("/term-registrations/{term_registration_id}/calculate-term-result")
def calculate_term_result(term_registration_id: int, request: Request, principal: Principal = Depends(active_principal),
                          db: Session = Depends(get_db)):
    """SGPA for one term registration and the running CGPA of the enrolment (published/calculated course results)."""
    tspec = build_registry()["student_term_registration"]
    term = crud.get_one(db, tspec, principal, term_registration_id, "READ")
    if not (principal.is_superuser or principal.can("RESULT", "STUDENT_TERM_RESULT", "CREATE")
            or principal.can("RESULT", "STUDENT_TERM_RESULT", "UPDATE")):
        raise Forbidden()
    rows = db.execute(text(
        "SELECT r.course_registration_id, c.credits, res.state, res.result_status, res.grade_point, res.credits_earned "
        "FROM student_course_registration r JOIN course_offering o ON o.course_offering_id = r.course_offering_id "
        "JOIN course_catalog c ON c.course_id = o.course_id "
        "LEFT JOIN student_course_result res ON res.course_registration_id = r.course_registration_id AND res.attempt_number = 1 "
        "WHERE r.term_registration_id = :t AND r.registration_status IN ('REGISTERED','APPROVED','COMPLETED')"),
        {"t": term_registration_id}).all()
    if not rows:
        raise Conflict("The term registration has no registered courses.")
    registered = sum((D(r.credits) for r in rows), D(0))
    earned = sum((D(r.credits_earned or 0) for r in rows), D(0))
    graded = [r for r in rows if r.result_status == "PASS" and r.grade_point is not None]
    gp_credits = sum((D(r.credits) for r in graded), D(0))
    sgpa = q2(sum((D(r.grade_point) * D(r.credits) for r in graded), D(0)) / gp_credits) if gp_credits else None
    missing = [r for r in rows if r.result_status is None or r.result_status == "INCOMPLETE"]
    if missing:
        status = "INCOMPLETE"
    elif any(r.result_status in ("FAIL", "ABSENT") for r in rows):
        status = "FAIL"
    elif any(r.result_status == "WITHHELD" for r in rows):
        status = "WITHHELD"
    else:
        status = "PASS"
    cg = db.execute(text(
        "SELECT sum(res.grade_point * c.credits), sum(c.credits) FROM student_course_result res "
        "JOIN student_course_registration r ON r.course_registration_id = res.course_registration_id "
        "JOIN student_term_registration t ON t.term_registration_id = r.term_registration_id "
        "JOIN course_offering o ON o.course_offering_id = r.course_offering_id "
        "JOIN course_catalog c ON c.course_id = o.course_id "
        "WHERE t.enrolment_id = :e AND res.result_status = 'PASS' AND res.grade_point IS NOT NULL"),
        {"e": term.enrolment_id}).first()
    cgpa = q2(D(cg[0]) / D(cg[1])) if cg and cg[1] else None
    existing = db.execute(text("SELECT student_term_result_id, state FROM student_term_result "
                               "WHERE term_registration_id = :t FOR UPDATE"), {"t": term_registration_id}).first()
    if existing and existing.state == "PUBLISHED":
        raise Conflict("The term result has been published. Withhold it before recalculating.", code="published")
    args = {"t": term_registration_id, "cr": registered, "ce": earned, "sg": sgpa, "cg": cgpa, "st": status,
            "u": principal.user_id}
    if existing:
        db.execute(text("UPDATE student_term_result SET credits_registered=:cr, credits_earned=:ce, sgpa=:sg, cgpa=:cg, "
                        "result_status=:st, actor_id=:u, version=version+1, updated_at=now() "
                        "WHERE student_term_result_id=:id"), {**args, "id": existing.student_term_result_id})
    else:
        db.execute(text("INSERT INTO student_term_result (term_registration_id, credits_registered, credits_earned, sgpa, "
                        "cgpa, result_status, state, evidence, actor_id, is_withheld, version, updated_at) VALUES "
                        "(:t, :cr, :ce, :sg, :cg, :st, 'CALCULATED', '{}'::jsonb, :u, false, 1, now())"), args)
    audit.record(db, principal, action="calculate_term_result", module="RESULT", resource="student_term_registration",
                 record_id=term_registration_id, after={"sgpa": sgpa, "cgpa": cgpa, "status": status},
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    return {"term_registration_id": term_registration_id, "credits_registered": registered, "credits_earned": earned,
            "sgpa": sgpa, "cgpa": cgpa, "result_status": status}


@router.get("/transcript/{student_id}")
def transcript(student_id: int, principal: Principal = Depends(active_principal), db: Session = Depends(get_db)):
    """Published course results for a student, grouped by term (students see only their own, only once published)."""
    sspec = build_registry()["student"]
    student = crud.get_one(db, sspec, principal, student_id, "READ")
    rspec = build_registry()["student_course_result"]
    q, _ = crud.scoped(rspec, principal, "READ")
    visible = list(db.scalars(select(rspec.model.__table__.c.student_course_result_id).where(
        rspec.model.__table__.c.student_course_result_id.in_(q.with_only_columns(rspec.col(rspec.pk))))))
    rows = db.execute(text(
        "SELECT t.term_registration_id, ay.year_code, c.course_code, c.course_title, c.credits, x.grade_letter, "
        "x.grade_point, x.result_status, x.total_marks FROM student_course_result x "
        "JOIN student_course_registration r ON r.course_registration_id = x.course_registration_id "
        "JOIN student_term_registration t ON t.term_registration_id = r.term_registration_id "
        "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
        "JOIN course_offering o ON o.course_offering_id = r.course_offering_id "
        "JOIN course_catalog c ON c.course_id = o.course_id "
        "JOIN programme_term_offering p ON p.programme_term_offering_id = t.programme_term_offering_id "
        "JOIN academic_term at ON at.academic_term_id = p.academic_term_id "
        "JOIN academic_year ay ON ay.academic_year_id = at.academic_year_id "
        "WHERE e.student_id = :s AND x.student_course_result_id = ANY(:ids) AND x.state = 'PUBLISHED' "
        "ORDER BY t.term_registration_id, c.course_code"),
        {"s": student.student_id, "ids": visible}).mappings().all()
    terms: dict[int, dict] = {}
    for r in rows:
        terms.setdefault(r["term_registration_id"], {"term_registration_id": r["term_registration_id"],
                                                   "academic_year": r["year_code"], "courses": []})["courses"].append(
            {k: r[k] for k in ("course_code", "course_title", "credits", "grade_letter", "grade_point", "result_status", "total_marks")})
    return {"student_id": student_id, "name": student.display_name, "terms": list(terms.values())}

