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
