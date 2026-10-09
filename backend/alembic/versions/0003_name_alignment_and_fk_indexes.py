"""Align long index/constraint names with the naming convention and index four remaining foreign keys.

Databases created from an earlier draft of the baseline (e.g. the first Supabase deployment) carry slightly different
truncated names; databases created from the current baseline already match, so every step is a no-op there.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

INDEX_RENAMES = [
    ("ix_evidence_document_staff_activity_id_document_type__61641a", "ix_evidence_document_staff_activity_id_document_type_61641a"),
    ("ix_evidence_document_verification_status_id_approval__26c490", "ix_evidence_document_verification_status_id_approval_26c490"),
    ("ix_evidence_document_version_evidence_document_id_is__74d199", "ix_evidence_document_version_evidence_document_id_is_74d199"),
    ("ix_registration_progression_enrolment_id_offering_id__00579b", "ix_registration_progression_enrolment_id_offering_id_00579b"),
    ("ix_student_term_registration_programme_term_offering__5786c8", "ix_student_term_registration_programme_term_offering_5786c8"),
]
CONSTRAINT_RENAMES = [
    ("course_offering", "uq_course_offering_course_offering_id_programme_term__a32d4e", "uq_course_offering_course_offering_id_programme_term_a32d4e"),
    ("faculty_course_assignment", "uq_faculty_course_assignment_course_offering_section__7c1221", "uq_faculty_course_assignment_course_offering_section_7c1221"),
    ("student_term_registration", "uq_student_term_registration_programme_term_offering__a1187c", "uq_student_term_registration_programme_term_offering_a1187c"),
]
NEW_INDEXES = [
    ("ix_employee_competency_employee_id", "employee_competency", "employee_id"),
    ("ix_job_created_by", "job", "created_by_id"),
    ("ix_role_permission_role_id", "role_permission", "role_id"),
    ("ix_status_history_changed_by", "status_history", "changed_by_id"),
]


def upgrade() -> None:
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX IF EXISTS "{old}" RENAME TO "{new}"')
    for table, old, new in CONSTRAINT_RENAMES:
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{old}') THEN "
            f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old}" TO "{new}"; END IF; END $$')
    for name, table, column in NEW_INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ("{column}")')


def downgrade() -> None:
    # Nothing to undo: the renames are cosmetic and the indexes belong to the baseline schema as well.
    pass
