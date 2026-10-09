"""Property-based fuzzing: no endpoint may answer 5xx whatever junk it is sent, as any persona."""
import re

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

JUNK = st.one_of(st.none(), st.booleans(), st.integers(-2**40, 2**40), st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=40),
                 st.lists(st.integers(), max_size=3), st.dictionaries(st.text(max_size=8), st.one_of(st.text(max_size=20), st.integers(), st.none()), max_size=4))
SEGMENT = st.one_of(st.integers(-5, 10**9).map(str), st.text("abc-_%;'\" 0123456789", min_size=1, max_size=12))
SKIP = ("/auth/logout-all", "/auth/login", "/auth/mfa", "/auth/change-password", "/health", "/files")


def operations(app):
    spec = app.openapi()
    for path, item in spec["paths"].items():
        if path.replace("/api/v1", "").startswith(SKIP):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            if method in item:
                yield method, path


@pytest.fixture(scope="module")
def ops(app):
    return list(operations(app))


@pytest.mark.parametrize("persona", ["demoadmin", "hod", "student"])
@settings(max_examples=60, deadline=None, suppress_health_check=list(HealthCheck))
@given(data=st.data())
def test_no_endpoint_ever_returns_5xx(persona, data, ops, as_user):
    c = as_user(persona)
    method, path = data.draw(st.sampled_from(ops))
    url = re.sub(r"\{[^}]+\}", lambda _m: data.draw(SEGMENT), path).replace("/api/v1", "")
    params = data.draw(st.dictionaries(st.sampled_from(["page", "page_size", "q", "ordering", "status", "on", "ids", "limit", "unread"]), JUNK.map(str), max_size=3))
    kw = {"params": params}
    if method in ("post", "put", "patch"):
        kw["json"] = data.draw(st.dictionaries(st.text(max_size=12), JUNK, max_size=6))
    r = getattr(c.http, method)("/api/v1" + url, headers=c.csrf_headers(), **kw)
    assert r.status_code < 500, (method, url, params, kw.get("json"), r.text[:300])
    if r.status_code >= 400:
        assert "error" in r.json() or r.status_code == 404 or r.headers.get("content-type", "").startswith("application/json")
