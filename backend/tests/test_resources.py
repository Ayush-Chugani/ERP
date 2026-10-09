"""Generic resource engine: coverage of every endpoint, scoping, CRUD semantics and data hygiene."""
import pytest
from sqlalchemy import text

import app.models  # noqa: F401
from app.resources.registry import build_registry

SPECS = sorted(build_registry().values(), key=lambda s: s.path)


@pytest.fixture()
def admin(as_user):
    return as_user("demoadmin")


@pytest.mark.parametrize("spec", SPECS, ids=[s.path for s in SPECS])
def test_every_resource_lists_and_describes(admin, spec):
    r = admin.get(f"/{spec.path}?page_size=2")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"count", "page", "page_size", "results"} <= set(body)
    for row in body["results"]:
        leaked = [k for k in row if any(w in k for w in ("password", "secret", "token_hash", "digest"))]
        assert not leaked, leaked
    meta = admin.get(f"/meta/{spec.path}")
    assert meta.status_code == 200
    names = {c["name"] for c in meta.json()["columns"]}
    assert spec.pk in names or spec.read_only
    # CSV export works and is bounded
    assert admin.get(f"/{spec.path}/export").status_code == 200


@pytest.mark.parametrize("user", ["student", "teacher", "examcell", "support", "campusadm"])
def test_no_endpoint_ever_returns_a_server_error(as_user, user):
    c = as_user(user)
    for spec in SPECS:
        r = c.get(f"/{spec.path}?page_size=1")
        assert r.status_code in (200, 403), (spec.path, r.status_code, r.text[:200])


def test_row_scope_by_role(as_user):
    counts = {u: as_user(u).get("/people/student?page_size=1").json() for u in ("registrar", "hod", "student")}
    assert counts["registrar"]["count"] > counts["hod"]["count"] > counts["student"]["count"] >= 1
    assert counts["student"]["count"] == 1


def test_student_cannot_see_other_students_or_staff(as_user):
    st = as_user("student")
    own = st.get("/people/student").json()["results"][0]["student_id"]
    other = as_user("registrar").get("/people/student?page_size=100").json()["results"]
    other_id = next(r["student_id"] for r in other if r["student_id"] != own)
    assert st.get(f"/people/student/{other_id}").status_code == 404
    assert st.get(f"/people/student/{own}").status_code == 200
    assert st.get("/people/employee").status_code == 403


def test_scope_blocks_writes_outside_remit(as_user):
    reg = as_user("registrar")
    row = reg.get("/people/student?page_size=1").json()["results"][0]
    hod = as_user("hod")
    # HOD of department 1 may not edit a student from another department
    foreign = next((r for r in reg.get("/people/student?page_size=100").json()["results"]
                    if r["department_id"] != 1), None)
    if foreign:
        r = hod.patch(f"/people/student/{foreign['student_id']}", json={"notes": "x"})
        assert r.status_code == 403             # a head of department reads students but does not edit their records
    assert row


def test_students_cannot_write_anything(as_user):
    st = as_user("student")
    sid = st.get("/people/student").json()["results"][0]["student_id"]
    assert st.patch(f"/people/student/{sid}", json={"notes": "hacked"}).status_code == 403
    assert st.post("/reference/gender", json={"gender_code": "Q", "gender_name": "Q"}).status_code == 403
    assert st.delete(f"/people/student/{sid}").status_code == 403


def test_crud_roundtrip_with_audit(as_user, db):
    c = as_user("registrar")
    r = c.post("/reference/gender", json={"gender_code": "NB", "gender_name": "Non-binary"})
    assert r.status_code == 201, r.text
    gid = r.json()["gender_id"]
    assert c.get(f"/reference/gender/{gid}").json()["gender_name"] == "Non-binary"
    r = c.patch(f"/reference/gender/{gid}", json={"gender_name": "Nonbinary"})
    assert r.status_code == 200 and r.json()["gender_name"] == "Nonbinary"
    assert c.post("/reference/gender", json={"gender_code": "NB", "gender_name": "dup"}).status_code == 409
    assert c.delete(f"/reference/gender/{gid}").status_code == 403           # registrar: no delete on reference data
    assert as_user("demoadmin").delete(f"/reference/gender/{gid}").status_code == 204
    assert c.get(f"/reference/gender/{gid}").status_code == 404
    actions = [a for (a,) in db.execute(text(
        "SELECT action FROM audit_log WHERE resource='gender' AND record_id=:i ORDER BY audit_id"), {"i": str(gid)})]
    assert actions == ["create", "update", "delete"]


