"""IAM views, append-only triggers and Supabase hardening (row level security).

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

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
VIEW_NAMES = ["employee_user_account", "student_user_account", "v_effective_user_permission",
              "v_active_role_permission", "v_active_user_role"]
IMMUTABLE_TABLES = ["audit_log", "status_history", "evidence_document_audit", "consultancy_receipt",
                    "consultancy_receipt_void", "research_utilization_void"]

RLS = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
  END LOOP;
  -- Supabase exposes the public schema through PostgREST. The API connects as the table owner, so these roles
  -- must never reach any table or view directly.
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon';
    EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon';
    EXECUTE 'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated';
    EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM authenticated';
    EXECUTE 'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM authenticated';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM authenticated';
  END IF;
END $$
"""


def upgrade() -> None:
    for sql in VIEWS:
        op.execute(sql)
    op.execute("""CREATE OR REPLACE FUNCTION sims_forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Table % is append-only', TG_TABLE_NAME USING ERRCODE = 'restrict_violation'; END $$""")
    for t in IMMUTABLE_TABLES:
        op.execute(f"CREATE TRIGGER trg_{t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                   "FOR EACH ROW EXECUTE FUNCTION sims_forbid_change()")
    op.execute(RLS)


def downgrade() -> None:
    for t in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_append_only ON {t}")
    op.execute("DROP FUNCTION IF EXISTS sims_forbid_change()")
    for v in VIEW_NAMES:
        op.execute(f"DROP VIEW IF EXISTS {v}")
