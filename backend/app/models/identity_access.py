"""SQLAlchemy models for the identity_access domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (Computed, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AccessAction(Base):
    __tablename__ = 'access_action'
    access_action_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    action_code = mapped_column(String(30), nullable=False)
    action_name = mapped_column(String(80), nullable=False)
    description = mapped_column(String(300))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('action_code', name='uq_access_action_action_code'),
        UniqueConstraint('action_name', name='uq_access_action_action_name'),
    )


class AccessModule(Base):
    __tablename__ = 'access_module'
    access_module_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_code = mapped_column(String(50), nullable=False)
    module_name = mapped_column(String(100), nullable=False)
    description = mapped_column(String(500))
    display_order = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('module_code', name='uq_access_module_module_code'),
        UniqueConstraint('module_name', name='uq_access_module_module_name'),
        CheckConstraint('(display_order >= 0)', name='ck_access_module_access_module_chk_1'),
    )


class AccessResource(Base):
    __tablename__ = 'access_resource'
    access_resource_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_code = mapped_column(String(80), nullable=False)
    resource_name = mapped_column(String(150), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    access_module_id = mapped_column(Integer, ForeignKey('access_module.access_module_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('access_module_id', 'resource_code', name='uq_access_resource_access_module_id_resource_code'),
    )


class LoginAudit(Base):
    __tablename__ = 'login_audit'
    login_audit_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username_attempted = mapped_column(String(100), nullable=False)
    login_at = mapped_column(DateTime(timezone=True), nullable=False)
    logout_at = mapped_column(DateTime(timezone=True))
    ip_address = mapped_column(String(45))
    user_agent = mapped_column(String(500))
    was_successful = mapped_column(Boolean, nullable=False, server_default=text("false"))
    failure_reason = mapped_column(String(200))
    session_identifier = mapped_column(String(128))
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    __table_args__ = (
        Index('ix_login_audit_user_id', 'user_id'),
    )


class PasswordHistory(Base):
    __tablename__ = 'password_history'
    password_history_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    password_hash = mapped_column(String(255), nullable=False)
    changed_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        Index('ix_password_history_user_id', 'user_id'),
    )


class Permission(Base):
    __tablename__ = 'permission'
    permission_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    permission_code = mapped_column(String(150), nullable=False)
    permission_name = mapped_column(String(200), nullable=False)
    description = mapped_column(String(500))
    is_sensitive = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    access_action_id = mapped_column(SmallInteger, ForeignKey('access_action.access_action_id'), nullable=False)
    access_resource_id = mapped_column(Integer, ForeignKey('access_resource.access_resource_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('permission_code', name='uq_permission_permission_code'),
        UniqueConstraint('access_resource_id', 'access_action_id', name='uq_permission_access_resource_id_access_action_id'),
        Index('ix_permission_access_action_id', 'access_action_id'),
    )


class Role(Base):
    __tablename__ = 'role'
    role_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_code = mapped_column(String(60), nullable=False)
    role_name = mapped_column(String(120), nullable=False)
    role_category = mapped_column(String(14), nullable=False)
    role_level = mapped_column(String(11), nullable=False)
    description = mapped_column(String(500))
    is_system_role = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_assignable = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    parent_role_id = mapped_column(Integer, ForeignKey('role.role_id'))
    __table_args__ = (
        UniqueConstraint('role_code', name='uq_role_role_code'),
        UniqueConstraint('role_name', name='uq_role_role_name'),
        Index('ix_role_parent_role_id', 'parent_role_id'),
        CheckConstraint("role_category IN ('SYSTEM', 'GOVERNANCE', 'ACADEMIC', 'ADMINISTRATIVE', 'FACULTY', 'STUDENT', 'PARENT', 'AUDIT', 'SUPPORT')", name='ck_role_role_category_enum'),
        CheckConstraint("role_level IN ('GLOBAL', 'INSTITUTION', 'CAMPUS', 'DEPARTMENT', 'PROGRAMME', 'SELF')", name='ck_role_role_level_enum'),
    )


class RoleDelegation(Base):
    __tablename__ = 'role_delegation'
    role_delegation_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    valid_from = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to = mapped_column(DateTime(timezone=True), nullable=False)
    delegation_status = mapped_column(String(7), nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    delegate_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    delegator_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    source_assignment_id = mapped_column(BigInteger, ForeignKey('user_role_assignment.user_role_assignment_id'), nullable=False)
    __table_args__ = (
        Index('ix_role_delegation_approved_by_user_id', 'approved_by_user_id'),
        Index('ix_role_delegation_delegate_user_id', 'delegate_user_id'),
        Index('ix_role_delegation_delegator_user_id', 'delegator_user_id'),
        Index('ix_role_delegation_source_assignment_id', 'source_assignment_id'),
        CheckConstraint("delegation_status IN ('PENDING', 'ACTIVE', 'REVOKED', 'EXPIRED')", name='ck_role_delegation_delegation_status_enum'),
        CheckConstraint('(valid_to > valid_from)', name='ck_role_delegation_role_delegation_dates'),
        CheckConstraint('(delegator_user_id <> delegate_user_id)', name='ck_role_delegation_role_delegation_users'),
    )


class RolePermission(Base):
    __tablename__ = 'role_permission'
    permission_effect = mapped_column(String(5), nullable=False)
    granted_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    permission_id = mapped_column(Integer, ForeignKey('permission.permission_id'), primary_key=True, autoincrement=False)
    role_id = mapped_column(Integer, ForeignKey('role.role_id'), primary_key=True, autoincrement=False)
    __table_args__ = (
        Index('ix_role_permission_role_id', 'role_id'),
        Index('ix_role_permission_permission_id', 'permission_id'),
        CheckConstraint("permission_effect IN ('ALLOW', 'DENY')", name='ck_role_permission_permission_effect_enum'),
    )


class UserPermissionOverride(Base):
    __tablename__ = 'user_permission_override'
    user_permission_override_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    permission_effect = mapped_column(String(5), nullable=False)
    scope_type = mapped_column(String(11), nullable=False)
    scope_entity_id = mapped_column(BigInteger)
    valid_from = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to = mapped_column(DateTime(timezone=True))
    justification = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    granted_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    permission_id = mapped_column(Integer, ForeignKey('permission.permission_id'), nullable=False)
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    revoked_at = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index('ix_user_permission_override_granted_by_user_id', 'granted_by_user_id'),
        Index('ix_user_permission_override_permission_id', 'permission_id'),
        CheckConstraint("permission_effect IN ('ALLOW', 'DENY')", name='ck_user_permission_override_permission_effect_enum'),
        CheckConstraint("scope_type IN ('GLOBAL', 'INSTITUTION', 'CAMPUS', 'DEPARTMENT', 'PROGRAMME', 'SELF')", name='ck_user_permission_override_scope_type_enum'),
        CheckConstraint('((valid_to is null) or (valid_to > valid_from))', name='ck_user_permission_override_user_permission_override_dates'),
        CheckConstraint("(((scope_entity_id is null) and (scope_type in ('GLOBAL','SELF'))) or ((scope_entity_id is not null) and (scope_type in ('INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME'))))", name='ck_user_permission_override_user_permission_override_scope'),
        CheckConstraint('(scope_entity_id >= 0)', name='ck_user_permission_override_user_permission_override_chk_1'),
    )


class UserRoleAssignment(Base):
    __tablename__ = 'user_role_assignment'
    user_role_assignment_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope_type = mapped_column(String(11), nullable=False)
    valid_from = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to = mapped_column(DateTime(timezone=True))
    assignment_status = mapped_column(String(9), nullable=False)
    is_primary = mapped_column(Boolean, nullable=False, server_default=text("false"))
    assignment_reason = mapped_column(String(500))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assigned_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'))
    department_id = mapped_column(Integer, ForeignKey('department.department_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'))
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'))
    role_id = mapped_column(Integer, ForeignKey('role.role_id'), nullable=False)
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    scope_entity_id = mapped_column(BigInteger, Computed(
        "CASE scope_type WHEN 'GLOBAL' THEN 0 WHEN 'SELF' THEN user_id WHEN 'INSTITUTION' THEN institution_id "
        "WHEN 'CAMPUS' THEN campus_id WHEN 'DEPARTMENT' THEN department_id WHEN 'PROGRAMME' THEN programme_id END",
        persisted=True))
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', 'scope_type', 'scope_entity_id', 'valid_from', name='uq_user_role_assignment'),
        Index('ix_user_role_assignment_assigned_by_user_id', 'assigned_by_user_id'),
        Index('ix_user_role_assignment_campus_id', 'campus_id'),
        Index('ix_user_role_assignment_department_id', 'department_id'),
        Index('ix_user_role_assignment_institution_id', 'institution_id'),
        Index('ix_user_role_assignment_programme_id', 'programme_id'),
        Index('ix_user_role_assignment_role_id', 'role_id'),
        CheckConstraint("scope_type IN ('GLOBAL', 'INSTITUTION', 'CAMPUS', 'DEPARTMENT', 'PROGRAMME', 'SELF')", name='ck_user_role_assignment_scope_type_enum'),
        CheckConstraint("assignment_status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'EXPIRED', 'REVOKED')", name='ck_user_role_assignment_assignment_status_enum'),
        CheckConstraint('((valid_to is null) or (valid_to > valid_from))', name='ck_user_role_assignment_user_role_dates'),
        CheckConstraint("(((campus_id is null) and (department_id is null) and (institution_id is null) and (programme_id is null) and (scope_type = 'GLOBAL')) or ((campus_id is null) and (department_id is null) and (institution_id is not null) and (programme_id is null) and (scope_type = 'INSTITUTION')) or ((campus_id is not null) and (department_id is null) and (institution_id is null) and (programme_id is null) and (scope_type = 'CAMPUS')) or ((campus_id is null) and (department_id is not null) and (institution_id is null) and (programme_id is null) and (scope_type = 'DEPARTMENT')) or ((campus_id is null) and (department_id is null) and (institution_id is null) and (programme_id is not null) and (scope_type = 'PROGRAMME')) or ((campus_id is null) and (department_id is null) and (institution_id is null) and (programme_id is null) and (scope_type = 'SELF')))", name='ck_user_role_assignment_user_role_scope'),
    )
