"""Personal identifiers of staff (Aadhaar, PAN, bank account). Values are validated, encrypted at rest with AES-256-GCM
and never returned; only masked forms are shown. Reading or writing needs the specific EMPLOYEE_* permission."""
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import active_principal, client_ip
from app.core import crypto
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.db.session import get_db
from app.models.people_master import Employee
from app.rbac.engine import Principal
from app.rbac.scope import scope_clause
from app.services import audit

router = APIRouter(prefix="/hr/secure", tags=["HR personal identifiers"])

_VERHOEFF_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
               [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
               [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
               [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_VERHOEFF_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
               [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
               [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_ok(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


class AadhaarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aadhaar_number: str = Field(min_length=12, max_length=14)
    name_as_per_aadhaar: str = Field(min_length=1, max_length=150)
    collection_purpose: str | None = Field(default=None, max_length=200)


class PanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pan_number: str = Field(min_length=10, max_length=10)
    name_as_per_pan: str = Field(min_length=1, max_length=150)


class BankIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_holder_name: str = Field(min_length=1, max_length=150)
    bank_name: str = Field(min_length=1, max_length=150)
    branch_name: str | None = Field(default=None, max_length=150)
    account_number: str = Field(min_length=9, max_length=18)
    ifsc_code: str = Field(min_length=11, max_length=11)
    is_primary: bool = False
    is_salary_account: bool = True


def _employee(db: Session, principal: Principal, resource: str, action: str, employee_id: int) -> Employee:
    """The employee must be inside the scope of the specific EMPLOYEE_* permission held by the caller."""
    scope = principal.scope_for("EMPLOYEE", resource, action)
    if scope.empty:
        raise Forbidden()
    q = select(Employee).where(Employee.employee_id == employee_id)
    clause = scope_clause(Employee, scope, principal)
    if clause is not None:
        q = q.where(clause)
    emp = db.scalar(q)
    if emp is None:
        raise NotFound()
    return emp


def _audit(db, principal, request, resource, employee_id):
    audit.record(db, principal, action="set_identifier", module="EMPLOYEE", resource=resource, record_id=employee_id,
                 request_id=request.state.request_id, ip=client_ip(request))


@router.put("/employees/{employee_id}/aadhaar")
def set_aadhaar(employee_id: int, body: AadhaarIn, request: Request, principal: Principal = Depends(active_principal),
                db: Session = Depends(get_db)):
    emp = _employee(db, principal, "EMPLOYEE_AADHAAR", "UPDATE", employee_id)
    number = re.sub(r"[\s-]", "", body.aadhaar_number)
    if not re.fullmatch(r"[2-9][0-9]{11}", number) or not verhoeff_ok(number):
        raise Invalid("That is not a valid Aadhaar number.", details={"aadhaar_number": ["Invalid number."]})
    fp = crypto.fingerprint("aadhaar:" + number)
    dup = db.execute(text("SELECT employee_id FROM employee_aadhaar WHERE aadhaar_number_fingerprint = :f AND deleted_at IS NULL "
                          "AND employee_id <> :e"), {"f": fp, "e": emp.employee_id}).first()
    if dup:
        raise Conflict("This Aadhaar number is already registered for another employee.", code="duplicate")
    db.execute(text("UPDATE employee_aadhaar SET deleted_at = now() WHERE employee_id = :e AND deleted_at IS NULL"),
               {"e": emp.employee_id})
    db.execute(text(
        "INSERT INTO employee_aadhaar (employee_id, aadhaar_number_ciphertext, aadhaar_number_fingerprint, "
        "aadhaar_number_last4, aadhaar_number_masked, name_as_per_aadhaar, format_validated, verification_status, "
        "collection_purpose, created_by_user_id, updated_by_user_id) VALUES (:e, :c, :f, :l, :m, :n, true, 'PENDING', :p, :u, :u)"),
        {"e": emp.employee_id, "c": crypto.encrypt(number), "f": fp, "l": number[-4:], "m": f"XXXX XXXX {number[-4:]}",
         "n": body.name_as_per_aadhaar, "p": body.collection_purpose, "u": principal.user_id})
    _audit(db, principal, request, "employee_aadhaar", emp.employee_id)
    db.commit()
    return {"employee_id": emp.employee_id, "aadhaar_number_masked": f"XXXX XXXX {number[-4:]}", "verification_status": "PENDING"}


@router.put("/employees/{employee_id}/pan")
def set_pan(employee_id: int, body: PanIn, request: Request, principal: Principal = Depends(active_principal),
            db: Session = Depends(get_db)):
    emp = _employee(db, principal, "EMPLOYEE_PAN", "UPDATE", employee_id)
    number = body.pan_number.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]", number):
        raise Invalid("That is not a valid PAN.", details={"pan_number": ["Invalid number."]})
    fp = crypto.fingerprint("pan:" + number)
    if db.execute(text("SELECT 1 FROM employee_pan WHERE pan_number_fingerprint = :f AND deleted_at IS NULL AND employee_id <> :e"),
                  {"f": fp, "e": emp.employee_id}).first():
        raise Conflict("This PAN is already registered for another employee.", code="duplicate")
    db.execute(text("UPDATE employee_pan SET deleted_at = now() WHERE employee_id = :e AND deleted_at IS NULL"), {"e": emp.employee_id})
    masked = number[:2] + "X" * 6 + number[-2:]
    db.execute(text(
        "INSERT INTO employee_pan (employee_id, pan_number_ciphertext, pan_number_fingerprint, pan_number_masked, "
        "name_as_per_pan, format_validated, verification_status, created_by_user_id, updated_by_user_id) "
        "VALUES (:e, :c, :f, :m, :n, true, 'PENDING', :u, :u)"),
        {"e": emp.employee_id, "c": crypto.encrypt(number), "f": fp, "m": masked, "n": body.name_as_per_pan, "u": principal.user_id})
    _audit(db, principal, request, "employee_pan", emp.employee_id)
    db.commit()
    return {"employee_id": emp.employee_id, "pan_number_masked": masked, "verification_status": "PENDING"}


@router.post("/employees/{employee_id}/bank-accounts", status_code=201)
def add_bank_account(employee_id: int, body: BankIn, request: Request, principal: Principal = Depends(active_principal),
                     db: Session = Depends(get_db)):
    emp = _employee(db, principal, "EMPLOYEE_BANK_ACCOUNT", "CREATE", employee_id)
    number = re.sub(r"\s", "", body.account_number)
    ifsc = body.ifsc_code.strip().upper()
    if not number.isdigit() or not 9 <= len(number) <= 18:
        raise Invalid("Account numbers are 9 to 18 digits.", details={"account_number": ["Invalid number."]})
    if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
        raise Invalid("That is not a valid IFSC code.", details={"ifsc_code": ["Invalid IFSC."]})
    fp = crypto.fingerprint(f"bank:{ifsc}:{number}")
    if db.execute(text("SELECT 1 FROM employee_bank_account WHERE account_number_fingerprint = :f AND deleted_at IS NULL"),
                  {"f": fp}).first():
        raise Conflict("This bank account is already registered.", code="duplicate")
    if body.is_primary:
        db.execute(text("UPDATE employee_bank_account SET is_primary = false WHERE employee_id = :e AND deleted_at IS NULL"),
                   {"e": emp.employee_id})
    new_id = db.execute(text(
        "INSERT INTO employee_bank_account (employee_id, account_holder_name, bank_name, branch_name, "
        "account_number_ciphertext, account_number_fingerprint, account_number_last4, ifsc_code, is_primary, "
        "is_salary_account, account_status, verification_status, effective_from, created_by_user_id, updated_by_user_id) "
        "VALUES (:e, :h, :b, :br, :c, :f, :l, :i, :p, :s, 'PENDING_VERIFICATION', 'PENDING', :d, :u, :u) "
        "RETURNING employee_bank_account_id"),
        {"e": emp.employee_id, "h": body.account_holder_name, "b": body.bank_name, "br": body.branch_name,
         "c": crypto.encrypt(number), "f": fp, "l": number[-4:], "i": ifsc, "p": body.is_primary,
         "s": body.is_salary_account, "d": datetime.now(UTC).date(), "u": principal.user_id}).scalar_one()
    _audit(db, principal, request, "employee_bank_account", emp.employee_id)
    db.commit()
    return {"employee_bank_account_id": new_id, "account_number_masked": "X" * (len(number) - 4) + number[-4:],
            "verification_status": "PENDING"}
