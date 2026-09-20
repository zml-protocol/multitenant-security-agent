import hashlib
from contextlib import closing
import json
import logging
import os
from pathlib import Path
import sqlite3
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request

from app import policy as default_policy


FIELDS = ("user_id", "tenant_id", "role", "name", "email", "phone")
logger = logging.getLogger("lab.access")


def correlation_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        return str(uuid.uuid4())


def create_app(db_path=None, policy=None):
    policy = policy or default_policy
    if not callable(getattr(policy, "authorize_list", None)) or not callable(getattr(policy, "authorize_detail", None)):
        raise ValueError("Authorization policy must provide authorize_list and authorize_detail")
    path = Path(db_path or os.getenv("LAB_DB", ".local/app.sqlite3")).resolve()
    if not path.is_file():
        raise ValueError("Database missing; run python -m app.seed first.")

    def query(sql, params=()):
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    fixture_id = query("SELECT fixture_id FROM metadata")[0]["fixture_id"]
    api = FastAPI(title="Multi-tenant security lab", docs_url=None, redoc_url=None, openapi_url=None)

    @api.middleware("http")
    async def audit(request: Request, call_next):
        started = time.perf_counter()
        request.state.request_id = correlation_id(request.headers.get("x-request-id"))
        request.state.run_id = correlation_id(request.headers.get("x-run-id"))
        request.state.identity = None
        request.state.decision = "not_evaluated"
        request.state.reason = "unmatched_route"
        status = 500
        size = 0
        try:
            response = await call_next(request)
            status = response.status_code
            size = int(response.headers.get("content-length", 0))
            response.headers["X-Request-ID"] = request.state.request_id
            response.headers["X-Fixture-ID"] = fixture_id
            response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            identity = request.state.identity or {}
            route = request.scope.get("route")
            # Never log raw URLs, arbitrary headers, bearer tokens or response bodies.
            logger.info(json.dumps({
                "timestamp": time.time(), "request_id": request.state.request_id,
                "run_id": request.state.run_id, "route": getattr(route, "path", "unmatched"),
                "method": request.method, "status": status, "response_bytes": size,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "source_ip": request.client.host if request.client else "unknown",
                "identity": identity.get("alias", "unknown"), "tenant_id": identity.get("tenant_id"),
                "target_user_id": getattr(request.state, "target_user_id", None),
                "decision": request.state.decision, "reason": request.state.reason,
            }))

    def deny(request, status, reason):
        request.state.decision, request.state.reason = "deny", reason
        raise HTTPException(status, "Unauthorized" if status == 401 else "Not found" if status == 404 else "Forbidden",
                            headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)

    def authenticate(request: Request):
        parts = request.headers.get("authorization", "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            deny(request, 401, "missing_or_malformed_credential")
        rows = query("SELECT * FROM users WHERE token_hash = ?", (hashlib.sha256(parts[1].encode()).hexdigest(),))
        if not rows:
            deny(request, 401, "invalid_credential")
        request.state.identity = rows[0]
        return rows[0]

    def allow(request, reason):
        request.state.decision, request.state.reason = "allow", reason

    def public(user):
        return {field: user[field] for field in FIELDS}

    @api.get("/api/me")
    def me(request: Request, actor=Depends(authenticate)):
        allow(request, "identity_baseline")
        return public(actor)

    @api.get("/api/users")
    def users(request: Request, actor=Depends(authenticate)):
        permitted, reason = policy.authorize_list(actor)
        if not permitted:
            deny(request, 403, reason)
        allow(request, reason)
        return [public(user) for user in query("SELECT * FROM users WHERE tenant_id = ? ORDER BY alias", (actor["tenant_id"],))]

    @api.get("/api/users/{user_id}")
    def detail(user_id: str, request: Request, actor=Depends(authenticate)):
        rows = query("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not rows:
            deny(request, 404, "unknown_user")
        target = rows[0]
        request.state.target_user_id = target["user_id"]
        permitted, reason = policy.authorize_detail(actor, target)
        if not permitted:
            # Do not reveal whether an object exists outside the actor's tenant.
            deny(request, 404 if reason == "tenant_boundary" else 403, reason)
        allow(request, reason)
        return public(target)

    return api
