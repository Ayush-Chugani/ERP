"""Build the review-only M6 DDL from the supplied baseline; never connect to a DB."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'Manuals/sims_v6_5_1_mariadb_full_schema.sql').read_text(encoding='utf-8-sig')
start = source.index('CREATE TABLE admission_applicant (')
end = source.index('-- =============================================================', start)
sql = source[start:end].strip()
sql = sql.replace('admitted_student_id BIGINT UNSIGNED NULL UNIQUE', 'admitted_student_id BIGINT UNSIGNED NULL')
additions = {
    'admission_applicant': '''    institution_id SMALLINT UNSIGNED NOT NULL,
    canonical_student_id BIGINT UNSIGNED NULL,
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT fk_m6_applicant_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_m6_applicant_identity FOREIGN KEY (canonical_student_id) REFERENCES student(student_id),
    CONSTRAINT fk_m6_applicant_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m6_applicant_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    INDEX ix_m6_applicant_email (institution_id, primary_email),
    INDEX ix_m6_applicant_phone (institution_id, primary_phone),
    INDEX ix_m6_applicant_name (institution_id, display_name),
''',
    'admission_application': '''    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    reviewer_id BIGINT NULL,
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT fk_m6_application_reviewer FOREIGN KEY (reviewer_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m6_application_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m6_application_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    CONSTRAINT uq_m6_application_student UNIQUE (application_id, admitted_student_id),
    CONSTRAINT chk_m6_application_conversion CHECK ((application_status = 'ADMITTED') = (admitted_student_id IS NOT NULL)),
    CONSTRAINT chk_m6_application_eligible CHECK (application_status NOT IN ('ELIGIBLE','SELECTED','ADMITTED') OR eligibility_status = 'ELIGIBLE'),
    INDEX ix_m6_application_queue (programme_id, academic_year_id, application_status, application_id),
''',
    'student_programme_enrolment': '''    application_id BIGINT UNSIGNED NOT NULL UNIQUE,
    transfer_from_id BIGINT UNSIGNED NULL UNIQUE,
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT fk_m6_conversion_student FOREIGN KEY (application_id, student_id) REFERENCES admission_application(application_id, admitted_student_id),
    CONSTRAINT fk_m6_enrolment_scheme_programme FOREIGN KEY (curriculum_scheme_id, programme_id) REFERENCES curriculum_scheme(curriculum_scheme_id, programme_id),
    CONSTRAINT fk_m6_enrolment_transfer FOREIGN KEY (transfer_from_id) REFERENCES student_programme_enrolment(enrolment_id),
    CONSTRAINT chk_m6_enrolment_completion CHECK (expected_completion_date IS NULL OR expected_completion_date >= admission_date),
    CONSTRAINT fk_m6_enrolment_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m6_enrolment_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    INDEX ix_m6_enrolment_queue (programme_id, enrolment_status, admission_academic_year_id),
''',
    'enrolment_status_history': '''    actor_id BIGINT NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source VARCHAR(30) NOT NULL,
    request_id CHAR(36) NOT NULL,
    sequence_number BIGINT UNSIGNED NOT NULL,
    correction_of_id BIGINT UNSIGNED NULL,
    CONSTRAINT fk_m6_history_actor FOREIGN KEY (actor_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m6_history_correction FOREIGN KEY (correction_of_id) REFERENCES enrolment_status_history(enrolment_status_history_id),
    CONSTRAINT uq_m6_history_sequence UNIQUE (enrolment_id, sequence_number),
    CONSTRAINT chk_m6_history_sequence CHECK (sequence_number > 0),
    CONSTRAINT chk_m6_history_reason CHECK (CHAR_LENGTH(TRIM(reason)) > 0),
    INDEX ix_m6_history_asof (enrolment_id, effective_date, sequence_number),
''',
}
for table, extra in additions.items():
    sql = sql.replace(f'CREATE TABLE {table} (\n', f'CREATE TABLE {table} (\n{extra}')
statuses = "ENUM('ACTIVE','ON_BREAK','WITHDRAWN','TRANSFERRED','COMPLETED','TERMINATED')"
sql = sql.replace('old_status VARCHAR(30) NULL', f'old_status {statuses} NULL')
sql = sql.replace('new_status VARCHAR(30) NOT NULL', f'new_status {statuses} NOT NULL')
sql = sql.replace('reason VARCHAR(500) NULL', 'reason VARCHAR(500) NOT NULL')
header = '''-- M6 REVIEW PROPOSAL. NOT APPROVED, NOT APPLIED. Do not execute on a populated database.
-- All omitted FK actions use MySQL RESTRICT/NO ACTION; Django uses PROTECT.
-- Existing M4 model state must receive this supporting unique key in its own migration.
ALTER TABLE curriculum_scheme
    ADD CONSTRAINT uq_m6_scheme_programme UNIQUE (curriculum_scheme_id, programme_id);

'''
(root / 'Manuals/M6_REVISED_SCHEMA_PROPOSAL.sql').write_text(header + sql + '\n', encoding='utf-8')
print('Wrote review-only DDL for four M6 tables; no database changes.')
