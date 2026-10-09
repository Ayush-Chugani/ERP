"""Platform tables: sessions, audit trail, status history, job queue, idempotency, rate limiting, notifications."""
import uuid

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func,
                        text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AuthSession(Base):
    """One row per signed-in device. The refresh token is rotated on every use; only its digest is stored."""

    __tablename__ = 'auth_session'
    session_id = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id', ondelete='CASCADE'), nullable=False)
    refresh_digest = mapped_column(String(64), nullable=False)
    previous_digest = mapped_column(String(64))
    rotated_at = mapped_column(DateTime(timezone=True))
    rotation_count = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at = mapped_column(DateTime(timezone=True))
    revoke_reason = mapped_column(String(60))
    ip_address = mapped_column(String(45))
    user_agent = mapped_column(String(300))
    __table_args__ = (
        Index('ix_auth_session_user', 'user_id', 'revoked_at'),
        Index('ix_auth_session_expires', 'expires_at'),
    )


class AuditLog(Base):
    """Append-only business audit trail (updates and deletes are blocked by a trigger)."""

    __tablename__ = 'audit_log'
    audit_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id', ondelete='SET NULL'))
    action = mapped_column(String(60), nullable=False)
    module = mapped_column(String(60), nullable=False)
    resource = mapped_column(String(80), nullable=False)
    record_id = mapped_column(String(80))
    institution_id = mapped_column(Integer)
    before = mapped_column(JSONB)
    after = mapped_column(JSONB)
    reason = mapped_column(String(500))
    request_id = mapped_column(String(64))
    ip_address = mapped_column(String(45))
    __table_args__ = (
        Index('ix_audit_log_resource', 'module', 'resource', 'record_id'),
        Index('ix_audit_log_actor', 'actor_user_id', 'occurred_at'),
        Index('ix_audit_log_time', 'occurred_at'),
    )


class StatusHistory(Base):
    """Append-only workflow history for every status-bearing record."""

    __tablename__ = 'status_history'
    status_history_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = mapped_column(String(80), nullable=False)
    entity_id = mapped_column(String(80), nullable=False)
    from_status = mapped_column(String(60))
    to_status = mapped_column(String(60), nullable=False)
    action = mapped_column(String(60))
    changed_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id', ondelete='SET NULL'))
    changed_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    remarks = mapped_column(String(1000))
    __table_args__ = (
        Index('ix_status_history_changed_by', 'changed_by_id'),Index('ix_status_history_entity', 'entity_type', 'entity_id', 'changed_at'),)


class Job(Base):
    """PostgreSQL-backed work queue (SELECT ... FOR UPDATE SKIP LOCKED)."""

    __tablename__ = 'job'
    job_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    queue = mapped_column(String(40), nullable=False, server_default=text("'default'"))
    kind = mapped_column(String(80), nullable=False)
    payload = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = mapped_column(String(12), nullable=False, server_default=text("'queued'"))
    priority = mapped_column(Integer, nullable=False, server_default=text("100"))
    run_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    attempts = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts = mapped_column(Integer, nullable=False, server_default=text("5"))
    locked_by = mapped_column(String(80))
    locked_at = mapped_column(DateTime(timezone=True))
    last_error = mapped_column(Text)
    result = mapped_column(JSONB)
    dedupe_key = mapped_column(String(160))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id', ondelete='SET NULL'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index('ix_job_created_by', 'created_by_id'),
        CheckConstraint("status IN ('queued','running','succeeded','failed','dead')", name='ck_job_status'),
        Index('ix_job_pick', 'queue', 'status', 'priority', 'run_at'),
        Index('uq_job_dedupe', 'dedupe_key', unique=True, postgresql_where=text("status IN ('queued','running')")),
    )


class JobSchedule(Base):
    """Recurring jobs. The worker enqueues a job whenever ``next_run_at`` passes."""

    __tablename__ = 'job_schedule'
    schedule_id = mapped_column(String(80), primary_key=True)
    kind = mapped_column(String(80), nullable=False)
    payload = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    interval_seconds = mapped_column(Integer, nullable=False)
    next_run_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    enabled = mapped_column(Boolean, nullable=False, server_default=text("true"))


class IdempotencyKey(Base):
    __tablename__ = 'idempotency_key'
    key = mapped_column(String(120), primary_key=True)
    user_id = mapped_column(BigInteger, primary_key=True)
    route = mapped_column(String(200), nullable=False)
    request_digest = mapped_column(String(64), nullable=False)
    response_status = mapped_column(Integer)
    response_body = mapped_column(JSONB)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index('ix_idempotency_created', 'created_at'),)


class RateLimitBucket(Base):
    __tablename__ = 'rate_limit_bucket'
    bucket = mapped_column(String(160), primary_key=True)
    window_start = mapped_column(BigInteger, primary_key=True)
    hits = mapped_column(Integer, nullable=False, server_default=text("0"))
    __table_args__ = (Index('ix_rate_limit_window', 'window_start'),)


class Notification(Base):
    __tablename__ = 'notification'
    notification_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id', ondelete='CASCADE'), nullable=False)
    title = mapped_column(String(200), nullable=False)
    body = mapped_column(String(2000))
    link = mapped_column(String(300))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    read_at = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index('ix_notification_user', 'user_id', 'read_at', 'created_at'),)
