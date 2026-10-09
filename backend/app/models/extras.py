"""Constraints that MySQL expressed with generated columns, re-expressed as PostgreSQL partial / expression indexes."""
from sqlalchemy import Index, func, text

from app.db.base import Base

T = Base.metadata.tables


def _ix(name, table, *cols, where=None):
    t = T[table]
    exprs = [c if not isinstance(c, str) else t.c[c] for c in cols]
    Index(name, *exprs, unique=True, postgresql_where=text(where) if where else None)


_ix('uq_attendance_correction_pending', 'attendance_correction_request', 'attendance_id', where="request_status = 'PENDING'")
_ix('uq_caste_uncategorized_name', 'caste', 'caste_name', where="social_category_id IS NULL")
_ix('uq_course_offering_section', 'course_offering_section', 'course_offering_id', 'class_section_id',
    func.coalesce(T['course_offering_section'].c.class_batch_id, 0), 'session_type')
_ix('uq_section_student_active_roster', 'course_offering_section_student', 'course_registration_id', 'session_type',
    where="roster_status = 'ACTIVE'")
_ix('uq_employee_current_primary_address', 'employee_address', 'employee_id', where="is_primary AND valid_to IS NULL")
_ix('uq_employee_current_primary', 'employee_assignment', 'employee_id', where="end_date IS NULL AND is_primary")
_ix('uq_employee_primary_bank', 'employee_bank_account', 'employee_id', where="deleted_at IS NULL AND is_primary")
_ix('uq_employee_highest_qualification', 'employee_qualification', 'employee_id',
    where="deleted_at IS NULL AND is_highest_qualification")
_ix('uq_evidence_current_version', 'evidence_document_version', 'evidence_document_id', where="is_current")
_ix('uq_person_link_student_user', 'person_account_link', 'user_id', where="student_id IS NOT NULL")
_ix('uq_person_link_employee_user', 'person_account_link', 'user_id', where="employee_id IS NOT NULL")
_ix('uq_programme_term', 'programme_term_offering', 'academic_term_id', 'programme_id',
    func.coalesce(T['programme_term_offering'].c.specialization_id, 0), 'semester_id')
_ix('uq_student_current_primary_address', 'student_address', 'student_id', where="is_primary AND valid_to IS NULL")
_o = T['user_permission_override']
_ix('uq_user_permission_override', 'user_permission_override', 'user_id', 'permission_id', 'scope_type',
    func.coalesce(_o.c.scope_entity_id, 0), 'valid_from')

# SQL statements applied by the baseline migration (views, immutability triggers).
VIEWS = [
    """CREATE VIEW v_active_user_role AS
    SELECT ura.user_role_assignment_id, ura.user_id, ura.role_id, r.role_code, r.role_name, ura.scope_type,
           ura.institution_id, ura.campus_id, ura.department_id, ura.programme_id, ura.valid_from, ura.valid_to
    FROM user_role_assignment ura JOIN role r ON r.role_id = ura.role_id
    WHERE ura.assignment_status = 'ACTIVE' AND r.is_active AND ura.valid_from <= now()
      AND (ura.valid_to IS NULL OR ura.valid_to > now())""",
    """CREATE VIEW v_active_role_permission AS
    SELECT aur.user_id, aur.user_role_assignment_id AS source_assignment_id, aur.role_id, aur.role_code, aur.scope_type,
           CASE aur.scope_type WHEN 'GLOBAL' THEN 0 WHEN 'INSTITUTION' THEN aur.institution_id WHEN 'CAMPUS' THEN aur.campus_id
                WHEN 'DEPARTMENT' THEN aur.department_id WHEN 'PROGRAMME' THEN aur.programme_id WHEN 'SELF' THEN aur.user_id END AS scope_entity_id,
           p.permission_id, p.permission_code, rp.permission_effect, 'DIRECT'::text AS permission_source
    FROM v_active_user_role aur
    JOIN role_permission rp ON rp.role_id = aur.role_id
    JOIN permission p ON p.permission_id = rp.permission_id
    WHERE p.is_active
    UNION ALL
    SELECT rd.delegate_user_id, aur.user_role_assignment_id, aur.role_id, aur.role_code, aur.scope_type,
           CASE aur.scope_type WHEN 'GLOBAL' THEN 0 WHEN 'INSTITUTION' THEN aur.institution_id WHEN 'CAMPUS' THEN aur.campus_id
                WHEN 'DEPARTMENT' THEN aur.department_id WHEN 'PROGRAMME' THEN aur.programme_id WHEN 'SELF' THEN rd.delegate_user_id END,
           p.permission_id, p.permission_code, rp.permission_effect, 'DELEGATED'::text
    FROM role_delegation rd
    JOIN v_active_user_role aur ON aur.user_role_assignment_id = rd.source_assignment_id
    JOIN role_permission rp ON rp.role_id = aur.role_id
    JOIN permission p ON p.permission_id = rp.permission_id
    WHERE rd.delegation_status = 'ACTIVE' AND rd.valid_from <= now() AND rd.valid_to > now() AND p.is_active""",
    """CREATE VIEW v_effective_user_permission AS
    SELECT x.user_id, x.permission_id, x.permission_code, x.scope_type, x.scope_entity_id,
           CASE WHEN max(x.is_deny) = 1 THEN 'DENY' ELSE 'ALLOW' END AS permission_effect
    FROM (
      SELECT arp.user_id, arp.permission_id, arp.permission_code, arp.scope_type, arp.scope_entity_id,
             CASE WHEN arp.permission_effect = 'DENY' THEN 1 ELSE 0 END AS is_deny
      FROM v_active_role_permission arp
      UNION ALL
      SELECT upo.user_id, upo.permission_id, p.permission_code, upo.scope_type,
             CASE upo.scope_type WHEN 'GLOBAL' THEN 0 WHEN 'SELF' THEN upo.user_id ELSE upo.scope_entity_id END,
             CASE WHEN upo.permission_effect = 'DENY' THEN 1 ELSE 0 END
      FROM user_permission_override upo JOIN permission p ON p.permission_id = upo.permission_id
      WHERE p.is_active AND upo.revoked_at IS NULL AND upo.valid_from <= now()
        AND (upo.valid_to IS NULL OR upo.valid_to > now())
    ) x
    GROUP BY x.user_id, x.permission_id, x.permission_code, x.scope_type, x.scope_entity_id""",
    """CREATE VIEW student_user_account AS
    SELECT DISTINCT student_id, user_id, created_at AS linked_at FROM person_account_link WHERE student_id IS NOT NULL""",
    """CREATE VIEW employee_user_account AS
    SELECT DISTINCT employee_id, user_id, created_at AS linked_at FROM person_account_link WHERE employee_id IS NOT NULL""",
]

IMMUTABLE_TABLES = ['audit_log', 'status_history', 'evidence_document_audit', 'consultancy_receipt',
                    'consultancy_receipt_void', 'research_utilization_void']
IMMUTABILITY_FN = """CREATE OR REPLACE FUNCTION sims_forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Table % is append-only', TG_TABLE_NAME USING ERRCODE = 'restrict_violation'; END $$"""
