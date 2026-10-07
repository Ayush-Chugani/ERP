-- M7 review DDL. Not a production migration; do not execute on populated tables.
-- Existing FK delete/update behavior remains RESTRICT/NO ACTION.
-- Actor IDs are SIGNED BIGINT, matching the live Django custom user table.
-- The M6 migration already supplies uq_m6_scheme_programme on curriculum_scheme.
-- These additional keys must be introduced by migrations owned by M6 and M4:
ALTER TABLE student_programme_enrolment
    ADD CONSTRAINT uq_m7_enrolment_programme UNIQUE (enrolment_id, programme_id);
ALTER TABLE curriculum_course
    ADD CONSTRAINT uq_m7_curriculum_course_identity UNIQUE (curriculum_course_id, course_id);

CREATE TABLE programme_term_offering (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT uq_m7_offering_programme UNIQUE (programme_term_offering_id, programme_id),
    CONSTRAINT fk_m7_offering_scheme_programme FOREIGN KEY (curriculum_scheme_id, programme_id)
        REFERENCES curriculum_scheme(curriculum_scheme_id, programme_id),
    INDEX ix_m7_offering_queue (programme_id, academic_term_id, status),
    CONSTRAINT fk_m7_0_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_0_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    programme_term_offering_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    academic_term_id INT UNSIGNED NOT NULL,
    programme_id SMALLINT UNSIGNED NOT NULL,
    specialization_id SMALLINT UNSIGNED NULL,
    specialization_key SMALLINT UNSIGNED GENERATED ALWAYS AS (COALESCE(specialization_id, 0)) STORED,
    curriculum_scheme_id INT UNSIGNED NOT NULL,
    semester_id TINYINT UNSIGNED NOT NULL,
    status ENUM('PLANNED','REGISTRATION_OPEN','ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'PLANNED',
    CONSTRAINT uq_programme_term UNIQUE (academic_term_id, programme_id, specialization_key, semester_id),
    CONSTRAINT fk_programme_term_academic_term FOREIGN KEY (academic_term_id) REFERENCES academic_term(academic_term_id),
    CONSTRAINT fk_programme_term_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_programme_term_specialization_programme FOREIGN KEY (specialization_id, programme_id)
        REFERENCES programme_specialization(specialization_id, programme_id),
    CONSTRAINT fk_programme_term_scheme FOREIGN KEY (curriculum_scheme_id) REFERENCES curriculum_scheme(curriculum_scheme_id),
    CONSTRAINT fk_programme_term_semester FOREIGN KEY (semester_id) REFERENCES semester(semester_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE class_section (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT chk_m7_section_capacity CHECK (capacity IS NULL OR capacity > 0),
    CONSTRAINT fk_m7_1_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_1_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    class_section_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    programme_term_offering_id BIGINT UNSIGNED NOT NULL,
    section_code VARCHAR(20) NOT NULL,
    section_name VARCHAR(100) NULL,
    capacity SMALLINT UNSIGNED NULL,
    home_room_id INT UNSIGNED NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_class_section UNIQUE (programme_term_offering_id, section_code),
    CONSTRAINT uq_class_section_owner UNIQUE (class_section_id, programme_term_offering_id),
    CONSTRAINT fk_class_section_offering FOREIGN KEY (programme_term_offering_id) REFERENCES programme_term_offering(programme_term_offering_id),
    CONSTRAINT fk_class_section_room FOREIGN KEY (home_room_id) REFERENCES room(room_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE class_batch (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT chk_m7_batch_capacity CHECK (capacity IS NULL OR capacity > 0),
    CONSTRAINT fk_m7_2_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_2_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    class_batch_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_section_id BIGINT UNSIGNED NOT NULL,
    batch_code VARCHAR(20) NOT NULL,
    batch_name VARCHAR(100) NULL,
    capacity SMALLINT UNSIGNED NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_class_batch UNIQUE (class_section_id, batch_code),
    CONSTRAINT uq_class_batch_owner UNIQUE (class_batch_id, class_section_id),
    CONSTRAINT fk_class_batch_section FOREIGN KEY (class_section_id) REFERENCES class_section(class_section_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_term_registration (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    programme_id SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT fk_m7_term_enrolment_programme FOREIGN KEY (enrolment_id, programme_id)
        REFERENCES student_programme_enrolment(enrolment_id, programme_id),
    CONSTRAINT fk_m7_term_offering_programme FOREIGN KEY (programme_term_offering_id, programme_id)
        REFERENCES programme_term_offering(programme_term_offering_id, programme_id),
    CONSTRAINT uq_m7_term_registration_owner UNIQUE (term_registration_id, programme_term_offering_id),
    INDEX ix_m7_section_seats (class_section_id, registration_status),
    INDEX ix_m7_batch_seats (class_batch_id, registration_status),
    CONSTRAINT chk_m7_roll_nonblank CHECK (roll_number IS NULL OR CHAR_LENGTH(TRIM(roll_number)) > 0),
    CONSTRAINT fk_m7_3_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_3_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    term_registration_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    enrolment_id BIGINT UNSIGNED NOT NULL,
    programme_term_offering_id BIGINT UNSIGNED NOT NULL,
    class_section_id BIGINT UNSIGNED NULL,
    class_batch_id BIGINT UNSIGNED NULL,
    roll_number VARCHAR(30) NULL,
    registration_date DATE NOT NULL,
    registration_status ENUM('DRAFT','REGISTERED','APPROVED','CANCELLED','COMPLETED') NOT NULL DEFAULT 'REGISTERED',
    CONSTRAINT uq_student_term_registration UNIQUE (enrolment_id, programme_term_offering_id),
    CONSTRAINT uq_term_roll UNIQUE (programme_term_offering_id, roll_number),
    CONSTRAINT chk_term_registration_batch_section CHECK (class_batch_id IS NULL OR class_section_id IS NOT NULL),
    CONSTRAINT fk_term_registration_enrolment FOREIGN KEY (enrolment_id) REFERENCES student_programme_enrolment(enrolment_id),
    CONSTRAINT fk_term_registration_offering FOREIGN KEY (programme_term_offering_id) REFERENCES programme_term_offering(programme_term_offering_id),
    CONSTRAINT fk_term_registration_section_owner FOREIGN KEY (class_section_id, programme_term_offering_id)
        REFERENCES class_section(class_section_id, programme_term_offering_id),
    CONSTRAINT fk_term_registration_batch_owner FOREIGN KEY (class_batch_id, class_section_id)
        REFERENCES class_batch(class_batch_id, class_section_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE course_offering (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT chk_m7_course_capacity CHECK (registration_capacity IS NULL OR registration_capacity > 0),
    CONSTRAINT fk_m7_curriculum_course_identity FOREIGN KEY (curriculum_course_id, course_id)
        REFERENCES curriculum_course(curriculum_course_id, course_id),
    INDEX ix_m7_course_queue (programme_term_offering_id, status),
    CONSTRAINT fk_m7_4_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_4_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    course_offering_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    programme_term_offering_id BIGINT UNSIGNED NOT NULL,
    curriculum_course_id BIGINT UNSIGNED NULL,
    course_id INT UNSIGNED NOT NULL,
    offering_code VARCHAR(50) NOT NULL UNIQUE,
    registration_capacity SMALLINT UNSIGNED NULL,
    status ENUM('PLANNED','OPEN','ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'PLANNED',
    CONSTRAINT uq_course_offering UNIQUE (programme_term_offering_id, course_id),
    CONSTRAINT uq_course_offering_owner UNIQUE (course_offering_id, programme_term_offering_id),
    CONSTRAINT fk_course_offering_programme_term FOREIGN KEY (programme_term_offering_id) REFERENCES programme_term_offering(programme_term_offering_id),
    CONSTRAINT fk_course_offering_curriculum FOREIGN KEY (curriculum_course_id) REFERENCES curriculum_course(curriculum_course_id),
    CONSTRAINT fk_course_offering_course FOREIGN KEY (course_id) REFERENCES course_catalog(course_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE course_offering_section (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    CONSTRAINT uq_m7_mapping_session UNIQUE (course_offering_section_id, session_type),
    CONSTRAINT fk_m7_5_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_5_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    course_offering_section_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    programme_term_offering_id BIGINT UNSIGNED NOT NULL,
    class_section_id BIGINT UNSIGNED NOT NULL,
    class_batch_id BIGINT UNSIGNED NULL,
    class_batch_key BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(class_batch_id, 0)) STORED,
    session_type ENUM('LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER') NOT NULL,
    CONSTRAINT uq_course_offering_section UNIQUE (course_offering_id, class_section_id, class_batch_key, session_type),
    CONSTRAINT uq_course_offering_section_course UNIQUE (course_offering_section_id, course_offering_id),
    CONSTRAINT uq_course_offering_section_owner UNIQUE (course_offering_section_id, programme_term_offering_id),
    CONSTRAINT chk_course_offering_section_batch CHECK (class_batch_id IS NULL OR class_section_id IS NOT NULL),
    CONSTRAINT fk_course_offering_section_offering_owner FOREIGN KEY (course_offering_id, programme_term_offering_id)
        REFERENCES course_offering(course_offering_id, programme_term_offering_id),
    CONSTRAINT fk_course_offering_section_section_owner FOREIGN KEY (class_section_id, programme_term_offering_id)
        REFERENCES class_section(class_section_id, programme_term_offering_id),
    CONSTRAINT fk_course_offering_section_batch_owner FOREIGN KEY (class_batch_id, class_section_id)
        REFERENCES class_batch(class_batch_id, class_section_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_course_registration (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    programme_term_offering_id BIGINT UNSIGNED NOT NULL,
    CONSTRAINT fk_m7_registration_term_owner FOREIGN KEY (term_registration_id, programme_term_offering_id)
        REFERENCES student_term_registration(term_registration_id, programme_term_offering_id),
    CONSTRAINT fk_m7_registration_offering_owner FOREIGN KEY (course_offering_id, programme_term_offering_id)
        REFERENCES course_offering(course_offering_id, programme_term_offering_id),
    INDEX ix_m7_course_seats (course_offering_id, registration_status),
    CONSTRAINT fk_m7_6_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_6_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    course_registration_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    term_registration_id BIGINT UNSIGNED NOT NULL,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    registration_type ENUM('REGULAR','ELECTIVE','BACKLOG','REPEAT','IMPROVEMENT','AUDIT','CREDIT_TRANSFER') NOT NULL DEFAULT 'REGULAR',
    registration_date DATE NOT NULL,
    registration_status ENUM('REGISTERED','APPROVED','DROPPED','WITHDRAWN','COMPLETED') NOT NULL DEFAULT 'REGISTERED',
    CONSTRAINT uq_student_course_registration UNIQUE (term_registration_id, course_offering_id),
    CONSTRAINT uq_course_registration_owner UNIQUE (course_registration_id, course_offering_id),
    CONSTRAINT fk_course_registration_term FOREIGN KEY (term_registration_id) REFERENCES student_term_registration(term_registration_id),
    CONSTRAINT fk_course_registration_offering FOREIGN KEY (course_offering_id) REFERENCES course_offering(course_offering_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Explicit roster membership binds a registered course to the exact lecture/lab/tutorial section.
CREATE TABLE course_offering_section_student (
    version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    session_type ENUM('LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER') NOT NULL,
    active_registration_key BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN roster_status = 'ACTIVE' THEN course_registration_id ELSE NULL END
    ) STORED,
    CONSTRAINT fk_m7_roster_session FOREIGN KEY (course_offering_section_id, session_type)
        REFERENCES course_offering_section(course_offering_section_id, session_type),
    CONSTRAINT uq_m7_active_roster_session UNIQUE (active_registration_key, session_type),
    CONSTRAINT chk_m7_roster_open CHECK (roster_status <> 'ACTIVE' OR effective_to IS NULL),
    INDEX ix_m7_roster_current (course_offering_section_id, roster_status, effective_from, effective_to),
    CONSTRAINT fk_m7_7_creator FOREIGN KEY (created_by_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_m7_7_editor FOREIGN KEY (updated_by_id) REFERENCES user_account(user_id),
    course_offering_section_student_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_section_id BIGINT UNSIGNED NOT NULL,
    course_registration_id BIGINT UNSIGNED NOT NULL,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    roster_status ENUM('ACTIVE','DROPPED','TRANSFERRED','COMPLETED') NOT NULL DEFAULT 'ACTIVE',
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    CONSTRAINT uq_course_section_student UNIQUE (course_offering_section_id, course_registration_id, effective_from),
    CONSTRAINT uq_course_section_student_owner UNIQUE (course_offering_section_student_id, course_offering_section_id),
    CONSTRAINT chk_course_section_student_dates CHECK (effective_to IS NULL OR effective_to > effective_from),
    CONSTRAINT fk_roster_section_course FOREIGN KEY (course_offering_section_id, course_offering_id)
        REFERENCES course_offering_section(course_offering_section_id, course_offering_id),
    CONSTRAINT fk_roster_registration_course FOREIGN KEY (course_registration_id, course_offering_id)
        REFERENCES student_course_registration(course_registration_id, course_offering_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
