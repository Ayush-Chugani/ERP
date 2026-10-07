"""Generate review DDL from Section 7. Does not connect to or modify a database."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
source = (root / 'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8-sig')
start = source.index('CREATE TABLE programme_term_offering (')
end = source.index('-- =============================================================', start)
sql = source[start:end].strip()

additions = {
    'programme_term_offering': '''    CONSTRAINT uq_m7_offering_programme UNIQUE (programme_term_offering_id, programme_id),
    CONSTRAINT fk_m7_offering_scheme_programme FOREIGN KEY (curriculum_scheme_id, programme_id)
        REFERENCES curriculum_scheme(curriculum_scheme_id, programme_id),
    INDEX ix_m7_offering_queue (programme_id, academic_term_id, status),
''',
    'class_section': '''    CONSTRAINT chk_m7_section_capacity CHECK (capacity IS NULL OR capacity > 0),
''',
    'class_batch': '''    CONSTRAINT chk_m7_batch_capacity CHECK (capacity IS NULL OR capacity > 0),
''',
    'student_term_registration': '''    programme_id SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT fk_m7_term_enrolment_programme FOREIGN KEY (enrolment_id, programme_id)
        REFERENCES student_programme_enrolment(enrolment_id, programme_id),
    CONSTRAINT fk_m7_term_offering_programme FOREIGN KEY (programme_term_offering_id, programme_id)
        REFERENCES programme_term_offering(programme_term_offering_id, programme_id),
    CONSTRAINT uq_m7_term_registration_owner UNIQUE (term_registration_id, programme_term_offering_id),
    INDEX ix_m7_section_seats (class_section_id, registration_status),
    INDEX ix_m7_batch_seats (class_batch_id, registration_status),
    CONSTRAINT chk_m7_roll_nonblank CHECK (roll_number IS NULL OR CHAR_LENGTH(TRIM(roll_number)) > 0),
''',
    'course_offering': '''    CONSTRAINT chk_m7_course_capacity CHECK (registration_capacity IS NULL OR registration_capacity > 0),
    CONSTRAINT fk_m7_curriculum_course_identity FOREIGN KEY (curriculum_course_id, course_id)
        REFERENCES curriculum_course(curriculum_course_id, course_id),
    INDEX ix_m7_course_queue (programme_term_offering_id, status),
''',
    'course_offering_section': '''    CONSTRAINT uq_m7_mapping_session UNIQUE (course_offering_section_id, session_type),
''',
    'student_course_registration': '''    programme_term_offering_id BIGINT UNSIGNED NOT NULL,
    CONSTRAINT fk_m7_registration_term_owner FOREIGN KEY (term_registration_id, programme_term_offering_id)
        REFERENCES student_term_registration(term_registration_id, programme_term_offering_id),
    CONSTRAINT fk_m7_registration_offering_owner FOREIGN KEY (course_offering_id, programme_term_offering_id)
        REFERENCES course_offering(course_offering_id, programme_term_offering_id),
    INDEX ix_m7_course_seats (course_offering_id, registration_status),
''',
    'course_offering_section_student': '''    session_type ENUM('LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER') NOT NULL,
    active_registration_key BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN roster_status = 'ACTIVE' THEN course_registration_id ELSE NULL END
    ) STORED,
    CONSTRAINT fk_m7_roster_session FOREIGN KEY (course_offering_section_id, session_type)
        REFERENCES course_offering_section(course_offering_section_id, session_type),
    CONSTRAINT uq_m7_active_roster_session UNIQUE (active_registration_key, session_type),
    CONSTRAINT chk_m7_roster_open CHECK (roster_status <> 'ACTIVE' OR effective_to IS NULL),
    INDEX ix_m7_roster_current (course_offering_section_id, roster_status, effective_from, effective_to),
''',
}
metadata = '''    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
'''
for table, extra in additions.items():
    actor_keys = f'''    CONSTRAINT fk_m7_{list(additions).index(table)}_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_{list(additions).index(table)}_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
'''
    sql = sql.replace(f'CREATE TABLE {table} (\n', f'CREATE TABLE {table} (\n' + metadata + extra + actor_keys)

# A roster row represents an immutable membership episode. Returning to a former
# section creates another episode rather than overwriting attendance-linked history.
sql = sql.replace('CONSTRAINT uq_course_section_student UNIQUE (course_offering_section_id, course_registration_id)',
                  'CONSTRAINT uq_course_section_student UNIQUE (course_offering_section_id, course_registration_id, effective_from)')
sql = sql.replace('effective_from DATE NULL', 'effective_from DATE NOT NULL')
sql = sql.replace('effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from',
                  'effective_to IS NULL OR effective_to > effective_from')

header = '''-- M7 review DDL. Not a production migration; do not execute on populated tables.
-- Existing FK delete/update behavior remains RESTRICT/NO ACTION.
-- Actor IDs are SIGNED BIGINT, matching the live Django custom user table.
-- The M6 migration already supplies uq_m6_scheme_programme on curriculum_scheme.
-- These additional keys must be introduced by migrations owned by M6 and M4:
ALTER TABLE student_programme_enrolment
    ADD CONSTRAINT uq_m7_enrolment_programme UNIQUE (enrolment_id, programme_id);
ALTER TABLE curriculum_course
    ADD CONSTRAINT uq_m7_curriculum_course_identity UNIQUE (curriculum_course_id, course_id);

'''
output = header + sql + '\n'
assert len(re.findall(r'^CREATE TABLE ', output, re.M)) == 8
assert 'fk_m7_registration_term_owner' in output and 'fk_m7_registration_offering_owner' in output
(root / 'Manuals/M7_REVISED_SCHEMA_PROPOSAL.sql').write_text(output, encoding='utf-8')
print('Generated complete review DDL for eight M7 tables; database unchanged.')