def test_validation_errors_use_the_envelope(as_user):
    c = as_user("registrar")
    r = c.post("/reference/gender", json={"gender_code": "X" * 50, "gender_name": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = c.post("/reference/gender", json={"gender_name": "only name"})
    assert r.status_code == 422
    r = c.post("/reference/gender", json={"gender_code": "Z", "gender_name": "z", "unknown_field": 1})
    assert r.status_code == 422
    assert c.get("/reference/gender?nonexistent=1").status_code == 422
    assert c.get("/reference/gender?ordering=password").status_code == 422
    assert c.get("/reference/gender?page=abc").status_code == 422


def test_filters_search_ordering_and_paging(as_user):
    c = as_user("registrar")
    all_ = c.get("/people/student?page_size=100&ordering=display_name").json()
    names = [r["display_name"] for r in all_["results"]]
    assert names == sorted(names, key=str.lower) or names == sorted(names)
    page2 = c.get("/people/student?page_size=10&page=2").json()
    assert page2["page"] == 2 and len(page2["results"]) == 10 and page2["previous"] == 1
    needle = names[0].split()[0]
    hit = c.get(f"/people/student?search={needle}").json()
    assert hit["count"] >= 1
    assert c.get("/people/student?student_status=ACTIVE").json()["count"] <= all_["count"]
    assert c.get("/people/student?student_status__in=ACTIVE,APPLICANT").status_code == 200
    # LIKE metacharacters are escaped, not interpreted
    assert c.get("/people/student?search=%25").json()["count"] == 0


def test_optimistic_concurrency(as_user):
    c = as_user("registrar")
    spec = next(s for s in SPECS if s.versioned and not s.read_only and s.pk in s.columns)
    first = c.get(f"/{spec.path}?page_size=1").json()["results"]
    if not first:
        pytest.skip("no sample row for a versioned resource")
    row = first[0]
    label = next((n for n in spec.columns if spec.columns[n].kind == "string" and not spec.columns[n].readonly
                  and not spec.columns[n].fk_table), None)
    if label is None:
        pytest.skip("no editable string column")
    stale = c.patch(f"/{spec.path}/{row[spec.pk]}", json={"version": row["version"] + 99})
    assert stale.status_code in (409, 403, 404)


def test_in_use_delete_is_a_conflict(as_user):
    c = as_user("demoadmin")            # the registrar maintains reference data but cannot delete it
    gender_in_use = c.get("/people/student?page_size=1").json()["results"][0]["gender_id"]
    assert as_user("registrar").delete(f"/reference/gender/{gender_in_use}").status_code == 403
    assert c.delete(f"/reference/gender/{gender_in_use}").status_code == 409


def test_audit_log_is_append_only(db):
    db.execute(text("INSERT INTO audit_log (action, module, resource) VALUES ('t','T','t')"))
    with pytest.raises(Exception, match="append-only"):
        db.execute(text("UPDATE audit_log SET action='x'"))
    db.rollback()


def test_lookups_respect_scope(as_user):
    st = as_user("student")
    reg = as_user("registrar")
    assert reg.get("/lookups/people/student?limit=100").json()["results"]
    assert len(st.get("/lookups/people/student").json()["results"]) == 1
    assert st.get("/lookups/people/employee").status_code == 403


def test_meta_only_lists_readable_resources(as_user):
    meta = as_user("student").get("/meta").json()
    paths = {r["path"] for g in meta["groups"] for r in g["resources"]}
    assert "people/employee" not in paths
    full = {r["path"] for g in as_user("demoadmin").get("/meta").json()["groups"] for r in g["resources"]}
    assert "people/employee" in full and len(full) > len(paths)


def test_idempotent_create(as_user):
    c = as_user("registrar")
    headers = {"Idempotency-Key": "abc-123"}
    body = {"gender_code": "IDM", "gender_name": "Idempotent"}
    a = c.post("/reference/gender", json=body, headers=headers)
    b = c.post("/reference/gender", json=body, headers=headers)
    assert a.status_code == 201 and b.status_code == 201 and a.json()["gender_id"] == b.json()["gender_id"]
    assert c.post("/reference/gender", json={**body, "gender_name": "Other"}, headers=headers).status_code == 409
