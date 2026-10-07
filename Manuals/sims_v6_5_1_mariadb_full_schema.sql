-- REVIEW REVISION: 2026-09-14. Read SIMS_schema_review.md before installation.
-- Full schema for an EMPTY database only; not an upgrade migration.
-- Static review completed; execution on MySQL and Django integration remain required.
-- Select a database created with utf8mb4 / utf8mb4_unicode_ci before sourcing.
-- Use mysql without --force. MySQL DDL is not one rollbackable transaction.
-- Tenant authorization MUST use a context-aware service, not a view alone.
-- Legacy RBAC catalogue is retained for reconciliation; user migration is separate.

-- =============================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS)
-- Version 6.5.1 REVIEW CANDIDATE - Django Auth Plugin-Ready Modular Monolith - MySQL 8.0.16+
-- Enforces programme-specialization ownership, deterministic nullable uniqueness,
-- section/batch/course ownership, attendance rosters, assessment-course integrity,
-- HR single-current rules, RBAC scope/effective permissions, unified admission payments,
-- and financial arithmetic/allocation/refund/benefit integrity.
-- Extended with Employee Qualification, Experience, Bank, PAN, Aadhaar and Evidence Management
-- Naming: singular snake_case; PK: <table>_id; FK: referenced PK name
-- Character set: utf8mb4; Engine: InnoDB; Timezone recommended: UTC
-- =============================================================

-- CREATE DATABASE IF NOT EXISTS sims_v6
--  CHARACTER SET utf8mb4
--  COLLATE utf8mb4_unicode_ci;
--  USE sims_v6;

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET SESSION time_zone = '+00:00';
SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================
-- 1. COMMON REFERENCE MODULE
-- =============================================================
CREATE TABLE country (
    country_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    iso_code CHAR(2) NOT NULL UNIQUE,
    country_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE state (
    state_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    country_id SMALLINT UNSIGNED NOT NULL,
    state_code VARCHAR(10) NOT NULL,
    state_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_state_country_code UNIQUE (country_id, state_code),
    CONSTRAINT uq_state_country_name UNIQUE (country_id, state_name),
    CONSTRAINT fk_state_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE gender (
    gender_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    gender_code VARCHAR(20) NOT NULL UNIQUE,
    gender_name VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE blood_group (
    blood_group_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    blood_group_code VARCHAR(5) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE religion (
    religion_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    religion_code VARCHAR(20) NULL UNIQUE,
    religion_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE social_category (
    social_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(20) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE caste (
    caste_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    social_category_id SMALLINT UNSIGNED NULL,
    caste_code VARCHAR(30) NULL UNIQUE,
    caste_name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_caste_name_category UNIQUE (social_category_id, caste_name),
    CONSTRAINT fk_caste_social_category FOREIGN KEY (social_category_id) REFERENCES social_category(social_category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sub_caste (
    sub_caste_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    caste_id INT UNSIGNED NOT NULL,
    sub_caste_code VARCHAR(30) NULL,
    sub_caste_name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_sub_caste UNIQUE (caste_id, sub_caste_name),
    CONSTRAINT fk_sub_caste_caste FOREIGN KEY (caste_id) REFERENCES caste(caste_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE admission_category (
    admission_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(30) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE document_type (
    document_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_code VARCHAR(30) NOT NULL UNIQUE,
    document_name VARCHAR(100) NOT NULL UNIQUE,
    requires_verification BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Karnataka reference baseline (source review: 2026-09-21).
-- Sources and limitations: Manuals/KARNATAKA_REFERENCE_SEEDS.md.
-- Local application codes, not government-issued religion identifiers.
-- Religion does not determine caste, category, or reservation eligibility.
-- Repeated execution preserves existing rows and administrator edits.
INSERT INTO country (iso_code, country_name)
SELECT 'IN', 'India'
WHERE NOT EXISTS (SELECT 1 FROM country WHERE iso_code='IN' OR country_name='India');

INSERT INTO state (country_id, state_code, state_name)
SELECT country_id, 'KA', 'Karnataka' FROM country c
WHERE c.iso_code='IN' AND NOT EXISTS (
    SELECT 1 FROM state s WHERE s.country_id=c.country_id
    AND (s.state_code='KA' OR s.state_name='Karnataka')
);

INSERT INTO religion (religion_code, religion_name)
SELECT seed.code, seed.name FROM (
    SELECT 'HINDU' AS code, 'Hindu' AS name
    UNION ALL SELECT 'MUSLIM', 'Muslim'
    UNION ALL SELECT 'CHRISTIAN', 'Christian'
    UNION ALL SELECT 'SIKH', 'Sikh'
    UNION ALL SELECT 'BUDDHIST', 'Buddhist'
    UNION ALL SELECT 'JAIN', 'Jain'
    UNION ALL SELECT 'PARSI', 'Parsi'
) seed
WHERE NOT EXISTS (
    SELECT 1 FROM religion r WHERE r.religion_code=seed.code OR r.religion_name=seed.name
);

-- KEA UGCET-2026 bulletin, 16 January 2026: category labels only.
-- KA_* are local keys. General Merit is not a caste. No quota percentages or
-- automatic eligibility mappings are seeded. Verify certificates and amendments.
INSERT INTO social_category (category_code, category_name)
SELECT seed.code, seed.name FROM (
    SELECT 'KA_CAT1' AS code, 'Karnataka Category 1' AS name
    UNION ALL SELECT 'KA_2A', 'Karnataka Category 2A'
    UNION ALL SELECT 'KA_2B', 'Karnataka Category 2B'
    UNION ALL SELECT 'KA_3A', 'Karnataka Category 3A'
    UNION ALL SELECT 'KA_3B', 'Karnataka Category 3B'
    UNION ALL SELECT 'KA_SC', 'Karnataka Scheduled Caste'
    UNION ALL SELECT 'KA_ST', 'Karnataka Scheduled Tribe'
) seed
WHERE NOT EXISTS (
    SELECT 1 FROM social_category r WHERE r.category_code=seed.code OR r.category_name=seed.name
);

INSERT INTO admission_category (category_code, category_name)
SELECT seed.code, seed.name FROM (
    SELECT 'KA_CAT1' AS code, 'Karnataka Category 1' AS name
    UNION ALL SELECT 'KA_2A', 'Karnataka Category 2A'
    UNION ALL SELECT 'KA_2B', 'Karnataka Category 2B'
    UNION ALL SELECT 'KA_3A', 'Karnataka Category 3A'
    UNION ALL SELECT 'KA_3B', 'Karnataka Category 3B'
    UNION ALL SELECT 'KA_SC', 'Karnataka Scheduled Caste'
    UNION ALL SELECT 'KA_ST', 'Karnataka Scheduled Tribe'
    UNION ALL SELECT 'KA_GM', 'Karnataka General Merit'
    UNION ALL SELECT 'KA_SCA', 'Karnataka Scheduled Caste - Internal Category A'
    UNION ALL SELECT 'KA_SCB', 'Karnataka Scheduled Caste - Internal Category B'
    UNION ALL SELECT 'KA_SCC', 'Karnataka Scheduled Caste - Internal Category C'
) seed
WHERE NOT EXISTS (
    SELECT 1 FROM admission_category r WHERE r.category_code=seed.code OR r.category_name=seed.name
);

-- Individual caste/sub-caste mappings await a verified consolidated admission list.
-- Do not substitute the Central OBC list or infer caste from religion.
-- A postal directory requires separate district/post-office/PIN-code tables.

-- =============================================================
-- 2. UNIVERSITY AND INSTITUTION STRUCTURE MODULE
-- =============================================================
CREATE TABLE university (
    university_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    university_code VARCHAR(30) NOT NULL UNIQUE,
    university_name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(250) NULL,
    university_type ENUM('CENTRAL','STATE','PRIVATE','DEEMED','OTHER') NOT NULL DEFAULT 'OTHER',
    website_url VARCHAR(255) NULL,
    email VARCHAR(254) NULL,
    phone VARCHAR(25) NULL,
    address_line_1 VARCHAR(200) NULL,
    address_line_2 VARCHAR(200) NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    postal_code VARCHAR(12) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_university_state FOREIGN KEY (state_id) REFERENCES state(state_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE institution (
    institution_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    university_id SMALLINT UNSIGNED NOT NULL,
    institution_code VARCHAR(20) NOT NULL UNIQUE,
    institution_name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(250) NULL,
    website_url VARCHAR(255) NULL,
    email VARCHAR(254) NULL,
    phone VARCHAR(25) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_institution_university FOREIGN KEY (university_id) REFERENCES university(university_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE campus (
    campus_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    campus_code VARCHAR(20) NOT NULL,
    campus_name VARCHAR(150) NOT NULL,
    address_line_1 VARCHAR(200) NULL,
    address_line_2 VARCHAR(200) NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    postal_code VARCHAR(12) NULL,
    phone VARCHAR(25) NULL,
    email VARCHAR(254) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_campus_code UNIQUE (institution_id, campus_code),
    CONSTRAINT fk_campus_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_campus_state FOREIGN KEY (state_id) REFERENCES state(state_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE department (
    department_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    campus_id SMALLINT UNSIGNED NOT NULL,
    department_code VARCHAR(20) NOT NULL,
    department_name VARCHAR(150) NOT NULL,
    department_type VARCHAR(30) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_department_code UNIQUE (campus_id, department_code),
    CONSTRAINT uq_department_id_campus UNIQUE (department_id, campus_id),
    CONSTRAINT fk_department_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE programme (
    programme_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    department_id SMALLINT UNSIGNED NOT NULL,
    programme_code VARCHAR(30) NOT NULL UNIQUE,
    programme_name VARCHAR(150) NOT NULL,
    award_name VARCHAR(150) NULL,
    programme_level ENUM('UG','PG','DIPLOMA','CERTIFICATE','DOCTORAL','OTHER') NOT NULL,
    duration_semesters TINYINT UNSIGNED NOT NULL,
    maximum_duration_semesters TINYINT UNSIGNED NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_programme_duration CHECK (duration_semesters > 0
        AND (maximum_duration_semesters IS NULL OR maximum_duration_semesters >= duration_semesters)),
    CONSTRAINT fk_programme_department FOREIGN KEY (department_id) REFERENCES department(department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE programme_specialization (
    specialization_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    programme_id SMALLINT UNSIGNED NOT NULL,
    specialization_code VARCHAR(30) NOT NULL,
    specialization_name VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_specialization_code UNIQUE (programme_id, specialization_code),
    CONSTRAINT uq_specialization_programme UNIQUE (specialization_id, programme_id),
    CONSTRAINT fk_specialization_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE building (
    building_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    campus_id SMALLINT UNSIGNED NOT NULL,
    building_code VARCHAR(20) NOT NULL,
    building_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_building_code UNIQUE (campus_id, building_code),
    CONSTRAINT fk_building_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE room (
    room_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    building_id SMALLINT UNSIGNED NOT NULL,
    room_code VARCHAR(20) NOT NULL,
    room_name VARCHAR(100) NULL,
    room_type ENUM('CLASSROOM','LAB','SEMINAR_HALL','AUDITORIUM','OFFICE','OTHER') NOT NULL,
    capacity SMALLINT UNSIGNED NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_room_code UNIQUE (building_id, room_code),
    CONSTRAINT fk_room_building FOREIGN KEY (building_id) REFERENCES building(building_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- BEGIN KLE TECH SECTION 2 SEED
-- Verified website snapshot: 2026-09-21. See Manuals/KLE_TECH_STRUCTURE_SEEDS.md.
-- Local SIMS codes, not CET/COMEDK/accreditation identifiers.
-- One institution record represents the university's own multi-campus operations.
-- Prerequisite: Section 1 India (IN) and Karnataka (KA), and Section 2 tables.
-- Additive: preserves existing codes, names, administrator edits and active flags.
-- Run serially. No hard-coded IDs, INSERT IGNORE, REPLACE, or destructive updates.

INSERT INTO university (university_code, university_name, legal_name, university_type,
    website_url, email, phone, address_line_1, address_line_2, city, state_id, postal_code)
SELECT 'KLETECH', 'KLE Technological University', 'KLE Technological University', 'PRIVATE',
    'https://www.kletech.ac.in/', 'info@kletech.ac.in', '+91-836-2378103',
    'B. V. Bhoomaraddi Campus', 'Vidyanagar', 'Hubballi', s.state_id, '580031'
FROM state s JOIN country c ON c.country_id=s.country_id
WHERE c.iso_code='IN' AND s.state_code='KA'
  AND NOT EXISTS (SELECT 1 FROM university WHERE university_code='KLETECH'
      OR university_name='KLE Technological University');

INSERT INTO institution (university_id, institution_code, institution_name, legal_name,
    website_url, email, phone)
SELECT u.university_id, 'KLETECH', 'KLE Technological University', 'KLE Technological University',
    'https://www.kletech.ac.in/', 'info@kletech.ac.in', '+91-836-2378103'
FROM university u
WHERE u.university_code='KLETECH'
  AND NOT EXISTS (SELECT 1 FROM institution i WHERE i.institution_code='KLETECH'
      OR (i.university_id=u.university_id AND i.institution_name='KLE Technological University'));

-- Campus names/addresses: https://www.kletech.ac.in/contact-us
INSERT INTO campus (institution_id, campus_code, campus_name, address_line_1,
    address_line_2, city, state_id, postal_code)
SELECT i.institution_id, seed.code, seed.name, seed.line1, seed.line2,
    seed.city, s.state_id, seed.pin
FROM (
    SELECT 'HUBBALLI' AS code, 'B. V. Bhoomaraddi Campus' AS name, 'B. V. Bhoomaraddi Campus' AS line1, 'Vidyanagar' AS line2, 'Hubballi' AS city, '580031' AS pin
    UNION ALL SELECT 'BELAGAVI', 'Dr. M. S. Sheshgiri Campus', 'Angol Main Road', 'Udyambag', 'Belagavi', '590008'
    UNION ALL SELECT 'BENGALURU', 'KLE Law Campus', 'CA-2, Sir M. Vishweshwaraiah Layout', 'V Block, Ullal', 'Bengaluru', '560091'
) seed
JOIN institution i ON i.institution_code='KLETECH'
JOIN university u ON u.university_id=i.university_id AND u.university_code='KLETECH'
JOIN country co ON co.iso_code='IN'
JOIN state s ON s.country_id=co.country_id AND s.state_code='KA'
WHERE NOT EXISTS (SELECT 1 FROM campus c WHERE c.institution_id=i.institution_id
    AND (c.campus_code=seed.code OR c.campus_name=seed.name));

-- Campus-specific published schools/departments; schools use department_type SCHOOL.
-- https://www.kletech.ac.in/hubballi/academic/schools-departemts
-- https://www.kletech.ac.in/belagavi/academic/department
INSERT INTO department (campus_id, department_code, department_name, department_type)
SELECT c.campus_id, seed.code, seed.name, seed.kind
FROM (
    SELECT 'HUBBALLI' AS campus_code, 'CSE' AS code, 'School of Computer Science and Engineering' AS name, 'SCHOOL' AS kind
    UNION ALL SELECT 'HUBBALLI', 'ME', 'School of Mechanical Engineering', 'SCHOOL'
    UNION ALL SELECT 'HUBBALLI', 'CE', 'School of Civil Engineering', 'SCHOOL'
    UNION ALL SELECT 'HUBBALLI', 'ECE', 'School of Electronics & Communication Engineering', 'SCHOOL'
    UNION ALL SELECT 'HUBBALLI', 'EEE', 'School of Electrical & Electronics Engineering', 'SCHOOL'
    UNION ALL SELECT 'HUBBALLI', 'AR', 'Department of Automation & Robotics', 'DEPARTMENT'
    UNION ALL SELECT 'HUBBALLI', 'BT', 'Department of Biotechnology', 'DEPARTMENT'
    UNION ALL SELECT 'HUBBALLI', 'ARCH', 'School of Architecture', 'SCHOOL'
    UNION ALL SELECT 'HUBBALLI', 'CA', 'Department of Computer Application', 'DEPARTMENT'
    UNION ALL SELECT 'HUBBALLI', 'MSR', 'School of Management Studies and Research', 'SCHOOL'
    UNION ALL SELECT 'HUBBALLI', 'COM', 'Department of Commerce', 'DEPARTMENT'
    UNION ALL SELECT 'HUBBALLI', 'FD', 'Department of Fashion Design', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'ECE', 'Department of Electronics and Communication Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'CHE', 'Department of Chemical Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'ME', 'Department of Mechanical Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'CE', 'Department of Civil Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'CSE', 'Department of Computer Science and Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'EEE', 'Department of Electrical & Electronics Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'CA', 'Department of Computer Applications', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'MSR', 'Department of Management Studies and Research', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'BME', 'Department of Bio Medical Engineering', 'DEPARTMENT'
    UNION ALL SELECT 'BELAGAVI', 'ESH', 'Department of Engineering Science and Humanities', 'DEPARTMENT'
) seed
JOIN institution i ON i.institution_code='KLETECH'
JOIN university u ON u.university_id=i.university_id AND u.university_code='KLETECH'
JOIN campus c ON c.institution_id=i.institution_id AND c.campus_code=seed.campus_code
WHERE NOT EXISTS (SELECT 1 FROM department d WHERE d.campus_id=c.campus_id
    AND (d.department_code=seed.code OR d.department_name=seed.name));

-- Hubballi B.E. programmes: campus catalogue + admission2026 explicitly lists 8 semesters.
-- https://www.kletech.ac.in/admission2026
-- CSE(AI) and Electronics(VLSI) are advertised as separate degrees, not specialization rows.
-- Ownership is the corresponding disciplinary school/department in the SIMS hierarchy.
INSERT INTO programme (department_id, programme_code, programme_name, award_name,
    programme_level, duration_semesters)
SELECT d.department_id, seed.code, seed.name, 'Bachelor of Engineering', 'UG', 8
FROM (
    SELECT 'KLE_HBL_BE_AR' AS code, 'AR' AS department_code, 'B.E. Automation & Robotics' AS name
    UNION ALL SELECT 'KLE_HBL_BE_BT', 'BT', 'B.E. Biotechnology'
    UNION ALL SELECT 'KLE_HBL_BE_CE', 'CE', 'B.E. Civil Engineering'
    UNION ALL SELECT 'KLE_HBL_BE_CSE', 'CSE', 'B.E. Computer Science and Engineering'
    UNION ALL SELECT 'KLE_HBL_BE_CSEAI', 'CSE', 'B.E. Computer Science and Engineering (Artificial Intelligence)'
    UNION ALL SELECT 'KLE_HBL_BE_EEE', 'EEE', 'B.E. Electrical & Electronics Engineering'
    UNION ALL SELECT 'KLE_HBL_BE_ECE', 'ECE', 'B.E. Electronics & Communication Engineering'
    UNION ALL SELECT 'KLE_HBL_BE_EVLSI', 'ECE', 'B.E. Electronics Engineering (VLSI Design & Technology)'
    UNION ALL SELECT 'KLE_HBL_BE_ME', 'ME', 'B.E. Mechanical Engineering'
) seed
JOIN institution i ON i.institution_code='KLETECH'
JOIN university u ON u.university_id=i.university_id AND u.university_code='KLETECH'
JOIN campus c ON c.institution_id=i.institution_id AND c.campus_code='HUBBALLI'
JOIN department d ON d.campus_id=c.campus_id AND d.department_code=seed.department_code
WHERE NOT EXISTS (SELECT 1 FROM programme p WHERE p.programme_code=seed.code
    OR (p.department_id=d.department_id AND p.programme_name=seed.name));

-- Other programmes, specializations, buildings and rooms await verified details.
-- In particular, programme duration is mandatory: no guessed duration or room capacity.
-- END KLE TECH SECTION 2 SEED

-- =============================================================
-- 3. ACADEMIC CALENDAR MODULE
-- =============================================================
CREATE TABLE academic_year (
    academic_year_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    year_code VARCHAR(9) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status ENUM('PLANNED','ACTIVE','CLOSED') NOT NULL DEFAULT 'PLANNED',
    CONSTRAINT chk_academic_year_dates CHECK (end_date > start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE academic_term (
    academic_term_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    term_code VARCHAR(20) NOT NULL,
    term_name VARCHAR(100) NOT NULL,
    term_type ENUM('ODD','EVEN','SUMMER','ANNUAL','OTHER') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    registration_start_date DATE NULL,
    registration_end_date DATE NULL,
    status ENUM('PLANNED','REGISTRATION_OPEN','ACTIVE','CLOSED') NOT NULL DEFAULT 'PLANNED',
    CONSTRAINT uq_term_code UNIQUE (academic_year_id, term_code),
    CONSTRAINT chk_term_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_term_registration_dates CHECK (registration_start_date IS NULL
        OR registration_end_date IS NULL OR registration_end_date >= registration_start_date),
    CONSTRAINT fk_term_academic_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE semester (
    semester_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    semester_number TINYINT UNSIGNED NOT NULL UNIQUE,
    semester_name VARCHAR(50) NOT NULL UNIQUE,
    CONSTRAINT chk_semester_number CHECK (semester_number > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE time_slot (
    time_slot_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    campus_id SMALLINT UNSIGNED NOT NULL,
    slot_code VARCHAR(20) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_break BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_time_slot UNIQUE (campus_id, slot_code),
    CONSTRAINT chk_time_slot CHECK (end_time > start_time),
    CONSTRAINT fk_time_slot_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 4. CURRICULUM AND COURSE CATALOG MODULE
-- =============================================================
CREATE TABLE course_category (
    course_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(30) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    is_graded BOOLEAN NOT NULL DEFAULT TRUE,
    contributes_to_gpa BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE course_catalog (
    course_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    owning_department_id SMALLINT UNSIGNED NOT NULL,
    course_category_id SMALLINT UNSIGNED NOT NULL,
    course_code VARCHAR(30) NOT NULL UNIQUE,
    course_title VARCHAR(200) NOT NULL,
    short_title VARCHAR(80) NULL,
    course_type ENUM('THEORY','LAB','THEORY_LAB','PROJECT','SEMINAR','INTERNSHIP','OTHER') NOT NULL,
    lecture_hours DECIMAL(4,1) NOT NULL DEFAULT 0,
    tutorial_hours DECIMAL(4,1) NOT NULL DEFAULT 0,
    practical_hours DECIMAL(4,1) NOT NULL DEFAULT 0,
    self_study_hours DECIMAL(4,1) NOT NULL DEFAULT 0,
    credits DECIMAL(4,1) NOT NULL DEFAULT 0,
    effective_from DATE NULL,
    effective_to DATE NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_course_nonnegative_values CHECK (lecture_hours >= 0 AND tutorial_hours >= 0
        AND practical_hours >= 0 AND self_study_hours >= 0 AND credits >= 0),
    CONSTRAINT chk_course_effective_dates CHECK (effective_from IS NULL OR effective_to IS NULL
        OR effective_to >= effective_from),
    CONSTRAINT fk_course_department FOREIGN KEY (owning_department_id) REFERENCES department(department_id),
    CONSTRAINT fk_course_category FOREIGN KEY (course_category_id) REFERENCES course_category(course_category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE curriculum_scheme (
    curriculum_scheme_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    programme_id SMALLINT UNSIGNED NOT NULL,
    specialization_id SMALLINT UNSIGNED NULL,
    scheme_code VARCHAR(30) NOT NULL UNIQUE,
    scheme_name VARCHAR(150) NOT NULL,
    regulation_year YEAR NOT NULL,
    total_credits DECIMAL(6,1) NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    status ENUM('DRAFT','ACTIVE','RETIRED') NOT NULL DEFAULT 'DRAFT',
    CONSTRAINT fk_scheme_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_scheme_specialization_programme FOREIGN KEY (specialization_id, programme_id)
        REFERENCES programme_specialization(specialization_id, programme_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE curriculum_course (
    curriculum_course_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    curriculum_scheme_id INT UNSIGNED NOT NULL,
    semester_id TINYINT UNSIGNED NOT NULL,
    course_id INT UNSIGNED NOT NULL,
    course_category_id SMALLINT UNSIGNED NOT NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    elective_group_code VARCHAR(30) NULL,
    display_order SMALLINT UNSIGNED NULL,
    internal_max_marks DECIMAL(6,2) NOT NULL DEFAULT 0,
    external_max_marks DECIMAL(6,2) NOT NULL DEFAULT 0,
    passing_marks DECIMAL(6,2) NULL,
    exam_duration_minutes SMALLINT UNSIGNED NULL,
    CONSTRAINT uq_curriculum_course UNIQUE (curriculum_scheme_id, semester_id, course_id),
    CONSTRAINT fk_curriculum_course_scheme FOREIGN KEY (curriculum_scheme_id) REFERENCES curriculum_scheme(curriculum_scheme_id),
    CONSTRAINT fk_curriculum_course_semester FOREIGN KEY (semester_id) REFERENCES semester(semester_id),
    CONSTRAINT fk_curriculum_course_course FOREIGN KEY (course_id) REFERENCES course_catalog(course_id),
    CONSTRAINT fk_curriculum_course_category FOREIGN KEY (course_category_id) REFERENCES course_category(course_category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE course_prerequisite (
    course_id INT UNSIGNED NOT NULL,
    prerequisite_course_id INT UNSIGNED NOT NULL,
    minimum_grade VARCHAR(5) NULL,
    PRIMARY KEY (course_id, prerequisite_course_id),
    CONSTRAINT chk_prerequisite_not_self CHECK (course_id <> prerequisite_course_id),
    CONSTRAINT fk_prerequisite_course FOREIGN KEY (course_id) REFERENCES course_catalog(course_id),
    CONSTRAINT fk_prerequisite_required FOREIGN KEY (prerequisite_course_id) REFERENCES course_catalog(course_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 5. STUDENT AND STAFF MASTER MODULES (INDEPENDENT ROOT ENTITIES)
-- Student and employee are intentionally NOT inherited from a generic person table.
-- Shared demographic/reference masters remain reusable through foreign keys.
-- =============================================================
CREATE TABLE student (
    student_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_number VARCHAR(30) NOT NULL UNIQUE,
    university_seat_number VARCHAR(30) NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100) NULL,
    last_name VARCHAR(100) NULL,
    display_name VARCHAR(250) NOT NULL,
    date_of_birth DATE NULL,
    gender_id TINYINT UNSIGNED NULL,
    blood_group_id TINYINT UNSIGNED NULL,
    primary_email VARCHAR(254) NULL,
    primary_phone VARCHAR(25) NULL,
    nationality_country_id SMALLINT UNSIGNED NULL,
    religion_id SMALLINT UNSIGNED NULL,
    social_category_id SMALLINT UNSIGNED NULL,
    caste_id INT UNSIGNED NULL,
    sub_caste_id INT UNSIGNED NULL,
    photo_url VARCHAR(500) NULL,
    admission_date DATE NULL,
    student_status ENUM('APPLICANT','ACTIVE','SUSPENDED','WITHDRAWN','COMPLETED','ALUMNUS','DECEASED') NOT NULL DEFAULT 'ACTIVE',
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_primary_email UNIQUE (primary_email),
    CONSTRAINT fk_student_gender FOREIGN KEY (gender_id) REFERENCES gender(gender_id),
    CONSTRAINT fk_student_blood_group FOREIGN KEY (blood_group_id) REFERENCES blood_group(blood_group_id),
    CONSTRAINT fk_student_nationality FOREIGN KEY (nationality_country_id) REFERENCES country(country_id),
    CONSTRAINT fk_student_religion FOREIGN KEY (religion_id) REFERENCES religion(religion_id),
    CONSTRAINT fk_student_social_category FOREIGN KEY (social_category_id) REFERENCES social_category(social_category_id),
    CONSTRAINT fk_student_caste FOREIGN KEY (caste_id) REFERENCES caste(caste_id),
    CONSTRAINT fk_student_sub_caste FOREIGN KEY (sub_caste_id) REFERENCES sub_caste(sub_caste_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_address (
    student_address_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    address_type ENUM('PERMANENT','CURRENT','CORRESPONDENCE','OTHER') NOT NULL,
    address_line_1 VARCHAR(200) NOT NULL,
    address_line_2 VARCHAR(200) NULL,
    city VARCHAR(100) NOT NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NOT NULL,
    postal_code VARCHAR(12) NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    current_primary_student_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_primary=TRUE AND valid_to IS NULL THEN student_id ELSE NULL END
    ) STORED,
    CONSTRAINT uq_student_current_primary_address UNIQUE (current_primary_student_id),
    CONSTRAINT chk_student_address_dates CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CONSTRAINT fk_student_address_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_address_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_student_address_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_parent_guardian (
    student_parent_guardian_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    relationship_type ENUM('FATHER','MOTHER','GUARDIAN','OTHER') NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    occupation VARCHAR(150) NULL,
    annual_income DECIMAL(14,2) NULL,
    email VARCHAR(254) NULL,
    phone VARCHAR(25) NULL,
    address_line_1 VARCHAR(200) NULL,
    address_line_2 VARCHAR(200) NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    postal_code VARCHAR(12) NULL,
    is_primary_contact BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_parent_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_parent_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_parent_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_residence (
    student_residence_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    residence_type ENUM('HOSTEL','DAY_SCHOLAR','PG','RENTED','RELATIVE','OTHER') NOT NULL,
    hostel_name VARCHAR(150) NULL,
    room_number VARCHAR(30) NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_residence_student FOREIGN KEY (student_id) REFERENCES student(student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_previous_education (
    previous_education_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    qualification_level ENUM('SSLC','PUC_I','PUC_II','DIPLOMA','UG','PG','OTHER') NOT NULL,
    examination_name VARCHAR(150) NULL,
    institution_name VARCHAR(250) NOT NULL,
    board_university VARCHAR(200) NULL,
    registration_number VARCHAR(50) NULL,
    month_of_passing TINYINT UNSIGNED NULL,
    year_of_passing YEAR NULL,
    result_class VARCHAR(50) NULL,
    marks_obtained DECIMAL(8,2) NULL,
    maximum_marks DECIMAL(8,2) NULL,
    percentage DECIMAL(5,2) NULL,
    CONSTRAINT uq_previous_education UNIQUE (student_id, qualification_level, registration_number),
    CONSTRAINT fk_previous_education_student FOREIGN KEY (student_id) REFERENCES student(student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_entrance_exam (
    student_entrance_exam_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    exam_name VARCHAR(100) NOT NULL,
    registration_number VARCHAR(50) NULL,
    rank_number INT UNSIGNED NULL,
    score DECIMAL(8,2) NULL,
    exam_year YEAR NULL,
    allotment_date DATE NULL,
    registration_fee DECIMAL(12,2) NULL,
    CONSTRAINT uq_student_exam UNIQUE (student_id, exam_name, exam_year),
    CONSTRAINT fk_student_exam_student FOREIGN KEY (student_id) REFERENCES student(student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE staff_type (
    staff_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(30) NOT NULL UNIQUE,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE staff_category (
    staff_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_type_id TINYINT UNSIGNED NOT NULL,
    category_code VARCHAR(50) NOT NULL UNIQUE,
    category_name VARCHAR(150) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_staff_category_type FOREIGN KEY (staff_type_id) REFERENCES staff_type(staff_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employment_source (
    employment_source_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    source_code VARCHAR(30) NOT NULL UNIQUE,
    source_name VARCHAR(100) NOT NULL UNIQUE,
    is_external BOOLEAN NOT NULL DEFAULT FALSE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE external_agency (
    external_agency_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    agency_code VARCHAR(50) NOT NULL,
    agency_name VARCHAR(200) NOT NULL,
    service_type VARCHAR(100) NULL,
    contact_person VARCHAR(150) NULL,
    phone VARCHAR(25) NULL,
    email VARCHAR(254) NULL,
    contract_start_date DATE NULL,
    contract_end_date DATE NULL,
    address VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_external_agency UNIQUE (institution_id, agency_code),
    CONSTRAINT chk_external_agency_contract_dates CHECK (contract_end_date IS NULL OR contract_start_date IS NULL OR contract_end_date >= contract_start_date),
    CONSTRAINT fk_external_agency_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE designation (
    designation_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_category_id SMALLINT UNSIGNED NOT NULL,
    designation_code VARCHAR(30) NOT NULL UNIQUE,
    designation_name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_designation_category_name UNIQUE (staff_category_id, designation_name),
    CONSTRAINT fk_designation_staff_category FOREIGN KEY (staff_category_id) REFERENCES staff_category(staff_category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee (
    employee_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    employment_source_id TINYINT UNSIGNED NOT NULL,
    external_agency_id BIGINT UNSIGNED NULL,
    employee_number VARCHAR(30) NOT NULL UNIQUE,
    agency_employee_number VARCHAR(50) NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100) NULL,
    last_name VARCHAR(100) NULL,
    display_name VARCHAR(250) NOT NULL,
    date_of_birth DATE NULL,
    gender_id TINYINT UNSIGNED NULL,
    blood_group_id TINYINT UNSIGNED NULL,
    primary_email VARCHAR(254) NULL,
    primary_phone VARCHAR(25) NULL,
    nationality_country_id SMALLINT UNSIGNED NULL,
    religion_id SMALLINT UNSIGNED NULL,
    social_category_id SMALLINT UNSIGNED NULL,
    caste_id INT UNSIGNED NULL,
    sub_caste_id INT UNSIGNED NULL,
    photo_url VARCHAR(500) NULL,
    joining_date DATE NOT NULL,
    employment_type ENUM('REGULAR','CONTRACT','VISITING','ADJUNCT','TEMPORARY','OTHER') NOT NULL,
    employment_status ENUM('ACTIVE','ON_LEAVE','SUSPENDED','RESIGNED','RETIRED','TERMINATED') NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_employee_agency_number UNIQUE (external_agency_id, agency_employee_number),
    CONSTRAINT uq_employee_primary_email UNIQUE (primary_email),
    CONSTRAINT fk_employee_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_employee_employment_source FOREIGN KEY (employment_source_id) REFERENCES employment_source(employment_source_id),
    CONSTRAINT fk_employee_external_agency FOREIGN KEY (external_agency_id) REFERENCES external_agency(external_agency_id),
    CONSTRAINT fk_employee_gender FOREIGN KEY (gender_id) REFERENCES gender(gender_id),
    CONSTRAINT fk_employee_blood_group FOREIGN KEY (blood_group_id) REFERENCES blood_group(blood_group_id),
    CONSTRAINT fk_employee_nationality FOREIGN KEY (nationality_country_id) REFERENCES country(country_id),
    CONSTRAINT fk_employee_religion FOREIGN KEY (religion_id) REFERENCES religion(religion_id),
    CONSTRAINT fk_employee_social_category FOREIGN KEY (social_category_id) REFERENCES social_category(social_category_id),
    CONSTRAINT fk_employee_caste FOREIGN KEY (caste_id) REFERENCES caste(caste_id),
    CONSTRAINT fk_employee_sub_caste FOREIGN KEY (sub_caste_id) REFERENCES sub_caste(sub_caste_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_address (
    employee_address_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    address_type ENUM('PERMANENT','CURRENT','CORRESPONDENCE','OTHER') NOT NULL,
    address_line_1 VARCHAR(200) NOT NULL,
    address_line_2 VARCHAR(200) NULL,
    city VARCHAR(100) NOT NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NOT NULL,
    postal_code VARCHAR(12) NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    current_primary_employee_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_primary=TRUE AND valid_to IS NULL THEN employee_id ELSE NULL END
    ) STORED,
    CONSTRAINT uq_employee_current_primary_address UNIQUE (current_primary_employee_id),
    CONSTRAINT chk_employee_address_dates CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CONSTRAINT fk_employee_address_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_address_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_employee_address_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_assignment (
    employee_assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    campus_id SMALLINT UNSIGNED NOT NULL,
    department_id SMALLINT UNSIGNED NULL,
    designation_id SMALLINT UNSIGNED NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    current_primary_employee_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_primary = TRUE AND end_date IS NULL THEN employee_id ELSE NULL END
    ) STORED,
    CONSTRAINT uq_employee_current_primary UNIQUE (current_primary_employee_id),
    CONSTRAINT chk_employee_assignment_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT fk_employee_assignment_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_assignment_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id),
    CONSTRAINT fk_employee_assignment_department_campus FOREIGN KEY (department_id, campus_id) REFERENCES department(department_id, campus_id),
    CONSTRAINT fk_employee_assignment_designation FOREIGN KEY (designation_id) REFERENCES designation(designation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_competency (
    employee_id BIGINT UNSIGNED NOT NULL,
    course_id INT UNSIGNED NOT NULL,
    competency_level ENUM('BEGINNER','INTERMEDIATE','ADVANCED','EXPERT') NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    PRIMARY KEY (employee_id, course_id),
    CONSTRAINT fk_competency_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_competency_course FOREIGN KEY (course_id) REFERENCES course_catalog(course_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO staff_type (type_code, type_name, description) VALUES
('TEACHING', 'Teaching', 'Academic and teaching personnel'),
('NON_TEACHING', 'Non-Teaching', 'Administrative, technical, support and service personnel');

INSERT INTO staff_category (staff_type_id, category_code, category_name, description) VALUES
((SELECT staff_type_id FROM staff_type WHERE type_code='TEACHING'),'TEACHING_STAFF','Teaching Staff','Faculty and other personnel engaged in teaching'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'OFFICE_STAFF','Office Staff','Administrative and office personnel'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'EXAM_SECTION_STAFF','Examination Section Staff','Personnel working in the examination section'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'LIBRARY_STAFF','Library Staff','Library professional and support personnel'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'MENIAL_STAFF','Menial Staff','Institutional support and menial personnel'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'INTERNAL_SECURITY','Internal Security Staff','Security personnel directly engaged by the institution'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'AGENCY_SECURITY','Security Staff - External Agency','Security personnel supplied by an external agency'),
((SELECT staff_type_id FROM staff_type WHERE type_code='NON_TEACHING'),'AGENCY_HOUSEKEEPING','Housekeeping Staff - External Agency','Housekeeping personnel supplied by an external agency');

INSERT INTO employment_source (source_code, source_name, is_external, description) VALUES
('INSTITUTION','Institution Employee',FALSE,'Person directly engaged by the institution'),
('EXTERNAL_AGENCY','External Agency',TRUE,'Person supplied by a contracted external agency');

INSERT INTO designation (staff_category_id, designation_code, designation_name) VALUES
((SELECT staff_category_id FROM staff_category WHERE category_code='TEACHING_STAFF'),'PROFESSOR','Professor'),
((SELECT staff_category_id FROM staff_category WHERE category_code='TEACHING_STAFF'),'ASSOC_PROFESSOR','Associate Professor'),
((SELECT staff_category_id FROM staff_category WHERE category_code='TEACHING_STAFF'),'ASST_PROFESSOR','Assistant Professor'),
((SELECT staff_category_id FROM staff_category WHERE category_code='OFFICE_STAFF'),'OFFICE_SUPERINTENDENT','Office Superintendent'),
((SELECT staff_category_id FROM staff_category WHERE category_code='OFFICE_STAFF'),'OFFICE_ASSISTANT','Office Assistant'),
((SELECT staff_category_id FROM staff_category WHERE category_code='EXAM_SECTION_STAFF'),'EXAM_SUPERINTENDENT','Examination Superintendent'),
((SELECT staff_category_id FROM staff_category WHERE category_code='EXAM_SECTION_STAFF'),'EXAM_ASSISTANT','Examination Assistant'),
((SELECT staff_category_id FROM staff_category WHERE category_code='LIBRARY_STAFF'),'LIBRARIAN','Librarian'),
((SELECT staff_category_id FROM staff_category WHERE category_code='LIBRARY_STAFF'),'ASST_LIBRARIAN','Assistant Librarian'),
((SELECT staff_category_id FROM staff_category WHERE category_code='MENIAL_STAFF'),'ATTENDER','Attender'),
((SELECT staff_category_id FROM staff_category WHERE category_code='INTERNAL_SECURITY'),'INTERNAL_SECURITY_GUARD','Security Guard'),
((SELECT staff_category_id FROM staff_category WHERE category_code='AGENCY_SECURITY'),'AGENCY_SECURITY_GUARD','Security Guard'),
((SELECT staff_category_id FROM staff_category WHERE category_code='AGENCY_HOUSEKEEPING'),'HOUSEKEEPING_STAFF','Housekeeping Staff');

-- =============================================================
-- 6. ADMISSION AND ENROLMENT TRANSACTION MODULE
-- =============================================================
CREATE TABLE admission_applicant (
    admission_applicant_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100) NULL,
    last_name VARCHAR(100) NULL,
    display_name VARCHAR(250) NOT NULL,
    date_of_birth DATE NULL,
    gender_id TINYINT UNSIGNED NULL,
    primary_email VARCHAR(254) NULL,
    primary_phone VARCHAR(25) NULL,
    nationality_country_id SMALLINT UNSIGNED NULL,
    social_category_id SMALLINT UNSIGNED NULL,
    caste_id INT UNSIGNED NULL,
    sub_caste_id INT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_admission_applicant_gender FOREIGN KEY (gender_id) REFERENCES gender(gender_id),
    CONSTRAINT fk_admission_applicant_nationality FOREIGN KEY (nationality_country_id) REFERENCES country(country_id),
    CONSTRAINT fk_admission_applicant_social_category FOREIGN KEY (social_category_id) REFERENCES social_category(social_category_id),
    CONSTRAINT fk_admission_applicant_caste FOREIGN KEY (caste_id) REFERENCES caste(caste_id),
    CONSTRAINT fk_admission_applicant_sub_caste FOREIGN KEY (sub_caste_id) REFERENCES sub_caste(sub_caste_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE admission_application (
    application_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    application_number VARCHAR(30) NOT NULL UNIQUE,
    admission_applicant_id BIGINT UNSIGNED NOT NULL,
    admitted_student_id BIGINT UNSIGNED NULL UNIQUE,
    programme_id SMALLINT UNSIGNED NOT NULL,
    specialization_id SMALLINT UNSIGNED NULL,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    admission_category_id SMALLINT UNSIGNED NULL,
    application_date DATE NOT NULL,
    application_status ENUM('DRAFT','SUBMITTED','UNDER_REVIEW','ELIGIBLE','INELIGIBLE','SELECTED','WAITLISTED','REJECTED','ADMITTED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
    eligibility_status ENUM('PENDING','ELIGIBLE','INELIGIBLE') NOT NULL DEFAULT 'PENDING',
    remarks TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_application_applicant FOREIGN KEY (admission_applicant_id) REFERENCES admission_applicant(admission_applicant_id),
    CONSTRAINT fk_application_admitted_student FOREIGN KEY (admitted_student_id) REFERENCES student(student_id),
    CONSTRAINT fk_application_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_application_specialization_programme FOREIGN KEY (specialization_id, programme_id)
        REFERENCES programme_specialization(specialization_id, programme_id),
    CONSTRAINT fk_application_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_application_category FOREIGN KEY (admission_category_id) REFERENCES admission_category(admission_category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_programme_enrolment (
    enrolment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    programme_id SMALLINT UNSIGNED NOT NULL,
    specialization_id SMALLINT UNSIGNED NULL,
    curriculum_scheme_id INT UNSIGNED NOT NULL,
    admission_academic_year_id SMALLINT UNSIGNED NOT NULL,
    admission_category_id SMALLINT UNSIGNED NULL,
    admission_date DATE NOT NULL,
    admission_semester_id TINYINT UNSIGNED NOT NULL,
    expected_completion_date DATE NULL,
    enrolment_status ENUM('ACTIVE','ON_BREAK','WITHDRAWN','TRANSFERRED','COMPLETED','TERMINATED') NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT uq_student_programme_enrolment UNIQUE (student_id, programme_id, admission_academic_year_id),
    CONSTRAINT fk_enrolment_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_enrolment_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_enrolment_specialization_programme FOREIGN KEY (specialization_id, programme_id)
        REFERENCES programme_specialization(specialization_id, programme_id),
    CONSTRAINT fk_enrolment_scheme FOREIGN KEY (curriculum_scheme_id) REFERENCES curriculum_scheme(curriculum_scheme_id),
    CONSTRAINT fk_enrolment_year FOREIGN KEY (admission_academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_enrolment_category FOREIGN KEY (admission_category_id) REFERENCES admission_category(admission_category_id),
    CONSTRAINT fk_enrolment_semester FOREIGN KEY (admission_semester_id) REFERENCES semester(semester_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE enrolment_status_history (
    enrolment_status_history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    enrolment_id BIGINT UNSIGNED NOT NULL,
    old_status VARCHAR(30) NULL,
    new_status VARCHAR(30) NOT NULL,
    effective_date DATE NOT NULL,
    reason VARCHAR(500) NULL,
    CONSTRAINT fk_enrolment_history_enrolment FOREIGN KEY (enrolment_id) REFERENCES student_programme_enrolment(enrolment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 7. TERM REGISTRATION, SECTION AND COURSE REGISTRATION MODULE
-- =============================================================
CREATE TABLE programme_term_offering (
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
    course_offering_section_student_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_section_id BIGINT UNSIGNED NOT NULL,
    course_registration_id BIGINT UNSIGNED NOT NULL,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    roster_status ENUM('ACTIVE','DROPPED','TRANSFERRED','COMPLETED') NOT NULL DEFAULT 'ACTIVE',
    effective_from DATE NULL,
    effective_to DATE NULL,
    CONSTRAINT uq_course_section_student UNIQUE (course_offering_section_id, course_registration_id),
    CONSTRAINT uq_course_section_student_owner UNIQUE (course_offering_section_student_id, course_offering_section_id),
    CONSTRAINT chk_course_section_student_dates CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from),
    CONSTRAINT fk_roster_section_course FOREIGN KEY (course_offering_section_id, course_offering_id)
        REFERENCES course_offering_section(course_offering_section_id, course_offering_id),
    CONSTRAINT fk_roster_registration_course FOREIGN KEY (course_registration_id, course_offering_id)
        REFERENCES student_course_registration(course_registration_id, course_offering_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 8. TEACHING ALLOCATION AND TIMETABLE MODULE
-- =============================================================
CREATE TABLE faculty_course_assignment (
    faculty_assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_section_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    assignment_role ENUM('PRIMARY_INSTRUCTOR','CO_INSTRUCTOR','LAB_INSTRUCTOR','TUTOR','COORDINATOR','OTHER') NOT NULL,
    workload_hours DECIMAL(6,2) NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    assignment_status ENUM('PLANNED','ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT uq_faculty_course_assignment UNIQUE (course_offering_section_id, employee_id, assignment_role),
    CONSTRAINT fk_faculty_assignment_section FOREIGN KEY (course_offering_section_id) REFERENCES course_offering_section(course_offering_section_id),
    CONSTRAINT fk_faculty_assignment_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE timetable_session (
    timetable_session_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_section_id BIGINT UNSIGNED NOT NULL,
    faculty_assignment_id BIGINT UNSIGNED NULL,
    day_of_week TINYINT UNSIGNED NOT NULL,
    time_slot_id SMALLINT UNSIGNED NOT NULL,
    room_id INT UNSIGNED NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    CONSTRAINT chk_day_of_week CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT uq_timetable_room UNIQUE (day_of_week, time_slot_id, room_id, effective_from),
    CONSTRAINT fk_timetable_section FOREIGN KEY (course_offering_section_id) REFERENCES course_offering_section(course_offering_section_id),
    CONSTRAINT fk_timetable_faculty FOREIGN KEY (faculty_assignment_id) REFERENCES faculty_course_assignment(faculty_assignment_id),
    CONSTRAINT fk_timetable_time_slot FOREIGN KEY (time_slot_id) REFERENCES time_slot(time_slot_id),
    CONSTRAINT fk_timetable_room FOREIGN KEY (room_id) REFERENCES room(room_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 9. ATTENDANCE AND LESSON PLAN MODULE
-- =============================================================
CREATE TABLE class_session (
    class_session_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_section_id BIGINT UNSIGNED NOT NULL,
    faculty_assignment_id BIGINT UNSIGNED NULL,
    timetable_session_id BIGINT UNSIGNED NULL,
    session_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room_id INT UNSIGNED NULL,
    session_type ENUM('LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER') NOT NULL,
    planned_topic TEXT NULL,
    topic_covered TEXT NULL,
    class_number SMALLINT UNSIGNED NULL,
    session_status ENUM('PLANNED','CONDUCTED','CANCELLED','RESCHEDULED') NOT NULL DEFAULT 'PLANNED',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_class_session_time CHECK (end_time > start_time),
    CONSTRAINT uq_class_session UNIQUE (course_offering_section_id, session_date, start_time),
    CONSTRAINT uq_class_session_owner UNIQUE (class_session_id, course_offering_section_id),
    CONSTRAINT fk_class_session_section FOREIGN KEY (course_offering_section_id) REFERENCES course_offering_section(course_offering_section_id),
    CONSTRAINT fk_class_session_faculty FOREIGN KEY (faculty_assignment_id) REFERENCES faculty_course_assignment(faculty_assignment_id),
    CONSTRAINT fk_class_session_timetable FOREIGN KEY (timetable_session_id) REFERENCES timetable_session(timetable_session_id),
    CONSTRAINT fk_class_session_room FOREIGN KEY (room_id) REFERENCES room(room_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE attendance_status (
    attendance_status_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    status_code VARCHAR(20) NOT NULL UNIQUE,
    status_name VARCHAR(50) NOT NULL UNIQUE,
    counts_as_present BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_attendance (
    class_session_id BIGINT UNSIGNED NOT NULL,
    course_offering_section_student_id BIGINT UNSIGNED NOT NULL,
    course_offering_section_id BIGINT UNSIGNED NOT NULL,
    attendance_status_id TINYINT UNSIGNED NOT NULL,
    marked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    marked_by_user_id BIGINT UNSIGNED NULL,
    remarks VARCHAR(500) NULL,
    PRIMARY KEY (class_session_id, course_offering_section_student_id),
    CONSTRAINT fk_student_attendance_session_owner FOREIGN KEY (class_session_id, course_offering_section_id)
        REFERENCES class_session(class_session_id, course_offering_section_id),
    CONSTRAINT fk_student_attendance_roster_owner FOREIGN KEY (course_offering_section_student_id, course_offering_section_id)
        REFERENCES course_offering_section_student(course_offering_section_student_id, course_offering_section_id),
    CONSTRAINT fk_student_attendance_status FOREIGN KEY (attendance_status_id) REFERENCES attendance_status(attendance_status_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE attendance_correction_request (
    attendance_correction_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    class_session_id BIGINT UNSIGNED NOT NULL,
    course_offering_section_student_id BIGINT UNSIGNED NOT NULL,
    old_status_id TINYINT UNSIGNED NOT NULL,
    requested_status_id TINYINT UNSIGNED NOT NULL,
    reason VARCHAR(1000) NOT NULL,
    request_status ENUM('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL DEFAULT 'PENDING',
    requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    CONSTRAINT fk_attendance_correction_attendance FOREIGN KEY (class_session_id, course_offering_section_student_id)
        REFERENCES student_attendance(class_session_id, course_offering_section_student_id),
    CONSTRAINT fk_attendance_correction_old FOREIGN KEY (old_status_id) REFERENCES attendance_status(attendance_status_id),
    CONSTRAINT fk_attendance_correction_requested FOREIGN KEY (requested_status_id) REFERENCES attendance_status(attendance_status_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 10. CONTINUOUS ASSESSMENT AND RESULT MODULE
-- =============================================================
CREATE TABLE assessment_component (
    assessment_component_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    component_code VARCHAR(30) NOT NULL,
    component_name VARCHAR(100) NOT NULL,
    component_type ENUM('INTERNAL_TEST','QUIZ','ASSIGNMENT','LAB','PROJECT','PRESENTATION','TERM_WORK','OTHER') NOT NULL,
    maximum_marks DECIMAL(7,2) NOT NULL,
    weightage_percent DECIMAL(5,2) NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_assessment_component UNIQUE (course_offering_id, component_code),
    CONSTRAINT uq_assessment_component_owner UNIQUE (assessment_component_id, course_offering_id),
    CONSTRAINT chk_assessment_marks CHECK (maximum_marks >= 0),
    CONSTRAINT fk_assessment_component_offering FOREIGN KEY (course_offering_id) REFERENCES course_offering(course_offering_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assessment_event (
    assessment_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assessment_component_id BIGINT UNSIGNED NOT NULL,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    event_number SMALLINT UNSIGNED NULL,
    event_title VARCHAR(150) NOT NULL,
    assessment_date DATE NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    maximum_marks DECIMAL(7,2) NOT NULL,
    reduced_maximum_marks DECIMAL(7,2) NULL,
    details TEXT NULL,
    status ENUM('PLANNED','CONDUCTED','CANCELLED','PUBLISHED') NOT NULL DEFAULT 'PLANNED',
    CONSTRAINT uq_assessment_event_owner UNIQUE (assessment_event_id, course_offering_id),
    CONSTRAINT chk_assessment_event_marks CHECK (maximum_marks >= 0 AND (reduced_maximum_marks IS NULL OR reduced_maximum_marks >= 0)),
    CONSTRAINT chk_assessment_event_time CHECK (end_time IS NULL OR start_time IS NULL OR end_time > start_time),
    CONSTRAINT fk_assessment_event_component_course FOREIGN KEY (assessment_component_id, course_offering_id)
        REFERENCES assessment_component(assessment_component_id, course_offering_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_assessment_mark (
    student_assessment_mark_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assessment_event_id BIGINT UNSIGNED NOT NULL,
    course_registration_id BIGINT UNSIGNED NOT NULL,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    attendance_status ENUM('PRESENT','ABSENT','EXEMPTED','MALPRACTICE') NOT NULL DEFAULT 'PRESENT',
    marks_obtained DECIMAL(7,2) NULL,
    reduced_marks DECIMAL(7,2) NULL,
    remarks VARCHAR(500) NULL,
    evaluated_at TIMESTAMP NULL,
    CONSTRAINT uq_student_assessment UNIQUE (assessment_event_id, course_registration_id),
    CONSTRAINT chk_student_assessment_marks CHECK (marks_obtained IS NULL OR marks_obtained >= 0),
    CONSTRAINT chk_student_assessment_reduced_marks CHECK (reduced_marks IS NULL OR reduced_marks >= 0),
    CONSTRAINT fk_student_assessment_event_course FOREIGN KEY (assessment_event_id, course_offering_id)
        REFERENCES assessment_event(assessment_event_id, course_offering_id),
    CONSTRAINT fk_student_assessment_registration_course FOREIGN KEY (course_registration_id, course_offering_id)
        REFERENCES student_course_registration(course_registration_id, course_offering_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grade_scale (
    grade_scale_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scale_name VARCHAR(100) NOT NULL UNIQUE,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grade_rule (
    grade_rule_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    grade_scale_id SMALLINT UNSIGNED NOT NULL,
    grade_letter VARCHAR(5) NOT NULL,
    grade_point DECIMAL(4,2) NOT NULL,
    minimum_percentage DECIMAL(5,2) NOT NULL,
    maximum_percentage DECIMAL(5,2) NOT NULL,
    result_status ENUM('PASS','FAIL','ABSENT','WITHHELD','EXEMPTED') NOT NULL DEFAULT 'PASS',
    CONSTRAINT uq_grade_rule UNIQUE (grade_scale_id, grade_letter),
    CONSTRAINT chk_grade_range CHECK (maximum_percentage >= minimum_percentage),
    CONSTRAINT fk_grade_rule_scale FOREIGN KEY (grade_scale_id) REFERENCES grade_scale(grade_scale_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_course_result (
    student_course_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_registration_id BIGINT UNSIGNED NOT NULL,
    attempt_number TINYINT UNSIGNED NOT NULL DEFAULT 1,
    internal_marks DECIMAL(7,2) NULL,
    external_marks DECIMAL(7,2) NULL,
    total_marks DECIMAL(7,2) NULL,
    grade_letter VARCHAR(5) NULL,
    grade_point DECIMAL(4,2) NULL,
    credits_earned DECIMAL(4,1) NOT NULL DEFAULT 0,
    result_status ENUM('PASS','FAIL','ABSENT','WITHHELD','EXEMPTED','INCOMPLETE') NOT NULL,
    result_date DATE NULL,
    remarks VARCHAR(500) NULL,
    CONSTRAINT uq_course_result_attempt UNIQUE (course_registration_id, attempt_number),
    CONSTRAINT fk_course_result_registration FOREIGN KEY (course_registration_id) REFERENCES student_course_registration(course_registration_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_term_result (
    student_term_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    term_registration_id BIGINT UNSIGNED NOT NULL UNIQUE,
    credits_registered DECIMAL(6,1) NOT NULL DEFAULT 0,
    credits_earned DECIMAL(6,1) NOT NULL DEFAULT 0,
    sgpa DECIMAL(4,2) NULL,
    cgpa DECIMAL(4,2) NULL,
    result_status ENUM('PASS','FAIL','PROMOTED','WITHHELD','INCOMPLETE') NOT NULL,
    published_at TIMESTAMP NULL,
    CONSTRAINT fk_term_result_registration FOREIGN KEY (term_registration_id) REFERENCES student_term_registration(term_registration_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 11. FEEDBACK MODULE
-- =============================================================
CREATE TABLE feedback_question_category (
    feedback_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(30) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_question (
    feedback_question_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    feedback_category_id SMALLINT UNSIGNED NOT NULL,
    question_text VARCHAR(1000) NOT NULL,
    response_type ENUM('SINGLE_CHOICE','MULTIPLE_CHOICE','RATING','TEXT') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_feedback_question_category FOREIGN KEY (feedback_category_id) REFERENCES feedback_question_category(feedback_category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_choice (
    feedback_choice_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    feedback_question_id INT UNSIGNED NOT NULL,
    choice_text VARCHAR(250) NOT NULL,
    score DECIMAL(6,2) NULL,
    display_order SMALLINT UNSIGNED NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_feedback_choice UNIQUE (feedback_question_id, choice_text),
    CONSTRAINT fk_feedback_choice_question FOREIGN KEY (feedback_question_id) REFERENCES feedback_question(feedback_question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_questionnaire (
    questionnaire_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    questionnaire_code VARCHAR(30) NOT NULL UNIQUE,
    questionnaire_name VARCHAR(150) NOT NULL,
    questionnaire_type ENUM('COURSE','FACULTY','PROGRAMME','INSTITUTION','EXIT','OTHER') NOT NULL,
    is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
    status ENUM('DRAFT','ACTIVE','RETIRED') NOT NULL DEFAULT 'DRAFT'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_questionnaire_item (
    questionnaire_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    questionnaire_id INT UNSIGNED NOT NULL,
    feedback_question_id INT UNSIGNED NOT NULL,
    weightage DECIMAL(6,2) NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_questionnaire_question UNIQUE (questionnaire_id, feedback_question_id),
    CONSTRAINT fk_questionnaire_item_questionnaire FOREIGN KEY (questionnaire_id) REFERENCES feedback_questionnaire(questionnaire_id),
    CONSTRAINT fk_questionnaire_item_question FOREIGN KEY (feedback_question_id) REFERENCES feedback_question(feedback_question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_cycle (
    feedback_cycle_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    questionnaire_id INT UNSIGNED NOT NULL,
    academic_term_id INT UNSIGNED NOT NULL,
    cycle_name VARCHAR(150) NOT NULL,
    start_at DATETIME NOT NULL,
    end_at DATETIME NOT NULL,
    result_visibility ENUM('HIDDEN','ADMIN_ONLY','FACULTY','PUBLIC') NOT NULL DEFAULT 'HIDDEN',
    status ENUM('SCHEDULED','OPEN','CLOSED','CANCELLED') NOT NULL DEFAULT 'SCHEDULED',
    CONSTRAINT chk_feedback_cycle_dates CHECK (end_at > start_at),
    CONSTRAINT fk_feedback_cycle_questionnaire FOREIGN KEY (questionnaire_id) REFERENCES feedback_questionnaire(questionnaire_id),
    CONSTRAINT fk_feedback_cycle_term FOREIGN KEY (academic_term_id) REFERENCES academic_term(academic_term_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_response (
    feedback_response_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    feedback_cycle_id BIGINT UNSIGNED NOT NULL,
    term_registration_id BIGINT UNSIGNED NULL,
    course_offering_id BIGINT UNSIGNED NULL,
    faculty_assignment_id BIGINT UNSIGNED NULL,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_token CHAR(36) NULL UNIQUE,
    CONSTRAINT fk_feedback_response_cycle FOREIGN KEY (feedback_cycle_id) REFERENCES feedback_cycle(feedback_cycle_id),
    CONSTRAINT fk_feedback_response_term_registration FOREIGN KEY (term_registration_id) REFERENCES student_term_registration(term_registration_id),
    CONSTRAINT fk_feedback_response_course FOREIGN KEY (course_offering_id) REFERENCES course_offering(course_offering_id),
    CONSTRAINT fk_feedback_response_faculty FOREIGN KEY (faculty_assignment_id) REFERENCES faculty_course_assignment(faculty_assignment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE feedback_response_item (
    feedback_response_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    feedback_response_id BIGINT UNSIGNED NOT NULL,
    questionnaire_item_id BIGINT UNSIGNED NOT NULL,
    feedback_choice_id INT UNSIGNED NULL,
    numeric_score DECIMAL(6,2) NULL,
    text_response TEXT NULL,
    CONSTRAINT uq_feedback_response_item UNIQUE (feedback_response_id, questionnaire_item_id),
    CONSTRAINT fk_feedback_item_response FOREIGN KEY (feedback_response_id) REFERENCES feedback_response(feedback_response_id),
    CONSTRAINT fk_feedback_item_questionnaire_item FOREIGN KEY (questionnaire_item_id) REFERENCES feedback_questionnaire_item(questionnaire_item_id),
    CONSTRAINT fk_feedback_item_choice FOREIGN KEY (feedback_choice_id) REFERENCES feedback_choice(feedback_choice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 12. MENTORING, COUNSELLING AND GRIEVANCE MODULE
-- =============================================================
CREATE TABLE mentor_assignment (
    mentor_assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    assignment_status ENUM('ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_mentor_assignment_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_mentor_assignment_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE counselling_session (
    counselling_session_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    mentor_assignment_id BIGINT UNSIGNED NOT NULL,
    session_date DATETIME NOT NULL,
    observations TEXT NULL,
    action_plan TEXT NULL,
    follow_up_date DATE NULL,
    session_status ENUM('SCHEDULED','COMPLETED','CANCELLED','FOLLOW_UP_REQUIRED') NOT NULL DEFAULT 'COMPLETED',
    confidentiality_level ENUM('NORMAL','RESTRICTED','HIGHLY_RESTRICTED') NOT NULL DEFAULT 'RESTRICTED',
    CONSTRAINT fk_counselling_mentor_assignment FOREIGN KEY (mentor_assignment_id) REFERENCES mentor_assignment(mentor_assignment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grievance_category (
    grievance_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(30) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grievance (
    grievance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    grievance_number VARCHAR(30) NOT NULL UNIQUE,
    student_id BIGINT UNSIGNED NOT NULL,
    grievance_category_id SMALLINT UNSIGNED NOT NULL,
    department_id SMALLINT UNSIGNED NULL,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subject VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    priority ENUM('LOW','NORMAL','HIGH','URGENT') NOT NULL DEFAULT 'NORMAL',
    status ENUM('SUBMITTED','ASSIGNED','UNDER_REVIEW','RESOLVED','REJECTED','CLOSED') NOT NULL DEFAULT 'SUBMITTED',
    resolved_at DATETIME NULL,
    resolution TEXT NULL,
    CONSTRAINT fk_grievance_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_grievance_category FOREIGN KEY (grievance_category_id) REFERENCES grievance_category(grievance_category_id),
    CONSTRAINT fk_grievance_department FOREIGN KEY (department_id) REFERENCES department(department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grievance_action (
    grievance_action_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    grievance_id BIGINT UNSIGNED NOT NULL,
    action_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_type VARCHAR(50) NOT NULL,
    action_notes TEXT NULL,
    new_status VARCHAR(30) NULL,
    CONSTRAINT fk_grievance_action_grievance FOREIGN KEY (grievance_id) REFERENCES grievance(grievance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 13. DOCUMENT, CERTIFICATE AND EXIT MODULE
-- =============================================================
CREATE TABLE file_object (
    file_object_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    storage_provider VARCHAR(30) NOT NULL,
    storage_key VARCHAR(500) NOT NULL UNIQUE,
    original_file_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT UNSIGNED NOT NULL,
    checksum_sha256 CHAR(64) NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Added metadata; original columns above remain unchanged.
    stored_file_name VARCHAR(255) NULL,
    storage_url VARCHAR(1000) NULL,
    file_extension VARCHAR(20) NULL,
    confidentiality_level ENUM('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED','HIGHLY_RESTRICTED') NOT NULL DEFAULT 'INTERNAL',
    is_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_by_user_id BIGINT UNSIGNED NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT chk_file_object_size CHECK (file_size_bytes > 0),
    CONSTRAINT chk_file_object_checksum CHECK (checksum_sha256 IS NULL OR checksum_sha256 REGEXP '^[0-9A-Fa-f]{64}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_document (
    student_document_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    document_type_id SMALLINT UNSIGNED NOT NULL,
    file_object_id BIGINT UNSIGNED NOT NULL,
    document_number VARCHAR(100) NULL,
    issue_date DATE NULL,
    expiry_date DATE NULL,
    verification_status ENUM('PENDING','VERIFIED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',
    verified_at DATETIME NULL,
    remarks VARCHAR(500) NULL,
    CONSTRAINT uq_student_document UNIQUE (student_id, document_type_id, document_number),
    CONSTRAINT fk_student_document_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_document_type FOREIGN KEY (document_type_id) REFERENCES document_type(document_type_id),
    CONSTRAINT fk_student_document_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE certificate_type (
    certificate_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    certificate_code VARCHAR(30) NOT NULL UNIQUE,
    certificate_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE certificate_request (
    certificate_request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    request_number VARCHAR(30) NOT NULL UNIQUE,
    student_id BIGINT UNSIGNED NOT NULL,
    certificate_type_id SMALLINT UNSIGNED NOT NULL,
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    purpose VARCHAR(500) NULL,
    request_status ENUM('SUBMITTED','UNDER_REVIEW','APPROVED','REJECTED','ISSUED','CANCELLED') NOT NULL DEFAULT 'SUBMITTED',
    issued_at DATETIME NULL,
    certificate_number VARCHAR(50) NULL UNIQUE,
    file_object_id BIGINT UNSIGNED NULL,
    CONSTRAINT fk_certificate_request_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_certificate_request_type FOREIGN KEY (certificate_type_id) REFERENCES certificate_type(certificate_type_id),
    CONSTRAINT fk_certificate_request_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_exit (
    student_exit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    enrolment_id BIGINT UNSIGNED NOT NULL,
    exit_type ENUM('COMPLETION','TRANSFER','WITHDRAWAL','TERMINATION','OTHER') NOT NULL,
    exit_date DATE NOT NULL,
    destination_institution VARCHAR(250) NULL,
    old_registration_number VARCHAR(50) NULL,
    remarks TEXT NULL,
    CONSTRAINT uq_student_exit_enrolment UNIQUE (enrolment_id),
    CONSTRAINT fk_student_exit_enrolment FOREIGN KEY (enrolment_id) REFERENCES student_programme_enrolment(enrolment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 14. COMMUNICATION MODULE
-- =============================================================
CREATE TABLE announcement_type (
    announcement_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(30) NOT NULL UNIQUE,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE announcement (
    announcement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    announcement_type_id SMALLINT UNSIGNED NOT NULL,
    department_id SMALLINT UNSIGNED NULL,
    title VARCHAR(250) NOT NULL,
    description TEXT NOT NULL,
    publish_from DATETIME NOT NULL,
    publish_to DATETIME NULL,
    approval_status ENUM('DRAFT','PENDING','APPROVED','REJECTED','ARCHIVED') NOT NULL DEFAULT 'DRAFT',
    audience_type ENUM('ALL','STUDENTS','STAFF','PROGRAMME','DEPARTMENT','CUSTOM') NOT NULL DEFAULT 'ALL',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_announcement_type FOREIGN KEY (announcement_type_id) REFERENCES announcement_type(announcement_type_id),
    CONSTRAINT fk_announcement_department FOREIGN KEY (department_id) REFERENCES department(department_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE announcement_attachment (
    announcement_id BIGINT UNSIGNED NOT NULL,
    file_object_id BIGINT UNSIGNED NOT NULL,
    display_order SMALLINT UNSIGNED NULL,
    PRIMARY KEY (announcement_id, file_object_id),
    CONSTRAINT fk_announcement_attachment_announcement FOREIGN KEY (announcement_id) REFERENCES announcement(announcement_id),
    CONSTRAINT fk_announcement_attachment_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 15. IDENTITY, ACCESS CONTROL (RBAC) AND AUDIT MODULE
-- =============================================================
CREATE TABLE user_account (
    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(254) NULL,
    account_status ENUM('PENDING','ACTIVE','LOCKED','DISABLED','EXPIRED') NOT NULL DEFAULT 'ACTIVE',
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    multi_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    failed_login_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    locked_until DATETIME NULL,
    password_changed_at DATETIME NULL,
    last_login_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_user_account (
    student_id BIGINT UNSIGNED PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL UNIQUE,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_student_user_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_user_account FOREIGN KEY (user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_user_account (
    employee_id BIGINT UNSIGNED PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL UNIQUE,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee_user_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_user_account FOREIGN KEY (user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE access_module (
    access_module_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    module_code VARCHAR(50) NOT NULL UNIQUE,
    module_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE access_resource (
    access_resource_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    access_module_id SMALLINT UNSIGNED NOT NULL,
    resource_code VARCHAR(80) NOT NULL,
    resource_name VARCHAR(150) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_access_resource UNIQUE (access_module_id, resource_code),
    CONSTRAINT fk_access_resource_module FOREIGN KEY (access_module_id) REFERENCES access_module(access_module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE access_action (
    access_action_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    action_code VARCHAR(30) NOT NULL UNIQUE,
    action_name VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(300) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE permission (
    permission_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    access_resource_id INT UNSIGNED NOT NULL,
    access_action_id TINYINT UNSIGNED NOT NULL,
    permission_code VARCHAR(150) NOT NULL UNIQUE,
    permission_name VARCHAR(200) NOT NULL,
    description VARCHAR(500) NULL,
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_permission_resource_action UNIQUE (access_resource_id, access_action_id),
    CONSTRAINT fk_permission_resource FOREIGN KEY (access_resource_id) REFERENCES access_resource(access_resource_id),
    CONSTRAINT fk_permission_action FOREIGN KEY (access_action_id) REFERENCES access_action(access_action_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE role (
    role_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_role_id SMALLINT UNSIGNED NULL,
    role_code VARCHAR(60) NOT NULL UNIQUE,
    role_name VARCHAR(120) NOT NULL UNIQUE,
    role_category ENUM('SYSTEM','GOVERNANCE','ACADEMIC','ADMINISTRATIVE','FACULTY','STUDENT','PARENT','AUDIT','SUPPORT') NOT NULL,
    role_level ENUM('GLOBAL','INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME','SELF') NOT NULL DEFAULT 'GLOBAL',
    description VARCHAR(500) NULL,
    is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    is_assignable BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_role_parent FOREIGN KEY (parent_role_id) REFERENCES role(role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE role_permission (
    role_id SMALLINT UNSIGNED NOT NULL,
    permission_id INT UNSIGNED NOT NULL,
    permission_effect ENUM('ALLOW','DENY') NOT NULL DEFAULT 'ALLOW',
    granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permission_role FOREIGN KEY (role_id) REFERENCES role(role_id),
    CONSTRAINT fk_role_permission_permission FOREIGN KEY (permission_id) REFERENCES permission(permission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_role_assignment (
    user_role_assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    role_id SMALLINT UNSIGNED NOT NULL,
    scope_type ENUM('GLOBAL','INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME','SELF') NOT NULL DEFAULT 'GLOBAL',
    institution_id SMALLINT UNSIGNED NULL,
    campus_id SMALLINT UNSIGNED NULL,
    department_id SMALLINT UNSIGNED NULL,
    programme_id SMALLINT UNSIGNED NULL,
    scope_entity_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE scope_type
            WHEN 'GLOBAL' THEN 0
            WHEN 'INSTITUTION' THEN institution_id
            WHEN 'CAMPUS' THEN campus_id
            WHEN 'DEPARTMENT' THEN department_id
            WHEN 'PROGRAMME' THEN programme_id
            WHEN 'SELF' THEN user_id
        END
    ) STORED,
    valid_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to DATETIME NULL,
    assignment_status ENUM('PENDING','ACTIVE','SUSPENDED','EXPIRED','REVOKED') NOT NULL DEFAULT 'ACTIVE',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_by_user_id BIGINT UNSIGNED NULL,
    assignment_reason VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_role_dates CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT chk_user_role_scope CHECK (
        (scope_type = 'GLOBAL' AND institution_id IS NULL AND campus_id IS NULL AND department_id IS NULL AND programme_id IS NULL) OR
        (scope_type = 'INSTITUTION' AND institution_id IS NOT NULL AND campus_id IS NULL AND department_id IS NULL AND programme_id IS NULL) OR
        (scope_type = 'CAMPUS' AND institution_id IS NULL AND campus_id IS NOT NULL AND department_id IS NULL AND programme_id IS NULL) OR
        (scope_type = 'DEPARTMENT' AND institution_id IS NULL AND campus_id IS NULL AND department_id IS NOT NULL AND programme_id IS NULL) OR
        (scope_type = 'PROGRAMME' AND institution_id IS NULL AND campus_id IS NULL AND department_id IS NULL AND programme_id IS NOT NULL) OR
        (scope_type = 'SELF' AND institution_id IS NULL AND campus_id IS NULL AND department_id IS NULL AND programme_id IS NULL)
    ),
    CONSTRAINT uq_user_role_assignment UNIQUE (user_id, role_id, scope_type, scope_entity_id, valid_from),
    CONSTRAINT fk_user_role_assignment_user FOREIGN KEY (user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_user_role_assignment_role FOREIGN KEY (role_id) REFERENCES role(role_id),
    CONSTRAINT fk_user_role_assignment_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_user_role_assignment_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id),
    CONSTRAINT fk_user_role_assignment_department FOREIGN KEY (department_id) REFERENCES department(department_id),
    CONSTRAINT fk_user_role_assignment_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_user_role_assignment_assigned_by FOREIGN KEY (assigned_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_permission_override (
    user_permission_override_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    permission_id INT UNSIGNED NOT NULL,
    permission_effect ENUM('ALLOW','DENY') NOT NULL,
    scope_type ENUM('GLOBAL','INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME','SELF') NOT NULL DEFAULT 'GLOBAL',
    scope_entity_id BIGINT UNSIGNED NULL,
    normalized_scope_entity_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN scope_type IN ('GLOBAL','SELF') THEN 0 ELSE COALESCE(scope_entity_id, 0) END
    ) STORED,
    valid_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to DATETIME NULL,
    granted_by_user_id BIGINT UNSIGNED NULL,
    justification VARCHAR(500) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_permission_override_dates CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT chk_user_permission_override_scope CHECK (
        (scope_type IN ('GLOBAL','SELF') AND scope_entity_id IS NULL) OR
        (scope_type IN ('INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME') AND scope_entity_id IS NOT NULL)
    ),
    CONSTRAINT uq_user_permission_override UNIQUE (user_id, permission_id, scope_type, normalized_scope_entity_id, valid_from),
    CONSTRAINT fk_user_permission_override_user FOREIGN KEY (user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_user_permission_override_permission FOREIGN KEY (permission_id) REFERENCES permission(permission_id),
    CONSTRAINT fk_user_permission_override_granted_by FOREIGN KEY (granted_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE role_delegation (
    role_delegation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    delegator_user_id BIGINT UNSIGNED NOT NULL,
    delegate_user_id BIGINT UNSIGNED NOT NULL,
    source_assignment_id BIGINT UNSIGNED NOT NULL,
    valid_from DATETIME NOT NULL,
    valid_to DATETIME NOT NULL,
    delegation_status ENUM('PENDING','ACTIVE','REVOKED','EXPIRED') NOT NULL DEFAULT 'PENDING',
    reason VARCHAR(500) NOT NULL,
    approved_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_role_delegation_dates CHECK (valid_to > valid_from),
    CONSTRAINT chk_role_delegation_users CHECK (delegator_user_id <> delegate_user_id),
    CONSTRAINT fk_role_delegation_delegator FOREIGN KEY (delegator_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_role_delegation_delegate FOREIGN KEY (delegate_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_role_delegation_assignment FOREIGN KEY (source_assignment_id) REFERENCES user_role_assignment(user_role_assignment_id),
    CONSTRAINT fk_role_delegation_approved_by FOREIGN KEY (approved_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE password_history (
    password_history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_password_history_user FOREIGN KEY (user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE login_audit (
    login_audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NULL,
    username_attempted VARCHAR(100) NOT NULL,
    login_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    logout_at DATETIME NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    was_successful BOOLEAN NOT NULL,
    failure_reason VARCHAR(200) NULL,
    session_identifier VARCHAR(128) NULL,
    CONSTRAINT fk_login_audit_user FOREIGN KEY (user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE activity_audit (
    activity_audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NULL,
    module_code VARCHAR(50) NOT NULL,
    action_code VARCHAR(30) NOT NULL,
    entity_name VARCHAR(100) NULL,
    entity_id VARCHAR(100) NULL,
    activity_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45) NULL,
    request_identifier VARCHAR(128) NULL,
    before_values JSON NULL,
    after_values JSON NULL,
    details JSON NULL,
    CONSTRAINT fk_activity_audit_user FOREIGN KEY (user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE student_attendance
    ADD CONSTRAINT fk_student_attendance_marked_by
    FOREIGN KEY (marked_by_user_id) REFERENCES user_account(user_id);

ALTER TABLE file_object
    ADD CONSTRAINT fk_file_object_uploaded_by
    FOREIGN KEY (uploaded_by_user_id) REFERENCES user_account(user_id);

-- -------------------------------------------------------------
-- RBAC REFERENCE DATA (original catalogue preserved)
-- -------------------------------------------------------------
INSERT INTO access_action (action_code, action_name, description) VALUES
('CREATE','Create','Create a new record'),
('READ','Read','View a record or list'),
('UPDATE','Update','Modify an existing record'),
('DELETE','Delete','Soft-delete or remove a record where permitted'),
('APPROVE','Approve','Approve or reject a workflow item'),
('PUBLISH','Publish','Publish an approved record'),
('EXPORT','Export','Export data or reports'),
('ASSIGN','Assign','Assign users, faculty, students or responsibilities'),
('VERIFY','Verify','Verify submitted data or documents'),
('CONFIGURE','Configure','Change module configuration'),
('IMPERSONATE','Impersonate','Access the system as another user for support');

INSERT INTO access_module (module_code, module_name, display_order) VALUES
('IAM','Identity and Access Management',1),
('INSTITUTION','Institution Structure',2),
('ACADEMIC_CALENDAR','Academic Calendar',3),
('CURRICULUM','Curriculum and Course Catalog',4),
('STUDENT','Student Records',5),
('EMPLOYEE','Employee Records',6),
('ADMISSION','Admissions',7),
('REGISTRATION','Registration and Enrolment',8),
('TEACHING','Course Offering and Teaching',9),
('TIMETABLE','Timetable',10),
('ATTENDANCE','Attendance',11),
('ASSESSMENT','Continuous Assessment',12),
('RESULT','Examination and Results',13),
('FEEDBACK','Feedback',14),
('MENTORING','Mentoring and Counselling',15),
('GRIEVANCE','Grievance',16),
('DOCUMENT','Documents and Certificates',17),
('COMMUNICATION','Announcements and Notifications',18),
('REPORTING','Reports and Analytics',19),
('AUDIT','Audit and Compliance',20);

INSERT INTO access_resource (access_module_id, resource_code, resource_name)
SELECT access_module_id, 'ALL', CONCAT(module_name, ' - All Resources') FROM access_module;

INSERT INTO permission (access_resource_id, access_action_id, permission_code, permission_name, is_sensitive)
SELECT r.access_resource_id, a.access_action_id,
       CONCAT(m.module_code, '.', r.resource_code, '.', a.action_code),
       CONCAT(a.action_name, ' ', m.module_name),
       CASE WHEN m.module_code IN ('IAM','AUDIT','RESULT','STUDENT','EMPLOYEE')
                 AND a.action_code IN ('UPDATE','DELETE','APPROVE','EXPORT','CONFIGURE','IMPERSONATE')
            THEN TRUE ELSE FALSE END
FROM access_module m
JOIN access_resource r ON r.access_module_id = m.access_module_id
CROSS JOIN access_action a;

INSERT INTO role (role_code, role_name, role_category, role_level, description, is_system_role) VALUES
('SUPER_ADMIN','Super Administrator','SYSTEM','GLOBAL','Unrestricted platform administration and emergency access',TRUE),
('SYSTEM_ADMIN','System Administrator','SYSTEM','GLOBAL','User, configuration and technical administration',TRUE),
('SECURITY_ADMIN','Security Administrator','SYSTEM','GLOBAL','Security policy, roles, permissions and audit review',TRUE),
('DATABASE_ADMIN','Database Administrator','SYSTEM','GLOBAL','Database operations, migration and recovery oversight',TRUE),
('VICE_CHANCELLOR','Vice Chancellor','GOVERNANCE','INSTITUTION','University-wide governance dashboards and approvals',FALSE),
('REGISTRAR','Registrar','GOVERNANCE','INSTITUTION','Official student records and administrative approvals',FALSE),
('DEAN_ACADEMICS','Dean Academics','ACADEMIC','INSTITUTION','Curriculum, academic calendar and academic governance',FALSE),
('CONTROLLER_EXAMINATIONS','Controller of Examinations','ACADEMIC','INSTITUTION','Examination, result processing and publication',FALSE),
('FINANCE_OFFICER','Finance Officer','ADMINISTRATIVE','INSTITUTION','Financial review and approval',FALSE),
('CAMPUS_DIRECTOR','Campus Director','GOVERNANCE','CAMPUS','Campus-level administration and monitoring',FALSE),
('HEAD_DEPARTMENT','Head of Department','ACADEMIC','DEPARTMENT','Department administration and approvals',FALSE),
('PROGRAMME_COORDINATOR','Programme Coordinator','ACADEMIC','PROGRAMME','Programme planning and academic coordination',FALSE),
('SEMESTER_COORDINATOR','Semester Coordinator','ACADEMIC','PROGRAMME','Semester operations and coordination',FALSE),
('TIMETABLE_COORDINATOR','Timetable Coordinator','ACADEMIC','DEPARTMENT','Timetable preparation and maintenance',FALSE),
('COURSE_COORDINATOR','Course Coordinator','FACULTY','DEPARTMENT','Course delivery and assessment coordination',FALSE),
('FACULTY','Faculty','FACULTY','DEPARTMENT','Teaching, attendance and assessment for assigned offerings',FALSE),
('LAB_INSTRUCTOR','Laboratory Instructor','FACULTY','DEPARTMENT','Laboratory delivery, attendance and assessment',FALSE),
('FACULTY_ADVISOR','Faculty Advisor','FACULTY','PROGRAMME','Academic advising for assigned students',FALSE),
('MENTOR','Mentor','FACULTY','PROGRAMME','Mentoring and follow-up for assigned students',FALSE),
('ADMISSION_OFFICER','Admission Officer','ADMINISTRATIVE','INSTITUTION','Admission processing and approval',FALSE),
('DOCUMENT_VERIFIER','Document Verification Officer','ADMINISTRATIVE','INSTITUTION','Admission and student document verification',FALSE),
('STUDENT_SECTION_OFFICER','Student Section Officer','ADMINISTRATIVE','INSTITUTION','Student record administration and certificates',FALSE),
('EXAMINATION_OFFICER','Examination Officer','ADMINISTRATIVE','INSTITUTION','Examination operations and marks processing',FALSE),
('EVALUATOR','Evaluator','FACULTY','DEPARTMENT','Assessment and examination mark entry',FALSE),
('RESULT_APPROVER','Result Approver','ACADEMIC','INSTITUTION','Result verification, approval and publication',FALSE),
('GRIEVANCE_OFFICER','Grievance Officer','ADMINISTRATIVE','INSTITUTION','Grievance review, assignment and closure',FALSE),
('INTERNAL_AUDITOR','Internal Auditor','AUDIT','INSTITUTION','Read-only audit, compliance and controlled export',FALSE),
('EXTERNAL_AUDITOR','External Auditor','AUDIT','INSTITUTION','Time-bound read-only audit access',FALSE),
('STUDENT','Student','STUDENT','SELF','Self-service access to own academic information',TRUE),
('APPLICANT','Applicant','STUDENT','SELF','Admission application self-service',TRUE),
('PARENT_GUARDIAN','Parent or Guardian','PARENT','SELF','Authorized view of linked student information',TRUE),
('ALUMNI','Alumni','STUDENT','SELF','Graduate self-service and document requests',TRUE);

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
WHERE r.role_code = 'SUPER_ADMIN';

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code = 'SYSTEM_ADMIN'
  AND am.module_code IN ('IAM','INSTITUTION','ACADEMIC_CALENDAR','COMMUNICATION','REPORTING','AUDIT')
  AND aa.action_code NOT IN ('IMPERSONATE');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code = 'SECURITY_ADMIN' AND am.module_code IN ('IAM','AUDIT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','APPROVE','ASSIGN','CONFIGURE','EXPORT');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('VICE_CHANCELLOR','REGISTRAR','DEAN_ACADEMICS','CAMPUS_DIRECTOR','HEAD_DEPARTMENT')
  AND am.module_code NOT IN ('IAM') AND aa.action_code IN ('READ','EXPORT');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('REGISTRAR','DEAN_ACADEMICS','CAMPUS_DIRECTOR','HEAD_DEPARTMENT')
  AND am.module_code IN ('ACADEMIC_CALENDAR','CURRICULUM','STUDENT','REGISTRATION','TEACHING','TIMETABLE','ATTENDANCE','ASSESSMENT','DOCUMENT','COMMUNICATION')
  AND aa.action_code IN ('CREATE','UPDATE','APPROVE','ASSIGN','PUBLISH');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('PROGRAMME_COORDINATOR','SEMESTER_COORDINATOR','TIMETABLE_COORDINATOR','COURSE_COORDINATOR','FACULTY','LAB_INSTRUCTOR','FACULTY_ADVISOR','MENTOR')
  AND am.module_code IN ('ACADEMIC_CALENDAR','CURRICULUM','STUDENT','REGISTRATION','TEACHING','TIMETABLE','ATTENDANCE','ASSESSMENT','RESULT','FEEDBACK','MENTORING','COMMUNICATION','REPORTING')
  AND aa.action_code IN ('READ','CREATE','UPDATE','ASSIGN','EXPORT');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('ADMISSION_OFFICER','DOCUMENT_VERIFIER','STUDENT_SECTION_OFFICER')
  AND am.module_code IN ('STUDENT','ADMISSION','REGISTRATION','DOCUMENT','COMMUNICATION','REPORTING')
  AND aa.action_code IN ('CREATE','READ','UPDATE','APPROVE','VERIFY','EXPORT');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('CONTROLLER_EXAMINATIONS','EXAMINATION_OFFICER','EVALUATOR','RESULT_APPROVER')
  AND am.module_code IN ('STUDENT','REGISTRATION','ASSESSMENT','RESULT','DOCUMENT','COMMUNICATION','REPORTING','AUDIT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','APPROVE','VERIFY','PUBLISH','EXPORT','ASSIGN');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('INTERNAL_AUDITOR','EXTERNAL_AUDITOR')
  AND am.module_code IN ('INSTITUTION','ACADEMIC_CALENDAR','CURRICULUM','STUDENT','EMPLOYEE','ADMISSION','REGISTRATION','TEACHING','ATTENDANCE','ASSESSMENT','RESULT','DOCUMENT','REPORTING','AUDIT')
  AND aa.action_code IN ('READ','EXPORT');

INSERT INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
WHERE r.role_code IN ('STUDENT','APPLICANT','PARENT_GUARDIAN','ALUMNI')
  AND am.module_code IN ('STUDENT','ADMISSION','REGISTRATION','ATTENDANCE','ASSESSMENT','RESULT','FEEDBACK','DOCUMENT','COMMUNICATION')
  AND aa.action_code IN ('READ','CREATE','UPDATE');

CREATE OR REPLACE VIEW v_active_user_role AS
SELECT ura.user_role_assignment_id, ura.user_id, ura.role_id, r.role_code, r.role_name,
       ura.scope_type, ura.institution_id, ura.campus_id, ura.department_id, ura.programme_id,
       ura.valid_from, ura.valid_to
FROM user_role_assignment ura
JOIN role r ON r.role_id = ura.role_id
WHERE ura.assignment_status = 'ACTIVE' AND r.is_active = TRUE
  AND ura.valid_from <= CURRENT_TIMESTAMP
  AND (ura.valid_to IS NULL OR ura.valid_to > CURRENT_TIMESTAMP);

CREATE OR REPLACE VIEW v_active_role_permission AS
SELECT aur.user_id,
       aur.user_role_assignment_id AS source_assignment_id,
       aur.role_id,
       aur.role_code,
       aur.scope_type,
       CASE aur.scope_type
           WHEN 'GLOBAL' THEN 0
           WHEN 'INSTITUTION' THEN aur.institution_id
           WHEN 'CAMPUS' THEN aur.campus_id
           WHEN 'DEPARTMENT' THEN aur.department_id
           WHEN 'PROGRAMME' THEN aur.programme_id
           WHEN 'SELF' THEN aur.user_id
       END AS scope_entity_id,
       p.permission_id,
       p.permission_code,
       rp.permission_effect,
       'DIRECT' AS permission_source
FROM v_active_user_role aur
JOIN role_permission rp ON rp.role_id = aur.role_id
JOIN permission p ON p.permission_id = rp.permission_id
WHERE p.is_active = TRUE
UNION ALL
SELECT rd.delegate_user_id AS user_id,
       aur.user_role_assignment_id AS source_assignment_id,
       aur.role_id,
       aur.role_code,
       aur.scope_type,
       CASE aur.scope_type
           WHEN 'GLOBAL' THEN 0
           WHEN 'INSTITUTION' THEN aur.institution_id
           WHEN 'CAMPUS' THEN aur.campus_id
           WHEN 'DEPARTMENT' THEN aur.department_id
           WHEN 'PROGRAMME' THEN aur.programme_id
           WHEN 'SELF' THEN rd.delegate_user_id
       END AS scope_entity_id,
       p.permission_id,
       p.permission_code,
       rp.permission_effect,
       'DELEGATED' AS permission_source
FROM role_delegation rd
JOIN v_active_user_role aur ON aur.user_role_assignment_id = rd.source_assignment_id
JOIN role_permission rp ON rp.role_id = aur.role_id
JOIN permission p ON p.permission_id = rp.permission_id
WHERE rd.delegation_status = 'ACTIVE'
  AND rd.valid_from <= CURRENT_TIMESTAMP
  AND rd.valid_to > CURRENT_TIMESTAMP
  AND p.is_active = TRUE;

-- Exact-scope effective permission. DENY wins over ALLOW; active user overrides participate.
CREATE OR REPLACE VIEW v_effective_user_permission AS
SELECT x.user_id, x.permission_id, x.permission_code, x.scope_type, x.scope_entity_id,
       CASE WHEN MAX(x.is_deny) = 1 THEN 'DENY' ELSE 'ALLOW' END AS permission_effect
FROM (
    SELECT arp.user_id, arp.permission_id, arp.permission_code, arp.scope_type, arp.scope_entity_id,
           CASE WHEN arp.permission_effect='DENY' THEN 1 ELSE 0 END AS is_deny
    FROM v_active_role_permission arp
    UNION ALL
    SELECT upo.user_id, upo.permission_id, p.permission_code, upo.scope_type,
           CASE WHEN upo.scope_type IN ('GLOBAL','SELF') THEN 0 ELSE upo.scope_entity_id END AS scope_entity_id,
           CASE WHEN upo.permission_effect='DENY' THEN 1 ELSE 0 END AS is_deny
    FROM user_permission_override upo
    JOIN permission p ON p.permission_id=upo.permission_id
    WHERE p.is_active=TRUE
      AND upo.valid_from <= CURRENT_TIMESTAMP
      AND (upo.valid_to IS NULL OR upo.valid_to > CURRENT_TIMESTAMP)
) x
GROUP BY x.user_id, x.permission_id, x.permission_code, x.scope_type, x.scope_entity_id;

-- =============================================================
-- 16. EMPLOYEE HR PROFILE, QUALIFICATION, EXPERIENCE AND SECURE EVIDENCE MODULE
-- =============================================================
-- Security model:
-- 1) Full bank/PAN/Aadhaar identifiers are application-encrypted before persistence.
-- 2) *_fingerprint stores a deterministic keyed HMAC generated by the application for
--    duplicate detection/search. Never store encryption keys or HMAC keys in this DB.
-- 3) Normal UI/API views should use masked/last-four values only.
-- 4) Evidence binaries remain in protected object storage; only file_object references are stored.
-- 5) Every decrypt/view/download/export of restricted information should be recorded in
--    employee_sensitive_access_audit in addition to the general activity_audit trail.

CREATE TABLE qualification_level (
    qualification_level_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    level_code VARCHAR(40) NOT NULL UNIQUE,
    level_name VARCHAR(120) NOT NULL UNIQUE,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_terminal_degree BOOLEAN NOT NULL DEFAULT FALSE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE study_mode (
    study_mode_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    mode_code VARCHAR(30) NOT NULL UNIQUE,
    mode_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE education_institution_type (
    education_institution_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(30) NOT NULL UNIQUE,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE awarding_body_type (
    awarding_body_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(30) NOT NULL UNIQUE,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE education_institution (
    education_institution_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    education_institution_type_id TINYINT UNSIGNED NULL,
    institution_name VARCHAR(250) NOT NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    website_url VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_education_institution UNIQUE (institution_name, city, country_id),
    CONSTRAINT fk_education_institution_type FOREIGN KEY (education_institution_type_id) REFERENCES education_institution_type(education_institution_type_id),
    CONSTRAINT fk_education_institution_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_education_institution_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE awarding_body (
    awarding_body_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    awarding_body_type_id TINYINT UNSIGNED NULL,
    awarding_body_name VARCHAR(250) NOT NULL,
    university_type ENUM('CENTRAL','STATE','PRIVATE','DEEMED','FOREIGN','AUTONOMOUS','OTHER') NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    website_url VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_awarding_body UNIQUE (awarding_body_name, country_id),
    CONSTRAINT fk_awarding_body_type FOREIGN KEY (awarding_body_type_id) REFERENCES awarding_body_type(awarding_body_type_id),
    CONSTRAINT fk_awarding_body_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_awarding_body_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE previous_organization_type (
    previous_organization_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(40) NOT NULL UNIQUE,
    type_name VARCHAR(120) NOT NULL UNIQUE,
    classification ENUM('INDUSTRY','ACADEMIC','GOVERNMENT','PRIVATE','PUBLIC_SECTOR','NGO','SELF_EMPLOYED','OTHER') NOT NULL DEFAULT 'OTHER',
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE previous_organization (
    previous_organization_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    previous_organization_type_id TINYINT UNSIGNED NULL,
    organization_name VARCHAR(250) NOT NULL,
    address_line_1 VARCHAR(200) NULL,
    address_line_2 VARCHAR(200) NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    postal_code VARCHAR(12) NULL,
    phone VARCHAR(25) NULL,
    email VARCHAR(254) NULL,
    website_url VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_previous_organization UNIQUE (organization_name, city, country_id),
    CONSTRAINT fk_previous_organization_type FOREIGN KEY (previous_organization_type_id) REFERENCES previous_organization_type(previous_organization_type_id),
    CONSTRAINT fk_previous_organization_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_previous_organization_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_qualification (
    employee_qualification_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    qualification_level_id SMALLINT UNSIGNED NOT NULL,
    education_institution_id BIGINT UNSIGNED NULL,
    awarding_body_id BIGINT UNSIGNED NULL,
    study_mode_id TINYINT UNSIGNED NULL,
    degree_certificate_name VARCHAR(250) NOT NULL,
    specialization VARCHAR(200) NULL,
    course_program_name VARCHAR(250) NULL,
    start_date DATE NULL,
    start_year YEAR NULL,
    completion_date DATE NULL,
    completion_year YEAR NULL,
    passing_year YEAR NULL,
    registration_roll_number VARCHAR(100) NULL,
    result VARCHAR(100) NULL,
    class_grade VARCHAR(100) NULL,
    cgpa DECIMAL(6,3) NULL,
    cgpa_scale DECIMAL(6,3) NULL,
    percentage DECIMAL(5,2) NULL,
    maximum_marks DECIMAL(10,2) NULL,
    marks_obtained DECIMAL(10,2) NULL,
    qualification_status ENUM('COMPLETED','PURSUING','AWAITING_RESULT','DISCONTINUED','OTHER') NOT NULL DEFAULT 'COMPLETED',
    is_highest_qualification BOOLEAN NOT NULL DEFAULT FALSE,
    active_highest_employee_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_highest_qualification = TRUE AND deleted_at IS NULL THEN employee_id ELSE NULL END
    ) STORED,
    remarks VARCHAR(1000) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT uq_employee_qualification_owner UNIQUE (employee_qualification_id, employee_id),
    CONSTRAINT uq_employee_highest_qualification UNIQUE (active_highest_employee_id),
    CONSTRAINT chk_employee_qualification_dates CHECK (completion_date IS NULL OR start_date IS NULL OR completion_date >= start_date),
    CONSTRAINT chk_employee_qualification_percentage CHECK (percentage IS NULL OR (percentage >= 0 AND percentage <= 100)),
    CONSTRAINT chk_employee_qualification_cgpa CHECK (cgpa IS NULL OR cgpa >= 0),
    CONSTRAINT chk_employee_qualification_cgpa_scale CHECK (cgpa_scale IS NULL OR cgpa_scale > 0),
    CONSTRAINT chk_employee_qualification_cgpa_range CHECK (cgpa IS NULL OR cgpa_scale IS NULL OR cgpa <= cgpa_scale),
    CONSTRAINT chk_employee_qualification_marks CHECK (marks_obtained IS NULL OR maximum_marks IS NULL OR (marks_obtained >= 0 AND maximum_marks >= 0 AND marks_obtained <= maximum_marks)),
    CONSTRAINT fk_employee_qualification_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_qualification_level FOREIGN KEY (qualification_level_id) REFERENCES qualification_level(qualification_level_id),
    CONSTRAINT fk_employee_qualification_institution FOREIGN KEY (education_institution_id) REFERENCES education_institution(education_institution_id),
    CONSTRAINT fk_employee_qualification_awarding_body FOREIGN KEY (awarding_body_id) REFERENCES awarding_body(awarding_body_id),
    CONSTRAINT fk_employee_qualification_study_mode FOREIGN KEY (study_mode_id) REFERENCES study_mode(study_mode_id),
    CONSTRAINT fk_employee_qualification_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_qualification_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_previous_employment (
    employee_previous_employment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    previous_organization_id BIGINT UNSIGNED NOT NULL,
    department_division VARCHAR(200) NULL,
    designation VARCHAR(150) NOT NULL,
    employment_type ENUM('FULL_TIME','PART_TIME','CONTRACT','TEMPORARY','VISITING','CONSULTANT','TRAINEE','SELF_EMPLOYED','OTHER') NOT NULL,
    nature_of_work VARCHAR(1000) NULL,
    employment_start_date DATE NOT NULL,
    employment_end_date DATE NULL,
    experience_days INT UNSIGNED NULL,
    last_drawn_salary DECIMAL(14,2) NULL,
    salary_currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    reason_for_leaving VARCHAR(1000) NULL,
    reporting_authority_name VARCHAR(200) NULL,
    reporting_authority_designation VARCHAR(150) NULL,
    reporting_authority_phone VARCHAR(25) NULL,
    reporting_authority_email VARCHAR(254) NULL,
    remarks VARCHAR(1000) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT uq_employee_previous_employment_owner UNIQUE (employee_previous_employment_id, employee_id),
    CONSTRAINT chk_previous_employment_dates CHECK (employment_end_date IS NULL OR employment_end_date >= employment_start_date),
    CONSTRAINT chk_previous_employment_salary CHECK (last_drawn_salary IS NULL OR last_drawn_salary >= 0),
    CONSTRAINT fk_previous_employment_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_previous_employment_organization FOREIGN KEY (previous_organization_id) REFERENCES previous_organization(previous_organization_id),
    CONSTRAINT fk_previous_employment_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_previous_employment_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_bank_account (
    employee_bank_account_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    account_holder_name VARCHAR(200) NOT NULL,
    bank_name VARCHAR(200) NOT NULL,
    branch_name VARCHAR(200) NULL,
    account_number_ciphertext VARBINARY(1024) NOT NULL,
    account_number_fingerprint CHAR(64) NOT NULL UNIQUE,
    account_number_last4 CHAR(4) NOT NULL,
    account_number_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    account_type ENUM('SAVINGS','CURRENT','SALARY','NRE','NRO','OTHER') NOT NULL DEFAULT 'SAVINGS',
    ifsc_code VARCHAR(11) NOT NULL,
    micr_code VARCHAR(20) NULL,
    branch_code VARCHAR(30) NULL,
    bank_address VARCHAR(500) NULL,
    city VARCHAR(100) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    upi_id VARCHAR(150) NULL,
    is_salary_account BOOLEAN NOT NULL DEFAULT FALSE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    account_status ENUM('PENDING_VERIFICATION','ACTIVE','INACTIVE','CLOSED','REJECTED') NOT NULL DEFAULT 'PENDING_VERIFICATION',
    verification_status ENUM('PENDING','VERIFIED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,
    effective_from DATE NULL,
    effective_to DATE NULL,
    remarks VARCHAR(1000) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    active_primary_employee_id BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN is_primary = TRUE AND deleted_at IS NULL THEN employee_id ELSE NULL END) STORED,
    CONSTRAINT uq_employee_bank_owner UNIQUE (employee_bank_account_id, employee_id),
    CONSTRAINT uq_employee_primary_bank UNIQUE (active_primary_employee_id),
    CONSTRAINT chk_employee_bank_dates CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_employee_bank_last4 CHECK (account_number_last4 REGEXP '^[0-9]{4}$'),
    CONSTRAINT chk_employee_bank_ifsc CHECK (ifsc_code REGEXP '^[A-Za-z]{4}0[A-Za-z0-9]{6}$'),
    CONSTRAINT fk_employee_bank_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_bank_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_employee_bank_country FOREIGN KEY (country_id) REFERENCES country(country_id),
    CONSTRAINT fk_employee_bank_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_bank_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_bank_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_pan (
    employee_pan_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL UNIQUE,
    pan_number_ciphertext VARBINARY(1024) NOT NULL,
    pan_number_fingerprint CHAR(64) NOT NULL UNIQUE,
    pan_number_masked VARCHAR(15) NOT NULL,
    name_as_per_pan VARCHAR(200) NOT NULL,
    pan_issue_date DATE NULL,
    pan_issue_details VARCHAR(500) NULL,
    format_validated BOOLEAN NOT NULL DEFAULT FALSE,
    verification_status ENUM('PENDING','VERIFIED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,
    remarks VARCHAR(1000) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT uq_employee_pan_owner UNIQUE (employee_pan_id, employee_id),
    CONSTRAINT chk_employee_pan_masked CHECK (CHAR_LENGTH(pan_number_masked) BETWEEN 6 AND 15),
    CONSTRAINT fk_employee_pan_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_pan_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_pan_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_pan_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_aadhaar (
    employee_aadhaar_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL UNIQUE,
    aadhaar_number_ciphertext VARBINARY(1024) NOT NULL,
    aadhaar_number_fingerprint CHAR(64) NOT NULL UNIQUE,
    aadhaar_number_last4 CHAR(4) NOT NULL,
    aadhaar_number_masked VARCHAR(30) NOT NULL,
    name_as_per_aadhaar VARCHAR(200) NOT NULL,
    format_validated BOOLEAN NOT NULL DEFAULT FALSE,
    verification_status ENUM('PENDING','VERIFIED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,
    collection_purpose VARCHAR(500) NULL,
    remarks VARCHAR(1000) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT uq_employee_aadhaar_owner UNIQUE (employee_aadhaar_id, employee_id),
    CONSTRAINT chk_employee_aadhaar_last4 CHECK (aadhaar_number_last4 REGEXP '^[0-9]{4}$'),
    CONSTRAINT fk_employee_aadhaar_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_aadhaar_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_aadhaar_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_aadhaar_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_document_category (
    employee_document_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(50) NOT NULL UNIQUE,
    category_name VARCHAR(150) NOT NULL UNIQUE,
    default_confidentiality ENUM('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED','HIGHLY_RESTRICTED') NOT NULL DEFAULT 'INTERNAL',
    requires_verification BOOLEAN NOT NULL DEFAULT TRUE,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_document (
    employee_document_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    document_scope ENUM('EMPLOYEE_GENERAL','QUALIFICATION','PREVIOUS_EMPLOYMENT','BANK_ACCOUNT','PAN','AADHAAR') NOT NULL,
    employee_qualification_id BIGINT UNSIGNED NULL,
    employee_previous_employment_id BIGINT UNSIGNED NULL,
    employee_bank_account_id BIGINT UNSIGNED NULL,
    employee_pan_id BIGINT UNSIGNED NULL,
    employee_aadhaar_id BIGINT UNSIGNED NULL,
    employee_document_category_id SMALLINT UNSIGNED NOT NULL,
    document_type_id SMALLINT UNSIGNED NOT NULL,
    file_object_id BIGINT UNSIGNED NOT NULL,
    document_title VARCHAR(250) NOT NULL,
    document_number VARCHAR(150) NULL,
    issue_date DATE NULL,
    expiry_date DATE NULL,
    version_number SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    supersedes_employee_document_id BIGINT UNSIGNED NULL,
    verification_status ENUM('PENDING','UNDER_REVIEW','VERIFIED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,
    approval_status ENUM('NOT_REQUIRED','PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'NOT_REQUIRED',
    approved_by_user_id BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    approval_remarks VARCHAR(1000) NULL,
    confidentiality_level ENUM('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED','HIGHLY_RESTRICTED') NOT NULL DEFAULT 'CONFIDENTIAL',
    is_private BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    deleted_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    CONSTRAINT chk_employee_document_expiry CHECK (expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date),
    CONSTRAINT chk_employee_document_version CHECK (version_number > 0),
    CONSTRAINT chk_employee_document_scope CHECK (
        (document_scope='EMPLOYEE_GENERAL' AND employee_qualification_id IS NULL AND employee_previous_employment_id IS NULL AND employee_bank_account_id IS NULL AND employee_pan_id IS NULL AND employee_aadhaar_id IS NULL) OR
        (document_scope='QUALIFICATION' AND employee_qualification_id IS NOT NULL AND employee_previous_employment_id IS NULL AND employee_bank_account_id IS NULL AND employee_pan_id IS NULL AND employee_aadhaar_id IS NULL) OR
        (document_scope='PREVIOUS_EMPLOYMENT' AND employee_qualification_id IS NULL AND employee_previous_employment_id IS NOT NULL AND employee_bank_account_id IS NULL AND employee_pan_id IS NULL AND employee_aadhaar_id IS NULL) OR
        (document_scope='BANK_ACCOUNT' AND employee_qualification_id IS NULL AND employee_previous_employment_id IS NULL AND employee_bank_account_id IS NOT NULL AND employee_pan_id IS NULL AND employee_aadhaar_id IS NULL) OR
        (document_scope='PAN' AND employee_qualification_id IS NULL AND employee_previous_employment_id IS NULL AND employee_bank_account_id IS NULL AND employee_pan_id IS NOT NULL AND employee_aadhaar_id IS NULL) OR
        (document_scope='AADHAAR' AND employee_qualification_id IS NULL AND employee_previous_employment_id IS NULL AND employee_bank_account_id IS NULL AND employee_pan_id IS NULL AND employee_aadhaar_id IS NOT NULL)
    ),
    CONSTRAINT fk_employee_document_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_document_qualification_owner FOREIGN KEY (employee_qualification_id, employee_id) REFERENCES employee_qualification(employee_qualification_id, employee_id),
    CONSTRAINT fk_employee_document_experience_owner FOREIGN KEY (employee_previous_employment_id, employee_id) REFERENCES employee_previous_employment(employee_previous_employment_id, employee_id),
    CONSTRAINT fk_employee_document_bank_owner FOREIGN KEY (employee_bank_account_id, employee_id) REFERENCES employee_bank_account(employee_bank_account_id, employee_id),
    CONSTRAINT fk_employee_document_pan_owner FOREIGN KEY (employee_pan_id, employee_id) REFERENCES employee_pan(employee_pan_id, employee_id),
    CONSTRAINT fk_employee_document_aadhaar_owner FOREIGN KEY (employee_aadhaar_id, employee_id) REFERENCES employee_aadhaar(employee_aadhaar_id, employee_id),
    CONSTRAINT fk_employee_document_category FOREIGN KEY (employee_document_category_id) REFERENCES employee_document_category(employee_document_category_id),
    CONSTRAINT fk_employee_document_type FOREIGN KEY (document_type_id) REFERENCES document_type(document_type_id),
    CONSTRAINT fk_employee_document_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id),
    CONSTRAINT fk_employee_document_supersedes FOREIGN KEY (supersedes_employee_document_id) REFERENCES employee_document(employee_document_id),
    CONSTRAINT fk_employee_document_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_document_approved_by FOREIGN KEY (approved_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_document_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_document_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_document_deleted_by FOREIGN KEY (deleted_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_document_access_rule (
    employee_document_access_rule_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_document_id BIGINT UNSIGNED NOT NULL,
    role_id SMALLINT UNSIGNED NULL,
    user_id BIGINT UNSIGNED NULL,
    can_view BOOLEAN NOT NULL DEFAULT TRUE,
    can_download BOOLEAN NOT NULL DEFAULT FALSE,
    can_update BOOLEAN NOT NULL DEFAULT FALSE,
    can_verify BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to DATETIME NULL,
    granted_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_employee_document_access_principal CHECK ((role_id IS NOT NULL AND user_id IS NULL) OR (role_id IS NULL AND user_id IS NOT NULL)),
    CONSTRAINT chk_employee_document_access_dates CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT fk_employee_document_access_document FOREIGN KEY (employee_document_id) REFERENCES employee_document(employee_document_id),
    CONSTRAINT fk_employee_document_access_role FOREIGN KEY (role_id) REFERENCES role(role_id),
    CONSTRAINT fk_employee_document_access_user FOREIGN KEY (user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_document_access_granted_by FOREIGN KEY (granted_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE employee_sensitive_access_audit (
    employee_sensitive_access_audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    action_code ENUM('READ','DOWNLOAD','EXPORT','CREATE','UPDATE','VERIFY','APPROVE','DELETE','RESTORE','DECRYPT') NOT NULL,
    entity_type ENUM('QUALIFICATION','PREVIOUS_EMPLOYMENT','BANK_ACCOUNT','PAN','AADHAAR','EMPLOYEE_DOCUMENT') NOT NULL,
    entity_id BIGINT UNSIGNED NOT NULL,
    employee_document_id BIGINT UNSIGNED NULL,
    access_purpose VARCHAR(500) NULL,
    was_successful BOOLEAN NOT NULL DEFAULT TRUE,
    failure_reason VARCHAR(500) NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    request_identifier VARCHAR(128) NULL,
    accessed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee_sensitive_audit_user FOREIGN KEY (user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_employee_sensitive_audit_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_employee_sensitive_audit_document FOREIGN KEY (employee_document_id) REFERENCES employee_document(employee_document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE OR REPLACE VIEW v_employee_previous_experience AS
SELECT epe.employee_previous_employment_id,
       epe.employee_id,
       po.organization_name,
       epe.designation,
       epe.employment_type,
       epe.employment_start_date,
       epe.employment_end_date,
       COALESCE(epe.experience_days,
                DATEDIFF(COALESCE(epe.employment_end_date, CURRENT_DATE), epe.employment_start_date) + 1) AS calculated_experience_days,
       TIMESTAMPDIFF(YEAR, epe.employment_start_date, COALESCE(epe.employment_end_date, CURRENT_DATE)) AS completed_years,
       MOD(TIMESTAMPDIFF(MONTH, epe.employment_start_date, COALESCE(epe.employment_end_date, CURRENT_DATE)), 12) AS remaining_months
FROM employee_previous_employment epe
JOIN previous_organization po ON po.previous_organization_id = epe.previous_organization_id
WHERE epe.deleted_at IS NULL;

-- Reference data for employee qualifications and organizations.
INSERT INTO qualification_level (level_code, level_name, display_order, is_terminal_degree) VALUES
('SSLC_10','SSLC / 10th',10,FALSE),
('PUC_12','PUC / 12th',20,FALSE),
('DIPLOMA','Diploma',30,FALSE),
('UNDERGRADUATE','Undergraduate',40,FALSE),
('POSTGRADUATE','Postgraduate',50,FALSE),
('MPHIL','M.Phil.',60,FALSE),
('PHD','Ph.D.',70,TRUE),
('POSTDOCTORAL','Postdoctoral Qualification',80,TRUE),
('PROFESSIONAL_CERTIFICATION','Professional Certification',90,FALSE),
('OTHER','Other Qualification',100,FALSE);

INSERT INTO study_mode (mode_code, mode_name) VALUES
('REGULAR','Regular'),('FULL_TIME','Full-time'),('PART_TIME','Part-time'),
('DISTANCE','Distance Education'),('ONLINE','Online'),('HYBRID','Hybrid'),('OTHER','Other');

INSERT INTO education_institution_type (type_code, type_name) VALUES
('SCHOOL','School'),('PU_COLLEGE','PU / Higher Secondary College'),('COLLEGE','College'),
('UNIVERSITY','University'),('TRAINING_INSTITUTE','Training Institute'),('OTHER','Other');

INSERT INTO awarding_body_type (type_code, type_name) VALUES
('BOARD','Board'),('UNIVERSITY','University'),('AUTONOMOUS_BODY','Autonomous Body'),
('PROFESSIONAL_BODY','Professional Body'),('OTHER','Other');

INSERT INTO previous_organization_type (type_code, type_name, classification) VALUES
('ACADEMIC_INSTITUTION','Academic Institution','ACADEMIC'),
('GOVERNMENT_DEPARTMENT','Government Department','GOVERNMENT'),
('PRIVATE_COMPANY','Private Company','PRIVATE'),
('PUBLIC_SECTOR','Public Sector Undertaking','PUBLIC_SECTOR'),
('INDUSTRY','Industry','INDUSTRY'),
('NGO','NGO / Non-Profit','NGO'),
('SELF_EMPLOYED','Self Employed','SELF_EMPLOYED'),
('OTHER','Other Organization','OTHER');

INSERT INTO employee_document_category (category_code, category_name, default_confidentiality, requires_verification, requires_approval) VALUES
('QUALIFICATION','Qualification Evidence','CONFIDENTIAL',TRUE,FALSE),
('EXPERIENCE','Previous Employment Evidence','CONFIDENTIAL',TRUE,FALSE),
('BANK','Bank Account Evidence','HIGHLY_RESTRICTED',TRUE,TRUE),
('PAN','PAN Evidence','HIGHLY_RESTRICTED',TRUE,TRUE),
('AADHAAR','Aadhaar Evidence','HIGHLY_RESTRICTED',TRUE,TRUE),
('GENERAL','Other Employee Document','CONFIDENTIAL',TRUE,FALSE);

INSERT IGNORE INTO document_type (document_code, document_name, requires_verification, is_active) VALUES
('MARKS_CARD','Marks Card',TRUE,TRUE),
('DEGREE_CERT','Degree Certificate',TRUE,TRUE),
('PROVISIONAL_DEGREE','Provisional Degree Certificate',TRUE,TRUE),
('CONVOCATION_CERT','Convocation Certificate',TRUE,TRUE),
('CONSOLIDATED_MARKS','Consolidated Marks Card',TRUE,TRUE),
('TRANSCRIPT','Academic Transcript',TRUE,TRUE),
('MIGRATION_CERT','Migration Certificate',TRUE,TRUE),
('ELIGIBILITY_CERT','Eligibility Certificate',TRUE,TRUE),
('PHD_AWARD_CERT','Ph.D. Award Certificate',TRUE,TRUE),
('PROF_CERT','Professional Certification',TRUE,TRUE),
('EXPERIENCE_CERT','Experience Certificate',TRUE,TRUE),
('RELIEVING_LETTER','Relieving Letter',TRUE,TRUE),
('APPOINTMENT_LETTER','Appointment Letter',TRUE,TRUE),
('JOINING_LETTER','Joining Letter',TRUE,TRUE),
('SERVICE_CERT','Service Certificate',TRUE,TRUE),
('SALARY_CERT','Salary Certificate',TRUE,TRUE),
('PAY_SLIP','Pay Slip',TRUE,TRUE),
('PROMOTION_ORDER','Promotion Order',TRUE,TRUE),
('BANK_PASSBOOK_FRONT','Bank Passbook Front Page',TRUE,TRUE),
('CANCELLED_CHEQUE','Cancelled Cheque',TRUE,TRUE),
('BANK_STATEMENT','Bank Statement',TRUE,TRUE),
('BANK_CONFIRMATION','Bank Account Confirmation',TRUE,TRUE),
('PAN_CARD','PAN Card',TRUE,TRUE),
('PAN_VERIFICATION','PAN Verification Document',TRUE,TRUE),
('AADHAAR_FRONT','Aadhaar Front',TRUE,TRUE),
('AADHAAR_BACK','Aadhaar Back',TRUE,TRUE),
('E_AADHAAR','e-Aadhaar / Aadhaar PDF',TRUE,TRUE),
('OTHER_EMPLOYEE_DOC','Other Employee Supporting Document',TRUE,TRUE);

-- Granular RBAC for the new employee resources.
INSERT IGNORE INTO access_action (action_code, action_name, description)
VALUES ('DOWNLOAD','Download','Download an authorized stored document');

INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'QUALIFICATION', 'Employee Qualification', 'Employee qualification and educational history.' FROM access_module WHERE module_code='EMPLOYEE';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'EXPERIENCE', 'Previous Employment Experience', 'Employee previous employment and experience.' FROM access_module WHERE module_code='EMPLOYEE';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'BANK_ACCOUNT', 'Employee Bank Account', 'Restricted employee bank account information.' FROM access_module WHERE module_code='EMPLOYEE';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'PAN', 'Employee PAN', 'Highly restricted employee PAN information.' FROM access_module WHERE module_code='EMPLOYEE';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'AADHAAR', 'Employee Aadhaar', 'Highly restricted employee Aadhaar information.' FROM access_module WHERE module_code='EMPLOYEE';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'EMPLOYEE_DOCUMENT', 'Employee Evidence Document', 'Employee evidence files, verification and access control.' FROM access_module WHERE module_code='EMPLOYEE';

INSERT IGNORE INTO permission (access_resource_id, access_action_id, permission_code, permission_name, is_sensitive)
SELECT ar.access_resource_id, aa.access_action_id,
       CONCAT('EMPLOYEE.', ar.resource_code, '.', aa.action_code),
       CONCAT(aa.action_name, ' ', ar.resource_name),
       CASE WHEN ar.resource_code IN ('BANK_ACCOUNT','PAN','AADHAAR','EMPLOYEE_DOCUMENT')
                  OR aa.action_code IN ('DELETE','APPROVE','VERIFY','EXPORT','DOWNLOAD')
            THEN TRUE ELSE FALSE END
FROM access_resource ar
JOIN access_module am ON am.access_module_id=ar.access_module_id AND am.module_code='EMPLOYEE'
CROSS JOIN access_action aa
WHERE ar.resource_code IN ('QUALIFICATION','EXPERIENCE','BANK_ACCOUNT','PAN','AADHAAR','EMPLOYEE_DOCUMENT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','DELETE','APPROVE','VERIFY','EXPORT','DOWNLOAD');

INSERT IGNORE INTO role (role_code, role_name, role_category, role_level, description, is_system_role) VALUES
('HR_ADMIN','HR Administrator','ADMINISTRATIVE','INSTITUTION','Administers employee master, sensitive HR data and evidence subject to institutional policy.',TRUE),
('HR_OFFICER','HR Officer','ADMINISTRATIVE','INSTITUTION','Maintains qualifications, experience and employee evidence.',TRUE),
('PAYROLL_OFFICER','Payroll Officer','ADMINISTRATIVE','INSTITUTION','Maintains verified salary bank details and authorized payroll evidence.',TRUE);

-- Ensure Super Administrator also receives permissions inserted after the original broad grant.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
WHERE r.role_code='SUPER_ADMIN' AND p.permission_code LIKE 'EMPLOYEE.%';

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
WHERE r.role_code='HR_ADMIN' AND p.permission_code LIKE 'EMPLOYEE.%';

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='HR_OFFICER'
  AND ar.resource_code IN ('QUALIFICATION','EXPERIENCE','EMPLOYEE_DOCUMENT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','VERIFY','APPROVE','DOWNLOAD');

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='PAYROLL_OFFICER'
  AND ar.resource_code IN ('BANK_ACCOUNT','EMPLOYEE_DOCUMENT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','VERIFY','DOWNLOAD');

-- PAN/Aadhaar format validation must occur against plaintext in trusted application code
-- before encryption. The DB deliberately stores no plaintext PAN/Aadhaar values.

-- =============================================================
-- 17. STUDENT FEES AND FINANCIAL MANAGEMENT MODULE
-- Supports admission, academic, examination, service and other fees.
-- (Original fees module preserved; numbering shifted only because of the additive HR module.)
-- =============================================================
CREATE TABLE fee_category (
    fee_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(30) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_refundable BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE financial_ledger_account (
    ledger_account_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_account_id INT UNSIGNED NULL,
    account_code VARCHAR(40) NOT NULL UNIQUE,
    account_name VARCHAR(150) NOT NULL,
    account_type ENUM('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_ledger_parent FOREIGN KEY (parent_account_id) REFERENCES financial_ledger_account(ledger_account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_type (
    fee_type_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fee_category_id SMALLINT UNSIGNED NOT NULL,
    fee_code VARCHAR(40) NOT NULL UNIQUE,
    fee_name VARCHAR(150) NOT NULL,
    description VARCHAR(500) NULL,
    charge_frequency ENUM('ONE_TIME','ANNUAL','TERM','SEMESTER','MONTHLY','PER_APPLICATION','PER_EXAM','PER_COURSE','PER_SERVICE','OTHER') NOT NULL,
    ledger_account_id INT UNSIGNED NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
    is_refundable BOOLEAN NOT NULL DEFAULT FALSE,
    is_taxable BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_fee_type_category FOREIGN KEY (fee_category_id) REFERENCES fee_category(fee_category_id),
    CONSTRAINT fk_fee_type_ledger FOREIGN KEY (ledger_account_id) REFERENCES financial_ledger_account(ledger_account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_structure (
    fee_structure_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    structure_code VARCHAR(50) NOT NULL UNIQUE,
    structure_name VARCHAR(200) NOT NULL,
    institution_id SMALLINT UNSIGNED NOT NULL,
    campus_id SMALLINT UNSIGNED NULL,
    programme_id SMALLINT UNSIGNED NULL,
    specialization_id SMALLINT UNSIGNED NULL,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    admission_category_id SMALLINT UNSIGNED NULL,
    version_number SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    approval_status ENUM('DRAFT','SUBMITTED','APPROVED','REJECTED','SUPERSEDED') NOT NULL DEFAULT 'DRAFT',
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    remarks VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_fee_structure_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_fee_structure_specialization_programme CHECK (specialization_id IS NULL OR programme_id IS NOT NULL),
    CONSTRAINT fk_fee_structure_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_fee_structure_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id),
    CONSTRAINT fk_fee_structure_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_fee_structure_specialization_programme FOREIGN KEY (specialization_id, programme_id)
        REFERENCES programme_specialization(specialization_id, programme_id),
    CONSTRAINT fk_fee_structure_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_fee_structure_category FOREIGN KEY (admission_category_id) REFERENCES admission_category(admission_category_id),
    CONSTRAINT fk_fee_structure_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE late_fee_rule (
    late_fee_rule_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    rule_code VARCHAR(40) NOT NULL UNIQUE,
    rule_name VARCHAR(150) NOT NULL,
    calculation_method ENUM('FIXED','PER_DAY','PERCENTAGE','SLAB') NOT NULL,
    grace_period_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    fixed_amount DECIMAL(12,2) NULL,
    daily_amount DECIMAL(12,2) NULL,
    percentage_rate DECIMAL(7,4) NULL,
    maximum_amount DECIMAL(12,2) NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_late_fee_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE late_fee_slab (
    late_fee_slab_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    late_fee_rule_id INT UNSIGNED NOT NULL,
    from_day SMALLINT UNSIGNED NOT NULL,
    to_day SMALLINT UNSIGNED NULL,
    late_fee_amount DECIMAL(12,2) NOT NULL,
    CONSTRAINT uq_late_fee_slab UNIQUE (late_fee_rule_id, from_day),
    CONSTRAINT chk_late_fee_slab_days CHECK (to_day IS NULL OR to_day >= from_day),
    CONSTRAINT fk_late_fee_slab_rule FOREIGN KEY (late_fee_rule_id) REFERENCES late_fee_rule(late_fee_rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_structure_item (
    fee_structure_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fee_structure_id BIGINT UNSIGNED NOT NULL,
    fee_type_id INT UNSIGNED NOT NULL,
    semester_id TINYINT UNSIGNED NULL,
    academic_term_id INT UNSIGNED NULL,
    semester_key TINYINT UNSIGNED GENERATED ALWAYS AS (COALESCE(semester_id, 0)) STORED,
    academic_term_key INT UNSIGNED GENERATED ALWAYS AS (COALESCE(academic_term_id, 0)) STORED,
    amount DECIMAL(12,2) NOT NULL,
    due_date DATE NULL,
    due_days_from_registration SMALLINT UNSIGNED NULL,
    installment_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    waiver_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    late_fee_rule_id INT UNSIGNED NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    remarks VARCHAR(500) NULL,
    CONSTRAINT chk_fee_structure_item_amount CHECK (amount >= 0),
    CONSTRAINT uq_fee_structure_item UNIQUE (fee_structure_id, fee_type_id, semester_key, academic_term_key),
    CONSTRAINT fk_fee_structure_item_header FOREIGN KEY (fee_structure_id) REFERENCES fee_structure(fee_structure_id),
    CONSTRAINT fk_fee_structure_item_type FOREIGN KEY (fee_type_id) REFERENCES fee_type(fee_type_id),
    CONSTRAINT fk_fee_structure_item_semester FOREIGN KEY (semester_id) REFERENCES semester(semester_id),
    CONSTRAINT fk_fee_structure_item_term FOREIGN KEY (academic_term_id) REFERENCES academic_term(academic_term_id),
    CONSTRAINT fk_fee_structure_item_late_rule FOREIGN KEY (late_fee_rule_id) REFERENCES late_fee_rule(late_fee_rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_financial_account (
    student_account_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL UNIQUE,
    account_number VARCHAR(40) NOT NULL UNIQUE,
    account_status ENUM('ACTIVE','ON_HOLD','CLOSED') NOT NULL DEFAULT 'ACTIVE',
    opening_balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    credit_balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_student_financial_account_student FOREIGN KEY (student_id) REFERENCES student(student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_fee_assessment (
    fee_assessment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assessment_number VARCHAR(50) NOT NULL UNIQUE,
    student_account_id BIGINT UNSIGNED NULL,
    application_id BIGINT UNSIGNED NULL,
    enrolment_id BIGINT UNSIGNED NULL,
    term_registration_id BIGINT UNSIGNED NULL,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    academic_term_id INT UNSIGNED NULL,
    fee_structure_id BIGINT UNSIGNED NULL,
    assessment_type ENUM('ADMISSION','ACADEMIC','EXAMINATION','HOSTEL','TRANSPORT','LIBRARY','CERTIFICATE','PENALTY','SERVICE','OTHER') NOT NULL,
    assessment_date DATE NOT NULL,
    gross_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    concession_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    scholarship_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    adjustment_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    net_payable_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    amount_paid DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    balance_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    due_date DATE NULL,
    assessment_status ENUM('DRAFT','ASSESSED','PARTIALLY_PAID','PAID','OVERDUE','CANCELLED','WAIVED') NOT NULL DEFAULT 'DRAFT',
    remarks VARCHAR(500) NULL,
    created_by BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_fee_assessment_context CHECK (student_account_id IS NOT NULL OR application_id IS NOT NULL),
    CONSTRAINT chk_fee_assessment_amounts CHECK (
        gross_amount >= 0 AND concession_amount >= 0 AND scholarship_amount >= 0 AND
        net_payable_amount >= 0 AND amount_paid >= 0 AND amount_paid <= net_payable_amount AND
        net_payable_amount = gross_amount - concession_amount - scholarship_amount + adjustment_amount AND
        balance_amount = net_payable_amount - amount_paid
    ),
    CONSTRAINT fk_fee_assessment_account FOREIGN KEY (student_account_id) REFERENCES student_financial_account(student_account_id),
    CONSTRAINT fk_fee_assessment_application FOREIGN KEY (application_id) REFERENCES admission_application(application_id),
    CONSTRAINT fk_fee_assessment_enrolment FOREIGN KEY (enrolment_id) REFERENCES student_programme_enrolment(enrolment_id),
    CONSTRAINT fk_fee_assessment_term_registration FOREIGN KEY (term_registration_id) REFERENCES student_term_registration(term_registration_id),
    CONSTRAINT fk_fee_assessment_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_fee_assessment_term FOREIGN KEY (academic_term_id) REFERENCES academic_term(academic_term_id),
    CONSTRAINT fk_fee_assessment_structure FOREIGN KEY (fee_structure_id) REFERENCES fee_structure(fee_structure_id),
    CONSTRAINT fk_fee_assessment_creator FOREIGN KEY (created_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_fee_assessment_item (
    assessment_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fee_assessment_id BIGINT UNSIGNED NOT NULL,
    fee_type_id INT UNSIGNED NOT NULL,
    fee_structure_item_id BIGINT UNSIGNED NULL,
    description VARCHAR(250) NULL,
    original_amount DECIMAL(12,2) NOT NULL,
    concession_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    scholarship_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    adjustment_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    net_amount DECIMAL(12,2) NOT NULL,
    amount_paid DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    balance_amount DECIMAL(12,2) NOT NULL,
    due_date DATE NULL,
    item_status ENUM('ASSESSED','PARTIALLY_PAID','PAID','OVERDUE','CANCELLED','WAIVED') NOT NULL DEFAULT 'ASSESSED',
    CONSTRAINT chk_fee_assessment_item_amounts CHECK (
        original_amount >= 0 AND concession_amount >= 0 AND scholarship_amount >= 0 AND
        net_amount >= 0 AND amount_paid >= 0 AND amount_paid <= net_amount AND
        net_amount = original_amount - concession_amount - scholarship_amount + adjustment_amount AND
        balance_amount = net_amount - amount_paid
    ),
    CONSTRAINT fk_fee_item_assessment FOREIGN KEY (fee_assessment_id) REFERENCES student_fee_assessment(fee_assessment_id),
    CONSTRAINT fk_fee_item_type FOREIGN KEY (fee_type_id) REFERENCES fee_type(fee_type_id),
    CONSTRAINT fk_fee_item_structure_item FOREIGN KEY (fee_structure_item_id) REFERENCES fee_structure_item(fee_structure_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_charge_source (
    charge_source_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assessment_item_id BIGINT UNSIGNED NOT NULL,
    source_module VARCHAR(50) NOT NULL,
    source_entity VARCHAR(80) NOT NULL,
    source_entity_id BIGINT UNSIGNED NOT NULL,
    CONSTRAINT uq_fee_charge_source UNIQUE (assessment_item_id, source_module, source_entity, source_entity_id),
    CONSTRAINT fk_fee_charge_source_item FOREIGN KEY (assessment_item_id) REFERENCES student_fee_assessment_item(assessment_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE concession_type (
    concession_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    concession_code VARCHAR(40) NOT NULL UNIQUE,
    concession_name VARCHAR(150) NOT NULL,
    concession_basis ENUM('PERCENTAGE','FIXED_AMOUNT') NOT NULL,
    maximum_percentage DECIMAL(5,2) NULL,
    maximum_amount DECIMAL(12,2) NULL,
    approval_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_fee_concession (
    student_concession_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    concession_type_id SMALLINT UNSIGNED NOT NULL,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    application_number VARCHAR(50) NULL,
    application_date DATE NULL,
    approved_percentage DECIMAL(5,2) NULL,
    approved_amount DECIMAL(12,2) NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    approval_status ENUM('DRAFT','SUBMITTED','APPROVED','REJECTED','EXPIRED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    remarks VARCHAR(500) NULL,
    CONSTRAINT fk_student_concession_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_concession_type FOREIGN KEY (concession_type_id) REFERENCES concession_type(concession_type_id),
    CONSTRAINT fk_student_concession_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_student_concession_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE scholarship_scheme (
    scholarship_scheme_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    scheme_code VARCHAR(50) NOT NULL UNIQUE,
    scheme_name VARCHAR(200) NOT NULL,
    sponsoring_authority VARCHAR(200) NULL,
    scheme_type ENUM('GOVERNMENT','INSTITUTIONAL','PRIVATE','CSR','OTHER') NOT NULL,
    maximum_amount DECIMAL(12,2) NULL,
    is_reimbursable BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_scholarship (
    student_scholarship_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    scholarship_scheme_id INT UNSIGNED NOT NULL,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    application_number VARCHAR(60) NULL,
    sanction_number VARCHAR(60) NULL,
    applied_amount DECIMAL(12,2) NULL,
    sanctioned_amount DECIMAL(12,2) NULL,
    received_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    application_status ENUM('DRAFT','SUBMITTED','VERIFIED','SANCTIONED','REJECTED','RECEIVED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
    sanction_date DATE NULL,
    received_date DATE NULL,
    remarks VARCHAR(500) NULL,
    CONSTRAINT fk_student_scholarship_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_scholarship_scheme FOREIGN KEY (scholarship_scheme_id) REFERENCES scholarship_scheme(scholarship_scheme_id),
    CONSTRAINT fk_student_scholarship_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_sponsorship (
    student_sponsorship_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    academic_year_id SMALLINT UNSIGNED NOT NULL,
    sponsoring_authority VARCHAR(200) NOT NULL,
    sanction_reference VARCHAR(100) NOT NULL,
    sanctioned_amount DECIMAL(12,2) NOT NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    approval_status ENUM('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL DEFAULT 'PENDING',
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    CONSTRAINT uq_student_sponsorship_reference UNIQUE (student_id, academic_year_id, sanction_reference),
    CONSTRAINT chk_student_sponsorship_amount CHECK (sanctioned_amount > 0),
    CONSTRAINT chk_student_sponsorship_dates CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CONSTRAINT fk_student_sponsorship_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_sponsorship_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_student_sponsorship_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_assessment_benefit (
    assessment_benefit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assessment_item_id BIGINT UNSIGNED NOT NULL,
    benefit_type ENUM('CONCESSION','SCHOLARSHIP','SPONSORSHIP') NOT NULL,
    student_concession_id BIGINT UNSIGNED NULL,
    student_scholarship_id BIGINT UNSIGNED NULL,
    student_sponsorship_id BIGINT UNSIGNED NULL,
    benefit_amount DECIMAL(12,2) NOT NULL,
    applied_date DATE NOT NULL,
    approved_by BIGINT UNSIGNED NULL,
    CONSTRAINT chk_fee_benefit_amount CHECK (benefit_amount > 0),
    CONSTRAINT chk_fee_benefit_source CHECK (
        (benefit_type='CONCESSION' AND student_concession_id IS NOT NULL AND student_scholarship_id IS NULL AND student_sponsorship_id IS NULL) OR
        (benefit_type='SCHOLARSHIP' AND student_concession_id IS NULL AND student_scholarship_id IS NOT NULL AND student_sponsorship_id IS NULL) OR
        (benefit_type='SPONSORSHIP' AND student_concession_id IS NULL AND student_scholarship_id IS NULL AND student_sponsorship_id IS NOT NULL)
    ),
    CONSTRAINT fk_fee_benefit_item FOREIGN KEY (assessment_item_id) REFERENCES student_fee_assessment_item(assessment_item_id),
    CONSTRAINT fk_fee_benefit_concession FOREIGN KEY (student_concession_id) REFERENCES student_fee_concession(student_concession_id),
    CONSTRAINT fk_fee_benefit_scholarship FOREIGN KEY (student_scholarship_id) REFERENCES student_scholarship(student_scholarship_id),
    CONSTRAINT fk_fee_benefit_sponsorship FOREIGN KEY (student_sponsorship_id) REFERENCES student_sponsorship(student_sponsorship_id),
    CONSTRAINT fk_fee_benefit_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE installment_plan (
    installment_plan_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    plan_code VARCHAR(40) NOT NULL UNIQUE,
    plan_name VARCHAR(120) NOT NULL,
    number_of_installments TINYINT UNSIGNED NOT NULL,
    minimum_initial_percentage DECIMAL(5,2) NULL,
    approval_required BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_installment_schedule (
    student_installment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fee_assessment_id BIGINT UNSIGNED NOT NULL,
    installment_plan_id SMALLINT UNSIGNED NULL,
    installment_number TINYINT UNSIGNED NOT NULL,
    due_date DATE NOT NULL,
    installment_amount DECIMAL(12,2) NOT NULL,
    amount_paid DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    balance_amount DECIMAL(12,2) NOT NULL,
    installment_status ENUM('PENDING','PARTIALLY_PAID','PAID','OVERDUE','WAIVED','CANCELLED') NOT NULL DEFAULT 'PENDING',
    CONSTRAINT uq_student_installment UNIQUE (fee_assessment_id, installment_number),
    CONSTRAINT fk_installment_assessment FOREIGN KEY (fee_assessment_id) REFERENCES student_fee_assessment(fee_assessment_id),
    CONSTRAINT fk_installment_plan FOREIGN KEY (installment_plan_id) REFERENCES installment_plan(installment_plan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payment_mode (
    payment_mode_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    mode_code VARCHAR(30) NOT NULL UNIQUE,
    mode_name VARCHAR(80) NOT NULL UNIQUE,
    requires_reference BOOLEAN NOT NULL DEFAULT FALSE,
    is_online BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payment_transaction (
    payment_transaction_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    transaction_number VARCHAR(60) NOT NULL UNIQUE,
    student_account_id BIGINT UNSIGNED NULL,
    application_id BIGINT UNSIGNED NULL,
    transaction_date DATETIME NOT NULL,
    payment_mode_id TINYINT UNSIGNED NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    payment_status ENUM('INITIATED','PENDING','SUCCESS','FAILED','CANCELLED','REVERSED','PARTIALLY_REFUNDED','REFUNDED') NOT NULL,
    gateway_name VARCHAR(80) NULL,
    gateway_transaction_id VARCHAR(120) NULL,
    bank_reference_number VARCHAR(120) NULL,
    cheque_number VARCHAR(50) NULL,
    cheque_date DATE NULL,
    bank_name VARCHAR(150) NULL,
    payer_name VARCHAR(150) NULL,
    payer_contact VARCHAR(100) NULL,
    received_by BIGINT UNSIGNED NULL,
    remarks VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_payment_context CHECK (student_account_id IS NOT NULL OR application_id IS NOT NULL),
    CONSTRAINT chk_payment_amount CHECK (amount > 0),
    CONSTRAINT uq_payment_application_owner UNIQUE (payment_transaction_id, application_id),
    CONSTRAINT fk_payment_account FOREIGN KEY (student_account_id) REFERENCES student_financial_account(student_account_id),
    CONSTRAINT fk_payment_application FOREIGN KEY (application_id) REFERENCES admission_application(application_id),
    CONSTRAINT fk_payment_mode FOREIGN KEY (payment_mode_id) REFERENCES payment_mode(payment_mode_id),
    CONSTRAINT fk_payment_receiver FOREIGN KEY (received_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Admission payments now use the same payment_transaction ledger as all other fees.
CREATE TABLE admission_payment (
    admission_payment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    application_id BIGINT UNSIGNED NOT NULL,
    payment_transaction_id BIGINT UNSIGNED NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_admission_payment_application FOREIGN KEY (application_id) REFERENCES admission_application(application_id),
    CONSTRAINT fk_admission_payment_transaction_application FOREIGN KEY (payment_transaction_id, application_id)
        REFERENCES payment_transaction(payment_transaction_id, application_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payment_allocation (
    payment_allocation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    payment_transaction_id BIGINT UNSIGNED NOT NULL,
    assessment_item_id BIGINT UNSIGNED NOT NULL,
    allocated_amount DECIMAL(12,2) NOT NULL,
    allocation_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    allocated_by BIGINT UNSIGNED NULL,
    CONSTRAINT uq_payment_allocation UNIQUE (payment_transaction_id, assessment_item_id),
    CONSTRAINT chk_allocated_amount CHECK (allocated_amount > 0),
    CONSTRAINT fk_payment_allocation_payment FOREIGN KEY (payment_transaction_id) REFERENCES payment_transaction(payment_transaction_id),
    CONSTRAINT fk_payment_allocation_item FOREIGN KEY (assessment_item_id) REFERENCES student_fee_assessment_item(assessment_item_id),
    CONSTRAINT fk_payment_allocation_user FOREIGN KEY (allocated_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_receipt (
    fee_receipt_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    receipt_number VARCHAR(60) NOT NULL UNIQUE,
    payment_transaction_id BIGINT UNSIGNED NOT NULL,
    receipt_date DATETIME NOT NULL,
    receipt_amount DECIMAL(12,2) NOT NULL,
    receipt_status ENUM('ISSUED','CANCELLED','REPLACED','REVERSED') NOT NULL DEFAULT 'ISSUED',
    issued_by BIGINT UNSIGNED NULL,
    cancelled_by BIGINT UNSIGNED NULL,
    cancelled_at DATETIME NULL,
    cancellation_reason VARCHAR(500) NULL,
    original_receipt_id BIGINT UNSIGNED NULL,
    CONSTRAINT fk_fee_receipt_payment FOREIGN KEY (payment_transaction_id) REFERENCES payment_transaction(payment_transaction_id),
    CONSTRAINT fk_fee_receipt_issuer FOREIGN KEY (issued_by) REFERENCES user_account(user_id),
    CONSTRAINT fk_fee_receipt_canceller FOREIGN KEY (cancelled_by) REFERENCES user_account(user_id),
    CONSTRAINT fk_fee_receipt_original FOREIGN KEY (original_receipt_id) REFERENCES fee_receipt(fee_receipt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_adjustment (
    fee_adjustment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    adjustment_number VARCHAR(60) NOT NULL UNIQUE,
    student_account_id BIGINT UNSIGNED NOT NULL,
    assessment_item_id BIGINT UNSIGNED NULL,
    adjustment_type ENUM('CREDIT','DEBIT','WAIVER','WRITE_OFF','TRANSFER','CORRECTION') NOT NULL,
    adjustment_date DATE NOT NULL,
    adjustment_amount DECIMAL(12,2) NOT NULL,
    reason VARCHAR(500) NOT NULL,
    approval_status ENUM('DRAFT','SUBMITTED','APPROVED','REJECTED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    CONSTRAINT chk_adjustment_amount CHECK (adjustment_amount > 0),
    CONSTRAINT fk_fee_adjustment_account FOREIGN KEY (student_account_id) REFERENCES student_financial_account(student_account_id),
    CONSTRAINT fk_fee_adjustment_item FOREIGN KEY (assessment_item_id) REFERENCES student_fee_assessment_item(assessment_item_id),
    CONSTRAINT fk_fee_adjustment_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE refund_request (
    refund_request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    refund_request_number VARCHAR(60) NOT NULL UNIQUE,
    student_account_id BIGINT UNSIGNED NOT NULL,
    payment_transaction_id BIGINT UNSIGNED NULL,
    request_date DATE NOT NULL,
    refund_reason VARCHAR(500) NOT NULL,
    requested_amount DECIMAL(12,2) NOT NULL,
    approved_amount DECIMAL(12,2) NULL,
    request_status ENUM('SUBMITTED','UNDER_REVIEW','APPROVED','REJECTED','PROCESSED','CANCELLED') NOT NULL DEFAULT 'SUBMITTED',
    approved_by BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    CONSTRAINT chk_refund_request_amounts CHECK (
        requested_amount > 0 AND (approved_amount IS NULL OR (approved_amount >= 0 AND approved_amount <= requested_amount))
    ),
    CONSTRAINT fk_refund_request_account FOREIGN KEY (student_account_id) REFERENCES student_financial_account(student_account_id),
    CONSTRAINT fk_refund_request_payment FOREIGN KEY (payment_transaction_id) REFERENCES payment_transaction(payment_transaction_id),
    CONSTRAINT fk_refund_request_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_refund (
    fee_refund_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    refund_request_id BIGINT UNSIGNED NOT NULL,
    refund_transaction_number VARCHAR(60) NOT NULL UNIQUE,
    refund_date DATETIME NOT NULL,
    refund_amount DECIMAL(12,2) NOT NULL,
    refund_mode_id TINYINT UNSIGNED NOT NULL,
    bank_reference_number VARCHAR(120) NULL,
    processed_by BIGINT UNSIGNED NULL,
    refund_status ENUM('INITIATED','PROCESSING','SUCCESS','FAILED','CANCELLED') NOT NULL,
    remarks VARCHAR(500) NULL,
    CONSTRAINT chk_refund_amount CHECK (refund_amount > 0),
    CONSTRAINT fk_fee_refund_request FOREIGN KEY (refund_request_id) REFERENCES refund_request(refund_request_id),
    CONSTRAINT fk_fee_refund_mode FOREIGN KEY (refund_mode_id) REFERENCES payment_mode(payment_mode_id),
    CONSTRAINT fk_fee_refund_processor FOREIGN KEY (processed_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_fee_penalty (
    fee_penalty_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_account_id BIGINT UNSIGNED NOT NULL,
    assessment_item_id BIGINT UNSIGNED NULL,
    fee_type_id INT UNSIGNED NOT NULL,
    penalty_date DATE NOT NULL,
    penalty_reason VARCHAR(500) NOT NULL,
    penalty_amount DECIMAL(12,2) NOT NULL,
    waived_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    net_penalty_amount DECIMAL(12,2) NOT NULL,
    penalty_status ENUM('ASSESSED','PARTIALLY_PAID','PAID','WAIVED','CANCELLED') NOT NULL DEFAULT 'ASSESSED',
    approved_by BIGINT UNSIGNED NULL,
    CONSTRAINT fk_fee_penalty_account FOREIGN KEY (student_account_id) REFERENCES student_financial_account(student_account_id),
    CONSTRAINT fk_fee_penalty_item FOREIGN KEY (assessment_item_id) REFERENCES student_fee_assessment_item(assessment_item_id),
    CONSTRAINT fk_fee_penalty_type FOREIGN KEY (fee_type_id) REFERENCES fee_type(fee_type_id),
    CONSTRAINT fk_fee_penalty_approver FOREIGN KEY (approved_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE service_fee_request (
    service_fee_request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    request_number VARCHAR(50) NOT NULL UNIQUE,
    student_id BIGINT UNSIGNED NOT NULL,
    certificate_request_id BIGINT UNSIGNED NULL,
    fee_type_id INT UNSIGNED NOT NULL,
    request_date DATE NOT NULL,
    service_description VARCHAR(500) NULL,
    quantity SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    unit_amount DECIMAL(12,2) NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL,
    fee_assessment_id BIGINT UNSIGNED NULL,
    request_status ENUM('DRAFT','SUBMITTED','ASSESSED','PAID','PROCESSING','COMPLETED','REJECTED','CANCELLED') NOT NULL DEFAULT 'DRAFT',
    processed_by BIGINT UNSIGNED NULL,
    processed_at DATETIME NULL,
    CONSTRAINT fk_service_fee_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_service_fee_certificate FOREIGN KEY (certificate_request_id) REFERENCES certificate_request(certificate_request_id),
    CONSTRAINT fk_service_fee_type FOREIGN KEY (fee_type_id) REFERENCES fee_type(fee_type_id),
    CONSTRAINT fk_service_fee_assessment FOREIGN KEY (fee_assessment_id) REFERENCES student_fee_assessment(fee_assessment_id),
    CONSTRAINT fk_service_fee_processor FOREIGN KEY (processed_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_financial_hold (
    financial_hold_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_account_id BIGINT UNSIGNED NOT NULL,
    hold_type ENUM('REGISTRATION','EXAMINATION','HALL_TICKET','RESULT','CERTIFICATE','HOSTEL_CHECKOUT','GRADUATION','OTHER') NOT NULL,
    hold_reason VARCHAR(500) NOT NULL,
    placed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    placed_by BIGINT UNSIGNED NOT NULL,
    released_at DATETIME NULL,
    released_by BIGINT UNSIGNED NULL,
    release_reason VARCHAR(500) NULL,
    hold_status ENUM('ACTIVE','RELEASED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_financial_hold_account FOREIGN KEY (student_account_id) REFERENCES student_financial_account(student_account_id),
    CONSTRAINT fk_financial_hold_placed_by FOREIGN KEY (placed_by) REFERENCES user_account(user_id),
    CONSTRAINT fk_financial_hold_released_by FOREIGN KEY (released_by) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fee_activity_audit (
    fee_audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NULL,
    action_code VARCHAR(50) NOT NULL,
    entity_name VARCHAR(80) NOT NULL,
    entity_id BIGINT UNSIGNED NOT NULL,
    old_values JSON NULL,
    new_values JSON NULL,
    ip_address VARCHAR(45) NULL,
    performed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fee_audit_user FOREIGN KEY (user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO fee_category (category_code, category_name, display_order, is_refundable) VALUES
('ADMISSION','Admission Fees',10,FALSE),('ACADEMIC','Academic Fees',20,FALSE),
('EXAMINATION','Examination Fees',30,FALSE),('HOSTEL','Hostel Fees',40,TRUE),
('TRANSPORT','Transport Fees',50,TRUE),('LIBRARY','Library Fees and Penalties',60,FALSE),
('CERTIFICATE','Certificate and Document Fees',70,FALSE),('PENALTY','Fines and Penalties',80,FALSE),
('OTHER','Other Fees',90,FALSE);

INSERT INTO payment_mode (mode_code, mode_name, requires_reference, is_online) VALUES
('CASH','Cash',FALSE,FALSE),('CARD','Card',TRUE,TRUE),('UPI','UPI',TRUE,TRUE),
('NET_BANKING','Net Banking',TRUE,TRUE),('BANK_TRANSFER','Bank Transfer',TRUE,FALSE),
('CHEQUE','Cheque',TRUE,FALSE),('DEMAND_DRAFT','Demand Draft',TRUE,FALSE),
('PAYMENT_GATEWAY','Payment Gateway',TRUE,TRUE),('SCHOLARSHIP','Scholarship Credit',TRUE,FALSE),
('SPONSOR','Sponsor Payment',TRUE,FALSE),('ADJUSTMENT','Account Adjustment',TRUE,FALSE);

INSERT IGNORE INTO role (role_code, role_name, role_category, role_level, description, is_system_role) VALUES
('FINANCE_OFFICER','Finance Officer','ADMINISTRATIVE','INSTITUTION','Approves fee structures, refunds and financial reports.',TRUE),
('ACCOUNTANT','Accountant','ADMINISTRATIVE','CAMPUS','Maintains fee assessments, allocations and reconciliation.',TRUE),
('CASHIER','Cashier','ADMINISTRATIVE','CAMPUS','Receives payments and issues receipts.',TRUE),
('FEE_VERIFICATION_OFFICER','Fee Verification Officer','ADMINISTRATIVE','CAMPUS','Verifies concessions, scholarships and fee records.',TRUE),
('SCHOLARSHIP_OFFICER','Scholarship Officer','ADMINISTRATIVE','INSTITUTION','Administers scholarships and sponsorships.',TRUE);

INSERT IGNORE INTO access_module (module_code, module_name, description, display_order)
VALUES ('FEES','Fees and Financial Management','Student fee structures, assessments, payments, concessions, refunds and audit.',160);

INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'FEE_STRUCTURE', 'Fee Structure', 'Configure and approve programme fee structures.' FROM access_module WHERE module_code='FEES';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'FEE_ASSESSMENT', 'Student Fee Assessment', 'Raise and maintain student fee demands.' FROM access_module WHERE module_code='FEES';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'FEE_PAYMENT', 'Fee Payment and Receipt', 'Record payments, allocate collections and issue receipts.' FROM access_module WHERE module_code='FEES';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'FEE_BENEFIT', 'Concession and Scholarship', 'Administer concessions, scholarships and sponsorships.' FROM access_module WHERE module_code='FEES';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'FEE_REFUND', 'Refund and Adjustment', 'Approve and process refunds, waivers and adjustments.' FROM access_module WHERE module_code='FEES';
INSERT IGNORE INTO access_resource (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'FEE_REPORT', 'Fee Reports and Audit', 'View outstanding dues, collections and audit reports.' FROM access_module WHERE module_code='FEES';

INSERT IGNORE INTO permission (access_resource_id, access_action_id, permission_code, permission_name, is_sensitive)
SELECT ar.access_resource_id, aa.access_action_id,
       CONCAT('FEES.', ar.resource_code, '.', aa.action_code),
       CONCAT(aa.action_name, ' ', ar.resource_name),
       CASE WHEN aa.action_code IN ('APPROVE','DELETE','CONFIGURE','EXPORT') THEN TRUE ELSE FALSE END
FROM access_resource ar
JOIN access_module am ON am.access_module_id=ar.access_module_id AND am.module_code='FEES'
CROSS JOIN access_action aa
WHERE aa.action_code IN ('CREATE','READ','UPDATE','DELETE','APPROVE','VERIFY','EXPORT','CONFIGURE');

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
WHERE r.role_code='FINANCE_OFFICER' AND p.permission_code LIKE 'FEES.%';

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='ACCOUNTANT' AND p.permission_code LIKE 'FEES.%'
  AND aa.action_code IN ('CREATE','READ','UPDATE','VERIFY','EXPORT');

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='CASHIER' AND ar.resource_code='FEE_PAYMENT'
  AND aa.action_code IN ('CREATE','READ','UPDATE','VERIFY');

INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id FROM role r CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code IN ('SCHOLARSHIP_OFFICER','FEE_VERIFICATION_OFFICER')
  AND ar.resource_code IN ('FEE_BENEFIT','FEE_ASSESSMENT','FEE_REPORT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','APPROVE','VERIFY','EXPORT');

CREATE OR REPLACE VIEW v_student_fee_balance AS
SELECT sfa.student_account_id, sfa.student_id, sfa.account_number,
       COALESCE(SUM(sfa2.net_payable_amount),0.00) AS total_assessed,
       COALESCE(SUM(sfa2.amount_paid),0.00) AS total_paid,
       COALESCE(SUM(sfa2.balance_amount),0.00) AS total_outstanding,
       sfa.credit_balance
FROM student_financial_account sfa
LEFT JOIN student_fee_assessment sfa2 ON sfa2.student_account_id=sfa.student_account_id
 AND sfa2.assessment_status NOT IN ('CANCELLED','WAIVED')
GROUP BY sfa.student_account_id, sfa.student_id, sfa.account_number, sfa.credit_balance;

CREATE OR REPLACE VIEW v_fee_collection_summary AS
SELECT DATE(pt.transaction_date) AS collection_date, pm.mode_code,
       COUNT(*) AS transaction_count, SUM(pt.amount) AS collected_amount
FROM payment_transaction pt
JOIN payment_mode pm ON pm.payment_mode_id=pt.payment_mode_id
WHERE pt.payment_status='SUCCESS'
GROUP BY DATE(pt.transaction_date), pm.mode_code;


-- =============================================================
-- 17A. ENFORCEMENT TRIGGERS FOR CROSS-ROW / CROSS-TABLE RULES
-- =============================================================
DELIMITER $$

CREATE TRIGGER trg_user_role_assignment_scope_bi
BEFORE INSERT ON user_role_assignment
FOR EACH ROW
BEGIN
    DECLARE v_role_level VARCHAR(20);
    SELECT role_level INTO v_role_level FROM role WHERE role_id = NEW.role_id;
    IF v_role_level <> NEW.scope_type THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Role level must match assignment scope_type';
    END IF;
END$$

CREATE TRIGGER trg_user_role_assignment_scope_bu
BEFORE UPDATE ON user_role_assignment
FOR EACH ROW
BEGIN
    DECLARE v_role_level VARCHAR(20);
    SELECT role_level INTO v_role_level FROM role WHERE role_id = NEW.role_id;
    IF v_role_level <> NEW.scope_type THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Role level must match assignment scope_type';
    END IF;
END$$

CREATE TRIGGER trg_user_permission_override_scope_bi
BEFORE INSERT ON user_permission_override
FOR EACH ROW
BEGIN
    IF NEW.scope_type='INSTITUTION' AND NOT EXISTS (SELECT 1 FROM institution WHERE institution_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid institution scope_entity_id';
    ELSEIF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus WHERE campus_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid campus scope_entity_id';
    ELSEIF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department WHERE department_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid department scope_entity_id';
    ELSEIF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme WHERE programme_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid programme scope_entity_id';
    END IF;
END$$

CREATE TRIGGER trg_user_permission_override_scope_bu
BEFORE UPDATE ON user_permission_override
FOR EACH ROW
BEGIN
    IF NEW.scope_type='INSTITUTION' AND NOT EXISTS (SELECT 1 FROM institution WHERE institution_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid institution scope_entity_id';
    ELSEIF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus WHERE campus_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid campus scope_entity_id';
    ELSEIF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department WHERE department_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid department scope_entity_id';
    ELSEIF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme WHERE programme_id=NEW.scope_entity_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid programme scope_entity_id';
    END IF;
END$$

-- Keep fee-assessment header totals synchronized with its detail items.
CREATE TRIGGER trg_fee_item_ai
AFTER INSERT ON student_fee_assessment_item
FOR EACH ROW
BEGIN
    UPDATE student_fee_assessment a
    SET gross_amount=(SELECT COALESCE(SUM(i.original_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        concession_amount=(SELECT COALESCE(SUM(i.concession_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        scholarship_amount=(SELECT COALESCE(SUM(i.scholarship_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        adjustment_amount=(SELECT COALESCE(SUM(i.adjustment_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        net_payable_amount=(SELECT COALESCE(SUM(i.net_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        amount_paid=(SELECT COALESCE(SUM(i.amount_paid),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        balance_amount=(SELECT COALESCE(SUM(i.balance_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id)
    WHERE a.fee_assessment_id=NEW.fee_assessment_id;
END$$

CREATE TRIGGER trg_fee_item_au
AFTER UPDATE ON student_fee_assessment_item
FOR EACH ROW
BEGIN
    UPDATE student_fee_assessment a
    SET gross_amount=(SELECT COALESCE(SUM(i.original_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        concession_amount=(SELECT COALESCE(SUM(i.concession_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        scholarship_amount=(SELECT COALESCE(SUM(i.scholarship_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        adjustment_amount=(SELECT COALESCE(SUM(i.adjustment_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        net_payable_amount=(SELECT COALESCE(SUM(i.net_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        amount_paid=(SELECT COALESCE(SUM(i.amount_paid),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id),
        balance_amount=(SELECT COALESCE(SUM(i.balance_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=NEW.fee_assessment_id)
    WHERE a.fee_assessment_id=NEW.fee_assessment_id;
    IF OLD.fee_assessment_id <> NEW.fee_assessment_id THEN
        UPDATE student_fee_assessment a
        SET gross_amount=(SELECT COALESCE(SUM(i.original_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
            concession_amount=(SELECT COALESCE(SUM(i.concession_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
            scholarship_amount=(SELECT COALESCE(SUM(i.scholarship_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
            adjustment_amount=(SELECT COALESCE(SUM(i.adjustment_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
            net_payable_amount=(SELECT COALESCE(SUM(i.net_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
            amount_paid=(SELECT COALESCE(SUM(i.amount_paid),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
            balance_amount=(SELECT COALESCE(SUM(i.balance_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id)
        WHERE a.fee_assessment_id=OLD.fee_assessment_id;
    END IF;
END$$

CREATE TRIGGER trg_fee_item_ad
AFTER DELETE ON student_fee_assessment_item
FOR EACH ROW
BEGIN
    UPDATE student_fee_assessment a
    SET gross_amount=(SELECT COALESCE(SUM(i.original_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
        concession_amount=(SELECT COALESCE(SUM(i.concession_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
        scholarship_amount=(SELECT COALESCE(SUM(i.scholarship_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
        adjustment_amount=(SELECT COALESCE(SUM(i.adjustment_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
        net_payable_amount=(SELECT COALESCE(SUM(i.net_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
        amount_paid=(SELECT COALESCE(SUM(i.amount_paid),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id),
        balance_amount=(SELECT COALESCE(SUM(i.balance_amount),0) FROM student_fee_assessment_item i WHERE i.fee_assessment_id=OLD.fee_assessment_id)
    WHERE a.fee_assessment_id=OLD.fee_assessment_id;
END$$

-- Payment allocation may only use a successful payment, may not exceed the payment,
-- may not exceed the fee item's net amount, and must match the same account/application context.
CREATE TRIGGER trg_payment_allocation_bi
BEFORE INSERT ON payment_allocation
FOR EACH ROW
BEGIN
    DECLARE v_payment_amount DECIMAL(12,2);
    DECLARE v_status VARCHAR(30);
    DECLARE v_payment_account BIGINT UNSIGNED;
    DECLARE v_payment_application BIGINT UNSIGNED;
    DECLARE v_item_net DECIMAL(12,2);
    DECLARE v_assessment_account BIGINT UNSIGNED;
    DECLARE v_assessment_application BIGINT UNSIGNED;
    DECLARE v_existing_payment DECIMAL(12,2);
    DECLARE v_existing_item DECIMAL(12,2);
    SELECT amount,payment_status,student_account_id,application_id
      INTO v_payment_amount,v_status,v_payment_account,v_payment_application
      FROM payment_transaction WHERE payment_transaction_id=NEW.payment_transaction_id FOR UPDATE;
    IF v_status <> 'SUCCESS' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Only SUCCESS payments can be allocated'; END IF;
    SELECT i.net_amount,a.student_account_id,a.application_id
      INTO v_item_net,v_assessment_account,v_assessment_application
      FROM student_fee_assessment_item i JOIN student_fee_assessment a ON a.fee_assessment_id=i.fee_assessment_id
      WHERE i.assessment_item_id=NEW.assessment_item_id FOR UPDATE;
    IF NOT ((v_payment_account IS NOT NULL AND v_payment_account <=> v_assessment_account)
            OR (v_payment_application IS NOT NULL AND v_payment_application <=> v_assessment_application)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Payment and assessment contexts do not match';
    END IF;
    SELECT COALESCE(SUM(allocated_amount),0) INTO v_existing_payment FROM payment_allocation WHERE payment_transaction_id=NEW.payment_transaction_id;
    IF v_existing_payment + NEW.allocated_amount > v_payment_amount THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Allocation exceeds payment amount'; END IF;
    SELECT COALESCE(SUM(allocated_amount),0) INTO v_existing_item FROM payment_allocation WHERE assessment_item_id=NEW.assessment_item_id;
    IF v_existing_item + NEW.allocated_amount > v_item_net THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Allocation exceeds assessment item net amount'; END IF;
END$$

CREATE TRIGGER trg_payment_allocation_bu
BEFORE UPDATE ON payment_allocation
FOR EACH ROW
BEGIN
    DECLARE v_payment_amount DECIMAL(12,2);
    DECLARE v_status VARCHAR(30);
    DECLARE v_payment_account BIGINT UNSIGNED;
    DECLARE v_payment_application BIGINT UNSIGNED;
    DECLARE v_item_net DECIMAL(12,2);
    DECLARE v_assessment_account BIGINT UNSIGNED;
    DECLARE v_assessment_application BIGINT UNSIGNED;
    DECLARE v_existing_payment DECIMAL(12,2);
    DECLARE v_existing_item DECIMAL(12,2);
    SELECT amount,payment_status,student_account_id,application_id
      INTO v_payment_amount,v_status,v_payment_account,v_payment_application
      FROM payment_transaction WHERE payment_transaction_id=NEW.payment_transaction_id FOR UPDATE;
    IF v_status <> 'SUCCESS' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Only SUCCESS payments can be allocated'; END IF;
    SELECT i.net_amount,a.student_account_id,a.application_id
      INTO v_item_net,v_assessment_account,v_assessment_application
      FROM student_fee_assessment_item i JOIN student_fee_assessment a ON a.fee_assessment_id=i.fee_assessment_id
      WHERE i.assessment_item_id=NEW.assessment_item_id FOR UPDATE;
    IF NOT ((v_payment_account IS NOT NULL AND v_payment_account <=> v_assessment_account)
            OR (v_payment_application IS NOT NULL AND v_payment_application <=> v_assessment_application)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Payment and assessment contexts do not match';
    END IF;
    SELECT COALESCE(SUM(allocated_amount),0) INTO v_existing_payment FROM payment_allocation WHERE payment_transaction_id=NEW.payment_transaction_id AND payment_allocation_id<>OLD.payment_allocation_id;
    IF v_existing_payment + NEW.allocated_amount > v_payment_amount THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Allocation exceeds payment amount'; END IF;
    SELECT COALESCE(SUM(allocated_amount),0) INTO v_existing_item FROM payment_allocation WHERE assessment_item_id=NEW.assessment_item_id AND payment_allocation_id<>OLD.payment_allocation_id;
    IF v_existing_item + NEW.allocated_amount > v_item_net THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Allocation exceeds assessment item net amount'; END IF;
END$$

CREATE TRIGGER trg_payment_allocation_ai
AFTER INSERT ON payment_allocation
FOR EACH ROW
BEGIN
    UPDATE student_fee_assessment_item i
    SET amount_paid=(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=NEW.assessment_item_id),
        balance_amount=net_amount-(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=NEW.assessment_item_id)
    WHERE i.assessment_item_id=NEW.assessment_item_id;
END$$

CREATE TRIGGER trg_payment_allocation_au
AFTER UPDATE ON payment_allocation
FOR EACH ROW
BEGIN
    UPDATE student_fee_assessment_item i
    SET amount_paid=(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=NEW.assessment_item_id),
        balance_amount=net_amount-(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=NEW.assessment_item_id)
    WHERE i.assessment_item_id=NEW.assessment_item_id;
    IF OLD.assessment_item_id <> NEW.assessment_item_id THEN
        UPDATE student_fee_assessment_item i
        SET amount_paid=(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=OLD.assessment_item_id),
            balance_amount=net_amount-(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=OLD.assessment_item_id)
        WHERE i.assessment_item_id=OLD.assessment_item_id;
    END IF;
END$$

CREATE TRIGGER trg_payment_allocation_ad
AFTER DELETE ON payment_allocation
FOR EACH ROW
BEGIN
    UPDATE student_fee_assessment_item i
    SET amount_paid=(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=OLD.assessment_item_id),
        balance_amount=net_amount-(SELECT COALESCE(SUM(pa.allocated_amount),0) FROM payment_allocation pa WHERE pa.assessment_item_id=OLD.assessment_item_id)
    WHERE i.assessment_item_id=OLD.assessment_item_id;
END$$

-- Benefit totals cannot exceed the original assessed item amount.
CREATE TRIGGER trg_fee_benefit_bi
BEFORE INSERT ON fee_assessment_benefit
FOR EACH ROW
BEGIN
    DECLARE v_original DECIMAL(12,2);
    DECLARE v_existing DECIMAL(12,2);
    SELECT original_amount INTO v_original FROM student_fee_assessment_item WHERE assessment_item_id=NEW.assessment_item_id FOR UPDATE;
    SELECT COALESCE(SUM(benefit_amount),0) INTO v_existing FROM fee_assessment_benefit WHERE assessment_item_id=NEW.assessment_item_id;
    IF v_existing + NEW.benefit_amount > v_original THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Benefits exceed original assessment item amount'; END IF;
END$$

CREATE TRIGGER trg_fee_benefit_bu
BEFORE UPDATE ON fee_assessment_benefit
FOR EACH ROW
BEGIN
    DECLARE v_original DECIMAL(12,2);
    DECLARE v_existing DECIMAL(12,2);
    SELECT original_amount INTO v_original FROM student_fee_assessment_item WHERE assessment_item_id=NEW.assessment_item_id FOR UPDATE;
    SELECT COALESCE(SUM(benefit_amount),0) INTO v_existing FROM fee_assessment_benefit WHERE assessment_item_id=NEW.assessment_item_id AND assessment_benefit_id<>OLD.assessment_benefit_id;
    IF v_existing + NEW.benefit_amount > v_original THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Benefits exceed original assessment item amount'; END IF;
END$$

-- Refund processing cannot exceed request approval or the original payment amount.
CREATE TRIGGER trg_fee_refund_bi
BEFORE INSERT ON fee_refund
FOR EACH ROW
BEGIN
    DECLARE v_approved DECIMAL(12,2);
    DECLARE v_request_status VARCHAR(30);
    DECLARE v_payment_id BIGINT UNSIGNED;
    DECLARE v_payment_amount DECIMAL(12,2);
    DECLARE v_request_refunded DECIMAL(12,2);
    DECLARE v_payment_refunded DECIMAL(12,2);
    SELECT approved_amount,request_status,payment_transaction_id INTO v_approved,v_request_status,v_payment_id
      FROM refund_request WHERE refund_request_id=NEW.refund_request_id FOR UPDATE;
    IF v_approved IS NULL OR v_request_status NOT IN ('APPROVED','PROCESSED') THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refund request must be approved'; END IF;
    SELECT COALESCE(SUM(refund_amount),0) INTO v_request_refunded FROM fee_refund WHERE refund_request_id=NEW.refund_request_id AND refund_status='SUCCESS';
    IF NEW.refund_status='SUCCESS' AND v_request_refunded + NEW.refund_amount > v_approved THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refund exceeds approved amount'; END IF;
    IF v_payment_id IS NOT NULL AND NEW.refund_status='SUCCESS' THEN
        SELECT amount INTO v_payment_amount FROM payment_transaction WHERE payment_transaction_id=v_payment_id FOR UPDATE;
        SELECT COALESCE(SUM(fr.refund_amount),0) INTO v_payment_refunded
          FROM fee_refund fr JOIN refund_request rr ON rr.refund_request_id=fr.refund_request_id
          WHERE rr.payment_transaction_id=v_payment_id AND fr.refund_status='SUCCESS';
        IF v_payment_refunded + NEW.refund_amount > v_payment_amount THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Cumulative refund exceeds payment amount'; END IF;
    END IF;
END$$

CREATE TRIGGER trg_fee_refund_bu
BEFORE UPDATE ON fee_refund
FOR EACH ROW
BEGIN
    DECLARE v_approved DECIMAL(12,2);
    DECLARE v_request_status VARCHAR(30);
    DECLARE v_payment_id BIGINT UNSIGNED;
    DECLARE v_payment_amount DECIMAL(12,2);
    DECLARE v_request_refunded DECIMAL(12,2);
    DECLARE v_payment_refunded DECIMAL(12,2);
    SELECT approved_amount,request_status,payment_transaction_id INTO v_approved,v_request_status,v_payment_id
      FROM refund_request WHERE refund_request_id=NEW.refund_request_id FOR UPDATE;
    IF v_approved IS NULL OR v_request_status NOT IN ('APPROVED','PROCESSED') THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refund request must be approved'; END IF;
    SELECT COALESCE(SUM(refund_amount),0) INTO v_request_refunded FROM fee_refund WHERE refund_request_id=NEW.refund_request_id AND refund_status='SUCCESS' AND fee_refund_id<>OLD.fee_refund_id;
    IF NEW.refund_status='SUCCESS' AND v_request_refunded + NEW.refund_amount > v_approved THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refund exceeds approved amount'; END IF;
    IF v_payment_id IS NOT NULL AND NEW.refund_status='SUCCESS' THEN
        SELECT amount INTO v_payment_amount FROM payment_transaction WHERE payment_transaction_id=v_payment_id FOR UPDATE;
        SELECT COALESCE(SUM(fr.refund_amount),0) INTO v_payment_refunded
          FROM fee_refund fr JOIN refund_request rr ON rr.refund_request_id=fr.refund_request_id
          WHERE rr.payment_transaction_id=v_payment_id AND fr.refund_status='SUCCESS' AND fr.fee_refund_id<>OLD.fee_refund_id;
        IF v_payment_refunded + NEW.refund_amount > v_payment_amount THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Cumulative refund exceeds payment amount'; END IF;
    END IF;
END$$

DELIMITER ;

-- =============================================================
-- 18. PERFORMANCE INDEXES
-- =============================================================
CREATE INDEX idx_student_name ON student(last_name, first_name);
CREATE INDEX idx_employee_name ON employee(last_name, first_name);
CREATE INDEX idx_admission_applicant_name ON admission_applicant(last_name, first_name);
CREATE INDEX idx_student_status ON student(student_status);
CREATE INDEX idx_employee_status ON employee(employment_status);
CREATE INDEX idx_employee_institution_source ON employee(institution_id, employment_source_id, employment_status);
CREATE INDEX idx_employee_external_agency ON employee(external_agency_id, employment_status);
CREATE INDEX idx_employee_assignment_location ON employee_assignment(campus_id, department_id, designation_id, is_primary);
CREATE INDEX idx_staff_category_type ON staff_category(staff_type_id, is_active);
CREATE INDEX idx_designation_category ON designation(staff_category_id, is_active);
CREATE INDEX idx_external_agency_institution ON external_agency(institution_id, is_active);
CREATE INDEX idx_application_status ON admission_application(application_status, academic_year_id);
CREATE INDEX idx_enrolment_status ON student_programme_enrolment(enrolment_status);
CREATE INDEX idx_term_registration_section ON student_term_registration(class_section_id, registration_status);
CREATE INDEX idx_course_registration_status ON student_course_registration(course_offering_id, registration_status);
CREATE INDEX idx_class_session_date ON class_session(session_date, course_offering_section_id);
CREATE INDEX idx_student_attendance_roster ON student_attendance(course_offering_section_student_id, attendance_status_id);
CREATE INDEX idx_assessment_event_date ON assessment_event(assessment_date);
CREATE INDEX idx_course_result_status ON student_course_result(result_status);
CREATE INDEX idx_grievance_status ON grievance(status, priority, submitted_at);
CREATE INDEX idx_announcement_publish ON announcement(approval_status, publish_from, publish_to);
CREATE INDEX idx_activity_audit_entity ON activity_audit(entity_name, entity_id, activity_at);
CREATE INDEX idx_user_account_status ON user_account(account_status, username);
CREATE INDEX idx_user_role_active ON user_role_assignment(user_id, assignment_status, valid_from, valid_to);
CREATE INDEX idx_user_role_scope ON user_role_assignment(scope_type, scope_entity_id);
CREATE INDEX idx_role_permission_effect ON role_permission(role_id, permission_effect);
CREATE INDEX idx_permission_lookup ON permission(access_resource_id, access_action_id, is_active);
CREATE INDEX idx_login_audit_user_time ON login_audit(user_id, login_at);
CREATE INDEX idx_password_history_user_time ON password_history(user_id, changed_at);

CREATE INDEX idx_fee_structure_scope ON fee_structure(academic_year_id, programme_id, admission_category_id, approval_status);
CREATE INDEX idx_fee_assessment_account_status ON student_fee_assessment(student_account_id, assessment_status, due_date);
CREATE INDEX idx_fee_assessment_year_term ON student_fee_assessment(academic_year_id, academic_term_id, assessment_type);
CREATE INDEX idx_fee_item_balance ON student_fee_assessment_item(item_status, due_date, balance_amount);
CREATE INDEX idx_payment_account_date ON payment_transaction(student_account_id, transaction_date);
CREATE INDEX idx_payment_gateway_reference ON payment_transaction(gateway_transaction_id);
CREATE INDEX idx_payment_status_date ON payment_transaction(payment_status, transaction_date);
CREATE INDEX idx_payment_allocation_item ON payment_allocation(assessment_item_id);
CREATE INDEX idx_receipt_date_status ON fee_receipt(receipt_date, receipt_status);
CREATE INDEX idx_concession_student_year ON student_fee_concession(student_id, academic_year_id, approval_status);
CREATE INDEX idx_scholarship_student_year ON student_scholarship(student_id, academic_year_id, application_status);
CREATE INDEX idx_refund_status_date ON refund_request(request_status, request_date);
CREATE INDEX idx_fee_audit_entity ON fee_activity_audit(entity_name, entity_id, performed_at);

-- New employee HR/security indexes.
CREATE INDEX idx_education_institution_lookup ON education_institution(institution_name, city, country_id, is_active);
CREATE INDEX idx_awarding_body_lookup ON awarding_body(awarding_body_name, university_type, country_id, is_active);
CREATE INDEX idx_employee_qualification_employee ON employee_qualification(employee_id, qualification_level_id, qualification_status, deleted_at);
CREATE INDEX idx_employee_qualification_passing ON employee_qualification(passing_year, is_highest_qualification);
CREATE INDEX idx_previous_organization_lookup ON previous_organization(organization_name, previous_organization_type_id, city, country_id);
CREATE INDEX idx_employee_previous_employment_employee ON employee_previous_employment(employee_id, employment_start_date, employment_end_date, deleted_at);
CREATE INDEX idx_employee_bank_employee_status ON employee_bank_account(employee_id, account_status, verification_status, is_primary, deleted_at);
CREATE INDEX idx_employee_bank_ifsc ON employee_bank_account(ifsc_code, bank_name);
CREATE INDEX idx_employee_pan_status ON employee_pan(employee_id, verification_status, deleted_at);
CREATE INDEX idx_employee_aadhaar_status ON employee_aadhaar(employee_id, verification_status, deleted_at);
CREATE INDEX idx_employee_document_owner_scope ON employee_document(employee_id, document_scope, is_active, deleted_at);
CREATE INDEX idx_employee_document_qualification ON employee_document(employee_qualification_id, verification_status, approval_status);
CREATE INDEX idx_employee_document_experience ON employee_document(employee_previous_employment_id, verification_status, approval_status);
CREATE INDEX idx_employee_document_bank ON employee_document(employee_bank_account_id, verification_status, approval_status);
CREATE INDEX idx_employee_document_pan ON employee_document(employee_pan_id, verification_status, approval_status);
CREATE INDEX idx_employee_document_aadhaar ON employee_document(employee_aadhaar_id, verification_status, approval_status);
CREATE INDEX idx_employee_document_category_type ON employee_document(employee_document_category_id, document_type_id, confidentiality_level);
CREATE INDEX idx_employee_document_file ON employee_document(file_object_id);
CREATE INDEX idx_employee_document_access_role ON employee_document_access_rule(role_id, valid_from, valid_to);
CREATE INDEX idx_employee_document_access_user ON employee_document_access_rule(user_id, valid_from, valid_to);
CREATE INDEX idx_employee_sensitive_audit_employee ON employee_sensitive_access_audit(employee_id, entity_type, accessed_at);
CREATE INDEX idx_employee_sensitive_audit_user ON employee_sensitive_access_audit(user_id, accessed_at);
CREATE INDEX idx_file_object_confidentiality ON file_object(confidentiality_level, is_encrypted, deleted_at);

-- Staff academic/research/evidence extension follows before FK checks are restored.

-- =============================================================
-- END OF SIMS V6 CORRECTED / ENFORCED SCHEMA
-- University + Academic + HR + RBAC + Unified Financial Integrity
-- =============================================================


-- =============================================================
-- 19+. STAFF ACADEMIC / RESEARCH / EVIDENCE EXTENSION (CONSOLIDATED)
-- =============================================================
-- =============================================================
-- SIMS V6 EXTENSION
-- STAFF ACADEMIC, RESEARCH, PROFESSIONAL DEVELOPMENT,
-- INDUSTRY, CO-CURRICULAR, EXTRA-CURRICULAR PROFILE
-- AND CENTRALIZED EVIDENCE MANAGEMENT
-- MySQL 8.0+
--
-- Baseline:
--   sims_v6_independent_student_staff_full_schema.sql
--
-- This module is integrated into this full schema. It preserves the independent
-- student and employee root entities while extending the Staff module.
-- Existing organizational hierarchy:
--   university -> institution -> campus -> department
-- Existing independent staff root entity:
--   employee (no generic person inheritance)
-- =============================================================

-- Integrated full-schema section; database selection and character set are controlled at the top of this file.
-- Foreign key checks are controlled by the consolidated schema.

-- =============================================================
-- 18. EXTEND EXISTING FILE STORAGE METADATA
-- =============================================================

ALTER TABLE file_object
    ADD COLUMN encryption_key_reference VARCHAR(255) NULL AFTER is_encrypted,
    ADD COLUMN virus_scan_status ENUM('NOT_SCANNED','PENDING','CLEAN','INFECTED','ERROR')
        NOT NULL DEFAULT 'NOT_SCANNED' AFTER encryption_key_reference,
    ADD COLUMN virus_scanned_at DATETIME NULL AFTER virus_scan_status;

-- =============================================================
-- 19. STAFF PROFILE REFERENCE / MASTER DATA
-- =============================================================

CREATE TABLE publication_type (
    publication_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    publication_type_code VARCHAR(40) NOT NULL UNIQUE,
    publication_type_name VARCHAR(120) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE journal_type (
    journal_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    journal_type_code VARCHAR(30) NOT NULL UNIQUE,
    journal_type_name VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(300) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE indexing_agency (
    indexing_agency_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    agency_code VARCHAR(40) NOT NULL UNIQUE,
    agency_name VARCHAR(150) NOT NULL UNIQUE,
    website_url VARCHAR(500) NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE metric_type (
    metric_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    metric_code VARCHAR(30) NOT NULL UNIQUE,
    metric_name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(300) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE organization_type (
    organization_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    organization_type_code VARCHAR(40) NOT NULL UNIQUE,
    organization_type_name VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE external_organization (
    organization_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    organization_code VARCHAR(60) NULL UNIQUE,
    organization_name VARCHAR(250) NOT NULL,
    short_name VARCHAR(100) NULL,
    website_url VARCHAR(500) NULL,
    email VARCHAR(254) NULL,
    phone VARCHAR(30) NULL,
    address_line_1 VARCHAR(250) NULL,
    address_line_2 VARCHAR(250) NULL,
    city VARCHAR(120) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    postal_code VARCHAR(20) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_external_organization_name UNIQUE (organization_name, city, country_id),
    CONSTRAINT fk_external_organization_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_external_organization_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE external_organization_type (
    organization_id BIGINT UNSIGNED NOT NULL,
    organization_type_id SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (organization_id, organization_type_id),
    CONSTRAINT fk_external_org_type_org FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_external_org_type_type FOREIGN KEY (organization_type_id)
        REFERENCES organization_type(organization_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Role-specific reusable organization masters requested by the design.
CREATE TABLE organizer (
    organizer_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    organization_id BIGINT UNSIGNED NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_organizer_organization FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE publisher (
    publisher_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    organization_id BIGINT UNSIGNED NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_publisher_organization FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE funding_type (
    funding_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    funding_type_code VARCHAR(30) NOT NULL UNIQUE,
    funding_type_name VARCHAR(100) NOT NULL UNIQUE,
    is_external BOOLEAN NOT NULL DEFAULT FALSE,
    description VARCHAR(300) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE funding_agency (
    funding_agency_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    organization_id BIGINT UNSIGNED NOT NULL UNIQUE,
    funding_type_id TINYINT UNSIGNED NOT NULL,
    agency_category VARCHAR(100) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_funding_agency_org FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_funding_agency_type FOREIGN KEY (funding_type_id)
        REFERENCES funding_type(funding_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE activity_type (
    activity_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    activity_type_code VARCHAR(50) NOT NULL UNIQUE,
    activity_type_name VARCHAR(150) NOT NULL UNIQUE,
    activity_group ENUM(
        'PUBLICATION','CONFERENCE','PROFESSIONAL_DEVELOPMENT','INTERNSHIP',
        'RESEARCH','CONSULTANCY','CO_CURRICULAR','EXTRA_CURRICULAR',
        'AWARD','MEMBERSHIP','ACADEMIC_PROFESSIONAL_CONTRIBUTION','OTHER'
    ) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE participation_level (
    participation_level_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    level_code VARCHAR(30) NOT NULL UNIQUE,
    level_name VARCHAR(100) NOT NULL UNIQUE,
    display_order TINYINT UNSIGNED NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE role_type (
    role_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    role_code VARCHAR(50) NOT NULL UNIQUE,
    role_name VARCHAR(150) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE research_status (
    research_status_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    status_code VARCHAR(30) NOT NULL UNIQUE,
    status_name VARCHAR(100) NOT NULL UNIQUE,
    display_order TINYINT UNSIGNED NOT NULL DEFAULT 0,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE event_mode (
    event_mode_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    mode_code VARCHAR(20) NOT NULL UNIQUE,
    mode_name VARCHAR(60) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE evidence_type (
    evidence_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    evidence_type_code VARCHAR(60) NOT NULL UNIQUE,
    evidence_type_name VARCHAR(180) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE verification_status (
    verification_status_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    status_code VARCHAR(30) NOT NULL UNIQUE,
    status_name VARCHAR(80) NOT NULL UNIQUE,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE approval_status (
    approval_status_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    status_code VARCHAR(30) NOT NULL UNIQUE,
    status_name VARCHAR(80) NOT NULL UNIQUE,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE training_program_type (
    training_program_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(40) NOT NULL UNIQUE,
    type_name VARCHAR(120) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE conference_contribution_type (
    conference_contribution_type_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(40) NOT NULL UNIQUE,
    type_name VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE industry_sector (
    industry_sector_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sector_code VARCHAR(50) NOT NULL UNIQUE,
    sector_name VARCHAR(150) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cocurricular_category (
    cocurricular_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(50) NOT NULL UNIQUE,
    category_name VARCHAR(150) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE extracurricular_category (
    extracurricular_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(50) NOT NULL UNIQUE,
    category_name VARCHAR(150) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE award_category (
    award_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_code VARCHAR(50) NOT NULL UNIQUE,
    category_name VARCHAR(150) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE membership_type (
    membership_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(50) NOT NULL UNIQUE,
    type_name VARCHAR(150) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE professional_contribution_type (
    professional_contribution_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    contribution_code VARCHAR(60) NOT NULL UNIQUE,
    contribution_name VARCHAR(180) NOT NULL UNIQUE,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE confidentiality_level (
    confidentiality_level_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    level_code VARCHAR(30) NOT NULL UNIQUE,
    level_name VARCHAR(80) NOT NULL UNIQUE,
    display_order TINYINT UNSIGNED NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 20. STAFF ACTIVITY SUPERTYPE
-- Every specialized staff profile record has exactly one parent activity.
-- =============================================================

CREATE TABLE staff_activity (
    staff_activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NOT NULL,
    activity_type_id SMALLINT UNSIGNED NOT NULL,
    academic_year_id SMALLINT UNSIGNED NULL,
    institution_id SMALLINT UNSIGNED NOT NULL,
    campus_id SMALLINT UNSIGNED NULL,
    department_id SMALLINT UNSIGNED NULL,
    participation_level_id TINYINT UNSIGNED NULL,
    primary_role_type_id SMALLINT UNSIGNED NULL,
    activity_title VARCHAR(500) NOT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    description TEXT NULL,
    outcomes TEXT NULL,
    remarks TEXT NULL,

    verification_status_id TINYINT UNSIGNED NOT NULL,
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,

    approval_status_id TINYINT UNSIGNED NOT NULL,
    approved_by_user_id BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    approval_remarks VARCHAR(1000) NULL,
    rejection_reason VARCHAR(1000) NULL,

    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    deleted_at DATETIME NULL,
    deleted_by_user_id BIGINT UNSIGNED NULL,
    deletion_reason VARCHAR(1000) NULL,

    CONSTRAINT chk_staff_activity_dates CHECK (
        end_date IS NULL OR start_date IS NULL OR end_date >= start_date
    ),
    CONSTRAINT fk_staff_activity_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
    CONSTRAINT fk_staff_activity_type FOREIGN KEY (activity_type_id) REFERENCES activity_type(activity_type_id),
    CONSTRAINT fk_staff_activity_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_staff_activity_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_staff_activity_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id),
    CONSTRAINT fk_staff_activity_department FOREIGN KEY (department_id) REFERENCES department(department_id),
    CONSTRAINT fk_staff_activity_level FOREIGN KEY (participation_level_id) REFERENCES participation_level(participation_level_id),
    CONSTRAINT fk_staff_activity_role FOREIGN KEY (primary_role_type_id) REFERENCES role_type(role_type_id),
    CONSTRAINT fk_staff_activity_verification_status FOREIGN KEY (verification_status_id)
        REFERENCES verification_status(verification_status_id),
    CONSTRAINT fk_staff_activity_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_staff_activity_approval_status FOREIGN KEY (approval_status_id)
        REFERENCES approval_status(approval_status_id),
    CONSTRAINT fk_staff_activity_approved_by FOREIGN KEY (approved_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_staff_activity_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_staff_activity_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_staff_activity_deleted_by FOREIGN KEY (deleted_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Internal/external collaborators, co-authors, investigators, consultants,
-- team members and other participants.
CREATE TABLE staff_activity_contributor (
    staff_activity_contributor_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_activity_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NULL,
    external_person_name VARCHAR(250) NULL,
    external_person_email VARCHAR(254) NULL,
    external_organization_id BIGINT UNSIGNED NULL,
    affiliation_text VARCHAR(500) NULL,
    role_type_id SMALLINT UNSIGNED NULL,
    contributor_sequence SMALLINT UNSIGNED NULL,
    is_corresponding_author BOOLEAN NOT NULL DEFAULT FALSE,
    contribution_details VARCHAR(1000) NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_staff_activity_contributor_identity CHECK (
        (employee_id IS NOT NULL AND external_person_name IS NULL)
        OR
        (employee_id IS NULL AND external_person_name IS NOT NULL)
    ),
    CONSTRAINT uq_staff_activity_internal_contributor UNIQUE
        (staff_activity_id, employee_id, role_type_id),
    CONSTRAINT fk_staff_activity_contributor_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_staff_activity_contributor_employee FOREIGN KEY (employee_id)
        REFERENCES employee(employee_id),
    CONSTRAINT fk_staff_activity_contributor_org FOREIGN KEY (external_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_staff_activity_contributor_role FOREIGN KEY (role_type_id)
        REFERENCES role_type(role_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 21. JOURNALS AND JOURNAL PUBLICATIONS
-- =============================================================

CREATE TABLE journal (
    journal_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    journal_name VARCHAR(300) NOT NULL,
    journal_type_id TINYINT UNSIGNED NOT NULL,
    publisher_id BIGINT UNSIGNED NULL,
    issn VARCHAR(20) NULL,
    eissn VARCHAR(20) NULL,
    website_url VARCHAR(500) NULL,
    country_id SMALLINT UNSIGNED NULL,
    is_peer_reviewed_default BOOLEAN NULL,
    is_open_access_default BOOLEAN NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT uq_journal_issn UNIQUE (issn),
    CONSTRAINT uq_journal_eissn UNIQUE (eissn),
    CONSTRAINT fk_journal_type FOREIGN KEY (journal_type_id) REFERENCES journal_type(journal_type_id),
    CONSTRAINT fk_journal_publisher FOREIGN KEY (publisher_id) REFERENCES publisher(publisher_id),
    CONSTRAINT fk_journal_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE journal_publication (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    publication_type_id SMALLINT UNSIGNED NOT NULL,
    journal_id BIGINT UNSIGNED NOT NULL,
    paper_title VARCHAR(500) NOT NULL,
    volume_number VARCHAR(50) NULL,
    issue_number VARCHAR(50) NULL,
    edition VARCHAR(100) NULL,
    page_from VARCHAR(30) NULL,
    page_to VARCHAR(30) NULL,
    article_number VARCHAR(60) NULL,
    publication_date DATE NULL,
    publication_year YEAR NOT NULL,
    doi VARCHAR(255) NULL,
    url VARCHAR(1000) NULL,
    peer_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    open_access BOOLEAN NOT NULL DEFAULT FALSE,
    primary_author_position SMALLINT UNSIGNED NULL,
    primary_staff_corresponding_author BOOLEAN NOT NULL DEFAULT FALSE,
    affiliation_text VARCHAR(500) NULL,
    abstract_text TEXT NULL,
    keywords TEXT NULL,

    CONSTRAINT uq_journal_publication_doi UNIQUE (doi),
    CONSTRAINT fk_journal_publication_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_journal_publication_type FOREIGN KEY (publication_type_id)
        REFERENCES publication_type(publication_type_id),
    CONSTRAINT fk_journal_publication_journal FOREIGN KEY (journal_id)
        REFERENCES journal(journal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE journal_publication_indexing (
    staff_activity_id BIGINT UNSIGNED NOT NULL,
    indexing_agency_id SMALLINT UNSIGNED NOT NULL,
    indexed_year YEAR NULL,
    indexing_status ENUM('CLAIMED','VERIFIED','DISCONTINUED','NOT_INDEXED') NOT NULL DEFAULT 'CLAIMED',
    source_url VARCHAR(1000) NULL,
    remarks VARCHAR(500) NULL,
    PRIMARY KEY (staff_activity_id, indexing_agency_id),
    CONSTRAINT fk_journal_indexing_publication FOREIGN KEY (staff_activity_id)
        REFERENCES journal_publication(staff_activity_id),
    CONSTRAINT fk_journal_indexing_agency FOREIGN KEY (indexing_agency_id)
        REFERENCES indexing_agency(indexing_agency_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE journal_metric (
    journal_metric_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    journal_id BIGINT UNSIGNED NOT NULL,
    metric_type_id TINYINT UNSIGNED NOT NULL,
    metric_year YEAR NOT NULL,
    metric_value DECIMAL(12,4) NOT NULL,
    quartile VARCHAR(10) NULL,
    source_name VARCHAR(150) NULL,
    source_url VARCHAR(1000) NULL,
    verified_at DATETIME NULL,
    CONSTRAINT uq_journal_metric UNIQUE (journal_id, metric_type_id, metric_year),
    CONSTRAINT chk_journal_metric_value CHECK (metric_value >= 0),
    CONSTRAINT fk_journal_metric_journal FOREIGN KEY (journal_id) REFERENCES journal(journal_id),
    CONSTRAINT fk_journal_metric_type FOREIGN KEY (metric_type_id) REFERENCES metric_type(metric_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 22. CONFERENCES, PUBLICATIONS AND PRESENTATIONS
-- =============================================================

CREATE TABLE conference_event (
    conference_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conference_title VARCHAR(500) NOT NULL,
    conference_edition VARCHAR(100) NULL,
    organizer_id BIGINT UNSIGNED NULL,
    sponsoring_organization_id BIGINT UNSIGNED NULL,
    proceedings_publisher_id BIGINT UNSIGNED NULL,
    participation_level_id TINYINT UNSIGNED NULL,
    event_mode_id TINYINT UNSIGNED NULL,
    venue_name VARCHAR(250) NULL,
    city VARCHAR(120) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    conference_website VARCHAR(1000) NULL,
    brochure_url VARCHAR(1000) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT chk_conference_event_dates CHECK (end_date >= start_date),
    CONSTRAINT fk_conference_event_organizer FOREIGN KEY (organizer_id) REFERENCES organizer(organizer_id),
    CONSTRAINT fk_conference_event_sponsor FOREIGN KEY (sponsoring_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_conference_event_publisher FOREIGN KEY (proceedings_publisher_id)
        REFERENCES publisher(publisher_id),
    CONSTRAINT fk_conference_event_level FOREIGN KEY (participation_level_id)
        REFERENCES participation_level(participation_level_id),
    CONSTRAINT fk_conference_event_mode FOREIGN KEY (event_mode_id) REFERENCES event_mode(event_mode_id),
    CONSTRAINT fk_conference_event_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_conference_event_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE conference_activity (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    conference_event_id BIGINT UNSIGNED NOT NULL,
    conference_contribution_type_id TINYINT UNSIGNED NOT NULL,
    publication_type_id SMALLINT UNSIGNED NULL,
    paper_title VARCHAR(500) NULL,
    abstract_text TEXT NULL,
    proceedings_title VARCHAR(500) NULL,
    proceedings_volume VARCHAR(100) NULL,
    proceedings_issue VARCHAR(100) NULL,
    page_from VARCHAR(30) NULL,
    page_to VARCHAR(30) NULL,
    isbn VARCHAR(30) NULL,
    issn VARCHAR(20) NULL,
    doi VARCHAR(255) NULL,
    proceedings_url VARCHAR(1000) NULL,
    presentation_title VARCHAR(500) NULL,
    award_name VARCHAR(250) NULL,
    award_details TEXT NULL,
    award_date DATE NULL,

    CONSTRAINT uq_conference_activity_doi UNIQUE (doi),
    CONSTRAINT fk_conference_activity_parent FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_conference_activity_event FOREIGN KEY (conference_event_id)
        REFERENCES conference_event(conference_event_id),
    CONSTRAINT fk_conference_activity_contribution_type FOREIGN KEY (conference_contribution_type_id)
        REFERENCES conference_contribution_type(conference_contribution_type_id),
    CONSTRAINT fk_conference_activity_publication_type FOREIGN KEY (publication_type_id)
        REFERENCES publication_type(publication_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE conference_activity_indexing (
    staff_activity_id BIGINT UNSIGNED NOT NULL,
    indexing_agency_id SMALLINT UNSIGNED NOT NULL,
    indexing_status ENUM('CLAIMED','VERIFIED','DISCONTINUED','NOT_INDEXED') NOT NULL DEFAULT 'CLAIMED',
    source_url VARCHAR(1000) NULL,
    remarks VARCHAR(500) NULL,
    PRIMARY KEY (staff_activity_id, indexing_agency_id),
    CONSTRAINT fk_conference_activity_indexing_activity FOREIGN KEY (staff_activity_id)
        REFERENCES conference_activity(staff_activity_id),
    CONSTRAINT fk_conference_activity_indexing_agency FOREIGN KEY (indexing_agency_id)
        REFERENCES indexing_agency(indexing_agency_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 23. WORKSHOP / FDP / STTP / TRAINING / CERTIFICATION
-- =============================================================

CREATE TABLE professional_development_activity (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    training_program_type_id SMALLINT UNSIGNED NOT NULL,
    program_title VARCHAR(500) NOT NULL,
    organizer_id BIGINT UNSIGNED NULL,
    sponsoring_organization_id BIGINT UNSIGNED NULL,
    funding_agency_id BIGINT UNSIGNED NULL,
    venue_name VARCHAR(250) NULL,
    city VARCHAR(120) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    event_mode_id TINYINT UNSIGNED NULL,
    duration_days DECIMAL(8,2) NULL,
    duration_hours DECIMAL(10,2) NULL,
    financial_support_received BOOLEAN NOT NULL DEFAULT FALSE,
    financial_support_amount DECIMAL(14,2) NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    certificate_number VARCHAR(120) NULL,
    learning_outcomes TEXT NULL,

    CONSTRAINT chk_prof_dev_duration CHECK (
        (duration_days IS NULL OR duration_days >= 0)
        AND (duration_hours IS NULL OR duration_hours >= 0)
    ),
    CONSTRAINT chk_prof_dev_support CHECK (
        financial_support_amount IS NULL OR financial_support_amount >= 0
    ),
    CONSTRAINT fk_prof_dev_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_prof_dev_type FOREIGN KEY (training_program_type_id)
        REFERENCES training_program_type(training_program_type_id),
    CONSTRAINT fk_prof_dev_organizer FOREIGN KEY (organizer_id) REFERENCES organizer(organizer_id),
    CONSTRAINT fk_prof_dev_sponsor FOREIGN KEY (sponsoring_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_prof_dev_funder FOREIGN KEY (funding_agency_id) REFERENCES funding_agency(funding_agency_id),
    CONSTRAINT fk_prof_dev_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_prof_dev_country FOREIGN KEY (country_id) REFERENCES country(country_id),
    CONSTRAINT fk_prof_dev_mode FOREIGN KEY (event_mode_id) REFERENCES event_mode(event_mode_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 24. INDUSTRY / FACULTY INTERNSHIP
-- =============================================================

CREATE TABLE faculty_internship (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    organization_id BIGINT UNSIGNED NOT NULL,
    internship_title VARCHAR(500) NOT NULL,
    internship_domain VARCHAR(250) NULL,
    industry_sector_id SMALLINT UNSIGNED NULL,
    location_text VARCHAR(300) NULL,
    mentor_name VARCHAR(200) NULL,
    mentor_designation VARCHAR(150) NULL,
    mentor_email VARCHAR(254) NULL,
    work_undertaken TEXT NULL,
    technologies_tools TEXT NULL,
    outcomes TEXT NULL,
    stipend_incentive_type ENUM('NONE','STIPEND','INCENTIVE','HONORARIUM','OTHER') NOT NULL DEFAULT 'NONE',
    stipend_incentive_amount DECIMAL(14,2) NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    funding_source VARCHAR(250) NULL,
    mou_reference VARCHAR(150) NULL,
    collaboration_reference VARCHAR(250) NULL,

    CONSTRAINT chk_faculty_internship_amount CHECK (
        stipend_incentive_amount IS NULL OR stipend_incentive_amount >= 0
    ),
    CONSTRAINT fk_faculty_internship_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_faculty_internship_org FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_faculty_internship_sector FOREIGN KEY (industry_sector_id)
        REFERENCES industry_sector(industry_sector_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 25. RESEARCH PROPOSALS
-- =============================================================

CREATE TABLE research_proposal (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    proposal_title VARCHAR(500) NOT NULL,
    principal_investigator_employee_id BIGINT UNSIGNED NOT NULL,
    department_id SMALLINT UNSIGNED NOT NULL,
    proposal_submission_date DATE NULL,
    funding_agency_id BIGINT UNSIGNED NULL,
    funding_type_id TINYINT UNSIGNED NULL,
    scheme_program_name VARCHAR(300) NULL,
    requested_amount DECIMAL(16,2) NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    research_status_id TINYINT UNSIGNED NOT NULL,
    proposal_reference_number VARCHAR(150) NULL,
    project_objectives TEXT NULL,
    research_domain VARCHAR(300) NULL,
    expected_outcomes TEXT NULL,
    review_comments TEXT NULL,

    CONSTRAINT chk_research_proposal_requested_amount CHECK (
        requested_amount IS NULL OR requested_amount >= 0
    ),
    CONSTRAINT fk_research_proposal_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_research_proposal_pi FOREIGN KEY (principal_investigator_employee_id)
        REFERENCES employee(employee_id),
    CONSTRAINT fk_research_proposal_department FOREIGN KEY (department_id)
        REFERENCES department(department_id),
    CONSTRAINT fk_research_proposal_funder FOREIGN KEY (funding_agency_id)
        REFERENCES funding_agency(funding_agency_id),
    CONSTRAINT fk_research_proposal_funding_type FOREIGN KEY (funding_type_id)
        REFERENCES funding_type(funding_type_id),
    CONSTRAINT fk_research_proposal_status FOREIGN KEY (research_status_id)
        REFERENCES research_status(research_status_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 26. FUNDED RESEARCH PROJECTS
-- A funded project may originate from a research proposal.
-- =============================================================

CREATE TABLE funded_research_project (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    source_proposal_activity_id BIGINT UNSIGNED NULL,
    project_title VARCHAR(500) NOT NULL,
    principal_investigator_employee_id BIGINT UNSIGNED NOT NULL,
    department_id SMALLINT UNSIGNED NOT NULL,
    funding_agency_id BIGINT UNSIGNED NOT NULL,
    funding_type_id TINYINT UNSIGNED NOT NULL,
    scheme_program_name VARCHAR(300) NULL,
    requested_amount DECIMAL(16,2) NULL,
    sanctioned_amount DECIMAL(16,2) NOT NULL,
    amount_received DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    amount_utilized DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    sanction_date DATE NOT NULL,
    sanction_order_number VARCHAR(150) NULL,
    project_start_date DATE NOT NULL,
    project_end_date DATE NULL,
    duration_months SMALLINT UNSIGNED NULL,
    research_status_id TINYINT UNSIGNED NOT NULL,
    project_objectives TEXT NULL,
    research_domain VARCHAR(300) NULL,
    project_outcomes TEXT NULL,
    publications_generated TEXT NULL,
    patents_generated TEXT NULL,
    products_generated TEXT NULL,
    other_outputs TEXT NULL,
    utilization_summary TEXT NULL,
    completion_date DATE NULL,

    CONSTRAINT chk_funded_project_amounts CHECK (
        sanctioned_amount >= 0
        AND amount_received >= 0
        AND amount_utilized >= 0
        AND (requested_amount IS NULL OR requested_amount >= 0)
    ),
    CONSTRAINT chk_funded_project_dates CHECK (
        project_end_date IS NULL OR project_end_date >= project_start_date
    ),
    CONSTRAINT fk_funded_project_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_funded_project_proposal FOREIGN KEY (source_proposal_activity_id)
        REFERENCES research_proposal(staff_activity_id),
    CONSTRAINT fk_funded_project_pi FOREIGN KEY (principal_investigator_employee_id)
        REFERENCES employee(employee_id),
    CONSTRAINT fk_funded_project_department FOREIGN KEY (department_id)
        REFERENCES department(department_id),
    CONSTRAINT fk_funded_project_funder FOREIGN KEY (funding_agency_id)
        REFERENCES funding_agency(funding_agency_id),
    CONSTRAINT fk_funded_project_funding_type FOREIGN KEY (funding_type_id)
        REFERENCES funding_type(funding_type_id),
    CONSTRAINT fk_funded_project_status FOREIGN KEY (research_status_id)
        REFERENCES research_status(research_status_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE research_project_financial_utilization (
    utilization_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_activity_id BIGINT UNSIGNED NOT NULL,
    financial_year VARCHAR(9) NULL,
    reporting_period_from DATE NULL,
    reporting_period_to DATE NULL,
    opening_balance DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    amount_received DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    expenditure_amount DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    closing_balance DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    utilization_certificate_number VARCHAR(150) NULL,
    statement_of_expenditure_number VARCHAR(150) NULL,
    remarks TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_project_utilization_amounts CHECK (
        opening_balance >= 0 AND amount_received >= 0
        AND expenditure_amount >= 0 AND closing_balance >= 0
    ),
    CONSTRAINT chk_project_utilization_dates CHECK (
        reporting_period_to IS NULL OR reporting_period_from IS NULL
        OR reporting_period_to >= reporting_period_from
    ),
    CONSTRAINT fk_project_utilization_project FOREIGN KEY (staff_activity_id)
        REFERENCES funded_research_project(staff_activity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 27. CONSULTANCY / INDUSTRY-SPONSORED PROJECT
-- =============================================================

CREATE TABLE consultancy_project (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    consultancy_title VARCHAR(500) NOT NULL,
    client_organization_id BIGINT UNSIGNED NOT NULL,
    principal_consultant_employee_id BIGINT UNSIGNED NOT NULL,
    consultancy_type ENUM('CONSULTANCY','INDUSTRY_SPONSORED_PROJECT','TESTING_SERVICE','TRAINING_SERVICE','OTHER')
        NOT NULL DEFAULT 'CONSULTANCY',
    work_order_number VARCHAR(150) NULL,
    agreement_number VARCHAR(150) NULL,
    purchase_order_number VARCHAR(150) NULL,
    project_start_date DATE NOT NULL,
    completion_date DATE NULL,
    consultancy_amount DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    amount_received DECIMAL(16,2) NOT NULL DEFAULT 0.00,
    faculty_incentive_share DECIMAL(16,2) NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    deliverables TEXT NULL,
    status ENUM('PROPOSED','APPROVED','ONGOING','COMPLETED','CANCELLED','CLOSED') NOT NULL DEFAULT 'PROPOSED',
    client_feedback TEXT NULL,

    CONSTRAINT chk_consultancy_dates CHECK (
        completion_date IS NULL OR completion_date >= project_start_date
    ),
    CONSTRAINT chk_consultancy_amounts CHECK (
        consultancy_amount >= 0 AND amount_received >= 0
        AND (faculty_incentive_share IS NULL OR faculty_incentive_share >= 0)
    ),
    CONSTRAINT fk_consultancy_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_consultancy_client FOREIGN KEY (client_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_consultancy_principal FOREIGN KEY (principal_consultant_employee_id)
        REFERENCES employee(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 28. CO-CURRICULAR ACTIVITIES
-- =============================================================

CREATE TABLE cocurricular_activity (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    cocurricular_category_id SMALLINT UNSIGNED NOT NULL,
    event_name VARCHAR(500) NOT NULL,
    organizer_id BIGINT UNSIGNED NULL,
    institution_organization_id BIGINT UNSIGNED NULL,
    event_date DATE NULL,
    venue_name VARCHAR(250) NULL,
    city VARCHAR(120) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    achievement_award VARCHAR(500) NULL,
    contribution_details TEXT NULL,

    CONSTRAINT fk_cocurricular_activity_parent FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_cocurricular_activity_category FOREIGN KEY (cocurricular_category_id)
        REFERENCES cocurricular_category(cocurricular_category_id),
    CONSTRAINT fk_cocurricular_activity_organizer FOREIGN KEY (organizer_id)
        REFERENCES organizer(organizer_id),
    CONSTRAINT fk_cocurricular_activity_org FOREIGN KEY (institution_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_cocurricular_activity_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_cocurricular_activity_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 29. EXTRA-CURRICULAR ACTIVITIES
-- =============================================================

CREATE TABLE extracurricular_activity (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    extracurricular_category_id SMALLINT UNSIGNED NOT NULL,
    event_name VARCHAR(500) NOT NULL,
    organizer_id BIGINT UNSIGNED NULL,
    institution_organization_id BIGINT UNSIGNED NULL,
    event_date DATE NULL,
    venue_name VARCHAR(250) NULL,
    city VARCHAR(120) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    award_recognition VARCHAR(500) NULL,
    activity_details TEXT NULL,

    CONSTRAINT fk_extracurricular_activity_parent FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_extracurricular_activity_category FOREIGN KEY (extracurricular_category_id)
        REFERENCES extracurricular_category(extracurricular_category_id),
    CONSTRAINT fk_extracurricular_activity_organizer FOREIGN KEY (organizer_id)
        REFERENCES organizer(organizer_id),
    CONSTRAINT fk_extracurricular_activity_org FOREIGN KEY (institution_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_extracurricular_activity_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_extracurricular_activity_country FOREIGN KEY (country_id) REFERENCES country(country_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 30. AWARDS, HONOURS AND RECOGNITIONS
-- =============================================================

CREATE TABLE staff_award (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    award_category_id SMALLINT UNSIGNED NULL,
    award_name VARCHAR(500) NOT NULL,
    awarding_organization_id BIGINT UNSIGNED NULL,
    award_date DATE NOT NULL,
    citation_details TEXT NULL,
    cash_prize_amount DECIMAL(14,2) NULL,
    incentive_amount DECIMAL(14,2) NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    award_reference_number VARCHAR(150) NULL,

    CONSTRAINT chk_staff_award_amounts CHECK (
        (cash_prize_amount IS NULL OR cash_prize_amount >= 0)
        AND (incentive_amount IS NULL OR incentive_amount >= 0)
    ),
    CONSTRAINT fk_staff_award_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_staff_award_category FOREIGN KEY (award_category_id)
        REFERENCES award_category(award_category_id),
    CONSTRAINT fk_staff_award_org FOREIGN KEY (awarding_organization_id)
        REFERENCES external_organization(organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 31. PROFESSIONAL MEMBERSHIPS AND ACADEMIC BODIES
-- =============================================================

CREATE TABLE staff_professional_membership (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    organization_id BIGINT UNSIGNED NOT NULL,
    membership_type_id SMALLINT UNSIGNED NOT NULL,
    membership_number VARCHAR(150) NULL,
    membership_start_date DATE NULL,
    membership_expiry_date DATE NULL,
    is_lifetime_membership BOOLEAN NOT NULL DEFAULT FALSE,
    role_type_id SMALLINT UNSIGNED NULL,
    participation_level_id TINYINT UNSIGNED NULL,
    renewal_required BOOLEAN NOT NULL DEFAULT FALSE,
    membership_status ENUM('ACTIVE','EXPIRED','SUSPENDED','CANCELLED','LIFETIME') NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT chk_staff_membership_dates CHECK (
        membership_expiry_date IS NULL OR membership_start_date IS NULL
        OR membership_expiry_date >= membership_start_date
    ),
    CONSTRAINT uq_staff_membership_number UNIQUE (organization_id, membership_number),
    CONSTRAINT fk_staff_membership_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_staff_membership_org FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_staff_membership_type FOREIGN KEY (membership_type_id)
        REFERENCES membership_type(membership_type_id),
    CONSTRAINT fk_staff_membership_role FOREIGN KEY (role_type_id)
        REFERENCES role_type(role_type_id),
    CONSTRAINT fk_staff_membership_level FOREIGN KEY (participation_level_id)
        REFERENCES participation_level(participation_level_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 32. ACADEMIC AND PROFESSIONAL CONTRIBUTIONS
-- =============================================================

CREATE TABLE staff_professional_contribution (
    staff_activity_id BIGINT UNSIGNED PRIMARY KEY,
    professional_contribution_type_id SMALLINT UNSIGNED NOT NULL,
    organization_id BIGINT UNSIGNED NULL,
    journal_id BIGINT UNSIGNED NULL,
    conference_event_id BIGINT UNSIGNED NULL,
    programme_id SMALLINT UNSIGNED NULL,
    course_id INT UNSIGNED NULL,
    student_id BIGINT UNSIGNED NULL,
    title_topic VARCHAR(500) NULL,
    appointment_reference_number VARCHAR(150) NULL,
    contribution_date DATE NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    number_of_reviews SMALLINT UNSIGNED NULL,
    number_of_candidates SMALLINT UNSIGNED NULL,
    contribution_details TEXT NULL,
    outcome_details TEXT NULL,

    CONSTRAINT chk_prof_contribution_dates CHECK (
        end_date IS NULL OR start_date IS NULL OR end_date >= start_date
    ),
    CONSTRAINT fk_prof_contribution_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_prof_contribution_type FOREIGN KEY (professional_contribution_type_id)
        REFERENCES professional_contribution_type(professional_contribution_type_id),
    CONSTRAINT fk_prof_contribution_org FOREIGN KEY (organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_prof_contribution_journal FOREIGN KEY (journal_id) REFERENCES journal(journal_id),
    CONSTRAINT fk_prof_contribution_conference FOREIGN KEY (conference_event_id)
        REFERENCES conference_event(conference_event_id),
    CONSTRAINT fk_prof_contribution_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_prof_contribution_course FOREIGN KEY (course_id) REFERENCES course_catalog(course_id),
    CONSTRAINT fk_prof_contribution_student FOREIGN KEY (student_id) REFERENCES student(student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Research supervision supports PG/PhD supervision with multiple scholars.
CREATE TABLE research_supervision (
    research_supervision_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_activity_id BIGINT UNSIGNED NOT NULL,
    supervision_level ENUM('PG','MPHIL','PHD','POST_DOCTORAL','OTHER') NOT NULL,
    scholar_name VARCHAR(250) NOT NULL,
    student_id BIGINT UNSIGNED NULL,
    registration_number VARCHAR(100) NULL,
    research_title VARCHAR(500) NULL,
    registration_date DATE NULL,
    completion_date DATE NULL,
    supervision_role ENUM('SUPERVISOR','CO_SUPERVISOR','GUIDE','CO_GUIDE','ADVISOR') NOT NULL,
    status ENUM('REGISTERED','ONGOING','SUBMITTED','AWARDED','DISCONTINUED') NOT NULL DEFAULT 'ONGOING',
    awarding_organization_id BIGINT UNSIGNED NULL,

    CONSTRAINT chk_research_supervision_dates CHECK (
        completion_date IS NULL OR registration_date IS NULL OR completion_date >= registration_date
    ),
    CONSTRAINT fk_research_supervision_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_professional_contribution(staff_activity_id),
    CONSTRAINT fk_research_supervision_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_research_supervision_org FOREIGN KEY (awarding_organization_id)
        REFERENCES external_organization(organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 33. CENTRALIZED EVIDENCE / DOCUMENT MANAGEMENT
-- =============================================================

CREATE TABLE evidence_document (
    evidence_document_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_activity_id BIGINT UNSIGNED NOT NULL,
    document_type_id SMALLINT UNSIGNED NOT NULL,
    evidence_type_id SMALLINT UNSIGNED NULL,
    confidentiality_level_id TINYINT UNSIGNED NOT NULL,

    document_title VARCHAR(500) NOT NULL,
    description TEXT NULL,
    academic_year_id SMALLINT UNSIGNED NULL,

    document_issue_date DATE NULL,
    issuing_authority VARCHAR(300) NULL,
    issuing_organization_id BIGINT UNSIGNED NULL,
    certificate_document_number VARCHAR(150) NULL,
    expiry_date DATE NULL,

    verification_status_id TINYINT UNSIGNED NOT NULL,
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,

    approval_status_id TINYINT UNSIGNED NOT NULL,
    approved_by_user_id BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    rejection_reason VARCHAR(1000) NULL,

    current_version_number SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_by_user_id BIGINT UNSIGNED NOT NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    deleted_at DATETIME NULL,
    deleted_by_user_id BIGINT UNSIGNED NULL,
    deletion_reason VARCHAR(1000) NULL,

    CONSTRAINT chk_evidence_document_dates CHECK (
        expiry_date IS NULL OR document_issue_date IS NULL OR expiry_date >= document_issue_date
    ),
    CONSTRAINT chk_evidence_document_version CHECK (current_version_number >= 1),

    CONSTRAINT fk_evidence_document_activity FOREIGN KEY (staff_activity_id)
        REFERENCES staff_activity(staff_activity_id),
    CONSTRAINT fk_evidence_document_document_type FOREIGN KEY (document_type_id)
        REFERENCES document_type(document_type_id),
    CONSTRAINT fk_evidence_document_evidence_type FOREIGN KEY (evidence_type_id)
        REFERENCES evidence_type(evidence_type_id),
    CONSTRAINT fk_evidence_document_confidentiality FOREIGN KEY (confidentiality_level_id)
        REFERENCES confidentiality_level(confidentiality_level_id),
    CONSTRAINT fk_evidence_document_year FOREIGN KEY (academic_year_id)
        REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_evidence_document_issuing_org FOREIGN KEY (issuing_organization_id)
        REFERENCES external_organization(organization_id),
    CONSTRAINT fk_evidence_document_verification_status FOREIGN KEY (verification_status_id)
        REFERENCES verification_status(verification_status_id),
    CONSTRAINT fk_evidence_document_verified_by FOREIGN KEY (verified_by_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_evidence_document_approval_status FOREIGN KEY (approval_status_id)
        REFERENCES approval_status(approval_status_id),
    CONSTRAINT fk_evidence_document_approved_by FOREIGN KEY (approved_by_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_evidence_document_created_by FOREIGN KEY (created_by_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_evidence_document_updated_by FOREIGN KEY (updated_by_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_evidence_document_deleted_by FOREIGN KEY (deleted_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE evidence_document_version (
    evidence_document_version_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    evidence_document_id BIGINT UNSIGNED NOT NULL,
    version_number SMALLINT UNSIGNED NOT NULL,
    file_object_id BIGINT UNSIGNED NOT NULL,
    change_reason VARCHAR(1000) NULL,
    uploaded_by_user_id BIGINT UNSIGNED NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_evidence_document_version UNIQUE (evidence_document_id, version_number),
    CONSTRAINT uq_evidence_document_file UNIQUE (evidence_document_id, file_object_id),
    CONSTRAINT chk_evidence_version_number CHECK (version_number >= 1),
    CONSTRAINT fk_evidence_version_document FOREIGN KEY (evidence_document_id)
        REFERENCES evidence_document(evidence_document_id),
    CONSTRAINT fk_evidence_version_file FOREIGN KEY (file_object_id)
        REFERENCES file_object(file_object_id),
    CONSTRAINT fk_evidence_version_uploaded_by FOREIGN KEY (uploaded_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional evidence tags make searching/reporting easier.
CREATE TABLE evidence_tag (
    evidence_tag_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tag_code VARCHAR(60) NOT NULL UNIQUE,
    tag_name VARCHAR(120) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE evidence_document_tag (
    evidence_document_id BIGINT UNSIGNED NOT NULL,
    evidence_tag_id INT UNSIGNED NOT NULL,
    PRIMARY KEY (evidence_document_id, evidence_tag_id),
    CONSTRAINT fk_evidence_document_tag_document FOREIGN KEY (evidence_document_id)
        REFERENCES evidence_document(evidence_document_id),
    CONSTRAINT fk_evidence_document_tag_tag FOREIGN KEY (evidence_tag_id)
        REFERENCES evidence_tag(evidence_tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Full audit trail for upload/update/replace/delete/verification/approval/download.
CREATE TABLE evidence_document_audit (
    evidence_document_audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    evidence_document_id BIGINT UNSIGNED NOT NULL,
    evidence_document_version_id BIGINT UNSIGNED NULL,
    action_code ENUM(
        'CREATE','UPLOAD','REPLACE','UPDATE_METADATA','PREVIEW','DOWNLOAD',
        'VERIFY','REJECT_VERIFICATION','APPROVE','REJECT_APPROVAL',
        'SOFT_DELETE','RESTORE','ACCESS_DENIED'
    ) NOT NULL,
    performed_by_user_id BIGINT UNSIGNED NULL,
    performed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    before_values JSON NULL,
    after_values JSON NULL,
    remarks VARCHAR(1000) NULL,

    CONSTRAINT fk_evidence_audit_document FOREIGN KEY (evidence_document_id)
        REFERENCES evidence_document(evidence_document_id),
    CONSTRAINT fk_evidence_audit_version FOREIGN KEY (evidence_document_version_id)
        REFERENCES evidence_document_version(evidence_document_version_id),
    CONSTRAINT fk_evidence_audit_user FOREIGN KEY (performed_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 34. DOCUMENT/EVIDENCE REQUIREMENT CONFIGURATION
-- Defines which evidence types are expected for each activity type.
-- =============================================================

CREATE TABLE activity_evidence_requirement (
    activity_evidence_requirement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    activity_type_id SMALLINT UNSIGNED NOT NULL,
    evidence_type_id SMALLINT UNSIGNED NOT NULL,
    document_type_id SMALLINT UNSIGNED NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT FALSE,
    minimum_files TINYINT UNSIGNED NOT NULL DEFAULT 0,
    maximum_files TINYINT UNSIGNED NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_activity_evidence_requirement UNIQUE
        (activity_type_id, evidence_type_id, document_type_id),
    CONSTRAINT chk_activity_evidence_file_counts CHECK (
        maximum_files IS NULL OR maximum_files >= minimum_files
    ),
    CONSTRAINT chk_activity_evidence_requirement_dates CHECK (
        valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from
    ),
    CONSTRAINT fk_activity_evidence_requirement_activity FOREIGN KEY (activity_type_id)
        REFERENCES activity_type(activity_type_id),
    CONSTRAINT fk_activity_evidence_requirement_evidence FOREIGN KEY (evidence_type_id)
        REFERENCES evidence_type(evidence_type_id),
    CONSTRAINT fk_activity_evidence_requirement_document FOREIGN KEY (document_type_id)
        REFERENCES document_type(document_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 35. SEED REFERENCE DATA
-- =============================================================

INSERT INTO publication_type (publication_type_code, publication_type_name, description) VALUES
('JOURNAL_ARTICLE','Journal Article','Article or paper published in a journal'),
('CONFERENCE_PAPER','Conference Paper','Paper published in conference proceedings'),
('BOOK_CHAPTER','Book Chapter','Chapter published in an edited book'),
('OTHER_PUBLICATION','Other Publication','Other scholarly publication');

INSERT INTO journal_type (journal_type_code, journal_type_name) VALUES
('INTERNATIONAL','International'),
('NATIONAL','National');

INSERT INTO indexing_agency (agency_code, agency_name) VALUES
('SCOPUS','Scopus'),
('WOS','Web of Science'),
('SCI','Science Citation Index'),
('SCIE','Science Citation Index Expanded'),
('ESCI','Emerging Sources Citation Index'),
('UGC_CARE','UGC-CARE'),
('PUBMED','PubMed'),
('DOAJ','Directory of Open Access Journals'),
('IEEE_XPLORE','IEEE Xplore'),
('DBLP','DBLP');

INSERT INTO metric_type (metric_code, metric_name) VALUES
('IMPACT_FACTOR','Impact Factor'),
('CITESCORE','CiteScore'),
('SJR','SCImago Journal Rank'),
('SNIP','Source Normalized Impact per Paper'),
('H_INDEX','H-Index');

INSERT INTO funding_type (funding_type_code, funding_type_name, is_external) VALUES
('INTERNAL','Internal Funding',FALSE),
('EXTERNAL','External Funding',TRUE),
('INDUSTRY','Industry Funding',TRUE),
('GOVERNMENT','Government Funding',TRUE),
('CENTRAL_GOVERNMENT','Central Government Funding',TRUE),
('STATE_GOVERNMENT','State Government Funding',TRUE),
('CSR','Corporate Social Responsibility Funding',TRUE),
('UNIVERSITY','University Funding',FALSE);

INSERT INTO participation_level (level_code, level_name, display_order) VALUES
('DEPARTMENT','Department',10),
('INSTITUTE','Institute',20),
('UNIVERSITY','University',30),
('REGIONAL','Regional',40),
('STATE','State',50),
('NATIONAL','National',60),
('INTERNATIONAL','International',70);

INSERT INTO event_mode (mode_code, mode_name) VALUES
('ONLINE','Online'),
('OFFLINE','Offline'),
('HYBRID','Hybrid');

INSERT INTO verification_status (status_code, status_name, is_terminal) VALUES
('NOT_SUBMITTED','Not Submitted',FALSE),
('PENDING','Pending Verification',FALSE),
('UNDER_VERIFICATION','Under Verification',FALSE),
('VERIFIED','Verified',TRUE),
('REJECTED','Rejected',TRUE),
('NEEDS_CORRECTION','Needs Correction',FALSE);

INSERT INTO approval_status (status_code, status_name, is_terminal) VALUES
('DRAFT','Draft',FALSE),
('SUBMITTED','Submitted',FALSE),
('UNDER_REVIEW','Under Review',FALSE),
('APPROVED','Approved',TRUE),
('REJECTED','Rejected',TRUE),
('ARCHIVED','Archived',TRUE);

INSERT INTO research_status (status_code, status_name, display_order, is_terminal) VALUES
('DRAFT','Draft',10,FALSE),
('SUBMITTED','Submitted',20,FALSE),
('UNDER_REVIEW','Under Review',30,FALSE),
('APPROVED','Approved',40,FALSE),
('SANCTIONED','Sanctioned',50,FALSE),
('REJECTED','Rejected',60,TRUE),
('ONGOING','Ongoing',70,FALSE),
('COMPLETED','Completed',80,TRUE),
('CLOSED','Closed',90,TRUE);

INSERT INTO training_program_type (type_code, type_name) VALUES
('WORKSHOP','Workshop'),
('FDP','Faculty Development Programme'),
('STTP','Short-Term Training Programme'),
('REFRESHER','Refresher Course'),
('ORIENTATION','Orientation Programme'),
('CERTIFICATION','Certification Programme'),
('INDUSTRIAL_TRAINING','Industrial Training'),
('PROFESSIONAL_TRAINING','Professional Training'),
('OTHER','Other Training Programme');

INSERT INTO conference_contribution_type (type_code, type_name) VALUES
('PAPER_PRESENTATION','Paper Presentation'),
('POSTER_PRESENTATION','Poster Presentation'),
('PAPER_PUBLICATION','Paper Publication'),
('PARTICIPATION','Participation'),
('INVITED_TALK','Invited Talk'),
('KEYNOTE','Keynote Address'),
('SESSION_CHAIR','Session Chair'),
('CONFERENCE_CHAIR','Conference Chair'),
('OTHER','Other Contribution');

INSERT INTO extracurricular_category (category_code, category_name) VALUES
('SPORTS','Sports'),
('CULTURAL','Cultural Activity'),
('SOCIAL_SERVICE','Social Service'),
('NSS','NSS Activity'),
('NCC','NCC Activity'),
('CLUB','Club Activity'),
('PROFESSIONAL_SOCIETY','Professional Society Activity'),
('COMMUNITY_OUTREACH','Community Outreach'),
('INSTITUTIONAL_ACTIVITY','Institutional Activity'),
('COMPETITION','Competition'),
('OTHER','Other Extra-Curricular Activity');

INSERT INTO cocurricular_category (category_code, category_name) VALUES
('TECHNICAL_EVENT','Technical Event'),
('HACKATHON','Hackathon'),
('PROJECT_EXHIBITION','Project Exhibition'),
('ACADEMIC_COMPETITION','Academic Competition'),
('MENTORING_EVENT','Mentoring Event'),
('JUDGING','Judging / Evaluation'),
('COMMITTEE_ACTIVITY','Committee Activity'),
('OTHER','Other Co-Curricular Activity');

INSERT INTO award_category (category_code, category_name) VALUES
('ACADEMIC','Academic Award'),
('RESEARCH','Research Award'),
('TEACHING','Teaching Award'),
('PROFESSIONAL','Professional Award'),
('SERVICE','Service Recognition'),
('SPORTS','Sports Award'),
('CULTURAL','Cultural Award'),
('OTHER','Other Award');

INSERT INTO membership_type (type_code, type_name) VALUES
('MEMBER','Member'),
('LIFE_MEMBER','Life Member'),
('FELLOW','Fellow'),
('SENIOR_MEMBER','Senior Member'),
('ASSOCIATE_MEMBER','Associate Member'),
('HONORARY_MEMBER','Honorary Member'),
('OFFICE_BEARER','Office Bearer'),
('OTHER','Other Membership');

INSERT INTO role_type (role_code, role_name) VALUES
('AUTHOR','Author'),
('CO_AUTHOR','Co-Author'),
('CORRESPONDING_AUTHOR','Corresponding Author'),
('PI','Principal Investigator'),
('CO_PI','Co-Principal Investigator'),
('CO_INVESTIGATOR','Co-Investigator'),
('PRINCIPAL_CONSULTANT','Principal Consultant'),
('TEAM_MEMBER','Team Member'),
('PARTICIPANT','Participant'),
('COORDINATOR','Coordinator'),
('RESOURCE_PERSON','Resource Person'),
('TRAINER','Trainer'),
('JUDGE','Judge'),
('MENTOR','Mentor'),
('COMMITTEE_MEMBER','Committee Member'),
('CHAIRPERSON','Chairperson'),
('OFFICE_BEARER','Office Bearer'),
('REVIEWER','Reviewer'),
('EDITOR','Editor'),
('EDITORIAL_BOARD_MEMBER','Editorial Board Member'),
('SESSION_CHAIR','Session Chair'),
('SUPERVISOR','Supervisor'),
('CO_SUPERVISOR','Co-Supervisor'),
('INVITED_SPEAKER','Invited Speaker'),
('GUEST_LECTURER','Guest Lecturer'),
('OTHER','Other');

INSERT INTO professional_contribution_type (contribution_code, contribution_name) VALUES
('JOURNAL_REVIEWER','Journal Reviewer'),
('CONFERENCE_REVIEWER','Conference Reviewer'),
('JOURNAL_EDITOR','Journal Editor'),
('EDITORIAL_BOARD','Editorial Board Member'),
('CONFERENCE_CHAIR','Conference Chair'),
('SESSION_CHAIR','Session Chair'),
('BOARD_OF_STUDIES','Board of Studies Member'),
('ACADEMIC_COUNCIL','Academic Council Member'),
('EXAMINATION_DUTY','Examination Duty'),
('QUESTION_PAPER_SETTING','Question Paper Setting'),
('PHD_SUPERVISION','Ph.D. Research Supervision'),
('PG_SUPERVISION','PG Research Supervision'),
('INVITED_TALK','Invited Talk'),
('GUEST_LECTURE','Guest Lecture'),
('RESOURCE_PERSON','Resource Person Activity'),
('MENTORING','Mentoring'),
('CURRICULUM_DEVELOPMENT','Curriculum Development'),
('INSTITUTIONAL_COMMITTEE','Institutional Committee'),
('OTHER','Other Professional Contribution');

INSERT INTO confidentiality_level (level_code, level_name, display_order) VALUES
('PUBLIC','Public',10),
('INTERNAL','Internal',20),
('RESTRICTED','Restricted',30),
('CONFIDENTIAL','Confidential',40),
('HIGHLY_CONFIDENTIAL','Highly Confidential',50);

INSERT INTO activity_type (activity_type_code, activity_type_name, activity_group) VALUES
('JOURNAL_PUBLICATION','Journal Publication','PUBLICATION'),
('CONFERENCE_PUBLICATION','Conference Publication','CONFERENCE'),
('CONFERENCE_PRESENTATION','Conference Presentation','CONFERENCE'),
('WORKSHOP','Workshop','PROFESSIONAL_DEVELOPMENT'),
('FDP','Faculty Development Programme','PROFESSIONAL_DEVELOPMENT'),
('STTP','Short-Term Training Programme','PROFESSIONAL_DEVELOPMENT'),
('TRAINING','Training Programme','PROFESSIONAL_DEVELOPMENT'),
('FACULTY_INTERNSHIP','Faculty / Industry Internship','INTERNSHIP'),
('RESEARCH_PROPOSAL','Research Proposal','RESEARCH'),
('FUNDED_RESEARCH_PROJECT','Funded Research Project','RESEARCH'),
('CONSULTANCY','Consultancy Assignment','CONSULTANCY'),
('INDUSTRY_SPONSORED_PROJECT','Industry-Sponsored Project','CONSULTANCY'),
('CO_CURRICULAR','Co-Curricular Activity','CO_CURRICULAR'),
('EXTRA_CURRICULAR','Extra-Curricular Activity','EXTRA_CURRICULAR'),
('AWARD_RECOGNITION','Award / Honour / Recognition','AWARD'),
('PROFESSIONAL_MEMBERSHIP','Professional Membership / Academic Body','MEMBERSHIP'),
('ACADEMIC_PROFESSIONAL_CONTRIBUTION','Academic / Professional Contribution','ACADEMIC_PROFESSIONAL_CONTRIBUTION');

-- Common evidence categories.
INSERT INTO evidence_type (evidence_type_code, evidence_type_name) VALUES
('PUBLISHED_PAPER','Published Paper PDF'),
('FIRST_PAGE','First Page of Publication'),
('JOURNAL_COVER','Journal Cover Page'),
('TABLE_OF_CONTENTS','Table of Contents'),
('DOI_PROOF','DOI Proof'),
('INDEXING_PROOF','Indexing Proof'),
('ACCEPTANCE_LETTER','Acceptance Letter'),
('PUBLICATION_CERTIFICATE','Publication Certificate'),
('CONFERENCE_PAPER','Conference Paper'),
('PROCEEDINGS_COPY','Proceedings Copy'),
('PRESENTATION_CERTIFICATE','Presentation Certificate'),
('PARTICIPATION_CERTIFICATE','Participation Certificate'),
('COMPLETION_CERTIFICATE','Completion Certificate'),
('RESOURCE_PERSON_CERTIFICATE','Resource Person Certificate'),
('REGISTRATION_PROOF','Registration Proof'),
('AWARD_CERTIFICATE','Award / Best Paper Certificate'),
('BROCHURE','Program / Conference Brochure'),
('PHOTOGRAPH','Photograph'),
('INVITATION_LETTER','Invitation Letter'),
('ATTENDANCE_PROOF','Attendance Proof'),
('TRAINING_MATERIAL','Training Material'),
('INTERNSHIP_OFFER','Internship Offer Letter'),
('INTERNSHIP_CERTIFICATE','Internship Certificate'),
('INDUSTRY_EVALUATION','Industry Evaluation'),
('INTERNSHIP_REPORT','Internship Report'),
('STIPEND_PROOF','Stipend / Incentive Proof'),
('MOU_AGREEMENT','MoU / Agreement'),
('RESEARCH_PROPOSAL','Research Proposal'),
('SUBMISSION_ACK','Proposal Submission Acknowledgement'),
('APPROVAL_LETTER','Approval Letter'),
('SANCTION_LETTER','Sanction Letter'),
('FUNDING_ORDER','Funding Order'),
('PROGRESS_REPORT','Progress Report'),
('UTILIZATION_CERTIFICATE','Utilization Certificate'),
('STATEMENT_EXPENDITURE','Statement of Expenditure'),
('AUDITED_STATEMENT','Audited Financial Statement'),
('PROJECT_COMPLETION_REPORT','Project Completion Report'),
('OUTCOME_REPORT','Outcome Report'),
('WORK_ORDER','Work Order'),
('PURCHASE_ORDER','Purchase Order'),
('INVOICE','Invoice'),
('PAYMENT_PROOF','Payment Proof'),
('CLIENT_FEEDBACK','Client Feedback'),
('CONSULTANCY_REPORT','Consultancy Report'),
('APPRECIATION_CERTIFICATE','Appreciation Certificate'),
('APPOINTMENT_ORDER','Appointment / Order Letter'),
('CITATION','Citation'),
('AWARD_LETTER','Award Letter'),
('MEDIA_EVIDENCE','Newspaper / Media Evidence'),
('MEMBERSHIP_CERTIFICATE','Membership Certificate / Card'),
('RENEWAL_DOCUMENT','Renewal Document'),
('REVIEWER_CERTIFICATE','Reviewer Certificate'),
('EDITORIAL_BOARD_CERTIFICATE','Editorial Board Certificate'),
('ACKNOWLEDGEMENT_LETTER','Acknowledgement Letter'),
('OFFICIAL_ORDER','Official Order'),
('OTHER_SUPPORTING','Other Supporting Evidence');

-- =============================================================
-- 36. RBAC REGISTRATION FOR STAFF PROFILE AND EVIDENCE
-- =============================================================

INSERT IGNORE INTO access_module
    (module_code, module_name, description, display_order)
VALUES
    ('STAFF_PROFILE',
     'Staff Academic and Professional Profile',
     'Academic, research, professional development, industry, consultancy, awards, memberships, co-curricular and extra-curricular staff profile.',
     170);

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STAFF_ACTIVITY', 'Staff Activity Records',
       'Create and maintain staff academic and professional activity records.'
FROM access_module WHERE module_code='STAFF_PROFILE';

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STAFF_EVIDENCE', 'Staff Evidence Documents',
       'Upload, preview, download, version, verify and approve staff evidence documents.'
FROM access_module WHERE module_code='STAFF_PROFILE';

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STAFF_RESEARCH', 'Staff Research and Projects',
       'Maintain research proposals, funded projects and project utilization.'
FROM access_module WHERE module_code='STAFF_PROFILE';

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STAFF_REPORT', 'Staff Profile Reports',
       'Search, filter, report and export staff profile and evidence data.'
FROM access_module WHERE module_code='STAFF_PROFILE';

INSERT IGNORE INTO permission
    (access_resource_id, access_action_id, permission_code, permission_name, is_sensitive)
SELECT ar.access_resource_id,
       aa.access_action_id,
       CONCAT('STAFF_PROFILE.', ar.resource_code, '.', aa.action_code),
       CONCAT(aa.action_name, ' ', ar.resource_name),
       CASE
           WHEN ar.resource_code='STAFF_EVIDENCE'
                AND aa.action_code IN ('DELETE','APPROVE','VERIFY','EXPORT')
           THEN TRUE
           WHEN aa.action_code IN ('DELETE','APPROVE','CONFIGURE')
           THEN TRUE
           ELSE FALSE
       END
FROM access_resource ar
JOIN access_module am
  ON am.access_module_id=ar.access_module_id
 AND am.module_code='STAFF_PROFILE'
CROSS JOIN access_action aa
WHERE aa.action_code IN
      ('CREATE','READ','UPDATE','DELETE','APPROVE','VERIFY','EXPORT','CONFIGURE');

-- Faculty: self-service creation/read/update of own profile records.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code IN ('FACULTY','LAB_INSTRUCTOR')
  AND p.permission_code LIKE 'STAFF_PROFILE.%'
  AND aa.action_code IN ('CREATE','READ','UPDATE');

-- Department leadership: departmental read/verification/approval/reporting.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code IN ('HEAD_DEPARTMENT','DEAN_ACADEMICS')
  AND p.permission_code LIKE 'STAFF_PROFILE.%'
  AND aa.action_code IN ('CREATE','READ','UPDATE','VERIFY','APPROVE','EXPORT');

-- Internal auditor: read/export verified evidence within authorized scope.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='INTERNAL_AUDITOR'
  AND p.permission_code LIKE 'STAFF_PROFILE.%'
  AND aa.action_code IN ('READ','EXPORT');

-- Super admin automatically receives new permissions.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
WHERE r.role_code='SUPER_ADMIN'
  AND p.permission_code LIKE 'STAFF_PROFILE.%';

-- =============================================================
-- 37. REPORTING / SEARCH VIEWS
-- =============================================================

CREATE OR REPLACE VIEW v_staff_activity_profile AS
SELECT
    sa.staff_activity_id,
    sa.employee_id,
    e.employee_number,
    e.display_name AS staff_name,
    at.activity_type_code,
    at.activity_type_name,
    at.activity_group,
    sa.activity_title,
    ay.year_code AS academic_year,
    u.university_name,
    i.institution_name,
    c.campus_name,
    d.department_name,
    pl.level_name AS participation_level,
    rt.role_name AS primary_role,
    sa.start_date,
    sa.end_date,
    vs.status_name AS verification_status,
    aps.status_name AS approval_status,
    sa.created_at,
    sa.updated_at,
    sa.deleted_at
FROM staff_activity sa
JOIN employee e ON e.employee_id=sa.employee_id
JOIN activity_type at ON at.activity_type_id=sa.activity_type_id
LEFT JOIN academic_year ay ON ay.academic_year_id=sa.academic_year_id
JOIN institution i ON i.institution_id=sa.institution_id
JOIN university u ON u.university_id=i.university_id
LEFT JOIN campus c ON c.campus_id=sa.campus_id
LEFT JOIN department d ON d.department_id=sa.department_id
LEFT JOIN participation_level pl ON pl.participation_level_id=sa.participation_level_id
LEFT JOIN role_type rt ON rt.role_type_id=sa.primary_role_type_id
JOIN verification_status vs ON vs.verification_status_id=sa.verification_status_id
JOIN approval_status aps ON aps.approval_status_id=sa.approval_status_id;

CREATE OR REPLACE VIEW v_staff_evidence_search AS
SELECT
    ed.evidence_document_id,
    ed.staff_activity_id,
    sa.employee_id,
    e.employee_number,
    e.display_name AS staff_name,
    d.department_id,
    d.department_name,
    at.activity_type_code,
    at.activity_type_name,
    ay.year_code AS academic_year,
    dt.document_code,
    dt.document_name,
    et.evidence_type_code,
    et.evidence_type_name,
    ed.document_title,
    ed.certificate_document_number,
    ed.document_issue_date,
    ed.expiry_date,
    vs.status_name AS verification_status,
    aps.status_name AS approval_status,
    cl.level_name AS confidentiality_level,
    ed.current_version_number,
    ed.is_active,
    ed.created_at,
    ed.updated_at,
    ed.deleted_at
FROM evidence_document ed
JOIN staff_activity sa ON sa.staff_activity_id=ed.staff_activity_id
JOIN employee e ON e.employee_id=sa.employee_id
JOIN activity_type at ON at.activity_type_id=sa.activity_type_id
LEFT JOIN academic_year ay ON ay.academic_year_id=ed.academic_year_id
LEFT JOIN department d ON d.department_id=sa.department_id
JOIN document_type dt ON dt.document_type_id=ed.document_type_id
LEFT JOIN evidence_type et ON et.evidence_type_id=ed.evidence_type_id
JOIN verification_status vs ON vs.verification_status_id=ed.verification_status_id
JOIN approval_status aps ON aps.approval_status_id=ed.approval_status_id
JOIN confidentiality_level cl ON cl.confidentiality_level_id=ed.confidentiality_level_id;

-- =============================================================
-- 38. PERFORMANCE INDEXES
-- =============================================================

CREATE INDEX idx_staff_activity_employee_year
    ON staff_activity(employee_id, academic_year_id, activity_type_id, deleted_at);

CREATE INDEX idx_staff_activity_department_year
    ON staff_activity(department_id, academic_year_id, activity_type_id, deleted_at);

CREATE INDEX idx_staff_activity_verification
    ON staff_activity(verification_status_id, approval_status_id, created_at);

CREATE INDEX idx_staff_activity_scope
    ON staff_activity(institution_id, campus_id, department_id);

CREATE INDEX idx_staff_activity_dates
    ON staff_activity(start_date, end_date);

CREATE INDEX idx_staff_activity_contributor_activity
    ON staff_activity_contributor(staff_activity_id, contributor_sequence);

CREATE INDEX idx_staff_activity_contributor_employee
    ON staff_activity_contributor(employee_id, staff_activity_id);

CREATE INDEX idx_journal_publication_year
    ON journal_publication(publication_year, journal_id);

CREATE INDEX idx_journal_publication_title
    ON journal_publication(paper_title(191));

CREATE INDEX idx_journal_name
    ON journal(journal_name(191));

CREATE INDEX idx_conference_event_dates
    ON conference_event(start_date, end_date, participation_level_id);

CREATE INDEX idx_conference_activity_event
    ON conference_activity(conference_event_id, conference_contribution_type_id);

CREATE INDEX idx_prof_dev_type_mode
    ON professional_development_activity(training_program_type_id, event_mode_id);

CREATE INDEX idx_internship_org
    ON faculty_internship(organization_id, industry_sector_id);

CREATE INDEX idx_research_proposal_status
    ON research_proposal(research_status_id, funding_agency_id, proposal_submission_date);

CREATE INDEX idx_funded_project_status
    ON funded_research_project(research_status_id, funding_agency_id, project_start_date, project_end_date);

CREATE INDEX idx_consultancy_client_status
    ON consultancy_project(client_organization_id, status, project_start_date);

CREATE INDEX idx_membership_org_status
    ON staff_professional_membership(organization_id, membership_status, membership_expiry_date);

CREATE INDEX idx_prof_contribution_type_date
    ON staff_professional_contribution(professional_contribution_type_id, contribution_date);

CREATE INDEX idx_evidence_activity
    ON evidence_document(staff_activity_id, document_type_id, evidence_type_id, is_active);

CREATE INDEX idx_evidence_verification
    ON evidence_document(verification_status_id, approval_status_id, created_at);

CREATE INDEX idx_evidence_academic_year
    ON evidence_document(academic_year_id, document_type_id);

CREATE INDEX idx_evidence_certificate_number
    ON evidence_document(certificate_document_number);

CREATE INDEX idx_evidence_expiry
    ON evidence_document(expiry_date, is_active);

CREATE INDEX idx_evidence_version_current
    ON evidence_document_version(evidence_document_id, is_current, version_number);

CREATE INDEX idx_evidence_audit_time
    ON evidence_document_audit(evidence_document_id, performed_at);

CREATE INDEX idx_external_org_name
    ON external_organization(organization_name(191), city, country_id);

-- =============================================================
-- 39. DATA-INTEGRITY NOTES ENFORCED AT APPLICATION/SERVICE LAYER
-- =============================================================
-- 1. Exactly one specialized child table should exist for each staff_activity,
--    matching activity_type.activity_group/activity_type_code.
-- 2. staff_activity.employee_id must be within the authorized RBAC row scope.
-- 3. campus_id and department_id should match the employee assignment valid
--    for the activity date when the institution requires historical accuracy.
-- 4. Only allowed MIME types/extensions should be accepted:
--      PDF, JPG/JPEG, PNG, DOC/DOCX, XLS/XLSX, PPT/PPTX, ZIP.
-- 5. Validate MIME type from file content; do not trust extension alone.
-- 6. Restrict executable/script formats and scan uploads for malware.
-- 7. For confidential evidence, storage objects should be private and accessed
--    through authorization-checked signed/temporary URLs.
-- 8. Replacement should create a new evidence_document_version; do not overwrite
--    prior file_object records when version retention is required.
-- 9. Exactly one version should have is_current=TRUE for each evidence document.
-- 10. Verification and approval actions should append evidence_document_audit rows
--     and the existing activity_audit log.
-- 11. Soft deletion should be the normal delete path for staff_activity and
--     evidence_document. Hard deletion should be restricted to privileged admins.
-- 12. DOI, ISSN, ISBN, membership numbers, sanction/order numbers and certificate
--     numbers should receive format validation appropriate to their issuing source.
-- 13. Sanctioned/received/utilized research amounts should be reconciled by service
--     logic and financial reports.
-- 14. Search results must enforce confidentiality and row-level RBAC before
--     exposing evidence metadata or file download URLs.
-- =============================================================

-- Foreign key checks restored by the consolidated schema footer.

-- =============================================================
-- END OF SIMS V5 STAFF PROFILE / RESEARCH / EVIDENCE EXTENSION
-- =============================================================


-- =============================================================
-- 40. STUDENT ACTIVITY & EVIDENCE MODULE
-- Independent student co-curricular / extra-curricular portfolio
-- =============================================================

CREATE TABLE student_activity_type (
    student_activity_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type_code VARCHAR(50) NOT NULL UNIQUE,
    type_name VARCHAR(150) NOT NULL UNIQUE,
    activity_group ENUM(
        'CONFERENCE','WORKSHOP','HACKATHON','SPORTS','CULTURAL','TECHNICAL',
        'COMPETITION','CERTIFICATION','CLUB','NSS','NCC','COMMUNITY_SERVICE',
        'ENTREPRENEURSHIP','INNOVATION','OTHER'
    ) NOT NULL,
    description VARCHAR(500) NULL,
    requires_team_details BOOLEAN NOT NULL DEFAULT FALSE,
    supports_achievement BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_activity (
    student_activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id BIGINT UNSIGNED NOT NULL,
    student_activity_type_id SMALLINT UNSIGNED NOT NULL,
    academic_year_id SMALLINT UNSIGNED NULL,
    institution_id SMALLINT UNSIGNED NOT NULL,
    campus_id SMALLINT UNSIGNED NULL,
    department_id SMALLINT UNSIGNED NULL,
    programme_id SMALLINT UNSIGNED NULL,
    participation_level_id TINYINT UNSIGNED NULL,
    event_mode_id TINYINT UNSIGNED NULL,
    external_organization_id BIGINT UNSIGNED NULL,
    organizer_name VARCHAR(300) NULL,
    activity_title VARCHAR(500) NOT NULL,
    event_name VARCHAR(500) NULL,
    team_name VARCHAR(250) NULL,
    participation_role VARCHAR(150) NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    venue_name VARCHAR(250) NULL,
    city VARCHAR(120) NULL,
    state_id SMALLINT UNSIGNED NULL,
    country_id SMALLINT UNSIGNED NULL,
    achievement_type ENUM(
        'PARTICIPATION','WINNER','RUNNER_UP','FIRST_PLACE','SECOND_PLACE','THIRD_PLACE',
        'MERIT','SPECIAL_MENTION','QUALIFIED','FINALIST','MEDAL_GOLD','MEDAL_SILVER',
        'MEDAL_BRONZE','RECOGNITION','OTHER'
    ) NOT NULL DEFAULT 'PARTICIPATION',
    position_rank SMALLINT UNSIGNED NULL,
    award_name VARCHAR(500) NULL,
    award_details TEXT NULL,
    cash_prize_amount DECIMAL(14,2) NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'INR',
    certificate_number VARCHAR(150) NULL,
    activity_url VARCHAR(1000) NULL,
    description TEXT NULL,
    outcomes TEXT NULL,
    remarks TEXT NULL,
    verification_status_id TINYINT UNSIGNED NOT NULL,
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,
    approval_status_id TINYINT UNSIGNED NOT NULL,
    approved_by_user_id BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    approval_remarks VARCHAR(1000) NULL,
    rejection_reason VARCHAR(1000) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    deleted_by_user_id BIGINT UNSIGNED NULL,
    deletion_reason VARCHAR(1000) NULL,

    CONSTRAINT chk_student_activity_dates CHECK (
        end_date IS NULL OR start_date IS NULL OR end_date >= start_date
    ),
    CONSTRAINT chk_student_activity_prize CHECK (
        cash_prize_amount IS NULL OR cash_prize_amount >= 0
    ),
    CONSTRAINT chk_student_activity_rank CHECK (
        position_rank IS NULL OR position_rank > 0
    ),
    CONSTRAINT fk_student_activity_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_activity_type FOREIGN KEY (student_activity_type_id) REFERENCES student_activity_type(student_activity_type_id),
    CONSTRAINT fk_student_activity_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_student_activity_institution FOREIGN KEY (institution_id) REFERENCES institution(institution_id),
    CONSTRAINT fk_student_activity_campus FOREIGN KEY (campus_id) REFERENCES campus(campus_id),
    CONSTRAINT fk_student_activity_department FOREIGN KEY (department_id) REFERENCES department(department_id),
    CONSTRAINT fk_student_activity_programme FOREIGN KEY (programme_id) REFERENCES programme(programme_id),
    CONSTRAINT fk_student_activity_level FOREIGN KEY (participation_level_id) REFERENCES participation_level(participation_level_id),
    CONSTRAINT fk_student_activity_mode FOREIGN KEY (event_mode_id) REFERENCES event_mode(event_mode_id),
    CONSTRAINT fk_student_activity_org FOREIGN KEY (external_organization_id) REFERENCES external_organization(organization_id),
    CONSTRAINT fk_student_activity_state FOREIGN KEY (state_id) REFERENCES state(state_id),
    CONSTRAINT fk_student_activity_country FOREIGN KEY (country_id) REFERENCES country(country_id),
    CONSTRAINT fk_student_activity_verification_status FOREIGN KEY (verification_status_id) REFERENCES verification_status(verification_status_id),
    CONSTRAINT fk_student_activity_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_activity_approval_status FOREIGN KEY (approval_status_id) REFERENCES approval_status(approval_status_id),
    CONSTRAINT fk_student_activity_approved_by FOREIGN KEY (approved_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_activity_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_activity_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_activity_deleted_by FOREIGN KEY (deleted_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional team / collaborator details for hackathons, sports and group events.
CREATE TABLE student_activity_team_member (
    student_activity_team_member_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_activity_id BIGINT UNSIGNED NOT NULL,
    student_id BIGINT UNSIGNED NULL,
    external_member_name VARCHAR(250) NULL,
    external_member_email VARCHAR(254) NULL,
    external_organization_id BIGINT UNSIGNED NULL,
    member_role VARCHAR(150) NULL,
    member_sequence SMALLINT UNSIGNED NULL,
    is_team_lead BOOLEAN NOT NULL DEFAULT FALSE,
    remarks VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_student_activity_member_identity CHECK (
        (student_id IS NOT NULL AND external_member_name IS NULL)
        OR (student_id IS NULL AND external_member_name IS NOT NULL)
    ),
    CONSTRAINT uq_student_activity_internal_member UNIQUE (student_activity_id, student_id),
    CONSTRAINT fk_student_activity_member_activity FOREIGN KEY (student_activity_id) REFERENCES student_activity(student_activity_id),
    CONSTRAINT fk_student_activity_member_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_student_activity_member_org FOREIGN KEY (external_organization_id) REFERENCES external_organization(organization_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_activity_evidence (
    student_activity_evidence_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_activity_id BIGINT UNSIGNED NOT NULL,
    document_type_id SMALLINT UNSIGNED NOT NULL,
    evidence_type_id SMALLINT UNSIGNED NULL,
    confidentiality_level_id TINYINT UNSIGNED NOT NULL,
    document_title VARCHAR(500) NOT NULL,
    description TEXT NULL,
    academic_year_id SMALLINT UNSIGNED NULL,
    document_issue_date DATE NULL,
    issuing_authority VARCHAR(300) NULL,
    issuing_organization_id BIGINT UNSIGNED NULL,
    certificate_document_number VARCHAR(150) NULL,
    expiry_date DATE NULL,
    verification_status_id TINYINT UNSIGNED NOT NULL,
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at DATETIME NULL,
    verification_remarks VARCHAR(1000) NULL,
    approval_status_id TINYINT UNSIGNED NOT NULL,
    approved_by_user_id BIGINT UNSIGNED NULL,
    approved_at DATETIME NULL,
    rejection_reason VARCHAR(1000) NULL,
    current_version_number SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id BIGINT UNSIGNED NOT NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    deleted_by_user_id BIGINT UNSIGNED NULL,
    deletion_reason VARCHAR(1000) NULL,
    CONSTRAINT chk_student_evidence_dates CHECK (
        expiry_date IS NULL OR document_issue_date IS NULL OR expiry_date >= document_issue_date
    ),
    CONSTRAINT chk_student_evidence_version CHECK (current_version_number >= 1),
    CONSTRAINT fk_student_evidence_activity FOREIGN KEY (student_activity_id) REFERENCES student_activity(student_activity_id),
    CONSTRAINT fk_student_evidence_document_type FOREIGN KEY (document_type_id) REFERENCES document_type(document_type_id),
    CONSTRAINT fk_student_evidence_evidence_type FOREIGN KEY (evidence_type_id) REFERENCES evidence_type(evidence_type_id),
    CONSTRAINT fk_student_evidence_confidentiality FOREIGN KEY (confidentiality_level_id) REFERENCES confidentiality_level(confidentiality_level_id),
    CONSTRAINT fk_student_evidence_year FOREIGN KEY (academic_year_id) REFERENCES academic_year(academic_year_id),
    CONSTRAINT fk_student_evidence_issuing_org FOREIGN KEY (issuing_organization_id) REFERENCES external_organization(organization_id),
    CONSTRAINT fk_student_evidence_verification_status FOREIGN KEY (verification_status_id) REFERENCES verification_status(verification_status_id),
    CONSTRAINT fk_student_evidence_verified_by FOREIGN KEY (verified_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_evidence_approval_status FOREIGN KEY (approval_status_id) REFERENCES approval_status(approval_status_id),
    CONSTRAINT fk_student_evidence_approved_by FOREIGN KEY (approved_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_evidence_created_by FOREIGN KEY (created_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_evidence_updated_by FOREIGN KEY (updated_by_user_id) REFERENCES user_account(user_id),
    CONSTRAINT fk_student_evidence_deleted_by FOREIGN KEY (deleted_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_activity_evidence_version (
    student_activity_evidence_version_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_activity_evidence_id BIGINT UNSIGNED NOT NULL,
    version_number SMALLINT UNSIGNED NOT NULL,
    file_object_id BIGINT UNSIGNED NOT NULL,
    change_reason VARCHAR(1000) NULL,
    uploaded_by_user_id BIGINT UNSIGNED NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    current_document_key BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN is_current = TRUE THEN student_activity_evidence_id ELSE NULL END
    ) STORED,
    CONSTRAINT uq_student_evidence_version UNIQUE (student_activity_evidence_id, version_number),
    CONSTRAINT uq_student_evidence_file UNIQUE (student_activity_evidence_id, file_object_id),
    CONSTRAINT uq_student_evidence_current UNIQUE (current_document_key),
    CONSTRAINT chk_student_evidence_version_number CHECK (version_number >= 1),
    CONSTRAINT fk_student_evidence_version_document FOREIGN KEY (student_activity_evidence_id) REFERENCES student_activity_evidence(student_activity_evidence_id),
    CONSTRAINT fk_student_evidence_version_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id),
    CONSTRAINT fk_student_evidence_version_uploaded_by FOREIGN KEY (uploaded_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_activity_evidence_audit (
    student_activity_evidence_audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_activity_evidence_id BIGINT UNSIGNED NOT NULL,
    student_activity_evidence_version_id BIGINT UNSIGNED NULL,
    action_code ENUM(
        'CREATE','UPLOAD','REPLACE','UPDATE_METADATA','PREVIEW','DOWNLOAD',
        'VERIFY','REJECT_VERIFICATION','APPROVE','REJECT_APPROVAL',
        'SOFT_DELETE','RESTORE','ACCESS_DENIED'
    ) NOT NULL,
    performed_by_user_id BIGINT UNSIGNED NULL,
    performed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    before_values JSON NULL,
    after_values JSON NULL,
    remarks VARCHAR(1000) NULL,
    CONSTRAINT fk_student_evidence_audit_document FOREIGN KEY (student_activity_evidence_id) REFERENCES student_activity_evidence(student_activity_evidence_id),
    CONSTRAINT fk_student_evidence_audit_version FOREIGN KEY (student_activity_evidence_version_id) REFERENCES student_activity_evidence_version(student_activity_evidence_version_id),
    CONSTRAINT fk_student_evidence_audit_user FOREIGN KEY (performed_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_activity_evidence_requirement (
    student_activity_evidence_requirement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_activity_type_id SMALLINT UNSIGNED NOT NULL,
    evidence_type_id SMALLINT UNSIGNED NOT NULL,
    document_type_id SMALLINT UNSIGNED NULL,
    is_mandatory BOOLEAN NOT NULL DEFAULT FALSE,
    minimum_files TINYINT UNSIGNED NOT NULL DEFAULT 0,
    maximum_files TINYINT UNSIGNED NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    document_type_key SMALLINT UNSIGNED GENERATED ALWAYS AS (COALESCE(document_type_id, 0)) STORED,
    CONSTRAINT uq_student_activity_evidence_requirement UNIQUE (student_activity_type_id, evidence_type_id, document_type_key),
    CONSTRAINT chk_student_activity_evidence_counts CHECK (maximum_files IS NULL OR maximum_files >= minimum_files),
    CONSTRAINT chk_student_activity_evidence_req_dates CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CONSTRAINT fk_student_activity_evidence_req_type FOREIGN KEY (student_activity_type_id) REFERENCES student_activity_type(student_activity_type_id),
    CONSTRAINT fk_student_activity_evidence_req_evidence FOREIGN KEY (evidence_type_id) REFERENCES evidence_type(evidence_type_id),
    CONSTRAINT fk_student_activity_evidence_req_document FOREIGN KEY (document_type_id) REFERENCES document_type(document_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Student activity reference data.
INSERT INTO student_activity_type
    (type_code, type_name, activity_group, requires_team_details, supports_achievement)
VALUES
('CONFERENCE_PARTICIPATION','Conference Participation','CONFERENCE',FALSE,TRUE),
('CONFERENCE_PRESENTATION','Conference Paper / Poster Presentation','CONFERENCE',FALSE,TRUE),
('WORKSHOP','Workshop','WORKSHOP',FALSE,TRUE),
('HACKATHON','Hackathon','HACKATHON',TRUE,TRUE),
('SPORTS','Sports','SPORTS',TRUE,TRUE),
('CULTURAL_EVENT','Cultural Event','CULTURAL',TRUE,TRUE),
('TECHNICAL_EVENT','Technical Event','TECHNICAL',TRUE,TRUE),
('COMPETITION','Competition','COMPETITION',TRUE,TRUE),
('CERTIFICATION','Certification','CERTIFICATION',FALSE,TRUE),
('CLUB_ACTIVITY','Club Activity','CLUB',TRUE,TRUE),
('NSS_ACTIVITY','NSS Activity','NSS',TRUE,TRUE),
('NCC_ACTIVITY','NCC Activity','NCC',TRUE,TRUE),
('COMMUNITY_SERVICE','Community / Social Service','COMMUNITY_SERVICE',TRUE,TRUE),
('ENTREPRENEURSHIP','Entrepreneurship Activity','ENTREPRENEURSHIP',TRUE,TRUE),
('INNOVATION','Innovation / Prototype Activity','INNOVATION',TRUE,TRUE),
('OTHER','Other Student Activity','OTHER',FALSE,TRUE);

-- Common evidence categories specific to student activities.
INSERT IGNORE INTO evidence_type (evidence_type_code, evidence_type_name) VALUES
('STUDENT_PARTICIPATION_CERTIFICATE','Student Participation Certificate'),
('STUDENT_ACHIEVEMENT_CERTIFICATE','Student Achievement / Winner Certificate'),
('STUDENT_MEDAL_PROOF','Medal / Sports Achievement Proof'),
('STUDENT_SCORE_SHEET','Competition Score / Result Sheet'),
('STUDENT_EVENT_PHOTO','Student Event Photograph'),
('STUDENT_HACKATHON_RESULT','Hackathon Result / Ranking Proof'),
('STUDENT_PRESENTATION_PROOF','Presentation / Paper Presentation Proof');

-- RBAC resources under the existing STUDENT module.
INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STUDENT_ACTIVITY', 'Student Activity Records',
       'Create and maintain student conference, workshop, hackathon, sports, cultural, technical and other activity records.'
FROM access_module WHERE module_code='STUDENT';

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STUDENT_ACTIVITY_EVIDENCE', 'Student Activity Evidence',
       'Upload, preview, download, version, verify and approve evidence for student activities.'
FROM access_module WHERE module_code='STUDENT';

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT access_module_id, 'STUDENT_ACTIVITY_REPORT', 'Student Activity Reports',
       'Search, filter, report and export student activities and achievements.'
FROM access_module WHERE module_code='STUDENT';

INSERT IGNORE INTO permission
    (access_resource_id, access_action_id, permission_code, permission_name, is_sensitive)
SELECT ar.access_resource_id,
       aa.access_action_id,
       CONCAT('STUDENT.', ar.resource_code, '.', aa.action_code),
       CONCAT(aa.action_name, ' ', ar.resource_name),
       CASE WHEN ar.resource_code='STUDENT_ACTIVITY_EVIDENCE'
                 AND aa.action_code IN ('DELETE','APPROVE','VERIFY','EXPORT')
            THEN TRUE
            WHEN aa.action_code IN ('DELETE','APPROVE','CONFIGURE') THEN TRUE
            ELSE FALSE END
FROM access_resource ar
JOIN access_module am ON am.access_module_id=ar.access_module_id AND am.module_code='STUDENT'
CROSS JOIN access_action aa
WHERE ar.resource_code IN ('STUDENT_ACTIVITY','STUDENT_ACTIVITY_EVIDENCE','STUDENT_ACTIVITY_REPORT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','DELETE','APPROVE','VERIFY','EXPORT','CONFIGURE');

-- Student self-service: own activity/evidence create/read/update.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='STUDENT'
  AND am.module_code='STUDENT'
  AND ar.resource_code IN ('STUDENT_ACTIVITY','STUDENT_ACTIVITY_EVIDENCE')
  AND aa.action_code IN ('CREATE','READ','UPDATE');

-- Department/programme staff: review, verification and reporting within authorized scope.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code IN ('HEAD_DEPARTMENT','PROGRAMME_COORDINATOR','FACULTY_ADVISOR','MENTOR','STUDENT_SECTION_OFFICER','DOCUMENT_VERIFIER')
  AND am.module_code='STUDENT'
  AND ar.resource_code IN ('STUDENT_ACTIVITY','STUDENT_ACTIVITY_EVIDENCE','STUDENT_ACTIVITY_REPORT')
  AND aa.action_code IN ('CREATE','READ','UPDATE','VERIFY','APPROVE','EXPORT');

-- Internal auditor: read/export verified student activity evidence in authorized scope.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='INTERNAL_AUDITOR'
  AND am.module_code='STUDENT'
  AND ar.resource_code IN ('STUDENT_ACTIVITY','STUDENT_ACTIVITY_EVIDENCE','STUDENT_ACTIVITY_REPORT')
  AND aa.action_code IN ('READ','EXPORT');

-- Super admin receives all new permissions.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
WHERE r.role_code='SUPER_ADMIN'
  AND p.permission_code LIKE 'STUDENT.STUDENT_ACTIVITY%';

CREATE OR REPLACE VIEW v_student_activity_profile AS
SELECT
    sa.student_activity_id,
    sa.student_id,
    s.student_number,
    s.display_name AS student_name,
    sat.type_code AS activity_type_code,
    sat.type_name AS activity_type_name,
    sat.activity_group,
    sa.activity_title,
    sa.event_name,
    ay.year_code AS academic_year,
    i.institution_name,
    c.campus_name,
    d.department_name,
    p.programme_name,
    pl.level_name AS participation_level,
    em.mode_name AS event_mode,
    sa.start_date,
    sa.end_date,
    sa.achievement_type,
    sa.position_rank,
    sa.award_name,
    sa.cash_prize_amount,
    vs.status_name AS verification_status,
    aps.status_name AS approval_status,
    sa.created_at,
    sa.updated_at,
    sa.deleted_at
FROM student_activity sa
JOIN student s ON s.student_id=sa.student_id
JOIN student_activity_type sat ON sat.student_activity_type_id=sa.student_activity_type_id
LEFT JOIN academic_year ay ON ay.academic_year_id=sa.academic_year_id
JOIN institution i ON i.institution_id=sa.institution_id
LEFT JOIN campus c ON c.campus_id=sa.campus_id
LEFT JOIN department d ON d.department_id=sa.department_id
LEFT JOIN programme p ON p.programme_id=sa.programme_id
LEFT JOIN participation_level pl ON pl.participation_level_id=sa.participation_level_id
LEFT JOIN event_mode em ON em.event_mode_id=sa.event_mode_id
JOIN verification_status vs ON vs.verification_status_id=sa.verification_status_id
JOIN approval_status aps ON aps.approval_status_id=sa.approval_status_id;

CREATE OR REPLACE VIEW v_student_activity_evidence_search AS
SELECT
    sae.student_activity_evidence_id,
    sae.student_activity_id,
    sa.student_id,
    s.student_number,
    s.display_name AS student_name,
    sat.type_code AS activity_type_code,
    sat.type_name AS activity_type_name,
    d.department_id,
    d.department_name,
    p.programme_id,
    p.programme_name,
    ay.year_code AS academic_year,
    dt.document_code,
    dt.document_name,
    et.evidence_type_code,
    et.evidence_type_name,
    sae.document_title,
    sae.certificate_document_number,
    sae.document_issue_date,
    sae.expiry_date,
    vs.status_name AS verification_status,
    aps.status_name AS approval_status,
    cl.level_name AS confidentiality_level,
    sae.current_version_number,
    sae.is_active,
    sae.created_at,
    sae.updated_at,
    sae.deleted_at
FROM student_activity_evidence sae
JOIN student_activity sa ON sa.student_activity_id=sae.student_activity_id
JOIN student s ON s.student_id=sa.student_id
JOIN student_activity_type sat ON sat.student_activity_type_id=sa.student_activity_type_id
LEFT JOIN academic_year ay ON ay.academic_year_id=sae.academic_year_id
LEFT JOIN department d ON d.department_id=sa.department_id
LEFT JOIN programme p ON p.programme_id=sa.programme_id
JOIN document_type dt ON dt.document_type_id=sae.document_type_id
LEFT JOIN evidence_type et ON et.evidence_type_id=sae.evidence_type_id
JOIN verification_status vs ON vs.verification_status_id=sae.verification_status_id
JOIN approval_status aps ON aps.approval_status_id=sae.approval_status_id
JOIN confidentiality_level cl ON cl.confidentiality_level_id=sae.confidentiality_level_id;

CREATE INDEX idx_student_activity_student_year
    ON student_activity(student_id, academic_year_id, student_activity_type_id, deleted_at);
CREATE INDEX idx_student_activity_department_year
    ON student_activity(department_id, academic_year_id, student_activity_type_id, deleted_at);
CREATE INDEX idx_student_activity_programme_year
    ON student_activity(programme_id, academic_year_id, student_activity_type_id, deleted_at);
CREATE INDEX idx_student_activity_achievement
    ON student_activity(achievement_type, participation_level_id, start_date);
CREATE INDEX idx_student_activity_verification
    ON student_activity(verification_status_id, approval_status_id, created_at);
CREATE INDEX idx_student_activity_member_activity
    ON student_activity_team_member(student_activity_id, member_sequence);
CREATE INDEX idx_student_activity_member_student
    ON student_activity_team_member(student_id, student_activity_id);
CREATE INDEX idx_student_evidence_activity
    ON student_activity_evidence(student_activity_id, document_type_id, evidence_type_id, is_active);
CREATE INDEX idx_student_evidence_verification
    ON student_activity_evidence(verification_status_id, approval_status_id, created_at);
CREATE INDEX idx_student_evidence_expiry
    ON student_activity_evidence(expiry_date, is_active);
CREATE INDEX idx_student_evidence_version_current
    ON student_activity_evidence_version(student_activity_evidence_id, is_current, version_number);
CREATE INDEX idx_student_evidence_audit_time
    ON student_activity_evidence_audit(student_activity_evidence_id, performed_at);

-- Student activity integrity notes enforced at application/service layer:
-- 1. Student self-service must only create/update activities for the authenticated student.
-- 2. institution/campus/department/programme should match the student's active enrolment
--    for the activity date when institutional reporting requires historical accuracy.
-- 3. Exactly one evidence version must be current; the generated unique key prevents
--    multiple current versions, while the service layer must ensure at least one exists.
-- 4. Verification/approval actions should append student_activity_evidence_audit rows.
-- 5. Evidence download/search must enforce confidentiality and row-level RBAC.
-- 6. MIME/content validation, malware scanning and private storage rules are identical
--    to staff evidence handling.
-- =============================================================

-- =============================================================
-- 41. LESSON PLAN, OUTCOME, ASSESSMENT BLUEPRINT AND RUBRIC MODULE
-- =============================================================
-- =============================================================
-- LP-1. OUTCOME AND ACCREDITATION MASTERS
-- =============================================================

CREATE TABLE bloom_level (
    bloom_level_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    level_no TINYINT UNSIGNED NOT NULL,
    level_code VARCHAR(3) NOT NULL,
    level_name VARCHAR(30) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_lp_bloom_number UNIQUE (level_no),
    CONSTRAINT uq_lp_bloom_code UNIQUE (level_code),
    CONSTRAINT uq_lp_bloom_name UNIQUE (level_name),
    CONSTRAINT chk_lp_bloom_level CHECK (level_no BETWEEN 1 AND 6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- PO, PSO, competency and PI are stored in one hierarchical catalogue.
-- Binding the catalogue to curriculum_scheme preserves regulation/version history.
CREATE TABLE curriculum_framework_node (
    framework_node_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    curriculum_scheme_id INT UNSIGNED NOT NULL,
    parent_node_id BIGINT UNSIGNED NULL,
    node_type ENUM('PO','PSO','COMPETENCY','PI') NOT NULL,
    node_code VARCHAR(30) NOT NULL,
    description TEXT NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_lp_framework_code UNIQUE
        (curriculum_scheme_id, node_type, node_code),
    CONSTRAINT fk_lp_framework_scheme FOREIGN KEY (curriculum_scheme_id)
        REFERENCES curriculum_scheme(curriculum_scheme_id),
    CONSTRAINT uq_framework_id_scheme UNIQUE (framework_node_id, curriculum_scheme_id),
    CONSTRAINT fk_lp_framework_parent FOREIGN KEY (parent_node_id, curriculum_scheme_id)
        REFERENCES curriculum_framework_node(framework_node_id, curriculum_scheme_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-2. LESSON PLAN HEADER AND FACULTY WORKFLOW
-- =============================================================

-- course_offering provides the academic term, programme, curriculum,
-- semester and course context without repeating those foreign keys.
CREATE TABLE lesson_plan (
    lesson_plan_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_offering_id BIGINT UNSIGNED NOT NULL,
    version_no DECIMAL(6,2) NOT NULL DEFAULT 1.00,
    status ENUM(
        'DRAFT','SUBMITTED','UNDER_REVIEW','RETURNED',
        'APPROVED','PUBLISHED','ARCHIVED'
    ) NOT NULL DEFAULT 'DRAFT',
    total_contact_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    theory_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    tutorial_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    practical_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    tw_sl_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    isa_marks DECIMAL(6,2) NOT NULL DEFAULT 0,
    esa_marks DECIMAL(6,2) NOT NULL DEFAULT 0,
    exam_duration_minutes SMALLINT UNSIGNED NULL,
    effective_from DATE NULL,
    effective_to DATE NULL,
    remarks TEXT NULL,
    created_by_user_id BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by_user_id BIGINT UNSIGNED NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP NULL,
    approved_at TIMESTAMP NULL,
    published_at TIMESTAMP NULL,
    archived_at TIMESTAMP NULL,
    published_offering_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN status='PUBLISHED' THEN course_offering_id ELSE NULL END
    ) STORED,
    CONSTRAINT uq_lp_version UNIQUE (course_offering_id, version_no),
    CONSTRAINT uq_lp_one_published UNIQUE (published_offering_id),
    CONSTRAINT chk_lp_version CHECK (version_no > 0),
    CONSTRAINT chk_lp_values CHECK (
        total_contact_hours >= 0 AND theory_hours >= 0
        AND tutorial_hours >= 0 AND practical_hours >= 0
        AND tw_sl_hours >= 0 AND isa_marks >= 0 AND esa_marks >= 0
    ),
    CONSTRAINT chk_lp_duration CHECK
        (exam_duration_minutes IS NULL OR exam_duration_minutes > 0),
    CONSTRAINT chk_lp_dates CHECK
        (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from),
    CONSTRAINT fk_lp_offering FOREIGN KEY (course_offering_id)
        REFERENCES course_offering(course_offering_id),
    CONSTRAINT fk_lp_created_by FOREIGN KEY (created_by_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_lp_updated_by FOREIGN KEY (updated_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- employee_id records the academic actor; action_by_user_id records the login.
CREATE TABLE lesson_plan_faculty (
    lesson_plan_faculty_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    role_code ENUM('AUTHOR','CHECKER','REVIEWER','APPROVER','HOD') NOT NULL,
    sequence_no SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    action_status ENUM('PENDING','ACCEPTED','RETURNED','APPROVED')
        NOT NULL DEFAULT 'PENDING',
    action_by_user_id BIGINT UNSIGNED NULL,
    action_at TIMESTAMP NULL,
    remarks TEXT NULL,
    CONSTRAINT uq_lp_faculty_role UNIQUE
        (lesson_plan_id, employee_id, role_code),
    CONSTRAINT chk_lp_faculty_sequence CHECK (sequence_no > 0),
    CONSTRAINT fk_lp_faculty_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_faculty_employee FOREIGN KEY (employee_id)
        REFERENCES employee(employee_id),
    CONSTRAINT fk_lp_faculty_action_user FOREIGN KEY (action_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Formal course-to-course prerequisites remain in course_prerequisite.
-- This table stores plan-specific prerequisite notes and learning resources.
CREATE TABLE lesson_plan_resource (
    lesson_plan_resource_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    resource_type ENUM(
        'PREREQUISITE_NOTE','TEXTBOOK','REFERENCE_BOOK','WEB_RESOURCE','OTHER'
    ) NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NULL,
    edition VARCHAR(80) NULL,
    publisher VARCHAR(200) NULL,
    publication_year YEAR NULL,
    isbn_or_url VARCHAR(500) NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    CONSTRAINT chk_lp_resource_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_resource_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-3. COURSE OUTCOMES AND ARTICULATION
-- =============================================================

CREATE TABLE course_outcome (
    course_outcome_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    outcome_code VARCHAR(12) NOT NULL,
    description TEXT NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_course_outcome_code UNIQUE
        (lesson_plan_id, outcome_code),
    CONSTRAINT uq_lp_course_outcome_order UNIQUE
        (lesson_plan_id, display_order),
    CONSTRAINT chk_lp_course_outcome_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_course_outcome_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE co_outcome_mapping (
    co_outcome_mapping_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_outcome_id BIGINT UNSIGNED NOT NULL,
    framework_node_id BIGINT UNSIGNED NOT NULL,
    mapping_level TINYINT UNSIGNED NOT NULL,
    rationale TEXT NULL,
    CONSTRAINT uq_lp_co_framework UNIQUE
        (course_outcome_id, framework_node_id),
    CONSTRAINT chk_lp_mapping_level CHECK (mapping_level BETWEEN 1 AND 3),
    CONSTRAINT fk_lp_co_mapping_outcome FOREIGN KEY (course_outcome_id)
        REFERENCES course_outcome(course_outcome_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_co_mapping_framework FOREIGN KEY (framework_node_id)
        REFERENCES curriculum_framework_node(framework_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE course_specific_pi (
    course_specific_pi_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    pi_node_id BIGINT UNSIGNED NOT NULL,
    cspi_code VARCHAR(30) NULL,
    description TEXT NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    CONSTRAINT uq_lp_cspi_order UNIQUE
        (lesson_plan_id, pi_node_id, display_order),
    CONSTRAINT chk_lp_cspi_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_cspi_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_cspi_pi FOREIGN KEY (pi_node_id)
        REFERENCES curriculum_framework_node(framework_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-4. SYLLABUS, TLO AND CHAPTER PLAN
-- =============================================================

CREATE TABLE syllabus_unit (
    syllabus_unit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    unit_no SMALLINT UNSIGNED NOT NULL,
    unit_title VARCHAR(200) NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_unit_number UNIQUE (lesson_plan_id, unit_no),
    CONSTRAINT uq_lp_unit_order UNIQUE (lesson_plan_id, display_order),
    CONSTRAINT chk_lp_unit_number CHECK (unit_no > 0),
    CONSTRAINT chk_lp_unit_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_unit_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE syllabus_chapter (
    syllabus_chapter_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    syllabus_unit_id BIGINT UNSIGNED NOT NULL,
    chapter_no SMALLINT UNSIGNED NOT NULL,
    chapter_title VARCHAR(250) NOT NULL,
    syllabus_content TEXT NOT NULL,
    planned_theory_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_chapter_number UNIQUE
        (syllabus_unit_id, chapter_no),
    CONSTRAINT uq_lp_chapter_order UNIQUE
        (syllabus_unit_id, display_order),
    CONSTRAINT chk_lp_chapter_number CHECK (chapter_no > 0),
    CONSTRAINT chk_lp_chapter_hours CHECK (planned_theory_hours >= 0),
    CONSTRAINT chk_lp_chapter_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_chapter_unit FOREIGN KEY (syllabus_unit_id)
        REFERENCES syllabus_unit(syllabus_unit_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE topic_learning_outcome (
    topic_learning_outcome_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    syllabus_chapter_id BIGINT UNSIGNED NOT NULL,
    tlo_code VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    course_outcome_id BIGINT UNSIGNED NOT NULL,
    bloom_level_id SMALLINT UNSIGNED NOT NULL,
    framework_node_id BIGINT UNSIGNED NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_tlo_code UNIQUE
        (syllabus_chapter_id, tlo_code),
    CONSTRAINT uq_lp_tlo_order UNIQUE
        (syllabus_chapter_id, display_order),
    CONSTRAINT chk_lp_tlo_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_tlo_chapter FOREIGN KEY (syllabus_chapter_id)
        REFERENCES syllabus_chapter(syllabus_chapter_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_tlo_co FOREIGN KEY (course_outcome_id)
        REFERENCES course_outcome(course_outcome_id),
    CONSTRAINT fk_lp_tlo_bloom FOREIGN KEY (bloom_level_id)
        REFERENCES bloom_level(bloom_level_id),
    CONSTRAINT fk_lp_tlo_framework FOREIGN KEY (framework_node_id)
        REFERENCES curriculum_framework_node(framework_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Planned hour-wise teaching. Actual delivery stays in class_session.
CREATE TABLE lesson_plan_session (
    lesson_plan_session_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    syllabus_chapter_id BIGINT UNSIGNED NOT NULL,
    session_no SMALLINT UNSIGNED NOT NULL,
    topic_description TEXT NOT NULL,
    planned_hours DECIMAL(5,2) NOT NULL DEFAULT 1,
    planned_date DATE NULL,
    expected_session_type ENUM(
        'LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER'
    ) NOT NULL DEFAULT 'LECTURE',
    remarks TEXT NULL,
    CONSTRAINT uq_lp_session_number UNIQUE
        (syllabus_chapter_id, session_no),
    CONSTRAINT chk_lp_session_number CHECK (session_no > 0),
    CONSTRAINT chk_lp_session_hours CHECK (planned_hours > 0),
    CONSTRAINT fk_lp_session_chapter FOREIGN KEY (syllabus_chapter_id)
        REFERENCES syllabus_chapter(syllabus_chapter_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lesson_plan_learning_activity (
    lesson_plan_learning_activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    syllabus_chapter_id BIGINT UNSIGNED NULL,
    activity_type ENUM(
        'LAB_DEMONSTRATION','LAB_EXERCISE',
        'SELF_LEARNING','TOOL_BASED_LEARNING'
    ) NOT NULL,
    activity_no VARCHAR(20) NULL,
    title VARCHAR(250) NOT NULL,
    description TEXT NULL,
    planned_hours DECIMAL(6,2) NOT NULL DEFAULT 0,
    marks DECIMAL(6,2) NOT NULL DEFAULT 0,
    course_outcome_id BIGINT UNSIGNED NULL,
    bloom_level_id SMALLINT UNSIGNED NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    CONSTRAINT chk_lp_activity_values CHECK
        (planned_hours >= 0 AND marks >= 0 AND display_order > 0),
    CONSTRAINT fk_lp_activity_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_activity_chapter FOREIGN KEY (syllabus_chapter_id)
        REFERENCES syllabus_chapter(syllabus_chapter_id),
    CONSTRAINT fk_lp_activity_co FOREIGN KEY (course_outcome_id)
        REFERENCES course_outcome(course_outcome_id),
    CONSTRAINT fk_lp_activity_bloom FOREIGN KEY (bloom_level_id)
        REFERENCES bloom_level(bloom_level_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-5. VERSION-SAFE ASSESSMENT PLANNING
-- =============================================================

-- Extend the existing operational assessment catalogue with lesson-plan types.
-- All previously valid ENUM values are preserved.
ALTER TABLE assessment_component
    MODIFY COLUMN component_type ENUM(
        'INTERNAL_TEST','END_SEMESTER_THEORY','END_SEMESTER_LAB',
        'QUIZ','ASSIGNMENT','LAB','PROJECT','PRESENTATION',
        'TERM_WORK','SELF_LEARNING','OTHER'
    ) NOT NULL;

-- Bridge approved/versioned plan configuration to the operational component.
CREATE TABLE lesson_plan_assessment (
    lesson_plan_assessment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    assessment_component_id BIGINT UNSIGNED NOT NULL,
    conducted_marks DECIMAL(7,2) NOT NULL,
    weightage_marks DECIMAL(7,2) NOT NULL DEFAULT 0,
    duration_minutes SMALLINT UNSIGNED NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    instructions TEXT NULL,
    CONSTRAINT uq_lp_assessment_component UNIQUE
        (lesson_plan_id, assessment_component_id),
    CONSTRAINT uq_lp_assessment_order UNIQUE
        (lesson_plan_id, display_order),
    CONSTRAINT chk_lp_assessment_values CHECK (
        conducted_marks >= 0 AND weightage_marks >= 0 AND display_order > 0
        AND (duration_minutes IS NULL OR duration_minutes > 0)
    ),
    CONSTRAINT fk_lp_assessment_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_assessment_component FOREIGN KEY (assessment_component_id)
        REFERENCES assessment_component(assessment_component_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assessment_blueprint (
    assessment_blueprint_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_assessment_id BIGINT UNSIGNED NOT NULL,
    syllabus_chapter_id BIGINT UNSIGNED NOT NULL,
    planned_question_count DECIMAL(5,2) NOT NULL DEFAULT 0,
    planned_marks DECIMAL(7,2) NULL,
    coverage_percentage DECIMAL(5,2) NULL,
    CONSTRAINT uq_lp_blueprint_chapter UNIQUE
        (lesson_plan_assessment_id, syllabus_chapter_id),
    CONSTRAINT chk_lp_blueprint_values CHECK (
        planned_question_count >= 0
        AND (planned_marks IS NULL OR planned_marks >= 0)
        AND (coverage_percentage IS NULL OR coverage_percentage BETWEEN 0 AND 100)
    ),
    CONSTRAINT fk_lp_blueprint_assessment FOREIGN KEY (lesson_plan_assessment_id)
        REFERENCES lesson_plan_assessment(lesson_plan_assessment_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_lp_blueprint_chapter FOREIGN KEY (syllabus_chapter_id)
        REFERENCES syllabus_chapter(syllabus_chapter_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE co_assessment_mapping (
    co_assessment_mapping_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_outcome_id BIGINT UNSIGNED NOT NULL,
    lesson_plan_assessment_id BIGINT UNSIGNED NOT NULL,
    weightage_percentage DECIMAL(5,2) NOT NULL,
    CONSTRAINT uq_lp_co_assessment UNIQUE
        (course_outcome_id, lesson_plan_assessment_id),
    CONSTRAINT chk_lp_co_assessment_weight CHECK
        (weightage_percentage BETWEEN 0 AND 100),
    CONSTRAINT fk_lp_co_assessment_co FOREIGN KEY (course_outcome_id)
        REFERENCES course_outcome(course_outcome_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_co_assessment_plan_assessment
        FOREIGN KEY (lesson_plan_assessment_id)
        REFERENCES lesson_plan_assessment(lesson_plan_assessment_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-6. RUBRICS
-- =============================================================

CREATE TABLE rubric (
    rubric_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    lesson_plan_assessment_id BIGINT UNSIGNED NULL,
    rubric_name VARCHAR(200) NOT NULL,
    rubric_type ENUM(
        'PRACTICAL','SELF_LEARNING','PROJECT','ASSIGNMENT','OTHER'
    ) NOT NULL,
    max_marks DECIMAL(7,2) NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    CONSTRAINT uq_lp_rubric_name UNIQUE (lesson_plan_id, rubric_name),
    CONSTRAINT chk_lp_rubric_values CHECK
        (max_marks > 0 AND display_order > 0),
    CONSTRAINT fk_lp_rubric_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_rubric_assessment FOREIGN KEY (lesson_plan_assessment_id)
        REFERENCES lesson_plan_assessment(lesson_plan_assessment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE rubric_criterion (
    rubric_criterion_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    rubric_id BIGINT UNSIGNED NOT NULL,
    criterion_name VARCHAR(200) NOT NULL,
    description TEXT NULL,
    max_marks DECIMAL(7,2) NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_rubric_criterion_order UNIQUE
        (rubric_id, display_order),
    CONSTRAINT chk_lp_rubric_criterion_values CHECK
        (max_marks > 0 AND display_order > 0),
    CONSTRAINT fk_lp_criterion_rubric FOREIGN KEY (rubric_id)
        REFERENCES rubric(rubric_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE rubric_band (
    rubric_band_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    rubric_criterion_id BIGINT UNSIGNED NOT NULL,
    band_name VARCHAR(80) NOT NULL,
    min_score DECIMAL(7,2) NOT NULL,
    max_score DECIMAL(7,2) NOT NULL,
    descriptor TEXT NOT NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_rubric_band_name UNIQUE
        (rubric_criterion_id, band_name),
    CONSTRAINT uq_lp_rubric_band_order UNIQUE
        (rubric_criterion_id, display_order),
    CONSTRAINT chk_lp_rubric_band_scores CHECK
        (min_score >= 0 AND max_score >= min_score),
    CONSTRAINT chk_lp_rubric_band_order CHECK (display_order > 0),
    CONSTRAINT fk_lp_band_criterion FOREIGN KEY (rubric_criterion_id)
        REFERENCES rubric_criterion(rubric_criterion_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE rubric_criterion_alignment (
    rubric_criterion_alignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    rubric_criterion_id BIGINT UNSIGNED NOT NULL,
    course_outcome_id BIGINT UNSIGNED NULL,
    framework_node_id BIGINT UNSIGNED NULL,
    bloom_level_id SMALLINT UNSIGNED NULL,
    course_outcome_key BIGINT UNSIGNED GENERATED ALWAYS AS
        (COALESCE(course_outcome_id, 0)) STORED,
    framework_node_key BIGINT UNSIGNED GENERATED ALWAYS AS
        (COALESCE(framework_node_id, 0)) STORED,
    bloom_level_key SMALLINT UNSIGNED GENERATED ALWAYS AS
        (COALESCE(bloom_level_id, 0)) STORED,
    CONSTRAINT uq_lp_rubric_alignment UNIQUE (
        rubric_criterion_id, course_outcome_key,
        framework_node_key, bloom_level_key
    ),
    CONSTRAINT chk_lp_rubric_alignment CHECK (
        course_outcome_id IS NOT NULL OR framework_node_id IS NOT NULL
        OR bloom_level_id IS NOT NULL
    ),
    CONSTRAINT fk_lp_alignment_criterion FOREIGN KEY (rubric_criterion_id)
        REFERENCES rubric_criterion(rubric_criterion_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_alignment_co FOREIGN KEY (course_outcome_id)
        REFERENCES course_outcome(course_outcome_id),
    CONSTRAINT fk_lp_alignment_framework FOREIGN KEY (framework_node_id)
        REFERENCES curriculum_framework_node(framework_node_id),
    CONSTRAINT fk_lp_alignment_bloom FOREIGN KEY (bloom_level_id)
        REFERENCES bloom_level(bloom_level_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-7. REVIEW BANKS AND QUESTION PAPERS
-- =============================================================

CREATE TABLE question_paper (
    question_paper_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lesson_plan_id BIGINT UNSIGNED NOT NULL,
    lesson_plan_assessment_id BIGINT UNSIGNED NULL,
    paper_type ENUM('REVIEW_BANK','MODEL_PAPER','ACTUAL_PAPER')
        NOT NULL DEFAULT 'MODEL_PAPER',
    paper_title VARCHAR(200) NOT NULL,
    version_no DECIMAL(6,2) NOT NULL DEFAULT 1.00,
    duration_minutes SMALLINT UNSIGNED NULL,
    maximum_marks DECIMAL(7,2) NULL,
    instructions TEXT NULL,
    paper_status ENUM('DRAFT','SUBMITTED','APPROVED','PUBLISHED','ARCHIVED')
        NOT NULL DEFAULT 'DRAFT',
    file_object_id BIGINT UNSIGNED NULL,
    created_by_user_id BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assessment_key BIGINT UNSIGNED GENERATED ALWAYS AS
        (COALESCE(lesson_plan_assessment_id, 0)) STORED,
    CONSTRAINT uq_lp_question_paper_version UNIQUE
        (lesson_plan_id, paper_type, assessment_key, version_no),
    CONSTRAINT uq_lp_question_paper_file UNIQUE (file_object_id),
    CONSTRAINT chk_lp_question_paper_values CHECK (
        version_no > 0
        AND (duration_minutes IS NULL OR duration_minutes > 0)
        AND (maximum_marks IS NULL OR maximum_marks > 0)
    ),
    CONSTRAINT chk_lp_question_paper_assessment CHECK
        (paper_type='REVIEW_BANK' OR lesson_plan_assessment_id IS NOT NULL),
    CONSTRAINT chk_lp_question_paper_header CHECK (
        paper_type='REVIEW_BANK'
        OR (duration_minutes IS NOT NULL AND maximum_marks IS NOT NULL)
    ),
    CONSTRAINT fk_lp_question_paper_plan FOREIGN KEY (lesson_plan_id)
        REFERENCES lesson_plan(lesson_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_lp_question_paper_assessment
        FOREIGN KEY (lesson_plan_assessment_id)
        REFERENCES lesson_plan_assessment(lesson_plan_assessment_id),
    CONSTRAINT fk_lp_question_paper_file FOREIGN KEY (file_object_id)
        REFERENCES file_object(file_object_id),
    CONSTRAINT fk_lp_question_paper_creator FOREIGN KEY (created_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE question_item (
    question_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    question_paper_id BIGINT UNSIGNED NOT NULL,
    parent_question_item_id BIGINT UNSIGNED NULL,
    question_label VARCHAR(20) NOT NULL,
    question_text TEXT NOT NULL,
    marks DECIMAL(7,2) NOT NULL,
    syllabus_unit_id BIGINT UNSIGNED NULL,
    syllabus_chapter_id BIGINT UNSIGNED NULL,
    topic_learning_outcome_id BIGINT UNSIGNED NULL,
    course_outcome_id BIGINT UNSIGNED NOT NULL,
    bloom_level_id SMALLINT UNSIGNED NOT NULL,
    po_pso_node_id BIGINT UNSIGNED NULL,
    pi_node_id BIGINT UNSIGNED NULL,
    display_order SMALLINT UNSIGNED NOT NULL,
    CONSTRAINT uq_lp_question_label UNIQUE
        (question_paper_id, question_label),
    CONSTRAINT uq_lp_question_order UNIQUE
        (question_paper_id, display_order),
    CONSTRAINT chk_lp_question_values CHECK
        (marks > 0 AND display_order > 0),
    CONSTRAINT fk_lp_question_paper FOREIGN KEY (question_paper_id)
        REFERENCES question_paper(question_paper_id) ON DELETE CASCADE,
    CONSTRAINT uq_question_id_paper UNIQUE (question_item_id, question_paper_id),
    CONSTRAINT fk_lp_question_parent FOREIGN KEY (parent_question_item_id, question_paper_id)
        REFERENCES question_item(question_item_id, question_paper_id),
    CONSTRAINT fk_lp_question_unit FOREIGN KEY (syllabus_unit_id)
        REFERENCES syllabus_unit(syllabus_unit_id),
    CONSTRAINT fk_lp_question_chapter FOREIGN KEY (syllabus_chapter_id)
        REFERENCES syllabus_chapter(syllabus_chapter_id),
    CONSTRAINT fk_lp_question_tlo FOREIGN KEY (topic_learning_outcome_id)
        REFERENCES topic_learning_outcome(topic_learning_outcome_id),
    CONSTRAINT fk_lp_question_co FOREIGN KEY (course_outcome_id)
        REFERENCES course_outcome(course_outcome_id),
    CONSTRAINT fk_lp_question_bloom FOREIGN KEY (bloom_level_id)
        REFERENCES bloom_level(bloom_level_id),
    CONSTRAINT fk_lp_question_po_pso FOREIGN KEY (po_pso_node_id)
        REFERENCES curriculum_framework_node(framework_node_id),
    CONSTRAINT fk_lp_question_pi FOREIGN KEY (pi_node_id)
        REFERENCES curriculum_framework_node(framework_node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- LP-8. LINK PLANNED TEACHING TO ACTUAL CLASS DELIVERY
-- =============================================================

ALTER TABLE class_session
    ADD COLUMN lesson_plan_session_id BIGINT UNSIGNED NULL
        AFTER timetable_session_id,
    ADD INDEX idx_lp_class_session_plan_session (lesson_plan_session_id),
    ADD CONSTRAINT fk_lp_class_session_plan_session
        FOREIGN KEY (lesson_plan_session_id)
        REFERENCES lesson_plan_session(lesson_plan_session_id);

-- =============================================================
-- LP-9. REFERENCE DATA
-- =============================================================

INSERT INTO bloom_level
    (level_no, level_code, level_name, description)
VALUES
    (1, 'L1', 'Remember',
     'Recall facts, terms, basic concepts and answers.'),
    (2, 'L2', 'Understand',
     'Explain ideas or concepts.'),
    (3, 'L3', 'Apply',
     'Use information in a new situation.'),
    (4, 'L4', 'Analyze',
     'Draw connections among ideas.'),
    (5, 'L5', 'Evaluate',
     'Justify a decision or course of action.'),
    (6, 'L6', 'Create',
     'Produce new or original work.');

-- =============================================================
-- LP-10. RBAC REGISTRATION
-- =============================================================

INSERT IGNORE INTO access_action
    (action_code, action_name, description)
VALUES
    ('SUBMIT','Submit','Submit a draft record for academic review'),
    ('REVIEW','Review','Review an academic workflow item'),
    ('RETURN','Return','Return a workflow item for correction'),
    ('ARCHIVE','Archive','Archive a superseded or retired record');

INSERT IGNORE INTO access_module
    (module_code, module_name, description, display_order)
VALUES
    ('LESSON_PLAN','Lesson Plan Management',
     'Course outcomes, syllabus, chapter plan, learning activities, assessments, rubrics, question papers and approval workflow.',
     180);

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT am.access_module_id, rs.resource_code, rs.resource_name, rs.description
FROM access_module am
CROSS JOIN (
    SELECT 'LESSON_PLAN' resource_code, 'Lesson Plans' resource_name,
           'Create, version, submit, review, approve and publish lesson plans.' description
    UNION ALL SELECT 'COURSE_OUTCOME', 'Course Outcomes',
           'Maintain CO and CO-PO/PSO/PI articulation.'
    UNION ALL SELECT 'SYLLABUS', 'Syllabus and Chapter Plan',
           'Maintain units, chapters, TLOs and planned teaching sessions.'
    UNION ALL SELECT 'LEARNING_ACTIVITY', 'Lab and Self Learning',
           'Maintain lab, self-learning and tool-based activities.'
    UNION ALL SELECT 'ASSESSMENT_BLUEPRINT', 'Assessment Blueprint',
           'Maintain assessment components, chapter coverage and CO weightage.'
    UNION ALL SELECT 'RUBRIC', 'Rubrics',
           'Maintain rubric criteria, bands and outcome alignment.'
    UNION ALL SELECT 'QUESTION_PAPER', 'Question Papers',
           'Maintain review banks, model papers and actual papers.'
    UNION ALL SELECT 'LESSON_PLAN_REPORT', 'Lesson Plan Reports',
           'View and export lesson plans, syllabus coverage and accreditation reports.'
) rs
WHERE am.module_code='LESSON_PLAN';

INSERT IGNORE INTO permission
    (access_resource_id, access_action_id,
     permission_code, permission_name, is_sensitive)
SELECT
    ar.access_resource_id,
    aa.access_action_id,
    CONCAT('LESSON_PLAN.', ar.resource_code, '.', aa.action_code),
    CONCAT(aa.action_name, ' ', ar.resource_name),
    CASE
        WHEN aa.action_code IN ('DELETE','APPROVE','PUBLISH','CONFIGURE')
        THEN TRUE ELSE FALSE
    END
FROM access_resource ar
JOIN access_module am
  ON am.access_module_id=ar.access_module_id
 AND am.module_code='LESSON_PLAN'
CROSS JOIN access_action aa
WHERE aa.action_code IN (
    'CREATE','READ','UPDATE','DELETE','SUBMIT','REVIEW','RETURN',
    'APPROVE','PUBLISH','ARCHIVE','EXPORT','CONFIGURE'
);

-- Faculty and course coordinators prepare plans for assigned offerings.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code IN ('FACULTY','LAB_INSTRUCTOR','COURSE_COORDINATOR')
  AND am.module_code='LESSON_PLAN'
  AND aa.action_code IN ('CREATE','READ','UPDATE','SUBMIT','EXPORT');

-- Academic leadership reviews, returns, approves and publishes plans.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code IN
      ('PROGRAMME_COORDINATOR','HEAD_DEPARTMENT','DEAN_ACADEMICS')
  AND am.module_code='LESSON_PLAN'
  AND aa.action_code IN (
      'CREATE','READ','UPDATE','SUBMIT','REVIEW','RETURN',
      'APPROVE','PUBLISH','ARCHIVE','EXPORT'
  );

-- Auditors receive reporting access; application scope still applies.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='INTERNAL_AUDITOR'
  AND am.module_code='LESSON_PLAN'
  AND aa.action_code IN ('READ','EXPORT');

-- Super administrators receive every lesson-plan permission.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
WHERE r.role_code='SUPER_ADMIN'
  AND p.permission_code LIKE 'LESSON_PLAN.%';

-- =============================================================
-- LP-11. REPORTING VIEWS
-- =============================================================

CREATE OR REPLACE VIEW v_lesson_plan_summary AS
SELECT
    lp.lesson_plan_id,
    lp.version_no,
    lp.status,
    co.course_offering_id,
    co.offering_code,
    cc.course_id,
    cc.course_code,
    cc.course_title,
    p.programme_id,
    p.programme_code,
    p.programme_name,
    sem.semester_number,
    at.academic_term_id,
    at.term_code,
    at.term_name,
    ay.academic_year_id,
    ay.year_code AS academic_year,
    lp.total_contact_hours,
    lp.theory_hours,
    lp.practical_hours,
    lp.tw_sl_hours,
    (SELECT COUNT(*) FROM course_outcome cox
      WHERE cox.lesson_plan_id=lp.lesson_plan_id) AS outcome_count,
    (SELECT COUNT(*)
       FROM syllabus_chapter scx
       JOIN syllabus_unit sux
         ON sux.syllabus_unit_id=scx.syllabus_unit_id
      WHERE sux.lesson_plan_id=lp.lesson_plan_id) AS chapter_count,
    lp.created_at,
    lp.submitted_at,
    lp.approved_at,
    lp.published_at
FROM lesson_plan lp
JOIN course_offering co
  ON co.course_offering_id=lp.course_offering_id
JOIN course_catalog cc
  ON cc.course_id=co.course_id
JOIN programme_term_offering pto
  ON pto.programme_term_offering_id=co.programme_term_offering_id
JOIN programme p
  ON p.programme_id=pto.programme_id
JOIN semester sem
  ON sem.semester_id=pto.semester_id
JOIN academic_term at
  ON at.academic_term_id=pto.academic_term_id
JOIN academic_year ay
  ON ay.academic_year_id=at.academic_year_id;

CREATE OR REPLACE VIEW v_lesson_plan_syllabus_coverage AS
SELECT
    lp.lesson_plan_id,
    lp.course_offering_id,
    su.unit_no,
    sc.chapter_no,
    sc.chapter_title,
    lps.lesson_plan_session_id,
    lps.session_no AS planned_session_no,
    lps.topic_description AS planned_topic,
    lps.planned_hours,
    cs.class_session_id,
    cs.session_date,
    cs.topic_covered,
    cs.session_status,
    CASE
        WHEN cs.class_session_id IS NULL THEN 'NOT_DELIVERED'
        WHEN cs.session_status='CONDUCTED' THEN 'DELIVERED'
        ELSE cs.session_status
    END AS coverage_status
FROM lesson_plan lp
JOIN syllabus_unit su
  ON su.lesson_plan_id=lp.lesson_plan_id
JOIN syllabus_chapter sc
  ON sc.syllabus_unit_id=su.syllabus_unit_id
JOIN lesson_plan_session lps
  ON lps.syllabus_chapter_id=sc.syllabus_chapter_id
LEFT JOIN class_session cs
  ON cs.lesson_plan_session_id=lps.lesson_plan_session_id;

-- =============================================================
-- LP-12. PERFORMANCE INDEXES
-- =============================================================

CREATE INDEX idx_lp_offering_status
    ON lesson_plan(course_offering_id, status, version_no);
CREATE INDEX idx_lp_faculty_employee
    ON lesson_plan_faculty(employee_id, role_code, action_status);
CREATE INDEX idx_lp_framework_parent
    ON curriculum_framework_node(parent_node_id);
CREATE INDEX idx_lp_outcome_plan
    ON course_outcome(lesson_plan_id, display_order);
CREATE INDEX idx_lp_chapter_unit
    ON syllabus_chapter(syllabus_unit_id, display_order);
CREATE INDEX idx_lp_tlo_chapter
    ON topic_learning_outcome(syllabus_chapter_id, display_order);
CREATE INDEX idx_lp_session_chapter
    ON lesson_plan_session(syllabus_chapter_id, session_no);
CREATE INDEX idx_lp_activity_plan_type
    ON lesson_plan_learning_activity(lesson_plan_id, activity_type);
CREATE INDEX idx_lp_assessment_plan
    ON lesson_plan_assessment(lesson_plan_id, display_order);
CREATE INDEX idx_lp_question_paper_plan
    ON question_paper(lesson_plan_id, paper_type, paper_status);
CREATE INDEX idx_lp_question_item_paper
    ON question_item(question_paper_id, display_order);

-- =============================================================
-- LP-13. REQUIRED SERVICE-LAYER INTEGRITY RULES
-- =============================================================
-- 1. COs, chapters, TLOs, assessments, rubrics and questions referenced
--    together must belong to the same lesson_plan_id.
-- 2. A lesson_plan curriculum context is obtained through:
--    lesson_plan -> course_offering -> programme_term_offering
--    -> curriculum_scheme/programme/semester/academic_term.
-- 3. curriculum_framework_node.curriculum_scheme_id must match the scheme
--    of the lesson plan's course offering.
-- 4. co_outcome_mapping targets must have node_type PO or PSO.
-- 5. course_specific_pi.pi_node_id and question_item.pi_node_id must have
--    node_type PI.
-- 6. lesson_plan_assessment.assessment_component_id must belong to the same
--    course_offering as its lesson_plan.
-- 7. Sum of chapter planned_theory_hours must equal lesson_plan.theory_hours.
-- 8. Lab/self-learning activity hours must reconcile with practical_hours
--    and tw_sl_hours.
-- 9. Assessment weightage totals must reconcile with ISA/ESA totals.
-- 10. Rubric criteria and question-item marks must equal header totals;
--     rubric bands must not overlap or exceed criterion.max_marks.
-- 11. State transitions must follow:
--     DRAFT -> SUBMITTED -> UNDER_REVIEW -> RETURNED/APPROVED
--     -> PUBLISHED -> ARCHIVED.
-- 12. Only APPROVED plans may be PUBLISHED. Published plans are immutable;
--     revisions create a new version_no.
-- 13. Each submission/review/approval/publish/archive operation must append
--     an activity_audit record with before_values and after_values.
-- 14. RBAC scope must limit faculty to assigned course offerings and academic
--     leaders to their institution/campus/department/programme scope.
-- 15. Uploaded question-paper documents must use file_object validation,
--     private storage, MIME checks and malware scanning.


-- =============================================================
-- END OF SIMS VERSION 6.3 LESSON PLAN INTEGRATION
-- =============================================================

-- =============================================================
-- 42. PLUGIN-READY MODULAR MONOLITH PLATFORM
-- =============================================================
-- =============================================================
-- MM-1. MODULE CATALOGUE AND INDEPENDENT VERSIONING
-- =============================================================

CREATE TABLE system_module (
    system_module_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    module_code VARCHAR(50) NOT NULL,
    module_name VARCHAR(120) NOT NULL,
    module_category ENUM('PLATFORM','CORE','FEATURE','INTEGRATION') NOT NULL,
    description VARCHAR(1000) NULL,
    django_app_path VARCHAR(255) NOT NULL,
    api_prefix VARCHAR(150) NULL,
    frontend_entrypoint VARCHAR(255) NULL,
    access_module_id SMALLINT UNSIGNED NULL,
    install_order SMALLINT UNSIGNED NOT NULL DEFAULT 100,
    is_core BOOLEAN NOT NULL DEFAULT FALSE,
    supports_institution_activation BOOLEAN NOT NULL DEFAULT TRUE,
    lifecycle_status ENUM('PLANNED','ACTIVE','DEPRECATED','RETIRED')
        NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_system_module_code UNIQUE (module_code),
    CONSTRAINT uq_system_module_django_app UNIQUE (django_app_path),
    CONSTRAINT chk_system_module_code CHECK
        (module_code REGEXP '^[A-Z][A-Z0-9_]{1,49}$'),
    CONSTRAINT chk_system_module_install_order CHECK (install_order > 0),
    CONSTRAINT fk_system_module_access_module FOREIGN KEY (access_module_id)
        REFERENCES access_module(access_module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE system_module_version (
    system_module_version_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    semantic_version VARCHAR(30) NOT NULL,
    migration_label VARCHAR(190) NOT NULL,
    minimum_platform_version VARCHAR(30) NULL,
    manifest_json JSON NOT NULL,
    schema_checksum_sha256 CHAR(64) NULL,
    release_status ENUM('DRAFT','RELEASED','WITHDRAWN')
        NOT NULL DEFAULT 'DRAFT',
    released_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_version_owner UNIQUE (system_module_version_id, system_module_id),
    CONSTRAINT uq_system_module_version UNIQUE
        (system_module_id, semantic_version),
    CONSTRAINT uq_system_module_migration UNIQUE
        (system_module_id, migration_label),
    CONSTRAINT chk_system_module_semver CHECK
        (semantic_version REGEXP '^[0-9]+\\.[0-9]+\\.[0-9]+([+-][0-9A-Za-z.-]+)?$'),
    CONSTRAINT chk_system_module_checksum CHECK
        (schema_checksum_sha256 IS NULL
         OR schema_checksum_sha256 REGEXP '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT fk_system_module_version_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE system_module_dependency (
    system_module_dependency_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_version_id BIGINT UNSIGNED NOT NULL,
    required_system_module_id SMALLINT UNSIGNED NOT NULL,
    dependency_type ENUM('REQUIRED','OPTIONAL','INTEGRATION') NOT NULL,
    version_constraint VARCHAR(100) NULL,
    is_runtime_dependency BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(500) NULL,
    CONSTRAINT uq_system_module_dependency UNIQUE
        (system_module_version_id, required_system_module_id, dependency_type),
    CONSTRAINT fk_system_module_dependency_version
        FOREIGN KEY (system_module_version_id)
        REFERENCES system_module_version(system_module_version_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_system_module_dependency_required
        FOREIGN KEY (required_system_module_id)
        REFERENCES system_module(system_module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One installation row per module in this deployable modular monolith.
CREATE TABLE module_installation (
    module_installation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    installed_version_id BIGINT UNSIGNED NOT NULL,
    installation_status ENUM(
        'INSTALLING','ACTIVE','DISABLED','UPGRADING','FAILED','UNINSTALLING'
    ) NOT NULL DEFAULT 'INSTALLING',
    installed_at TIMESTAMP NULL,
    installed_by_user_id BIGINT UNSIGNED NULL,
    last_health_check_at TIMESTAMP NULL,
    health_status ENUM('UNKNOWN','HEALTHY','DEGRADED','UNHEALTHY')
        NOT NULL DEFAULT 'UNKNOWN',
    last_error TEXT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_installation_module UNIQUE (system_module_id),
    CONSTRAINT fk_module_installation_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_module_installation_version FOREIGN KEY (installed_version_id, system_module_id)
        REFERENCES system_module_version(system_module_version_id, system_module_id),
    CONSTRAINT fk_module_installation_user FOREIGN KEY (installed_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- MM-2. CLIENT ACTIVATION, FEATURES AND TYPED CONFIGURATION
-- =============================================================

-- institution is the client/tenant boundary in the current SIMS hierarchy.
CREATE TABLE institution_module (
    institution_module_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    module_installation_id BIGINT UNSIGNED NOT NULL,
    activation_status ENUM('PENDING','ACTIVE','SUSPENDED','DISABLED')
        NOT NULL DEFAULT 'PENDING',
    enabled_from DATETIME NULL,
    enabled_until DATETIME NULL,
    enabled_by_user_id BIGINT UNSIGNED NULL,
    disabled_by_user_id BIGINT UNSIGNED NULL,
    disabled_reason VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_institution_module UNIQUE
        (institution_id, module_installation_id),
    CONSTRAINT chk_institution_module_dates CHECK
        (enabled_until IS NULL OR enabled_from IS NULL
         OR enabled_until > enabled_from),
    CONSTRAINT fk_institution_module_institution FOREIGN KEY (institution_id)
        REFERENCES institution(institution_id),
    CONSTRAINT fk_institution_module_installation
        FOREIGN KEY (module_installation_id)
        REFERENCES module_installation(module_installation_id),
    CONSTRAINT fk_institution_module_enabled_by FOREIGN KEY (enabled_by_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_institution_module_disabled_by FOREIGN KEY (disabled_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE module_feature (
    module_feature_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    feature_code VARCHAR(80) NOT NULL,
    feature_name VARCHAR(150) NOT NULL,
    description VARCHAR(500) NULL,
    default_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    is_configurable BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 100,
    CONSTRAINT uq_module_feature_code UNIQUE
        (system_module_id, feature_code),
    CONSTRAINT chk_module_feature_code CHECK
        (feature_code REGEXP '^[A-Z][A-Z0-9_]{1,79}$'),
    CONSTRAINT fk_module_feature_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE institution_module_feature (
    institution_module_feature_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_module_id BIGINT UNSIGNED NOT NULL,
    module_feature_id BIGINT UNSIGNED NOT NULL,
    is_enabled BOOLEAN NOT NULL,
    configuration_json JSON NULL,
    changed_by_user_id BIGINT UNSIGNED NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_institution_module_feature UNIQUE
        (institution_module_id, module_feature_id),
    CONSTRAINT fk_institution_module_feature_activation
        FOREIGN KEY (institution_module_id)
        REFERENCES institution_module(institution_module_id) ON DELETE CASCADE,
    CONSTRAINT fk_institution_module_feature_definition
        FOREIGN KEY (module_feature_id)
        REFERENCES module_feature(module_feature_id),
    CONSTRAINT fk_institution_module_feature_user FOREIGN KEY (changed_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE module_setting_definition (
    module_setting_definition_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    setting_key VARCHAR(120) NOT NULL,
    setting_name VARCHAR(180) NOT NULL,
    description VARCHAR(500) NULL,
    data_type ENUM('STRING','INTEGER','DECIMAL','BOOLEAN','DATE','JSON','SECRET')
        NOT NULL,
    default_value_json JSON NULL,
    validation_schema_json JSON NULL,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    client_overridable BOOLEAN NOT NULL DEFAULT TRUE,
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 100,
    CONSTRAINT uq_module_setting_key UNIQUE (system_module_id, setting_key),
    CONSTRAINT chk_module_setting_key CHECK
        (setting_key REGEXP '^[a-z][a-z0-9_.-]{1,119}$'),
    CONSTRAINT chk_module_setting_secret CHECK
        ((data_type='SECRET' AND is_secret=TRUE)
         OR (data_type<>'SECRET' AND is_secret=FALSE)),
    CONSTRAINT fk_module_setting_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE institution_module_setting (
    institution_module_setting_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_module_id BIGINT UNSIGNED NOT NULL,
    module_setting_definition_id BIGINT UNSIGNED NOT NULL,
    value_json JSON NULL,
    value_ciphertext VARBINARY(4096) NULL,
    encryption_key_version VARCHAR(50) NULL,
    changed_by_user_id BIGINT UNSIGNED NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_institution_module_setting UNIQUE
        (institution_module_id, module_setting_definition_id),
    CONSTRAINT chk_institution_module_setting_value CHECK (
        (value_json IS NOT NULL AND value_ciphertext IS NULL
         AND encryption_key_version IS NULL)
        OR
        (value_json IS NULL AND value_ciphertext IS NOT NULL
         AND encryption_key_version IS NOT NULL)
    ),
    CONSTRAINT fk_institution_module_setting_activation
        FOREIGN KEY (institution_module_id)
        REFERENCES institution_module(institution_module_id) ON DELETE CASCADE,
    CONSTRAINT fk_institution_module_setting_definition
        FOREIGN KEY (module_setting_definition_id)
        REFERENCES module_setting_definition(module_setting_definition_id),
    CONSTRAINT fk_institution_module_setting_user FOREIGN KEY (changed_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- MM-3. OWNERSHIP AND VERSIONED MODULE CONTRACTS
-- =============================================================

CREATE TABLE module_entity (
    module_entity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    entity_name VARCHAR(128) NOT NULL,
    entity_type ENUM('TABLE','VIEW','API','EVENT','JOB') NOT NULL,
    ownership_type ENUM('OWNED','SHARED','BRIDGE','READ_MODEL') NOT NULL,
    data_scope ENUM(
        'GLOBAL','UNIVERSITY','INSTITUTION','CAMPUS',
        'DEPARTMENT','PROGRAMME','SELF'
    ) NOT NULL DEFAULT 'GLOBAL',
    write_policy ENUM('OWNER_ONLY','SHARED_SERVICE','READ_ONLY')
        NOT NULL DEFAULT 'OWNER_ONLY',
    public_contract_name VARCHAR(150) NULL,
    description VARCHAR(500) NULL,
    CONSTRAINT uq_module_entity UNIQUE (entity_type, entity_name),
    CONSTRAINT fk_module_entity_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE module_contract (
    module_contract_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_version_id BIGINT UNSIGNED NOT NULL,
    contract_type ENUM('REST_API','DOMAIN_EVENT','SERVICE_INTERFACE','WEBHOOK')
        NOT NULL,
    contract_name VARCHAR(150) NOT NULL,
    contract_version VARCHAR(30) NOT NULL,
    schema_json JSON NOT NULL,
    checksum_sha256 CHAR(64) NULL,
    compatibility_policy ENUM('BACKWARD','FORWARD','FULL','NONE')
        NOT NULL DEFAULT 'BACKWARD',
    lifecycle_status ENUM('DRAFT','ACTIVE','DEPRECATED','RETIRED')
        NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_contract UNIQUE
        (system_module_version_id, contract_type, contract_name, contract_version),
    CONSTRAINT chk_module_contract_checksum CHECK
        (checksum_sha256 IS NULL
         OR checksum_sha256 REGEXP '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT fk_module_contract_version
        FOREIGN KEY (system_module_version_id)
        REFERENCES system_module_version(system_module_version_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- MM-4. TRANSACTIONAL OUTBOX, SUBSCRIPTIONS AND IDEMPOTENT INBOX
-- =============================================================

CREATE TABLE outbox_event (
    outbox_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id CHAR(36) NOT NULL,
    producer_system_module_id SMALLINT UNSIGNED NOT NULL,
    institution_id SMALLINT UNSIGNED NULL,
    event_type VARCHAR(150) NOT NULL,
    event_version VARCHAR(30) NOT NULL DEFAULT '1.0.0',
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    headers_json JSON NULL,
    event_status ENUM(
        'PENDING','PROCESSING','PUBLISHED','FAILED','DEAD_LETTER'
    ) NOT NULL DEFAULT 'PENDING',
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    available_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    published_at DATETIME(6) NULL,
    attempt_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    locked_by VARCHAR(120) NULL,
    locked_at DATETIME(6) NULL,
    last_error TEXT NULL,
    CONSTRAINT uq_outbox_event_uuid UNIQUE (event_id),
    CONSTRAINT chk_outbox_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT fk_outbox_module FOREIGN KEY (producer_system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_outbox_institution FOREIGN KEY (institution_id)
        REFERENCES institution(institution_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE event_subscription (
    event_subscription_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    subscriber_system_module_id SMALLINT UNSIGNED NOT NULL,
    producer_system_module_id SMALLINT UNSIGNED NULL,
    event_type_pattern VARCHAR(150) NOT NULL,
    handler_name VARCHAR(255) NOT NULL,
    subscription_version VARCHAR(30) NOT NULL DEFAULT '1.0.0',
    delivery_mode ENUM('SYNCHRONOUS','ASYNCHRONOUS')
        NOT NULL DEFAULT 'ASYNCHRONOUS',
    maximum_attempts SMALLINT UNSIGNED NOT NULL DEFAULT 5,
    retry_delay_seconds INT UNSIGNED NOT NULL DEFAULT 60,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_event_subscription UNIQUE
        (subscriber_system_module_id, event_type_pattern, handler_name),
    CONSTRAINT chk_event_subscription_retry CHECK
        (maximum_attempts > 0 AND retry_delay_seconds > 0),
    CONSTRAINT fk_event_subscription_subscriber
        FOREIGN KEY (subscriber_system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_event_subscription_producer
        FOREIGN KEY (producer_system_module_id)
        REFERENCES system_module(system_module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE event_delivery (
    event_delivery_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    outbox_event_id BIGINT UNSIGNED NOT NULL,
    event_subscription_id BIGINT UNSIGNED NOT NULL,
    delivery_status ENUM(
        'PENDING','PROCESSING','DELIVERED','FAILED','DEAD_LETTER'
    ) NOT NULL DEFAULT 'PENDING',
    attempt_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    next_attempt_at DATETIME(6) NULL,
    first_attempt_at DATETIME(6) NULL,
    delivered_at DATETIME(6) NULL,
    last_error TEXT NULL,
    CONSTRAINT uq_event_delivery UNIQUE
        (outbox_event_id, event_subscription_id),
    CONSTRAINT fk_event_delivery_outbox FOREIGN KEY (outbox_event_id)
        REFERENCES outbox_event(outbox_event_id) ON DELETE CASCADE,
    CONSTRAINT fk_event_delivery_subscription FOREIGN KEY (event_subscription_id)
        REFERENCES event_subscription(event_subscription_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Consumers record processed event UUIDs to make handlers idempotent.
CREATE TABLE inbox_event (
    inbox_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    subscriber_system_module_id SMALLINT UNSIGNED NOT NULL,
    source_event_id CHAR(36) NOT NULL,
    event_type VARCHAR(150) NOT NULL,
    event_version VARCHAR(30) NOT NULL,
    processing_status ENUM('RECEIVED','PROCESSING','PROCESSED','FAILED')
        NOT NULL DEFAULT 'RECEIVED',
    received_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    processed_at DATETIME(6) NULL,
    attempt_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    last_error TEXT NULL,
    CONSTRAINT uq_inbox_event_consumer UNIQUE
        (subscriber_system_module_id, source_event_id),
    CONSTRAINT fk_inbox_event_subscriber FOREIGN KEY (subscriber_system_module_id)
        REFERENCES system_module(system_module_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- MM-5. MODULE CATALOGUE SEED
-- =============================================================

INSERT INTO system_module
    (module_code, module_name, module_category, description,
     django_app_path, api_prefix, frontend_entrypoint, access_module_id,
     install_order, is_core, supports_institution_activation)
SELECT
    seed.module_code,
    seed.module_name,
    seed.module_category,
    seed.description,
    seed.django_app_path,
    seed.api_prefix,
    seed.frontend_entrypoint,
    am.access_module_id,
    seed.install_order,
    seed.is_core,
    seed.supports_activation
FROM (
    SELECT 'PLATFORM' module_code, 'SIMS Shared Platform' module_name,
           'PLATFORM' module_category,
           'Module registry, contracts, settings and event infrastructure.' description,
           'sims.platform' django_app_path, '/api/v1/platform/' api_prefix,
           'platform/index' frontend_entrypoint, NULL access_code,
           1 install_order, TRUE is_core, FALSE supports_activation
    UNION ALL SELECT 'IAM','Identity and Access Management','PLATFORM',
           'Authentication, RBAC, permissions and security audit.',
           'sims.platform.identity','/api/v1/iam/','iam/index','IAM',10,TRUE,FALSE
    UNION ALL SELECT 'INSTITUTION','Institution Structure','CORE',
           'University, institution, campus, department and programme hierarchy.',
           'sims.core.institution','/api/v1/institutions/','institution/index','INSTITUTION',20,TRUE,FALSE
    UNION ALL SELECT 'ACADEMIC_CALENDAR','Academic Calendar','CORE',
           'Academic years, terms, semesters and time slots.',
           'sims.core.academic_calendar','/api/v1/academic-calendar/','academic-calendar/index','ACADEMIC_CALENDAR',30,TRUE,FALSE
    UNION ALL SELECT 'CURRICULUM','Curriculum and Course Catalogue','CORE',
           'Course catalogue, curriculum schemes and curriculum courses.',
           'sims.core.curriculum','/api/v1/curriculum/','curriculum/index','CURRICULUM',40,TRUE,FALSE
    UNION ALL SELECT 'STUDENT','Student Core','CORE',
           'Independent student root and student master information.',
           'sims.core.student','/api/v1/students/','student/index','STUDENT',50,TRUE,FALSE
    UNION ALL SELECT 'EMPLOYEE','Employee Core','CORE',
           'Independent employee root, assignments and HR identity.',
           'sims.core.employee','/api/v1/employees/','employee/index','EMPLOYEE',60,TRUE,FALSE
    UNION ALL SELECT 'DOCUMENT','Document and File Services','PLATFORM',
           'Shared file objects, document metadata and certificate services.',
           'sims.platform.documents','/api/v1/documents/','documents/index','DOCUMENT',70,TRUE,FALSE
    UNION ALL SELECT 'AUDIT','Audit and Compliance','PLATFORM',
           'Append-only activity, access and compliance audit services.',
           'sims.platform.audit','/api/v1/audit/','audit/index','AUDIT',80,TRUE,FALSE
    UNION ALL SELECT 'COMMUNICATION','Communication','PLATFORM',
           'Announcements and shared notification delivery.',
           'sims.platform.communication','/api/v1/communication/','communication/index','COMMUNICATION',90,TRUE,FALSE
    UNION ALL SELECT 'ADMISSION','Admissions','FEATURE',
           'Applicant, application and admission enrolment processing.',
           'sims.modules.admission','/api/v1/admissions/','admission/index','ADMISSION',110,FALSE,TRUE
    UNION ALL SELECT 'REGISTRATION','Registration and Enrolment','CORE',
           'Term registration, sections, batches and course registration.',
           'sims.core.registration','/api/v1/registrations/','registration/index','REGISTRATION',120,TRUE,FALSE
    UNION ALL SELECT 'TEACHING','Course Offering and Teaching','CORE',
           'Course offerings, rosters and faculty teaching allocation.',
           'sims.core.teaching','/api/v1/teaching/','teaching/index','TEACHING',130,TRUE,FALSE
    UNION ALL SELECT 'TIMETABLE','Timetable','FEATURE',
           'Rooms, slots and timetable sessions.',
           'sims.modules.timetable','/api/v1/timetable/','timetable/index','TIMETABLE',140,FALSE,TRUE
    UNION ALL SELECT 'ATTENDANCE','Attendance','FEATURE',
           'Class sessions, attendance and correction workflow.',
           'sims.modules.attendance','/api/v1/attendance/','attendance/index','ATTENDANCE',150,FALSE,TRUE
    UNION ALL SELECT 'ASSESSMENT','Continuous Assessment','FEATURE',
           'Assessment components, events and student marks.',
           'sims.modules.assessment','/api/v1/assessments/','assessment/index','ASSESSMENT',160,FALSE,TRUE
    UNION ALL SELECT 'RESULT','Examination and Results','FEATURE',
           'Grade scales, course results and term results.',
           'sims.modules.result','/api/v1/results/','result/index','RESULT',170,FALSE,TRUE
    UNION ALL SELECT 'FEEDBACK','Feedback','FEATURE',
           'Questionnaires, cycles and responses.',
           'sims.modules.feedback','/api/v1/feedback/','feedback/index','FEEDBACK',180,FALSE,TRUE
    UNION ALL SELECT 'MENTORING','Mentoring and Counselling','FEATURE',
           'Mentor allocation and counselling sessions.',
           'sims.modules.mentoring','/api/v1/mentoring/','mentoring/index','MENTORING',190,FALSE,TRUE
    UNION ALL SELECT 'GRIEVANCE','Grievance','FEATURE',
           'Grievance registration, assignment and closure.',
           'sims.modules.grievance','/api/v1/grievances/','grievance/index','GRIEVANCE',200,FALSE,TRUE
    UNION ALL SELECT 'FINANCE','Student Finance and Fees','FEATURE',
           'Fees, payments, concessions, refunds and financial controls.',
           'sims.modules.finance','/api/v1/finance/','finance/index','FINANCE',210,FALSE,TRUE
    UNION ALL SELECT 'STAFF_PROFILE','Staff Profile and Research','FEATURE',
           'Staff academic, research and professional evidence profile.',
           'sims.modules.staff_profile','/api/v1/staff-profile/','staff-profile/index','STAFF_PROFILE',220,FALSE,TRUE
    UNION ALL SELECT 'STUDENT_ACTIVITY','Student Activity and Evidence','FEATURE',
           'Student co-curricular, extracurricular and achievement evidence.',
           'sims.modules.student_activity','/api/v1/student-activities/','student-activity/index','STUDENT',230,FALSE,TRUE
    UNION ALL SELECT 'LESSON_PLAN','Lesson Plan Management','FEATURE',
           'Course outcomes, syllabus, chapter plans, rubrics and question papers.',
           'sims.modules.lesson_plan','/api/v1/lesson-plans/','lesson-plan/index','LESSON_PLAN',240,FALSE,TRUE
    UNION ALL SELECT 'REPORTING','Reports and Analytics','FEATURE',
           'Cross-module reporting and read-model projections.',
           'sims.modules.reporting','/api/v1/reports/','reporting/index','REPORTING',900,FALSE,TRUE
) seed
LEFT JOIN access_module am ON am.module_code=seed.access_code;

INSERT INTO system_module_version
    (system_module_id, semantic_version, migration_label,
     minimum_platform_version, manifest_json, release_status, released_at)
SELECT
    sm.system_module_id,
    '1.0.0',
    'sims_v6_4_baseline',
    CASE WHEN sm.module_code='PLATFORM' THEN NULL ELSE '1.0.0' END,
    JSON_OBJECT(
        'code', sm.module_code,
        'name', sm.module_name,
        'version', '1.0.0',
        'django_app', sm.django_app_path,
        'api_prefix', sm.api_prefix,
        'frontend_entrypoint', sm.frontend_entrypoint,
        'category', sm.module_category
    ),
    'RELEASED',
    CURRENT_TIMESTAMP
FROM system_module sm;

INSERT INTO module_installation
    (system_module_id, installed_version_id, installation_status,
     installed_at, health_status)
SELECT sm.system_module_id, smv.system_module_version_id,
       'ACTIVE', CURRENT_TIMESTAMP, 'UNKNOWN'
FROM system_module sm
JOIN system_module_version smv
  ON smv.system_module_id=sm.system_module_id
 AND smv.semantic_version='1.0.0';

-- Preserve current v6.3 behaviour: modules already present in the schema start
-- enabled for existing institutions. Administrators may disable optional
-- modules afterward without deleting their data.
INSERT INTO institution_module
    (institution_id, module_installation_id, activation_status,
     enabled_from, enabled_by_user_id)
SELECT i.institution_id, mi.module_installation_id,
       'ACTIVE', CURRENT_TIMESTAMP, NULL
FROM institution i
CROSS JOIN module_installation mi
JOIN system_module sm ON sm.system_module_id=mi.system_module_id
WHERE sm.supports_institution_activation=TRUE;

-- Every module except PLATFORM depends on the common platform contract.
INSERT INTO system_module_dependency
    (system_module_version_id, required_system_module_id,
     dependency_type, version_constraint, description)
SELECT smv.system_module_version_id, platform.system_module_id,
       'REQUIRED', '>=1.0.0', 'Common modular-monolith platform services.'
FROM system_module_version smv
JOIN system_module sm ON sm.system_module_id=smv.system_module_id
JOIN system_module platform ON platform.module_code='PLATFORM'
WHERE sm.module_code<>'PLATFORM';

-- Domain-specific dependencies. Optional dependencies never block activation.
INSERT INTO system_module_dependency
    (system_module_version_id, required_system_module_id,
     dependency_type, version_constraint, description)
SELECT consumer_version.system_module_version_id,
       provider.system_module_id,
       dep.dependency_type,
       '>=1.0.0',
       dep.description
FROM (
    SELECT 'ACADEMIC_CALENDAR' consumer, 'INSTITUTION' provider,
           'REQUIRED' dependency_type, 'Academic ownership hierarchy.' description
    UNION ALL SELECT 'CURRICULUM','INSTITUTION','REQUIRED','Programme ownership.'
    UNION ALL SELECT 'CURRICULUM','ACADEMIC_CALENDAR','REQUIRED','Regulation calendar.'
    UNION ALL SELECT 'STUDENT','INSTITUTION','REQUIRED','Institutional student ownership.'
    UNION ALL SELECT 'STUDENT','IAM','REQUIRED','Student identity and access.'
    UNION ALL SELECT 'EMPLOYEE','INSTITUTION','REQUIRED','Institutional employee ownership.'
    UNION ALL SELECT 'EMPLOYEE','IAM','REQUIRED','Employee identity and access.'
    UNION ALL SELECT 'REGISTRATION','STUDENT','REQUIRED','Student registration owner.'
    UNION ALL SELECT 'REGISTRATION','CURRICULUM','REQUIRED','Curriculum registration rules.'
    UNION ALL SELECT 'REGISTRATION','ACADEMIC_CALENDAR','REQUIRED','Term registration.'
    UNION ALL SELECT 'TEACHING','REGISTRATION','REQUIRED','Course rosters.'
    UNION ALL SELECT 'TEACHING','EMPLOYEE','REQUIRED','Faculty assignment.'
    UNION ALL SELECT 'ADMISSION','INSTITUTION','REQUIRED','Institution admission ownership.'
    UNION ALL SELECT 'ADMISSION','CURRICULUM','REQUIRED','Programme admission.'
    UNION ALL SELECT 'TIMETABLE','TEACHING','REQUIRED','Offering schedule.'
    UNION ALL SELECT 'ATTENDANCE','TEACHING','REQUIRED','Class session and roster.'
    UNION ALL SELECT 'ATTENDANCE','STUDENT','REQUIRED','Student attendance.'
    UNION ALL SELECT 'ASSESSMENT','TEACHING','REQUIRED','Offering assessment.'
    UNION ALL SELECT 'ASSESSMENT','STUDENT','REQUIRED','Student marks.'
    UNION ALL SELECT 'RESULT','ASSESSMENT','REQUIRED','Assessment results.'
    UNION ALL SELECT 'RESULT','REGISTRATION','REQUIRED','Registered-course results.'
    UNION ALL SELECT 'FEEDBACK','TEACHING','REQUIRED','Course feedback context.'
    UNION ALL SELECT 'FEEDBACK','STUDENT','REQUIRED','Student feedback.'
    UNION ALL SELECT 'MENTORING','STUDENT','REQUIRED','Student mentees.'
    UNION ALL SELECT 'MENTORING','EMPLOYEE','REQUIRED','Employee mentors.'
    UNION ALL SELECT 'GRIEVANCE','STUDENT','REQUIRED','Student grievance owner.'
    UNION ALL SELECT 'FINANCE','STUDENT','REQUIRED','Student financial account.'
    UNION ALL SELECT 'FINANCE','ADMISSION','INTEGRATION','Admission payments.'
    UNION ALL SELECT 'STAFF_PROFILE','EMPLOYEE','REQUIRED','Employee profile owner.'
    UNION ALL SELECT 'STAFF_PROFILE','DOCUMENT','REQUIRED','Versioned evidence.'
    UNION ALL SELECT 'STUDENT_ACTIVITY','STUDENT','REQUIRED','Student activity owner.'
    UNION ALL SELECT 'STUDENT_ACTIVITY','DOCUMENT','REQUIRED','Versioned evidence.'
    UNION ALL SELECT 'LESSON_PLAN','TEACHING','REQUIRED','Course offering context.'
    UNION ALL SELECT 'LESSON_PLAN','CURRICULUM','REQUIRED','Curriculum outcomes.'
    UNION ALL SELECT 'LESSON_PLAN','ASSESSMENT','REQUIRED','Assessment bridge.'
    UNION ALL SELECT 'LESSON_PLAN','DOCUMENT','OPTIONAL','Question-paper files.'
    UNION ALL SELECT 'LESSON_PLAN','ATTENDANCE','INTEGRATION','Syllabus coverage.'
    UNION ALL SELECT 'REPORTING','AUDIT','REQUIRED','Audited report access.'
) dep
JOIN system_module consumer ON consumer.module_code=dep.consumer
JOIN system_module_version consumer_version
  ON consumer_version.system_module_id=consumer.system_module_id
 AND consumer_version.semantic_version='1.0.0'
JOIN system_module provider ON provider.module_code=dep.provider;

-- =============================================================
-- MM-6. INITIAL FEATURES AND SETTINGS
-- =============================================================

INSERT INTO module_feature
    (system_module_id, feature_code, feature_name,
     description, default_enabled, display_order)
SELECT sm.system_module_id, seed.feature_code, seed.feature_name,
       seed.description, seed.default_enabled, seed.display_order
FROM (
    SELECT 'LESSON_PLAN' module_code, 'OUTCOME_MAPPING' feature_code,
           'CO PO PSO and PI Mapping' feature_name,
           'Accreditation outcome and competency mapping.' description,
           TRUE default_enabled, 10 display_order
    UNION ALL SELECT 'LESSON_PLAN','RUBRICS','Assessment Rubrics',
           'Practical and self-learning rubric design.',TRUE,20
    UNION ALL SELECT 'LESSON_PLAN','QUESTION_PAPERS','Question Papers',
           'Review banks, model papers and actual papers.',TRUE,30
    UNION ALL SELECT 'LESSON_PLAN','DELIVERY_TRACKING','Syllabus Coverage',
           'Link planned lessons to actual class sessions.',TRUE,40
    UNION ALL SELECT 'STUDENT_ACTIVITY','TEAM_ACTIVITIES','Team Activities',
           'Hackathon, sports and group-event team membership.',TRUE,10
    UNION ALL SELECT 'STUDENT_ACTIVITY','EVIDENCE','Activity Evidence',
           'Versioned evidence upload and approval.',TRUE,20
    UNION ALL SELECT 'STAFF_PROFILE','RESEARCH','Research Profile',
           'Publications, proposals and funded research.',TRUE,10
    UNION ALL SELECT 'STAFF_PROFILE','PROFESSIONAL_ACTIVITY','Professional Activity',
           'Training, consultancy, awards and memberships.',TRUE,20
    UNION ALL SELECT 'FINANCE','ONLINE_PAYMENT','Online Payment',
           'Payment-gateway transaction processing.',FALSE,10
    UNION ALL SELECT 'FINANCE','SCHOLARSHIP','Scholarship Management',
           'Scholarship, concession and sponsorship processing.',TRUE,20
) seed
JOIN system_module sm ON sm.module_code=seed.module_code;

INSERT INTO institution_module_feature
    (institution_module_id, module_feature_id, is_enabled)
SELECT im.institution_module_id, mf.module_feature_id, mf.default_enabled
FROM institution_module im
JOIN module_installation mi
  ON mi.module_installation_id=im.module_installation_id
JOIN module_feature mf
  ON mf.system_module_id=mi.system_module_id;

INSERT INTO module_setting_definition
    (system_module_id, setting_key, setting_name, description,
     data_type, default_value_json, validation_schema_json,
     is_required, is_secret, client_overridable, display_order)
SELECT sm.system_module_id, seed.setting_key, seed.setting_name,
       seed.description, seed.data_type, seed.default_value_json,
       seed.validation_schema_json, seed.is_required, seed.is_secret,
       seed.client_overridable, seed.display_order
FROM (
    SELECT 'PLATFORM' module_code, 'events.max_attempts' setting_key,
           'Maximum Event Delivery Attempts' setting_name,
           'Maximum delivery attempts before dead-letter status.' description,
           'INTEGER' data_type, JSON_EXTRACT('5','$') default_value_json,
           JSON_OBJECT('minimum',1,'maximum',100) validation_schema_json,
           TRUE is_required, FALSE is_secret,
           FALSE client_overridable, 10 display_order
    UNION ALL SELECT 'PLATFORM','events.retry_delay_seconds',
           'Event Retry Delay Seconds','Default asynchronous event retry delay.',
           'INTEGER',JSON_EXTRACT('60','$'),
           JSON_OBJECT('minimum',1,'maximum',86400),TRUE,FALSE,FALSE,20
    UNION ALL SELECT 'LESSON_PLAN','workflow.approval_levels',
           'Lesson Plan Approval Levels','Number of configured approval levels.',
           'INTEGER',JSON_EXTRACT('2','$'),
           JSON_OBJECT('minimum',1,'maximum',5),TRUE,FALSE,TRUE,10
    UNION ALL SELECT 'LESSON_PLAN','workflow.auto_publish',
           'Automatically Publish Approved Plans',
           'Publish immediately after final approval.',
           'BOOLEAN',JSON_EXTRACT('false','$'),NULL,FALSE,FALSE,TRUE,20
    UNION ALL SELECT 'STUDENT_ACTIVITY','evidence.required_for_achievement',
           'Evidence Required for Achievement',
           'Require verified evidence before approving achievements.',
           'BOOLEAN',JSON_EXTRACT('true','$'),NULL,FALSE,FALSE,TRUE,10
    UNION ALL SELECT 'FINANCE','payment.gateway_secret',
           'Payment Gateway Secret','Encrypted payment gateway credential.',
           'SECRET',NULL,NULL,FALSE,TRUE,TRUE,10
) seed
JOIN system_module sm ON sm.module_code=seed.module_code;

-- =============================================================
-- MM-7. ENTITY OWNERSHIP CATALOGUE
-- =============================================================
-- Every table/view should be registered by its owning module migration.
-- The baseline mapping below covers the principal aggregate roots and all
-- plugin-platform tables. v_unregistered_database_entity reports omissions.

INSERT INTO module_entity
    (system_module_id, entity_name, entity_type,
     ownership_type, data_scope, write_policy, description)
SELECT sm.system_module_id, seed.entity_name, seed.entity_type,
       seed.ownership_type, seed.data_scope, seed.write_policy,
       seed.description
FROM (
    SELECT 'PLATFORM' module_code, 'system_module' entity_name,
           'TABLE' entity_type, 'OWNED' ownership_type,
           'GLOBAL' data_scope, 'OWNER_ONLY' write_policy,
           'Installed module catalogue.' description
    UNION ALL SELECT 'PLATFORM','system_module_version','TABLE','OWNED','GLOBAL','OWNER_ONLY','Independent module versions.'
    UNION ALL SELECT 'PLATFORM','system_module_dependency','TABLE','OWNED','GLOBAL','OWNER_ONLY','Declared module dependencies.'
    UNION ALL SELECT 'PLATFORM','module_installation','TABLE','OWNED','GLOBAL','OWNER_ONLY','Deployment installation state.'
    UNION ALL SELECT 'PLATFORM','institution_module','TABLE','OWNED','INSTITUTION','SHARED_SERVICE','Client module activation.'
    UNION ALL SELECT 'PLATFORM','module_feature','TABLE','OWNED','GLOBAL','OWNER_ONLY','Module feature catalogue.'
    UNION ALL SELECT 'PLATFORM','institution_module_feature','TABLE','OWNED','INSTITUTION','SHARED_SERVICE','Client feature activation.'
    UNION ALL SELECT 'PLATFORM','module_setting_definition','TABLE','OWNED','GLOBAL','OWNER_ONLY','Typed setting definitions.'
    UNION ALL SELECT 'PLATFORM','institution_module_setting','TABLE','OWNED','INSTITUTION','SHARED_SERVICE','Client setting values.'
    UNION ALL SELECT 'PLATFORM','module_entity','TABLE','OWNED','GLOBAL','OWNER_ONLY','Entity ownership catalogue.'
    UNION ALL SELECT 'PLATFORM','module_contract','TABLE','OWNED','GLOBAL','OWNER_ONLY','Versioned integration contracts.'
    UNION ALL SELECT 'PLATFORM','outbox_event','TABLE','OWNED','INSTITUTION','SHARED_SERVICE','Transactional event outbox.'
    UNION ALL SELECT 'PLATFORM','event_subscription','TABLE','OWNED','GLOBAL','SHARED_SERVICE','Event subscription catalogue.'
    UNION ALL SELECT 'PLATFORM','event_delivery','TABLE','OWNED','INSTITUTION','SHARED_SERVICE','Event delivery attempts.'
    UNION ALL SELECT 'PLATFORM','inbox_event','TABLE','OWNED','INSTITUTION','SHARED_SERVICE','Idempotent event inbox.'
    UNION ALL SELECT 'IAM','user_account','TABLE','OWNED','GLOBAL','OWNER_ONLY','Authentication account aggregate.'
    UNION ALL SELECT 'IAM','role','TABLE','OWNED','GLOBAL','OWNER_ONLY','RBAC role catalogue.'
    UNION ALL SELECT 'IAM','permission','TABLE','OWNED','GLOBAL','OWNER_ONLY','RBAC permission catalogue.'
    UNION ALL SELECT 'INSTITUTION','institution','TABLE','OWNED','GLOBAL','OWNER_ONLY','Client institution aggregate.'
    UNION ALL SELECT 'INSTITUTION','campus','TABLE','OWNED','INSTITUTION','OWNER_ONLY','Campus aggregate.'
    UNION ALL SELECT 'INSTITUTION','department','TABLE','OWNED','CAMPUS','OWNER_ONLY','Department aggregate.'
    UNION ALL SELECT 'INSTITUTION','programme','TABLE','OWNED','DEPARTMENT','OWNER_ONLY','Programme aggregate.'
    UNION ALL SELECT 'ACADEMIC_CALENDAR','academic_term','TABLE','OWNED','INSTITUTION','OWNER_ONLY','Academic term aggregate.'
    UNION ALL SELECT 'CURRICULUM','course_catalog','TABLE','OWNED','DEPARTMENT','OWNER_ONLY','Course catalogue aggregate.'
    UNION ALL SELECT 'CURRICULUM','curriculum_scheme','TABLE','OWNED','PROGRAMME','OWNER_ONLY','Curriculum scheme aggregate.'
    UNION ALL SELECT 'STUDENT','student','TABLE','OWNED','INSTITUTION','OWNER_ONLY','Independent student root.'
    UNION ALL SELECT 'EMPLOYEE','employee','TABLE','OWNED','INSTITUTION','OWNER_ONLY','Independent employee root.'
    UNION ALL SELECT 'REGISTRATION','student_course_registration','TABLE','OWNED','PROGRAMME','OWNER_ONLY','Student course registration aggregate.'
    UNION ALL SELECT 'TEACHING','course_offering','TABLE','OWNED','PROGRAMME','OWNER_ONLY','Course offering aggregate.'
    UNION ALL SELECT 'TIMETABLE','timetable_session','TABLE','OWNED','DEPARTMENT','OWNER_ONLY','Timetable session aggregate.'
    UNION ALL SELECT 'ATTENDANCE','class_session','TABLE','OWNED','DEPARTMENT','OWNER_ONLY','Actual class session aggregate.'
    UNION ALL SELECT 'ATTENDANCE','student_attendance','TABLE','OWNED','SELF','OWNER_ONLY','Student attendance record.'
    UNION ALL SELECT 'ASSESSMENT','assessment_component','TABLE','OWNED','PROGRAMME','OWNER_ONLY','Assessment component aggregate.'
    UNION ALL SELECT 'ASSESSMENT','assessment_event','TABLE','OWNED','PROGRAMME','OWNER_ONLY','Assessment event aggregate.'
    UNION ALL SELECT 'RESULT','student_course_result','TABLE','OWNED','SELF','OWNER_ONLY','Course result aggregate.'
    UNION ALL SELECT 'DOCUMENT','file_object','TABLE','SHARED','INSTITUTION','SHARED_SERVICE','Shared file-storage object.'
    UNION ALL SELECT 'FINANCE','student_financial_account','TABLE','OWNED','SELF','OWNER_ONLY','Student financial account aggregate.'
    UNION ALL SELECT 'STAFF_PROFILE','staff_activity','TABLE','OWNED','INSTITUTION','OWNER_ONLY','Staff activity aggregate.'
    UNION ALL SELECT 'STUDENT_ACTIVITY','student_activity','TABLE','OWNED','SELF','OWNER_ONLY','Student activity aggregate.'
    UNION ALL SELECT 'LESSON_PLAN','lesson_plan','TABLE','OWNED','PROGRAMME','OWNER_ONLY','Versioned lesson plan aggregate.'
    UNION ALL SELECT 'LESSON_PLAN','lesson_plan_assessment','TABLE','BRIDGE','PROGRAMME','OWNER_ONLY','Version-safe bridge to assessment.'
    UNION ALL SELECT 'LESSON_PLAN','lesson_plan_session','TABLE','BRIDGE','PROGRAMME','OWNER_ONLY','Planned teaching session linked to delivery.'
    UNION ALL SELECT 'PLATFORM','v_effective_institution_module','VIEW','READ_MODEL','INSTITUTION','READ_ONLY','Effective client module activation view.'
    UNION ALL SELECT 'PLATFORM','v_module_dependency_health','VIEW','READ_MODEL','GLOBAL','READ_ONLY','Installed dependency health view.'
    UNION ALL SELECT 'PLATFORM','v_unregistered_database_entity','VIEW','READ_MODEL','GLOBAL','READ_ONLY','Unregistered database entity audit view.'
    UNION ALL SELECT 'PLATFORM','v_pending_event_delivery','VIEW','READ_MODEL','INSTITUTION','READ_ONLY','Pending event dispatch view.'
) seed
JOIN system_module sm ON sm.module_code=seed.module_code;

-- Complete v6.3 entity ownership baseline. INSERT IGNORE preserves the
-- richer aggregate-root descriptions registered above.
INSERT IGNORE INTO module_entity
    (system_module_id, entity_name, entity_type,
     ownership_type, data_scope, write_policy)
SELECT sm.system_module_id, seed.entity_name, seed.entity_type,
       seed.ownership_type, seed.data_scope, seed.write_policy
FROM (
    SELECT 'PLATFORM' module_code, 'country' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'state' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'gender' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'blood_group' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'religion' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'social_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'caste' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'sub_caste' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'admission_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'PLATFORM' module_code, 'document_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'university' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'institution' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'campus' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'department' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'programme' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'programme_specialization' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'building' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'INSTITUTION' module_code, 'room' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ACADEMIC_CALENDAR' module_code, 'academic_year' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ACADEMIC_CALENDAR' module_code, 'academic_term' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ACADEMIC_CALENDAR' module_code, 'semester' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ACADEMIC_CALENDAR' module_code, 'time_slot' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'CURRICULUM' module_code, 'course_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'CURRICULUM' module_code, 'course_catalog' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'CURRICULUM' module_code, 'curriculum_scheme' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'CURRICULUM' module_code, 'curriculum_course' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'CURRICULUM' module_code, 'course_prerequisite' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT' module_code, 'student' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT' module_code, 'student_address' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT' module_code, 'student_parent_guardian' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT' module_code, 'student_residence' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT' module_code, 'student_previous_education' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT' module_code, 'student_entrance_exam' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'staff_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'staff_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employment_source' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'external_agency' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'designation' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_address' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_assignment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_competency' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ADMISSION' module_code, 'admission_applicant' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ADMISSION' module_code, 'admission_application' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ADMISSION' module_code, 'student_programme_enrolment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ADMISSION' module_code, 'enrolment_status_history' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'REGISTRATION' module_code, 'programme_term_offering' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'REGISTRATION' module_code, 'class_section' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'REGISTRATION' module_code, 'class_batch' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'REGISTRATION' module_code, 'student_term_registration' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'TEACHING' module_code, 'course_offering' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'TEACHING' module_code, 'course_offering_section' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'REGISTRATION' module_code, 'student_course_registration' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'REGISTRATION' module_code, 'course_offering_section_student' entity_name, 'TABLE' entity_type, 'BRIDGE' ownership_type, 'PROGRAMME' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'TEACHING' module_code, 'faculty_course_assignment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'TIMETABLE' module_code, 'timetable_session' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'DEPARTMENT' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ATTENDANCE' module_code, 'class_session' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ATTENDANCE' module_code, 'attendance_status' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ATTENDANCE' module_code, 'student_attendance' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ATTENDANCE' module_code, 'attendance_correction_request' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ASSESSMENT' module_code, 'assessment_component' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ASSESSMENT' module_code, 'assessment_event' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'ASSESSMENT' module_code, 'student_assessment_mark' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'RESULT' module_code, 'grade_scale' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'RESULT' module_code, 'grade_rule' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'RESULT' module_code, 'student_course_result' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'RESULT' module_code, 'student_term_result' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_question_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_question' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_choice' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_questionnaire' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_questionnaire_item' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_cycle' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_response' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FEEDBACK' module_code, 'feedback_response_item' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'MENTORING' module_code, 'mentor_assignment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'MENTORING' module_code, 'counselling_session' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'GRIEVANCE' module_code, 'grievance_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'GRIEVANCE' module_code, 'grievance' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'GRIEVANCE' module_code, 'grievance_action' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'DOCUMENT' module_code, 'file_object' entity_name, 'TABLE' entity_type, 'SHARED' ownership_type, 'INSTITUTION' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'DOCUMENT' module_code, 'student_document' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'DOCUMENT' module_code, 'certificate_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'DOCUMENT' module_code, 'certificate_request' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'DOCUMENT' module_code, 'student_exit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'COMMUNICATION' module_code, 'announcement_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'COMMUNICATION' module_code, 'announcement' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'COMMUNICATION' module_code, 'announcement_attachment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'user_account' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'student_user_account' entity_name, 'TABLE' entity_type, 'BRIDGE' ownership_type, 'GLOBAL' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'IAM' module_code, 'employee_user_account' entity_name, 'TABLE' entity_type, 'BRIDGE' ownership_type, 'GLOBAL' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'IAM' module_code, 'access_module' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'access_resource' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'access_action' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'permission' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'role' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'role_permission' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'user_role_assignment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'user_permission_override' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'role_delegation' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'password_history' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'login_audit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'GLOBAL' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'AUDIT' module_code, 'activity_audit' entity_name, 'TABLE' entity_type, 'SHARED' ownership_type, 'INSTITUTION' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'qualification_level' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'study_mode' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'education_institution_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'awarding_body_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'education_institution' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'awarding_body' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'previous_organization_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'previous_organization' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_qualification' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_previous_employment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_bank_account' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_pan' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_aadhaar' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_document_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_document' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_document_access_rule' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'employee_sensitive_access_audit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'financial_ledger_account' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_structure' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'late_fee_rule' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'late_fee_slab' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_structure_item' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_financial_account' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_fee_assessment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_fee_assessment_item' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_charge_source' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'concession_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_fee_concession' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'scholarship_scheme' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_scholarship' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_sponsorship' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_assessment_benefit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'installment_plan' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_installment_schedule' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'payment_mode' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'payment_transaction' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'admission_payment' entity_name, 'TABLE' entity_type, 'BRIDGE' ownership_type, 'INSTITUTION' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'payment_allocation' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_receipt' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_adjustment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'refund_request' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_refund' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_fee_penalty' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'service_fee_request' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'student_financial_hold' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'fee_activity_audit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'publication_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'journal_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'indexing_agency' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'metric_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'organization_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'external_organization' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'external_organization_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'organizer' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'publisher' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'funding_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'funding_agency' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'activity_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'participation_level' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'role_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'research_status' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'event_mode' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'evidence_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'verification_status' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'approval_status' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'training_program_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'conference_contribution_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'industry_sector' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'cocurricular_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'extracurricular_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'award_category' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'membership_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'professional_contribution_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'confidentiality_level' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'staff_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'staff_activity_contributor' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'journal' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'journal_publication' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'journal_publication_indexing' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'journal_metric' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'conference_event' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'conference_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'conference_activity_indexing' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'professional_development_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'faculty_internship' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'research_proposal' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'funded_research_project' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'research_project_financial_utilization' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'consultancy_project' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'cocurricular_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'extracurricular_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'staff_award' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'staff_professional_membership' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'staff_professional_contribution' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'research_supervision' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'evidence_document' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'evidence_document_version' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'evidence_tag' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'evidence_document_tag' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'evidence_document_audit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'activity_evidence_requirement' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'INSTITUTION' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity_type' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity_team_member' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity_evidence' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity_evidence_version' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity_evidence_audit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'student_activity_evidence_requirement' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'SELF' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'bloom_level' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'curriculum_framework_node' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'lesson_plan' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'lesson_plan_faculty' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'lesson_plan_resource' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'course_outcome' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'co_outcome_mapping' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'course_specific_pi' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'syllabus_unit' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'syllabus_chapter' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'topic_learning_outcome' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'lesson_plan_session' entity_name, 'TABLE' entity_type, 'BRIDGE' ownership_type, 'PROGRAMME' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'lesson_plan_learning_activity' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'lesson_plan_assessment' entity_name, 'TABLE' entity_type, 'BRIDGE' ownership_type, 'PROGRAMME' data_scope, 'SHARED_SERVICE' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'assessment_blueprint' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'co_assessment_mapping' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'rubric' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'rubric_criterion' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'rubric_band' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'rubric_criterion_alignment' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'question_paper' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'question_item' entity_name, 'TABLE' entity_type, 'OWNED' ownership_type, 'PROGRAMME' data_scope, 'OWNER_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'v_active_user_role' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'GLOBAL' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'v_active_role_permission' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'GLOBAL' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'IAM' module_code, 'v_effective_user_permission' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'GLOBAL' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'EMPLOYEE' module_code, 'v_employee_previous_experience' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'INSTITUTION' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'v_student_fee_balance' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'INSTITUTION' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'FINANCE' module_code, 'v_fee_collection_summary' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'INSTITUTION' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'v_staff_activity_profile' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'INSTITUTION' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'STAFF_PROFILE' module_code, 'v_staff_evidence_search' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'INSTITUTION' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'v_student_activity_profile' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'SELF' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'STUDENT_ACTIVITY' module_code, 'v_student_activity_evidence_search' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'SELF' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'v_lesson_plan_summary' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'PROGRAMME' data_scope, 'READ_ONLY' write_policy
    UNION ALL SELECT 'LESSON_PLAN' module_code, 'v_lesson_plan_syllabus_coverage' entity_name, 'VIEW' entity_type, 'READ_MODEL' ownership_type, 'PROGRAMME' data_scope, 'READ_ONLY' write_policy
) seed
JOIN system_module sm ON sm.module_code=seed.module_code;

-- =============================================================
-- MM-8. VERSIONED CONTRACT SEED
-- =============================================================

INSERT INTO module_contract
    (system_module_version_id, contract_type, contract_name,
     contract_version, schema_json, compatibility_policy)
SELECT smv.system_module_version_id, seed.contract_type,
       seed.contract_name, seed.contract_version,
       seed.schema_json, 'BACKWARD'
FROM (
    SELECT 'LESSON_PLAN' module_code, 'DOMAIN_EVENT' contract_type,
           'lesson_plan.published' contract_name, '1.0.0' contract_version,
           JSON_OBJECT(
               'required', JSON_ARRAY('event_id','lesson_plan_id','course_offering_id','version_no'),
               'properties', JSON_OBJECT(
                   'event_id',JSON_OBJECT('type','string','format','uuid'),
                   'lesson_plan_id',JSON_OBJECT('type','integer'),
                   'course_offering_id',JSON_OBJECT('type','integer'),
                   'version_no',JSON_OBJECT('type','string')
               )
           ) schema_json
    UNION ALL SELECT 'ASSESSMENT','DOMAIN_EVENT','assessment.result_published','1.0.0',
           JSON_OBJECT(
               'required',JSON_ARRAY('event_id','course_offering_id','assessment_event_id'),
               'properties',JSON_OBJECT(
                   'event_id',JSON_OBJECT('type','string','format','uuid'),
                   'course_offering_id',JSON_OBJECT('type','integer'),
                   'assessment_event_id',JSON_OBJECT('type','integer')
               )
           )
    UNION ALL SELECT 'STUDENT_ACTIVITY','DOMAIN_EVENT','student_activity.approved','1.0.0',
           JSON_OBJECT(
               'required',JSON_ARRAY('event_id','student_activity_id','student_id'),
               'properties',JSON_OBJECT(
                   'event_id',JSON_OBJECT('type','string','format','uuid'),
                   'student_activity_id',JSON_OBJECT('type','integer'),
                   'student_id',JSON_OBJECT('type','integer')
               )
           )
) seed
JOIN system_module sm ON sm.module_code=seed.module_code
JOIN system_module_version smv
  ON smv.system_module_id=sm.system_module_id
 AND smv.semantic_version='1.0.0';

INSERT INTO event_subscription
    (subscriber_system_module_id, producer_system_module_id,
     event_type_pattern, handler_name, subscription_version,
     delivery_mode, maximum_attempts, retry_delay_seconds)
SELECT subscriber.system_module_id, producer.system_module_id,
       seed.event_type_pattern, seed.handler_name,
       '1.0.0', 'ASYNCHRONOUS', 5, 60
FROM (
    SELECT 'REPORTING' subscriber_code, 'LESSON_PLAN' producer_code,
           'lesson_plan.published.v1' event_type_pattern,
           'sims.modules.reporting.handlers.lesson_plan_published' handler_name
    UNION ALL SELECT 'REPORTING','ASSESSMENT',
           'assessment.result_published.v1',
           'sims.modules.reporting.handlers.assessment_result_published'
    UNION ALL SELECT 'REPORTING','STUDENT_ACTIVITY',
           'student_activity.approved.v1',
           'sims.modules.reporting.handlers.student_activity_approved'
) seed
JOIN system_module subscriber
  ON subscriber.module_code=seed.subscriber_code
JOIN system_module producer
  ON producer.module_code=seed.producer_code;

-- =============================================================
-- MM-9. RBAC FOR MODULE INSTALLATION AND CLIENT CONFIGURATION
-- =============================================================

INSERT IGNORE INTO access_action
    (action_code, action_name, description)
VALUES
    ('INSTALL','Install','Install a module into the SIMS deployment'),
    ('UPGRADE','Upgrade','Upgrade an installed module version'),
    ('ENABLE','Enable','Enable a module or feature for a client'),
    ('DISABLE','Disable','Disable a module or feature for a client'),
    ('RETRY','Retry','Retry a failed asynchronous operation');

INSERT IGNORE INTO access_resource
    (access_module_id, resource_code, resource_name, description)
SELECT am.access_module_id, seed.resource_code,
       seed.resource_name, seed.description
FROM access_module am
CROSS JOIN (
    SELECT 'MODULE_REGISTRY' resource_code,
           'Module Registry' resource_name,
           'Module catalogue, versions, dependencies and installations.' description
    UNION ALL SELECT 'MODULE_ACTIVATION','Client Module Activation',
           'Institution-level module and feature activation.'
    UNION ALL SELECT 'MODULE_CONFIGURATION','Module Configuration',
           'Typed module configuration and client overrides.'
    UNION ALL SELECT 'INTEGRATION_EVENT','Integration Events',
           'Outbox, inbox, subscription and delivery operations.'
) seed
WHERE am.module_code='IAM';

INSERT IGNORE INTO permission
    (access_resource_id, access_action_id,
     permission_code, permission_name, is_sensitive)
SELECT ar.access_resource_id, aa.access_action_id,
       CONCAT('IAM.',ar.resource_code,'.',aa.action_code),
       CONCAT(aa.action_name,' ',ar.resource_name),
       CASE WHEN aa.action_code IN
            ('DELETE','CONFIGURE','INSTALL','UPGRADE','ENABLE','DISABLE')
            THEN TRUE ELSE FALSE END
FROM access_resource ar
JOIN access_module am
  ON am.access_module_id=ar.access_module_id
 AND am.module_code='IAM'
CROSS JOIN access_action aa
WHERE ar.resource_code IN (
    'MODULE_REGISTRY','MODULE_ACTIVATION',
    'MODULE_CONFIGURATION','INTEGRATION_EVENT'
)
AND aa.action_code IN (
    'CREATE','READ','UPDATE','DELETE','CONFIGURE',
    'INSTALL','UPGRADE','ENABLE','DISABLE','RETRY','EXPORT'
);

INSERT IGNORE INTO role
    (role_code, role_name, role_category, role_level,
     description, is_system_role)
VALUES
    ('INSTITUTION_ADMIN','Institution Administrator','ADMINISTRATIVE',
     'INSTITUTION','Client module activation and configuration administrator.',FALSE);

-- Super administrators manage the full module lifecycle.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
WHERE r.role_code='SUPER_ADMIN'
  AND am.module_code='IAM'
  AND ar.resource_code IN (
      'MODULE_REGISTRY','MODULE_ACTIVATION',
      'MODULE_CONFIGURATION','INTEGRATION_EVENT'
  );

-- System administrators install, upgrade and monitor modules/events.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_module am ON am.access_module_id=ar.access_module_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='SYSTEM_ADMIN'
  AND am.module_code='IAM'
  AND ar.resource_code IN (
      'MODULE_REGISTRY','MODULE_ACTIVATION',
      'MODULE_CONFIGURATION','INTEGRATION_EVENT'
  )
  AND aa.action_code IN
      ('CREATE','READ','UPDATE','CONFIGURE','INSTALL','UPGRADE','RETRY','EXPORT');

-- Institution administrators activate and configure already-installed modules.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='INSTITUTION_ADMIN'
  AND ar.resource_code IN ('MODULE_ACTIVATION','MODULE_CONFIGURATION')
  AND aa.action_code IN
      ('READ','UPDATE','CONFIGURE','ENABLE','DISABLE');

-- Security administrators have read/export visibility, not installation rights.
INSERT IGNORE INTO role_permission (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM role r
CROSS JOIN permission p
JOIN access_resource ar ON ar.access_resource_id=p.access_resource_id
JOIN access_action aa ON aa.access_action_id=p.access_action_id
WHERE r.role_code='SECURITY_ADMIN'
  AND ar.resource_code IN
      ('MODULE_REGISTRY','MODULE_ACTIVATION','INTEGRATION_EVENT')
  AND aa.action_code IN ('READ','EXPORT');

-- =============================================================
-- MM-10. OPERATIONAL VIEWS
-- =============================================================

CREATE OR REPLACE VIEW v_effective_institution_module AS
SELECT
    i.institution_id,
    i.institution_code,
    sm.system_module_id,
    sm.module_code,
    sm.module_name,
    sm.module_category,
    sm.is_core,
    sm.supports_institution_activation,
    mi.installation_status,
    smv.semantic_version AS installed_version,
    im.institution_module_id,
    im.activation_status,
    im.enabled_from,
    im.enabled_until,
    CASE
        WHEN i.is_active=FALSE OR sm.lifecycle_status<>'ACTIVE' THEN FALSE
        WHEN mi.installation_status<>'ACTIVE' THEN FALSE
        WHEN sm.supports_institution_activation=FALSE THEN TRUE
        WHEN im.activation_status='ACTIVE'
         AND (im.enabled_from IS NULL OR im.enabled_from<=CURRENT_TIMESTAMP)
         AND (im.enabled_until IS NULL OR im.enabled_until>CURRENT_TIMESTAMP)
        THEN TRUE
        ELSE FALSE
    END AS is_effectively_enabled
FROM institution i
CROSS JOIN module_installation mi
JOIN system_module sm
  ON sm.system_module_id=mi.system_module_id
JOIN system_module_version smv
  ON smv.system_module_version_id=mi.installed_version_id
LEFT JOIN institution_module im
  ON im.institution_id=i.institution_id
 AND im.module_installation_id=mi.module_installation_id;

CREATE OR REPLACE VIEW v_module_dependency_health AS
SELECT
    consumer.module_code AS consumer_module,
    consumer_version.semantic_version AS consumer_version,
    dependency.dependency_type,
    dependency.version_constraint,
    provider.module_code AS provider_module,
    provider_version.semantic_version AS installed_provider_version,
    provider_installation.installation_status AS provider_status,
    CASE
        WHEN provider_installation.module_installation_id IS NULL
         AND dependency.dependency_type='REQUIRED' THEN 'MISSING'
        WHEN provider_installation.installation_status<>'ACTIVE'
         AND dependency.dependency_type='REQUIRED' THEN 'INACTIVE'
        WHEN provider_installation.module_installation_id IS NULL THEN 'OPTIONAL_MISSING'
        ELSE 'AVAILABLE'
    END AS dependency_health
FROM system_module_dependency dependency
JOIN system_module_version consumer_version
  ON consumer_version.system_module_version_id=dependency.system_module_version_id
JOIN system_module consumer
  ON consumer.system_module_id=consumer_version.system_module_id
JOIN system_module provider
  ON provider.system_module_id=dependency.required_system_module_id
LEFT JOIN module_installation provider_installation
  ON provider_installation.system_module_id=provider.system_module_id
LEFT JOIN system_module_version provider_version
  ON provider_version.system_module_version_id=provider_installation.installed_version_id;

CREATE OR REPLACE VIEW v_unregistered_database_entity AS
SELECT
    t.TABLE_SCHEMA AS table_schema,
    t.TABLE_NAME AS entity_name,
    t.TABLE_TYPE AS entity_type
FROM information_schema.TABLES t
LEFT JOIN module_entity me
  ON me.entity_name=t.TABLE_NAME
 AND me.entity_type=CASE WHEN t.TABLE_TYPE='VIEW' THEN 'VIEW' ELSE 'TABLE' END
WHERE t.TABLE_SCHEMA=DATABASE()
  AND me.module_entity_id IS NULL;

CREATE OR REPLACE VIEW v_pending_event_delivery AS
SELECT
    oe.outbox_event_id,
    oe.event_id,
    producer.module_code AS producer_module,
    oe.institution_id,
    oe.event_type,
    oe.event_version,
    oe.aggregate_type,
    oe.aggregate_id,
    oe.payload,
    oe.available_at,
    oe.attempt_count
FROM outbox_event oe
JOIN system_module producer
  ON producer.system_module_id=oe.producer_system_module_id
WHERE oe.event_status IN ('PENDING','FAILED')
  AND oe.available_at<=CURRENT_TIMESTAMP(6);

-- =============================================================
-- MM-11. PERFORMANCE INDEXES
-- =============================================================

CREATE INDEX idx_system_module_category_status
    ON system_module(module_category, lifecycle_status, install_order);
CREATE INDEX idx_module_dependency_provider
    ON system_module_dependency(required_system_module_id, dependency_type);
CREATE INDEX idx_module_installation_status
    ON module_installation(installation_status, health_status);
CREATE INDEX idx_institution_module_status
    ON institution_module(institution_id, activation_status, enabled_until);
CREATE INDEX idx_module_entity_owner
    ON module_entity(system_module_id, entity_type, ownership_type);
CREATE INDEX idx_outbox_dispatch
    ON outbox_event(event_status, available_at, outbox_event_id);
CREATE INDEX idx_outbox_aggregate
    ON outbox_event(aggregate_type, aggregate_id, occurred_at);
CREATE INDEX idx_event_delivery_retry
    ON event_delivery(delivery_status, next_attempt_at, event_delivery_id);
CREATE INDEX idx_inbox_processing
    ON inbox_event(processing_status, received_at, inbox_event_id);

-- =============================================================
-- MM-12. REQUIRED APPLICATION AND DEPLOYMENT RULES
-- =============================================================
-- 1. Django discovers modules from signed/static code manifests. Database
--    registry rows describe installed code; they never execute arbitrary code.
-- 2. Validate semantic-version constraints in the module loader before startup,
--    installation, upgrade, activation and enablement.
-- 3. Reject circular REQUIRED dependencies. OPTIONAL and INTEGRATION edges do
--    not participate in startup ordering.
-- 4. Core/platform modules cannot be disabled per institution.
-- 5. An institution module can be ACTIVE only when its installation and all
--    REQUIRED dependencies are ACTIVE.
-- 5a. module_installation.installed_version_id must belong to the same
--     system_module_id as module_installation.system_module_id.
-- 6. A feature/setting must belong to the same system_module as the selected
--    institution_module. Enforce this in the configuration service.
-- 7. Only a module's repository/service layer may write its OWNED tables.
--    SHARED and BRIDGE writes must go through the declared shared service.
-- 8. Each new table, view, API, event and background job must be registered in
--    module_entity by the owning module migration. CI must fail when
--    v_unregistered_database_entity returns unexpected rows.
-- 9. Modules must not import another feature module's ORM models. Integrate via
--    versioned service interfaces, REST contracts, domain events or explicit
--    bridge tables.
-- 10. Write the business transaction and outbox_event in the same transaction.
--     Publish only after commit. Consumers must reserve inbox_event before work.
-- 11. Event handlers must be idempotent. Failed messages use retry limits and
--     dead-letter status; replay requires an audited RETRY permission.
-- 12. Never put secret plaintext in value_json or manifest_json. Encrypt SECRET
--     settings externally and store only value_ciphertext plus key version.
-- 13. Module enablement is not authorization. Every request must additionally
--     pass existing RBAC scope/effective-permission checks.
-- 14. Preserve institution/campus/department/programme ownership, independent
--     student and employee roots, evidence confidentiality, soft deletion and
--     append-only audit rules from SIMS v6.3.
-- 15. Disabling a module hides routes, navigation and jobs but retains data.
--     Uninstall/drop migrations require explicit export and approval.
-- 16. Use Django migrations as the authoritative module migration mechanism;
--     module_installation records the resulting deployed state.
-- 17. Deploy one application and one database at this stage. A module may be
--     extracted later only through its existing contracts and ownership boundary.


-- =============================================================
-- END OF SIMS VERSION 6.4 PLUGIN-READY MODULAR MONOLITH MIGRATION
-- =============================================================

-- ============================================================================
-- SIMS v6.5 - DJANGO AUTHENTICATION + SCOPED AUTHORIZATION MIGRATION
-- Target: MySQL 8.0.16+
-- Prerequisite: SIMS v6.4 plugin-ready modular monolith schema
--
-- Architectural decision:
--   * user_account becomes the project custom Django User table in place.
--   * Django content types, permissions and groups are authoritative.
--   * SIMS adds tenant, organisational, workflow, confidentiality and
--     record-level scope; it does not reimplement password/session security.
--   * Existing custom RBAC tables are preserved as LEGACY_READ_ONLY during
--     cutover so that permissions can be reconciled and rollback remains safe.
--   * Application setting: AUTH_USER_MODEL = 'accounts.User'.
-- ============================================================================


-- --------------------------------------------------------------------------
-- DA-1. ADAPT THE EXISTING USER ROOT TO DJANGO'S CUSTOM USER CONTRACT
-- Existing user_id values and all dependent foreign keys remain unchanged.
-- password_hash is deliberately retained until the application cutover is
-- accepted. Recognised Django hashes are copied; other accounts receive an
-- unusable password and must complete a password reset.
-- --------------------------------------------------------------------------

ALTER TABLE user_account
    MODIFY COLUMN username VARCHAR(150) NOT NULL,
    MODIFY COLUMN password_hash VARCHAR(255) NULL DEFAULT NULL,
    ADD COLUMN password VARCHAR(128) NULL AFTER username,
    ADD COLUMN last_login DATETIME(6) NULL AFTER password,
    ADD COLUMN is_superuser BOOLEAN NOT NULL DEFAULT FALSE AFTER last_login,
    ADD COLUMN first_name VARCHAR(150) NOT NULL DEFAULT '' AFTER is_superuser,
    ADD COLUMN last_name VARCHAR(150) NOT NULL DEFAULT '' AFTER first_name,
    ADD COLUMN is_staff BOOLEAN NOT NULL DEFAULT FALSE AFTER email,
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER is_staff,
    ADD COLUMN date_joined DATETIME(6) NULL AFTER is_active,
    ADD COLUMN user_uuid CHAR(36) NULL AFTER user_id;

UPDATE user_account
SET password = CASE
        WHEN CHAR_LENGTH(password_hash) <= 128
         AND password_hash REGEXP
             '^(pbkdf2_sha256|pbkdf2_sha1|argon2|bcrypt_sha256|bcrypt|scrypt)\\$'
            THEN password_hash
        ELSE CONCAT('!', REPLACE(UUID(), '-', ''))
    END,
    last_login = last_login_at,
    is_active = CASE WHEN account_status = 'ACTIVE' THEN TRUE ELSE FALSE END,
    date_joined = created_at,
    user_uuid = UUID()
WHERE password IS NULL OR user_uuid IS NULL;

ALTER TABLE user_account
    MODIFY COLUMN password VARCHAR(128) NOT NULL,
    MODIFY COLUMN date_joined DATETIME(6) NOT NULL,
    MODIFY COLUMN user_uuid CHAR(36) NOT NULL,
    ADD CONSTRAINT uq_user_account_uuid UNIQUE (user_uuid);

-- --------------------------------------------------------------------------
-- DA-2. DJANGO CONTENT TYPES, PERMISSIONS AND GROUPS
-- Table names match Django's built-in contenttypes/auth applications.
-- The custom User M2M tables use explicit db_table names shown below.
-- --------------------------------------------------------------------------

CREATE TABLE django_content_type (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_label VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    CONSTRAINT uq_django_content_type UNIQUE (app_label, model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE auth_permission (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    content_type_id INT NOT NULL,
    codename VARCHAR(100) NOT NULL,
    CONSTRAINT uq_permission_content_identity UNIQUE (id, content_type_id),
    CONSTRAINT uq_auth_permission UNIQUE (content_type_id, codename),
    CONSTRAINT fk_auth_permission_content_type FOREIGN KEY (content_type_id)
        REFERENCES django_content_type(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE auth_group (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    CONSTRAINT uq_auth_group_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE auth_group_permissions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    permission_id INT NOT NULL,
    CONSTRAINT uq_auth_group_permission UNIQUE (group_id, permission_id),
    CONSTRAINT fk_auth_group_permission_group FOREIGN KEY (group_id)
        REFERENCES auth_group(id) ON DELETE CASCADE,
    CONSTRAINT fk_auth_group_permission_permission FOREIGN KEY (permission_id)
        REFERENCES auth_permission(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_account_groups (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    group_id INT NOT NULL,
    CONSTRAINT uq_user_account_group UNIQUE (user_id, group_id),
    CONSTRAINT fk_user_account_group_user FOREIGN KEY (user_id)
        REFERENCES user_account(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_account_group_group FOREIGN KEY (group_id)
        REFERENCES auth_group(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_account_user_permissions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    permission_id INT NOT NULL,
    CONSTRAINT uq_user_account_permission UNIQUE (user_id, permission_id),
    CONSTRAINT fk_user_account_permission_user FOREIGN KEY (user_id)
        REFERENCES user_account(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_account_permission_permission FOREIGN KEY (permission_id)
        REFERENCES auth_permission(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- DA-3. INSTITUTION MEMBERSHIP AND INSTITUTION-SCOPED GROUP ASSIGNMENT
-- A Django Group defines a role. Assignment to that group is scoped here,
-- instead of placing tenant roles in Django's global user.groups relation.
-- --------------------------------------------------------------------------

CREATE TABLE institution_user_membership (
    institution_user_membership_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    membership_status ENUM(
        'INVITED','ACTIVE','SUSPENDED','EXPIRED','REVOKED'
    ) NOT NULL DEFAULT 'ACTIVE',
    valid_from DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    valid_until DATETIME(6) NULL,
    is_default_institution BOOLEAN NOT NULL DEFAULT FALSE,
    invited_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    default_institution_user_id BIGINT UNSIGNED GENERATED ALWAYS AS
        (CASE WHEN is_default_institution = TRUE THEN user_id ELSE NULL END) STORED,
    CONSTRAINT uq_user_default_institution UNIQUE (default_institution_user_id),
    CONSTRAINT uq_institution_user_membership UNIQUE (institution_id, user_id),
    CONSTRAINT chk_institution_membership_dates CHECK
        (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT fk_institution_membership_institution FOREIGN KEY (institution_id)
        REFERENCES institution(institution_id),
    CONSTRAINT fk_institution_membership_user FOREIGN KEY (user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_institution_membership_invited_by FOREIGN KEY (invited_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE institution_role_assignment (
    institution_role_assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_user_membership_id BIGINT UNSIGNED NOT NULL,
    group_id INT NOT NULL,
    scope_type ENUM(
        'INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME','SELF'
    ) NOT NULL DEFAULT 'INSTITUTION',
    campus_id SMALLINT UNSIGNED NULL,
    department_id SMALLINT UNSIGNED NULL,
    programme_id SMALLINT UNSIGNED NULL,
    normalized_scope_entity_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE scope_type
            WHEN 'INSTITUTION' THEN 0
            WHEN 'CAMPUS' THEN campus_id
            WHEN 'DEPARTMENT' THEN department_id
            WHEN 'PROGRAMME' THEN programme_id
            WHEN 'SELF' THEN 0
        END
    ) STORED,
    assignment_status ENUM(
        'PENDING','ACTIVE','SUSPENDED','EXPIRED','REVOKED'
    ) NOT NULL DEFAULT 'ACTIVE',
    valid_from DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    valid_until DATETIME(6) NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_by_user_id BIGINT UNSIGNED NULL,
    assignment_reason VARCHAR(500) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_institution_role_assignment UNIQUE
        (institution_user_membership_id, group_id, scope_type,
         normalized_scope_entity_id, valid_from),
    CONSTRAINT chk_institution_role_assignment_dates CHECK
        (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT chk_institution_role_assignment_scope CHECK (
        (scope_type IN ('INSTITUTION','SELF')
            AND campus_id IS NULL AND department_id IS NULL
            AND programme_id IS NULL) OR
        (scope_type = 'CAMPUS' AND campus_id IS NOT NULL
            AND department_id IS NULL AND programme_id IS NULL) OR
        (scope_type = 'DEPARTMENT' AND campus_id IS NULL
            AND department_id IS NOT NULL AND programme_id IS NULL) OR
        (scope_type = 'PROGRAMME' AND campus_id IS NULL
            AND department_id IS NULL AND programme_id IS NOT NULL)
    ),
    CONSTRAINT fk_institution_role_membership
        FOREIGN KEY (institution_user_membership_id)
        REFERENCES institution_user_membership(institution_user_membership_id),
    CONSTRAINT fk_institution_role_group FOREIGN KEY (group_id)
        REFERENCES auth_group(id),
    CONSTRAINT fk_institution_role_campus FOREIGN KEY (campus_id)
        REFERENCES campus(campus_id),
    CONSTRAINT fk_institution_role_department FOREIGN KEY (department_id)
        REFERENCES department(department_id),
    CONSTRAINT fk_institution_role_programme FOREIGN KEY (programme_id)
        REFERENCES programme(programme_id),
    CONSTRAINT fk_institution_role_assigned_by FOREIGN KEY (assigned_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE institution_permission_override (
    institution_permission_override_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_user_membership_id BIGINT UNSIGNED NOT NULL,
    permission_id INT NOT NULL,
    permission_effect ENUM('ALLOW','DENY') NOT NULL,
    scope_type ENUM(
        'INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME','SELF'
    ) NOT NULL DEFAULT 'INSTITUTION',
    scope_entity_id BIGINT UNSIGNED NULL,
    normalized_scope_entity_id BIGINT UNSIGNED GENERATED ALWAYS AS
        (CASE WHEN scope_type IN ('INSTITUTION','SELF') THEN 0
              ELSE COALESCE(scope_entity_id, 0) END) STORED,
    valid_from DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    valid_until DATETIME(6) NULL,
    granted_by_user_id BIGINT UNSIGNED NULL,
    justification VARCHAR(500) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_institution_permission_override UNIQUE
        (institution_user_membership_id, permission_id, scope_type,
         normalized_scope_entity_id, valid_from),
    CONSTRAINT chk_institution_permission_override_dates CHECK
        (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT chk_institution_permission_override_scope CHECK (
        (scope_type IN ('INSTITUTION','SELF') AND scope_entity_id IS NULL) OR
        (scope_type IN ('CAMPUS','DEPARTMENT','PROGRAMME')
            AND scope_entity_id IS NOT NULL)
    ),
    CONSTRAINT fk_institution_permission_membership
        FOREIGN KEY (institution_user_membership_id)
        REFERENCES institution_user_membership(institution_user_membership_id),
    CONSTRAINT fk_institution_permission_permission FOREIGN KEY (permission_id)
        REFERENCES auth_permission(id),
    CONSTRAINT fk_institution_permission_granted_by FOREIGN KEY (granted_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- DA-4. MODULE PERMISSIONS AND BUSINESS AUTHORITY
-- Module activation remains in institution_module. These tables answer which
-- Django permissions belong to a module and whether a group may execute a
-- workflow action inside an organisational scope.
-- --------------------------------------------------------------------------

CREATE TABLE system_module_permission (
    system_module_permission_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    permission_id INT NOT NULL,
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_system_module_permission UNIQUE
        (system_module_id, permission_id),
    CONSTRAINT fk_system_module_permission_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_system_module_permission_permission FOREIGN KEY (permission_id)
        REFERENCES auth_permission(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE workflow_authority (
    workflow_authority_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    group_id INT NOT NULL,
    workflow_code VARCHAR(80) NOT NULL,
    action_code VARCHAR(50) NOT NULL,
    scope_type ENUM(
        'INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME'
    ) NOT NULL DEFAULT 'INSTITUTION',
    campus_id SMALLINT UNSIGNED NULL,
    department_id SMALLINT UNSIGNED NULL,
    programme_id SMALLINT UNSIGNED NULL,
    normalized_scope_entity_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE scope_type
            WHEN 'INSTITUTION' THEN 0
            WHEN 'CAMPUS' THEN campus_id
            WHEN 'DEPARTMENT' THEN department_id
            WHEN 'PROGRAMME' THEN programme_id
        END
    ) STORED,
    authority_level SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    valid_from DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    valid_until DATETIME(6) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_workflow_authority UNIQUE
        (institution_id, system_module_id, group_id, workflow_code,
         action_code, scope_type, normalized_scope_entity_id),
    CONSTRAINT chk_workflow_authority_level CHECK (authority_level > 0),
    CONSTRAINT chk_workflow_authority_dates CHECK
        (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT chk_workflow_authority_scope CHECK (
        (scope_type = 'INSTITUTION' AND campus_id IS NULL
            AND department_id IS NULL AND programme_id IS NULL) OR
        (scope_type = 'CAMPUS' AND campus_id IS NOT NULL
            AND department_id IS NULL AND programme_id IS NULL) OR
        (scope_type = 'DEPARTMENT' AND campus_id IS NULL
            AND department_id IS NOT NULL AND programme_id IS NULL) OR
        (scope_type = 'PROGRAMME' AND campus_id IS NULL
            AND department_id IS NULL AND programme_id IS NOT NULL)
    ),
    CONSTRAINT fk_workflow_authority_institution FOREIGN KEY (institution_id)
        REFERENCES institution(institution_id),
    CONSTRAINT fk_workflow_authority_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_workflow_authority_group FOREIGN KEY (group_id)
        REFERENCES auth_group(id),
    CONSTRAINT fk_workflow_authority_campus FOREIGN KEY (campus_id)
        REFERENCES campus(campus_id),
    CONSTRAINT fk_workflow_authority_department FOREIGN KEY (department_id)
        REFERENCES department(department_id),
    CONSTRAINT fk_workflow_authority_programme FOREIGN KEY (programme_id)
        REFERENCES programme(programme_id),
    CONSTRAINT fk_workflow_authority_created_by FOREIGN KEY (created_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- DA-5. CONFIDENTIALITY AND RECORD-LEVEL ACCESS
-- Default-deny is an application policy. Explicit DENY overrides ALLOW.
-- Record identifiers are strings to support numeric IDs and UUID-based models.
-- --------------------------------------------------------------------------

CREATE TABLE confidentiality_access_policy (
    confidentiality_access_policy_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    confidentiality_level_id TINYINT UNSIGNED NOT NULL,
    group_id INT NOT NULL,
    system_module_id SMALLINT UNSIGNED NULL,
    can_view BOOLEAN NOT NULL DEFAULT FALSE,
    can_create BOOLEAN NOT NULL DEFAULT FALSE,
    can_update BOOLEAN NOT NULL DEFAULT FALSE,
    can_download BOOLEAN NOT NULL DEFAULT FALSE,
    can_share BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve BOOLEAN NOT NULL DEFAULT FALSE,
    can_export BOOLEAN NOT NULL DEFAULT FALSE,
    requires_purpose BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    normalized_system_module_id SMALLINT UNSIGNED GENERATED ALWAYS AS
        (COALESCE(system_module_id, 0)) STORED,
    CONSTRAINT uq_confidentiality_access_policy UNIQUE
        (institution_id, confidentiality_level_id, group_id, normalized_system_module_id),
    CONSTRAINT fk_confidentiality_policy_institution FOREIGN KEY (institution_id)
        REFERENCES institution(institution_id),
    CONSTRAINT fk_confidentiality_policy_level FOREIGN KEY (confidentiality_level_id)
        REFERENCES confidentiality_level(confidentiality_level_id),
    CONSTRAINT fk_confidentiality_policy_group FOREIGN KEY (group_id)
        REFERENCES auth_group(id),
    CONSTRAINT fk_confidentiality_policy_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_confidentiality_policy_created_by FOREIGN KEY (created_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE record_access_grant (
    record_access_grant_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id SMALLINT UNSIGNED NOT NULL,
    system_module_id SMALLINT UNSIGNED NOT NULL,
    content_type_id INT NOT NULL,
    object_id VARCHAR(100) NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    group_id INT NULL,
    permission_id INT NOT NULL,
    permission_effect ENUM('ALLOW','DENY') NOT NULL DEFAULT 'ALLOW',
    valid_from DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    valid_until DATETIME(6) NULL,
    granted_by_user_id BIGINT UNSIGNED NULL,
    justification VARCHAR(500) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT chk_record_access_principal CHECK
        ((user_id IS NOT NULL AND group_id IS NULL) OR
         (user_id IS NULL AND group_id IS NOT NULL)),
    CONSTRAINT chk_record_access_dates CHECK
        (valid_until IS NULL OR valid_until > valid_from),
    CONSTRAINT uq_record_user_grant UNIQUE
        (institution_id, content_type_id, object_id, user_id,
         permission_id, valid_from),
    CONSTRAINT uq_record_group_grant UNIQUE
        (institution_id, content_type_id, object_id, group_id,
         permission_id, valid_from),
    CONSTRAINT fk_record_access_institution FOREIGN KEY (institution_id)
        REFERENCES institution(institution_id),
    CONSTRAINT fk_record_access_module FOREIGN KEY (system_module_id)
        REFERENCES system_module(system_module_id),
    CONSTRAINT fk_record_access_content_type FOREIGN KEY (content_type_id)
        REFERENCES django_content_type(id),
    CONSTRAINT fk_record_access_user FOREIGN KEY (user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_record_access_group FOREIGN KEY (group_id)
        REFERENCES auth_group(id),
    CONSTRAINT fk_record_access_permission FOREIGN KEY (permission_id, content_type_id)
        REFERENCES auth_permission(id, content_type_id),
    CONSTRAINT fk_record_access_module_permission FOREIGN KEY (system_module_id, permission_id)
        REFERENCES system_module_permission(system_module_id, permission_id),
    CONSTRAINT fk_record_access_granted_by FOREIGN KEY (granted_by_user_id)
        REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE authorization_delegation (
    authorization_delegation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    source_role_assignment_id BIGINT UNSIGNED NOT NULL,
    delegate_user_id BIGINT UNSIGNED NOT NULL,
    valid_from DATETIME(6) NOT NULL,
    valid_until DATETIME(6) NOT NULL,
    delegation_status ENUM('PENDING','ACTIVE','REVOKED','EXPIRED')
        NOT NULL DEFAULT 'PENDING',
    reason VARCHAR(500) NOT NULL,
    approved_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT chk_authorization_delegation_dates CHECK
        (valid_until > valid_from),
    CONSTRAINT fk_authorization_delegation_assignment
        FOREIGN KEY (source_role_assignment_id)
        REFERENCES institution_role_assignment(institution_role_assignment_id),
    CONSTRAINT fk_authorization_delegation_user FOREIGN KEY (delegate_user_id)
        REFERENCES user_account(user_id),
    CONSTRAINT fk_authorization_delegation_approved_by
        FOREIGN KEY (approved_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- DA-6. CUTOVER CONTROL AND AUDITABILITY
-- --------------------------------------------------------------------------

CREATE TABLE authentication_migration_state (
    authentication_migration_state_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    migration_code VARCHAR(60) NOT NULL,
    migration_status ENUM(
        'PREPARED','DATA_COPIED','RECONCILED','CUTOVER','ROLLED_BACK'
    ) NOT NULL DEFAULT 'PREPARED',
    legacy_auth_read_only BOOLEAN NOT NULL DEFAULT TRUE,
    migrated_user_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    password_reset_required_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    migrated_group_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    migrated_permission_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    reconciliation_details JSON NULL,
    cutover_at DATETIME(6) NULL,
    completed_by_user_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT uq_authentication_migration_code UNIQUE (migration_code),
    CONSTRAINT fk_authentication_migration_completed_by
        FOREIGN KEY (completed_by_user_id) REFERENCES user_account(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------------------------
-- DA-7. COPY THE LEGACY CATALOGUE INTO DJANGO AUTH TABLES
-- Future permissions must be declared in each Django model's Meta.permissions
-- and created by Django migrations/post_migrate, not inserted here manually.
-- --------------------------------------------------------------------------

INSERT IGNORE INTO django_content_type (app_label, model)
SELECT LOWER(am.module_code), LOWER(ar.resource_code)
FROM access_resource ar
JOIN access_module am ON am.access_module_id = ar.access_module_id;

INSERT IGNORE INTO auth_permission (name, content_type_id, codename)
SELECT p.permission_name,
       ct.id,
       LEFT(LOWER(CONCAT(aa.action_code, '_', ar.resource_code)), 100)
FROM permission p
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
JOIN django_content_type ct
  ON ct.app_label = LOWER(am.module_code)
 AND ct.model = LOWER(ar.resource_code);

INSERT IGNORE INTO auth_group (name)
SELECT role_name FROM role WHERE is_active = TRUE;

INSERT IGNORE INTO auth_group_permissions (group_id, permission_id)
SELECT ag.id, ap.id
FROM role_permission rp
JOIN role r ON r.role_id = rp.role_id
JOIN auth_group ag ON ag.name = r.role_name
JOIN permission p ON p.permission_id = rp.permission_id
JOIN access_resource ar ON ar.access_resource_id = p.access_resource_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.access_action_id = p.access_action_id
JOIN django_content_type ct
  ON ct.app_label = LOWER(am.module_code)
 AND ct.model = LOWER(ar.resource_code)
JOIN auth_permission ap
  ON ap.content_type_id = ct.id
 AND ap.codename = LEFT(LOWER(CONCAT(aa.action_code, '_', ar.resource_code)), 100)
WHERE rp.permission_effect = 'ALLOW'
  AND r.is_active = TRUE AND p.is_active = TRUE
  AND ar.is_active = TRUE AND am.is_active = TRUE AND aa.is_active = TRUE;

-- This full schema intentionally performs no legacy user/group-assignment copy.
-- For an existing database, use a separate reviewed Django data migration that
-- reconciles DENY, overrides, SELF scope, membership intervals and delegation.
-- Time-limited GLOBAL roles must not be copied into timeless Django user.groups.

INSERT IGNORE INTO system_module_permission
    (system_module_id, permission_id, is_sensitive)
SELECT sm.system_module_id, ap.id, p.is_sensitive
FROM system_module sm
JOIN access_resource ar ON ar.access_module_id = sm.access_module_id
JOIN access_module am ON am.access_module_id = ar.access_module_id
JOIN access_action aa ON aa.is_active = TRUE
JOIN permission p
  ON p.access_resource_id = ar.access_resource_id
 AND p.access_action_id = aa.access_action_id
JOIN django_content_type ct
  ON ct.app_label = LOWER(am.module_code)
 AND ct.model = LOWER(ar.resource_code)
JOIN auth_permission ap
  ON ap.content_type_id = ct.id
 AND ap.codename = LEFT(LOWER(CONCAT(aa.action_code, '_', ar.resource_code)), 100);

INSERT INTO authentication_migration_state
    (migration_code, migration_status, legacy_auth_read_only,
     migrated_user_count, password_reset_required_count,
     migrated_group_count, migrated_permission_count,
     reconciliation_details)
SELECT 'V6_4_TO_V6_5_DJANGO_AUTH',
       'PREPARED',
       FALSE,
       (SELECT COUNT(*) FROM user_account),
       (SELECT COUNT(*) FROM user_account WHERE password LIKE '!%'),
       (SELECT COUNT(*) FROM auth_group),
       (SELECT COUNT(*) FROM auth_permission),
       JSON_OBJECT(
           'legacy_tables', JSON_ARRAY(
               'access_module','access_resource','access_action','permission',
               'role','role_permission','user_role_assignment',
               'user_permission_override','role_delegation'
           ),
           'required_next_step',
           'Configure Django migrations and authorization, enforce legacy read-only, reconcile, then CUTOVER'
       );

-- Register independently deployable platform/IAM revisions. Business-module
-- versions are unchanged because their tables and contracts are unchanged.
INSERT IGNORE INTO system_module_version
    (system_module_id, semantic_version, migration_label,
     minimum_platform_version, manifest_json, release_status, released_at)
SELECT system_module_id, '1.1.0',
       CASE module_code
           WHEN 'PLATFORM' THEN 'platform.0002_django_auth_contract'
           ELSE 'accounts.0002_scoped_django_auth'
       END,
       CASE WHEN module_code = 'IAM' THEN '1.1.0' ELSE NULL END,
       JSON_OBJECT(
           'architecture', 'DJANGO_AUTH_SCOPED_AUTHORIZATION',
           'auth_user_model', 'accounts.User',
           'legacy_rbac_mode', 'READ_ONLY_DURING_CUTOVER'
       ),
       'RELEASED', CURRENT_TIMESTAMP
FROM system_module
WHERE module_code IN ('PLATFORM','IAM');

UPDATE module_installation mi
JOIN system_module sm ON sm.system_module_id = mi.system_module_id
JOIN system_module_version smv
  ON smv.system_module_id = sm.system_module_id
 AND smv.semantic_version = '1.1.0'
SET mi.installed_version_id = smv.system_module_version_id,
    mi.installation_status = 'ACTIVE',
    mi.installed_at = COALESCE(mi.installed_at, CURRENT_TIMESTAMP)
WHERE sm.module_code IN ('PLATFORM','IAM');

-- --------------------------------------------------------------------------
-- DA-8. OPERATIONAL VIEWS
-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_active_institution_role AS
SELECT ira.institution_role_assignment_id,
       ium.institution_id,
       ium.user_id,
       ira.group_id,
       ag.name AS group_name,
       ira.scope_type,
       ira.campus_id,
       ira.department_id,
       ira.programme_id,
       ira.valid_from,
       ira.valid_until
FROM institution_role_assignment ira
JOIN institution_user_membership ium
  ON ium.institution_user_membership_id = ira.institution_user_membership_id
JOIN auth_group ag ON ag.id = ira.group_id
JOIN user_account ua ON ua.user_id = ium.user_id
JOIN institution inst ON inst.institution_id = ium.institution_id
WHERE ua.is_active = TRUE AND inst.is_active = TRUE
  AND ium.membership_status = 'ACTIVE'
  AND ira.assignment_status = 'ACTIVE'
  AND ium.valid_from <= CURRENT_TIMESTAMP
  AND (ium.valid_until IS NULL OR ium.valid_until > CURRENT_TIMESTAMP)
  AND ira.valid_from <= CURRENT_TIMESTAMP
  AND (ira.valid_until IS NULL OR ira.valid_until > CURRENT_TIMESTAMP);

-- Candidate role permissions only. A request-specific authorization service must
-- resolve overlapping scopes, DENY overrides, confidentiality, delegation and records.
CREATE OR REPLACE VIEW v_candidate_scoped_permission AS
SELECT air.institution_id,
       air.user_id,
       air.group_id,
       air.group_name,
       ap.id AS permission_id,
       CONCAT(ct.app_label, '.', ap.codename) AS permission_name,
       air.scope_type,
       CASE air.scope_type
           WHEN 'CAMPUS' THEN air.campus_id
           WHEN 'DEPARTMENT' THEN air.department_id
           WHEN 'PROGRAMME' THEN air.programme_id
           ELSE NULL
       END AS scope_entity_id
FROM v_active_institution_role air
JOIN auth_group_permissions agp ON agp.group_id = air.group_id
JOIN auth_permission ap ON ap.id = agp.permission_id
JOIN django_content_type ct ON ct.id = ap.content_type_id
WHERE EXISTS (
    SELECT 1 FROM system_module_permission smp
    JOIN v_effective_institution_module eim
      ON eim.system_module_id = smp.system_module_id
     AND eim.institution_id = air.institution_id
    WHERE smp.permission_id = ap.id AND eim.is_effectively_enabled = TRUE
);

-- DEPRECATED compatibility alias: not a final authorization decision.
CREATE OR REPLACE VIEW v_effective_scoped_permission AS
SELECT * FROM v_candidate_scoped_permission;

CREATE OR REPLACE VIEW v_active_record_access_grant AS
SELECT rag.*,
       CONCAT(ct.app_label, '.', ct.model) AS content_type_name,
       CONCAT(pct.app_label, '.', ap.codename) AS permission_name
FROM record_access_grant rag
JOIN django_content_type ct ON ct.id = rag.content_type_id
JOIN auth_permission ap ON ap.id = rag.permission_id
JOIN django_content_type pct ON pct.id = ap.content_type_id
WHERE rag.valid_from <= CURRENT_TIMESTAMP
  AND (rag.valid_until IS NULL OR rag.valid_until > CURRENT_TIMESTAMP);

CREATE OR REPLACE VIEW v_authentication_cutover_status AS
SELECT ams.*,
       CASE
           WHEN migration_status = 'CUTOVER'
            AND legacy_auth_read_only = TRUE THEN 'DJANGO_AUTH_ACTIVE'
           WHEN migration_status IN ('DATA_COPIED','RECONCILED')
                THEN 'RECONCILIATION_REQUIRED'
           ELSE migration_status
       END AS operational_status
FROM authentication_migration_state ams;

-- Complete the v6.4 ownership catalogue for the v6.5 entities.
INSERT IGNORE INTO module_entity
    (system_module_id, entity_type, entity_name, ownership_type,
     data_scope, write_policy, public_contract_name, description)
SELECT sm.system_module_id,
       seed.entity_type,
       seed.entity_name,
       'OWNED',
       CASE
           WHEN seed.entity_name IN (
               'django_content_type','auth_permission','auth_group',
               'auth_group_permissions','user_account_groups',
               'user_account_user_permissions','system_module_permission',
               'authentication_migration_state',
               'v_authentication_cutover_status'
           ) THEN 'GLOBAL'
           ELSE 'INSTITUTION'
       END,
       'OWNER_ONLY',
       CASE WHEN seed.visibility = 'PUBLIC_CONTRACT'
            THEN CONCAT('iam.', seed.entity_name, '.v1')
            ELSE NULL END,
       seed.description
FROM system_module sm
JOIN (
    SELECT 'IAM' module_code, 'TABLE' entity_type,
           'django_content_type' entity_name, 'PUBLIC_CONTRACT' visibility,
           'Django content-type registry.' description
    UNION ALL SELECT 'IAM','TABLE','auth_permission','PUBLIC_CONTRACT',
           'Django permission catalogue.'
    UNION ALL SELECT 'IAM','TABLE','auth_group','PUBLIC_CONTRACT',
           'Django authorization groups.'
    UNION ALL SELECT 'IAM','TABLE','auth_group_permissions','PRIVATE',
           'Django group-to-permission relation.'
    UNION ALL SELECT 'IAM','TABLE','user_account_groups','PRIVATE',
           'Deployment-global user groups.'
    UNION ALL SELECT 'IAM','TABLE','user_account_user_permissions','PRIVATE',
           'Deployment-global direct user permissions.'
    UNION ALL SELECT 'IAM','TABLE','institution_user_membership','PUBLIC_CONTRACT',
           'Institution membership and tenant boundary.'
    UNION ALL SELECT 'IAM','TABLE','institution_role_assignment','PUBLIC_CONTRACT',
           'Institution-scoped Django group assignment.'
    UNION ALL SELECT 'IAM','TABLE','institution_permission_override','PRIVATE',
           'Scoped allow or deny exception.'
    UNION ALL SELECT 'IAM','TABLE','system_module_permission','PUBLIC_CONTRACT',
           'Module ownership of Django permissions.'
    UNION ALL SELECT 'IAM','TABLE','workflow_authority','PUBLIC_CONTRACT',
           'Scoped workflow decision authority.'
    UNION ALL SELECT 'IAM','TABLE','confidentiality_access_policy','PUBLIC_CONTRACT',
           'Group access by confidentiality level.'
    UNION ALL SELECT 'IAM','TABLE','record_access_grant','PUBLIC_CONTRACT',
           'Explicit record-level allow or deny grant.'
    UNION ALL SELECT 'IAM','TABLE','authorization_delegation','PUBLIC_CONTRACT',
           'Time-bounded authority delegation.'
    UNION ALL SELECT 'IAM','TABLE','authentication_migration_state','PRIVATE',
           'Legacy-to-Django-auth cutover control.'
    UNION ALL SELECT 'IAM','VIEW','v_active_institution_role','PUBLIC_CONTRACT',
           'Currently effective institution role assignments.'
    UNION ALL SELECT 'IAM','VIEW','v_effective_scoped_permission','PUBLIC_CONTRACT',
           'Resolved group permissions with organisation scope.'
    UNION ALL SELECT 'IAM','VIEW','v_active_record_access_grant','PUBLIC_CONTRACT',
           'Currently effective record-level grants.'
    UNION ALL SELECT 'IAM','VIEW','v_authentication_cutover_status','PRIVATE',
           'Authentication cutover readiness.'
) seed ON seed.module_code = sm.module_code;

CREATE INDEX idx_institution_membership_user
    ON institution_user_membership(user_id, membership_status);
CREATE INDEX idx_institution_role_scope
    ON institution_role_assignment(
        group_id, scope_type, normalized_scope_entity_id, assignment_status);
CREATE INDEX idx_permission_override_scope
    ON institution_permission_override(
        permission_id, scope_type, normalized_scope_entity_id);
CREATE INDEX idx_workflow_authority_lookup
    ON workflow_authority(
        institution_id, system_module_id, workflow_code, action_code, is_active);
CREATE INDEX idx_record_access_object
    ON record_access_grant(
        institution_id, content_type_id, object_id, permission_id);

-- --------------------------------------------------------------------------
-- APPLICATION ENFORCEMENT RULES
-- --------------------------------------------------------------------------
-- 1. Configure AUTH_USER_MODEL='accounts.User' before initial Django migrate.
-- 2. accounts.User must map db_table='user_account' and PK db_column='user_id'.
-- 3. Configure explicit M2M through tables user_account_groups and
--    user_account_user_permissions, or represent them as managed=False models.
-- 4. Django authentication establishes identity; authorisation additionally
--    requires active institution membership and active institution_module.
-- 5. Tenant roles must use institution_role_assignment, not user.groups.
--    user.groups is reserved for deployment-global roles.
-- 6. QuerySets must always be filtered by resolved institution and scope.
-- 7. Explicit DENY overrides explicit ALLOW; record grants are evaluated after
--    module, membership, role and confidentiality checks.
-- 8. Every sensitive read/download/export/decrypt must append an audit record.
-- 9. is_superuser is restricted to deployment operators and never assigned to
--    institution administrators.
-- 10. Do not drop legacy RBAC tables until permission-count and user-access
--     reconciliation is accepted and migration_status is CUTOVER.

SET FOREIGN_KEY_CHECKS = 1;


-- =============================================================
-- 43. REVIEW HARDENING - v6.5.1
-- =============================================================
SET FOREIGN_KEY_CHECKS = 1;
DELIMITER $$
CREATE TRIGGER trg_curriculum_framework_node_self_ai
AFTER INSERT ON curriculum_framework_node
FOR EACH ROW
BEGIN
    IF NEW.parent_node_id IS NOT NULL AND NEW.parent_node_id = NEW.framework_node_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A row cannot be its own parent';
    END IF;
END$$
CREATE TRIGGER trg_curriculum_framework_node_self_bu
BEFORE UPDATE ON curriculum_framework_node
FOR EACH ROW
BEGIN
    IF NEW.parent_node_id IS NOT NULL AND NEW.parent_node_id = NEW.framework_node_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A row cannot be its own parent';
    END IF;
END$$
CREATE TRIGGER trg_question_item_self_ai
AFTER INSERT ON question_item
FOR EACH ROW
BEGIN
    IF NEW.parent_question_item_id IS NOT NULL AND NEW.parent_question_item_id = NEW.question_item_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A row cannot be its own parent';
    END IF;
END$$
CREATE TRIGGER trg_question_item_self_bu
BEFORE UPDATE ON question_item
FOR EACH ROW
BEGIN
    IF NEW.parent_question_item_id IS NOT NULL AND NEW.parent_question_item_id = NEW.question_item_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A row cannot be its own parent';
    END IF;
END$$
CREATE TRIGGER trg_campus_owner_bu
BEFORE UPDATE ON campus
FOR EACH ROW
BEGIN
    IF NOT (NEW.institution_id <=> OLD.institution_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Organisation reparenting requires a reviewed data migration';
    END IF;
END$$
CREATE TRIGGER trg_department_owner_bu
BEFORE UPDATE ON department
FOR EACH ROW
BEGIN
    IF NOT (NEW.campus_id <=> OLD.campus_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Organisation reparenting requires a reviewed data migration';
    END IF;
END$$
CREATE TRIGGER trg_programme_owner_bu
BEFORE UPDATE ON programme
FOR EACH ROW
BEGIN
    IF NOT (NEW.department_id <=> OLD.department_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Organisation reparenting requires a reviewed data migration';
    END IF;
END$$
CREATE TRIGGER trg_membership_identity_bu
BEFORE UPDATE ON institution_user_membership
FOR EACH ROW
BEGIN
    IF NEW.institution_id <> OLD.institution_id OR NEW.user_id <> OLD.user_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Membership identity is immutable; create a new membership';
    END IF;
END$$
CREATE TRIGGER trg_ira_tenant_bi
BEFORE INSERT ON institution_role_assignment
FOR EACH ROW
BEGIN
    DECLARE v_institution SMALLINT UNSIGNED;
    SET v_institution = (SELECT institution_id FROM institution_user_membership WHERE institution_user_membership_id=NEW.institution_user_membership_id);
    IF v_institution IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Missing institution context';
    END IF;
    IF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus c WHERE c.campus_id=NEW.campus_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department d JOIN campus c ON c.campus_id=d.campus_id WHERE d.department_id=NEW.department_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme p JOIN department d ON d.department_id=p.department_id JOIN campus c ON c.campus_id=d.campus_id WHERE p.programme_id=NEW.programme_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;

END$$
CREATE TRIGGER trg_ira_tenant_bu
BEFORE UPDATE ON institution_role_assignment
FOR EACH ROW
BEGIN
    DECLARE v_institution SMALLINT UNSIGNED;
    SET v_institution = (SELECT institution_id FROM institution_user_membership WHERE institution_user_membership_id=NEW.institution_user_membership_id);
    IF v_institution IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Missing institution context';
    END IF;
    IF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus c WHERE c.campus_id=NEW.campus_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department d JOIN campus c ON c.campus_id=d.campus_id WHERE d.department_id=NEW.department_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme p JOIN department d ON d.department_id=p.department_id JOIN campus c ON c.campus_id=d.campus_id WHERE p.programme_id=NEW.programme_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;

END$$
CREATE TRIGGER trg_ipo_tenant_bi
BEFORE INSERT ON institution_permission_override
FOR EACH ROW
BEGIN
    DECLARE v_institution SMALLINT UNSIGNED;
    SET v_institution = (SELECT institution_id FROM institution_user_membership WHERE institution_user_membership_id=NEW.institution_user_membership_id);
    IF v_institution IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Missing institution context';
    END IF;
    IF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus c WHERE c.campus_id=NEW.scope_entity_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department d JOIN campus c ON c.campus_id=d.campus_id WHERE d.department_id=NEW.scope_entity_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme p JOIN department d ON d.department_id=p.department_id JOIN campus c ON c.campus_id=d.campus_id WHERE p.programme_id=NEW.scope_entity_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;

END$$
CREATE TRIGGER trg_ipo_tenant_bu
BEFORE UPDATE ON institution_permission_override
FOR EACH ROW
BEGIN
    DECLARE v_institution SMALLINT UNSIGNED;
    SET v_institution = (SELECT institution_id FROM institution_user_membership WHERE institution_user_membership_id=NEW.institution_user_membership_id);
    IF v_institution IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Missing institution context';
    END IF;
    IF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus c WHERE c.campus_id=NEW.scope_entity_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department d JOIN campus c ON c.campus_id=d.campus_id WHERE d.department_id=NEW.scope_entity_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme p JOIN department d ON d.department_id=p.department_id JOIN campus c ON c.campus_id=d.campus_id WHERE p.programme_id=NEW.scope_entity_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;

END$$
CREATE TRIGGER trg_wa_tenant_bi
BEFORE INSERT ON workflow_authority
FOR EACH ROW
BEGIN
    DECLARE v_institution SMALLINT UNSIGNED;
    SET v_institution = NEW.institution_id;
    IF v_institution IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Missing institution context';
    END IF;
    IF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus c WHERE c.campus_id=NEW.campus_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department d JOIN campus c ON c.campus_id=d.campus_id WHERE d.department_id=NEW.department_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme p JOIN department d ON d.department_id=p.department_id JOIN campus c ON c.campus_id=d.campus_id WHERE p.programme_id=NEW.programme_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;

END$$
CREATE TRIGGER trg_wa_tenant_bu
BEFORE UPDATE ON workflow_authority
FOR EACH ROW
BEGIN
    DECLARE v_institution SMALLINT UNSIGNED;
    SET v_institution = NEW.institution_id;
    IF v_institution IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Missing institution context';
    END IF;
    IF NEW.scope_type='CAMPUS' AND NOT EXISTS (SELECT 1 FROM campus c WHERE c.campus_id=NEW.campus_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='DEPARTMENT' AND NOT EXISTS (SELECT 1 FROM department d JOIN campus c ON c.campus_id=d.campus_id WHERE d.department_id=NEW.department_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;
    IF NEW.scope_type='PROGRAMME' AND NOT EXISTS (SELECT 1 FROM programme p JOIN department d ON d.department_id=p.department_id JOIN campus c ON c.campus_id=d.campus_id WHERE p.programme_id=NEW.programme_id AND c.institution_id=v_institution) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Scope does not belong to membership/workflow institution';
    END IF;

END$$
CREATE TRIGGER trg_imf_bi
BEFORE INSERT ON institution_module_feature
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM institution_module im JOIN module_installation mi ON mi.module_installation_id=im.module_installation_id JOIN module_feature d ON d.system_module_id=mi.system_module_id WHERE im.institution_module_id=NEW.institution_module_id AND d.module_feature_id=NEW.module_feature_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Feature/setting belongs to another module';
    END IF;
END$$
CREATE TRIGGER trg_imf_bu
BEFORE UPDATE ON institution_module_feature
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM institution_module im JOIN module_installation mi ON mi.module_installation_id=im.module_installation_id JOIN module_feature d ON d.system_module_id=mi.system_module_id WHERE im.institution_module_id=NEW.institution_module_id AND d.module_feature_id=NEW.module_feature_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Feature/setting belongs to another module';
    END IF;
END$$
CREATE TRIGGER trg_ims_bi
BEFORE INSERT ON institution_module_setting
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM institution_module im JOIN module_installation mi ON mi.module_installation_id=im.module_installation_id JOIN module_setting_definition d ON d.system_module_id=mi.system_module_id WHERE im.institution_module_id=NEW.institution_module_id AND d.module_setting_definition_id=NEW.module_setting_definition_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Feature/setting belongs to another module';
    END IF;
    IF EXISTS (SELECT 1 FROM module_setting_definition d WHERE d.module_setting_definition_id=NEW.module_setting_definition_id AND ((d.is_secret=TRUE AND NEW.value_ciphertext IS NULL) OR (d.is_secret=FALSE AND NEW.value_json IS NULL) OR d.client_overridable=FALSE)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Setting secret representation or override policy is invalid';
    END IF;
END$$
CREATE TRIGGER trg_ims_bu
BEFORE UPDATE ON institution_module_setting
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM institution_module im JOIN module_installation mi ON mi.module_installation_id=im.module_installation_id JOIN module_setting_definition d ON d.system_module_id=mi.system_module_id WHERE im.institution_module_id=NEW.institution_module_id AND d.module_setting_definition_id=NEW.module_setting_definition_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Feature/setting belongs to another module';
    END IF;
    IF EXISTS (SELECT 1 FROM module_setting_definition d WHERE d.module_setting_definition_id=NEW.module_setting_definition_id AND ((d.is_secret=TRUE AND NEW.value_ciphertext IS NULL) OR (d.is_secret=FALSE AND NEW.value_json IS NULL) OR d.client_overridable=FALSE)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Setting secret representation or override policy is invalid';
    END IF;
END$$
CREATE TRIGGER trg_module_feature_identity_bu
BEFORE UPDATE ON module_feature
FOR EACH ROW
BEGIN
    IF NOT (NEW.system_module_id <=> OLD.system_module_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Module ownership/type change requires a reviewed migration';
    END IF;
END$$
CREATE TRIGGER trg_module_setting_definition_identity_bu
BEFORE UPDATE ON module_setting_definition
FOR EACH ROW
BEGIN
    IF NOT (NEW.system_module_id <=> OLD.system_module_id) OR NOT (NEW.is_secret <=> OLD.is_secret) OR NOT (NEW.data_type <=> OLD.data_type) OR NOT (NEW.client_overridable <=> OLD.client_overridable) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Module ownership/type change requires a reviewed migration';
    END IF;
END$$
CREATE TRIGGER trg_institution_module_identity_bu
BEFORE UPDATE ON institution_module
FOR EACH ROW
BEGIN
    IF NOT (NEW.institution_id <=> OLD.institution_id) OR NOT (NEW.module_installation_id <=> OLD.module_installation_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Module ownership/type change requires a reviewed migration';
    END IF;
END$$
CREATE TRIGGER trg_module_installation_identity_bu
BEFORE UPDATE ON module_installation
FOR EACH ROW
BEGIN
    IF NOT (NEW.system_module_id <=> OLD.system_module_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Module ownership/type change requires a reviewed migration';
    END IF;
END$$
DELIMITER ;
ALTER TABLE institution_permission_override
    ADD COLUMN scope_campus_id SMALLINT UNSIGNED GENERATED ALWAYS AS
        (CASE WHEN scope_type='CAMPUS' THEN scope_entity_id ELSE NULL END) STORED,
    ADD COLUMN scope_department_id SMALLINT UNSIGNED GENERATED ALWAYS AS
        (CASE WHEN scope_type='DEPARTMENT' THEN scope_entity_id ELSE NULL END) STORED,
    ADD COLUMN scope_programme_id SMALLINT UNSIGNED GENERATED ALWAYS AS
        (CASE WHEN scope_type='PROGRAMME' THEN scope_entity_id ELSE NULL END) STORED,
    ADD CONSTRAINT fk_ipo_scope_campus FOREIGN KEY (scope_campus_id) REFERENCES campus(campus_id),
    ADD CONSTRAINT fk_ipo_scope_department FOREIGN KEY (scope_department_id) REFERENCES department(department_id),
    ADD CONSTRAINT fk_ipo_scope_programme FOREIGN KEY (scope_programme_id) REFERENCES programme(programme_id);

INSERT INTO module_entity
    (system_module_id, entity_type, entity_name, ownership_type,
     data_scope, write_policy, public_contract_name, description)
SELECT system_module_id, 'VIEW', 'v_candidate_scoped_permission', 'OWNED',
       'INSTITUTION', 'READ_ONLY', 'v_candidate_scoped_permission',
       'Candidate role grants only; final authorization requires request context.'
FROM system_module WHERE module_code='IAM';

-- REMAINING REQUIRED APPLICATION RULES:
-- Resolve all matching scope levels and DENY before ALLOW. Enforce object ownership,
-- confidentiality, workflow and bounded delegation; never authorize from views alone.
-- Validate longer hierarchy cycles under serialized writes; direct self-parent is blocked.
-- Financial services must reconcile refunds/benefits and use transaction locking.
-- accounts.User: user_id unsigned-compatible PK, UUID-compatible CharField(max_length=36),
-- default UUID string callable, date_joined default timezone.now, explicit M2M mappings.
-- Django migrations own deployment; never blindly fake migrations over this script.
SET FOREIGN_KEY_CHECKS = 1;
