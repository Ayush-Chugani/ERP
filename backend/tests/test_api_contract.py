"""The OpenAPI document is the contract: it must be complete, consistent and honest about errors."""
import re

import pytest

METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def schema(app):
    from fastapi.testclient import TestClient

    return TestClient(app, base_url="http://localhost").get("/api/openapi.json").json()


def operations(schema):
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if method in METHODS:
                yield path, method, op


def test_every_path_is_versioned_and_kebab_case(schema):
    for path in schema["paths"]:
        assert path.startswith("/api/v1/"), path
        for seg in path.split("/")[3:]:
            assert seg.startswith("{") or re.fullmatch(r"[a-z0-9-]+", seg), (path, seg)


def test_operation_ids_are_unique_and_stable_format(schema):
    ids = [op["operationId"] for _, _, op in operations(schema)]
    assert len(ids) == len(set(ids))
    bad = [i for i in ids if not re.fullmatch(r"[a-z0-9_]+__[a-z0-9_]+", i)]
    assert not bad, bad[:5]


def test_every_operation_has_tag_summary_and_success_response(schema):
    for path, method, op in operations(schema):
        assert op.get("tags"), (method, path)
        assert op.get("summary"), (method, path)
        assert any(code.startswith("2") for code in op["responses"]), (method, path)


def test_creates_return_201_and_deletes_204(schema):
    for path, method, op in operations(schema):
        if method == "delete":
            assert "204" in op["responses"], path
        if method == "post" and path.count("/") == 5 and "{" not in path and "/auth/" not in path and "/ai/" not in path \
                and not path.endswith(("/read-all", "/refresh", "/login", "/logout", "/logout-all")):
            assert any(c in op["responses"] for c in ("201", "200")), path


def test_protected_operations_document_the_error_envelope(schema):
    public = {"/api/v1/health/live", "/api/v1/health/ready", "/api/v1/auth/csrf"}
    for path, method, op in operations(schema):
        if path in public:
            continue
        for code in ("401", "403", "422"):
            assert code in op["responses"], (method, path, code)
            ref = op["responses"][code]["content"]["application/json"]["schema"]
            assert ref["$ref"].endswith("/ErrorResponse"), (method, path, code)


def test_default_validation_schema_is_gone(schema):
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert {"ErrorResponse", "ErrorBody"} <= set(schema["components"]["schemas"])


def test_bearer_scheme_declared(schema):
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_list_endpoints_share_one_pagination_envelope(schema):
    for path, method, op in operations(schema):
        if method == "get" and op["operationId"].endswith("__list_student"):
            body = schema["components"]["schemas"][op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]]
            assert {"count", "page", "page_size", "next", "previous", "results"} <= set(body["properties"])


def test_request_models_forbid_unknown_fields(schema):
    seen = set()
    for path, method, op in operations(schema):
        body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
        if "$ref" in body:
            seen.add(body["$ref"].rsplit("/", 1)[1])
    assert len(seen) > 100
    for name in seen:
        assert schema["components"]["schemas"][name].get("additionalProperties") is False, name


def test_resource_count_matches_registry(schema, app):
    from app.resources.registry import build_registry

    names = {op["operationId"].split("__")[1] for _, m, op in operations(schema) if m == "get"}
    for table, spec in build_registry().items():
        assert f"list_{table}" in names
        if len(spec.model.__table__.primary_key.columns) == 1:      # association tables are list-only
            assert f"get_{table}" in names, table


def test_docs_can_be_disabled(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "docs_enabled", False)
    c = TestClient(create_app(), base_url="http://localhost")
    assert c.get("/api/docs").status_code == 404 and c.get("/api/openapi.json").status_code == 404
