"""Staff identifiers: validated, encrypted at rest, masked in responses, restricted to explicit permissions."""
import pytest
from sqlalchemy import text

from app.api.routers.hr_secure import verhoeff_ok
from app.core import crypto

GOOD_AADHAAR = "234567890124"


def _valid_aadhaar() -> str:
    base = "23456789012"
    for d in "0123456789":
        if verhoeff_ok(base + d):
            return base + d
    raise AssertionError


@pytest.fixture()
def employee_id(db):
    return db.execute(text("SELECT employee_id FROM employee ORDER BY employee_id LIMIT 1")).scalar()


def test_crypto_roundtrip_and_tamper_detection():
    blob = crypto.encrypt("ABCDE1234F")
    assert b"ABCDE1234F" not in blob and crypto.decrypt(blob) == "ABCDE1234F"
    assert crypto.encrypt("x") != crypto.encrypt("x")                     # random nonce
    with pytest.raises(Exception):
        crypto.decrypt(blob[:-1] + bytes([blob[-1] ^ 1]))
    assert crypto.fingerprint("a") == crypto.fingerprint("a") != crypto.fingerprint("b")


def test_aadhaar_is_encrypted_masked_and_deduplicated(as_user, db, employee_id):
    admin = as_user("demoadmin")
    number = _valid_aadhaar()
    assert admin.put(f"/hr/secure/employees/{employee_id}/aadhaar", json={"aadhaar_number": "123456789012", "name_as_per_aadhaar": "A"}).status_code == 422
    r = admin.put(f"/hr/secure/employees/{employee_id}/aadhaar", json={"aadhaar_number": number, "name_as_per_aadhaar": "A B"})
    assert r.status_code == 200, r.text
    assert r.json()["aadhaar_number_masked"] == f"XXXX XXXX {number[-4:]}" and number not in r.text
    row = db.execute(text("SELECT aadhaar_number_ciphertext, aadhaar_number_last4 FROM employee_aadhaar WHERE employee_id=:e AND deleted_at IS NULL"), {"e": employee_id}).one()
    assert number.encode() not in bytes(row[0]) and crypto.decrypt(bytes(row[0])) == number
    listing = admin.get("/hr/employee-aadhaar").json()["results"][0]
    assert "aadhaar_number_ciphertext" not in listing and number not in str(listing)
    other = db.execute(text("SELECT employee_id FROM employee WHERE employee_id <> :e LIMIT 1"), {"e": employee_id}).scalar()
    assert admin.put(f"/hr/secure/employees/{other}/aadhaar", json={"aadhaar_number": number, "name_as_per_aadhaar": "X"}).status_code == 409


def test_pan_and_bank_account_validation(as_user, employee_id):
    admin = as_user("demoadmin")
    assert admin.put(f"/hr/secure/employees/{employee_id}/pan", json={"pan_number": "bad", "name_as_per_pan": "A"}).status_code == 422
    ok = admin.put(f"/hr/secure/employees/{employee_id}/pan", json={"pan_number": "abcpe1234f", "name_as_per_pan": "A B"})
    assert ok.status_code == 200 and ok.json()["pan_number_masked"] == "ABXXXXXXXF".replace("ABXXXXXXXF", "ABXXXXXX4F"[:2] + "XXXXXX" + "4F")
    body = {"account_holder_name": "A B", "bank_name": "SBI", "account_number": "123456789012", "ifsc_code": "SBIN0001234", "is_primary": True}
    assert admin.post(f"/hr/secure/employees/{employee_id}/bank-accounts", json={**body, "ifsc_code": "BAD"}).status_code == 422
    r = admin.post(f"/hr/secure/employees/{employee_id}/bank-accounts", json=body)
    assert r.status_code == 201 and r.json()["account_number_masked"].endswith("9012") and "12345678" not in r.text
    assert admin.post(f"/hr/secure/employees/{employee_id}/bank-accounts", json=body).status_code == 409


@pytest.mark.parametrize("user", ["registrar", "hod", "teacher", "student", "campusadm"])
def test_module_wide_grants_do_not_unlock_identifiers(as_user, employee_id, user):
    c = as_user(user)
    assert c.put(f"/hr/secure/employees/{employee_id}/aadhaar", json={"aadhaar_number": _valid_aadhaar(), "name_as_per_aadhaar": "A"}).status_code == 403
    assert c.get("/hr/employee-aadhaar").status_code == 403
    assert c.get("/hr/employee-bank-account").status_code == 403
