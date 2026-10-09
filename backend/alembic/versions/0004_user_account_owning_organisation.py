"""Each login belongs to an organisation (institution) so organisation administrators manage only their own people.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_account", sa.Column("institution_id", sa.Integer(), nullable=True,
                                            comment="Organisation that owns this login; NULL for platform-level accounts"))
    op.create_index("ix_user_account_institution_id", "user_account", ["institution_id"], unique=False)
    op.create_foreign_key(op.f("fk_user_account_institution_id_institution"), "user_account", "institution",
                          ["institution_id"], ["institution_id"], ondelete="RESTRICT")
    # Back-fill from what is already known: the person a login is linked to, else an institution-level role.
    op.execute("""
        UPDATE user_account u SET institution_id = x.institution_id FROM (
            SELECT l.user_id, s.institution_id FROM person_account_link l JOIN student s ON s.student_id = l.student_id
            UNION ALL
            SELECT l.user_id, e.institution_id FROM person_account_link l JOIN employee e ON e.employee_id = l.employee_id
        ) x WHERE x.user_id = u.user_id AND u.institution_id IS NULL AND x.institution_id IS NOT NULL AND NOT u.is_superuser""")
    op.execute("""
        UPDATE user_account u SET institution_id = a.institution_id FROM user_role_assignment a
        WHERE a.user_id = u.user_id AND a.assignment_status = 'ACTIVE' AND a.scope_type = 'INSTITUTION'
          AND a.institution_id IS NOT NULL AND u.institution_id IS NULL AND NOT u.is_superuser""")


def downgrade() -> None:
    op.drop_constraint(op.f("fk_user_account_institution_id_institution"), "user_account", type_="foreignkey")
    op.drop_index("ix_user_account_institution_id", table_name="user_account")
    op.drop_column("user_account", "institution_id")
