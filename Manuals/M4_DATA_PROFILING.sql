-- M4 legacy preflight. Read-only; run only when all five curriculum tables exist.
-- Duplicate comparison deliberately uses the target baseline collation.
SELECT course_code COLLATE utf8mb4_unicode_ci AS normalized_code, COUNT(*) AS n
FROM course_catalog GROUP BY normalized_code HAVING COUNT(*) > 1;
SELECT scheme_code COLLATE utf8mb4_unicode_ci AS normalized_code, COUNT(*) AS n
FROM curriculum_scheme GROUP BY normalized_code HAVING COUNT(*) > 1;
SELECT category_code COLLATE utf8mb4_unicode_ci AS normalized_code, COUNT(*) AS n
FROM course_category GROUP BY normalized_code HAVING COUNT(*) > 1;
SELECT category_name COLLATE utf8mb4_unicode_ci AS normalized_name, COUNT(*) AS n
FROM course_category GROUP BY normalized_name HAVING COUNT(*) > 1;
SELECT s.curriculum_scheme_id FROM curriculum_scheme s LEFT JOIN programme_specialization p
ON p.specialization_id=s.specialization_id AND p.programme_id=s.programme_id
WHERE s.specialization_id IS NOT NULL AND p.specialization_id IS NULL;
SELECT c.course_id FROM course_catalog c LEFT JOIN department d ON d.department_id=c.owning_department_id
LEFT JOIN course_category k ON k.course_category_id=c.course_category_id
WHERE d.department_id IS NULL OR k.course_category_id IS NULL;
SELECT curriculum_scheme_id FROM curriculum_scheme
WHERE effective_to < effective_from OR total_credits < 0 OR regulation_year=0;
SELECT course_id FROM course_catalog WHERE effective_to < effective_from
OR lecture_hours<0 OR tutorial_hours<0 OR practical_hours<0 OR self_study_hours<0 OR credits<0;
SELECT curriculum_course_id FROM curriculum_course
WHERE internal_max_marks<0 OR external_max_marks<0 OR passing_marks<0
OR passing_marks>internal_max_marks+external_max_marks
OR (is_mandatory=TRUE AND elective_group_code IS NOT NULL)
OR (is_mandatory=FALSE AND (elective_group_code IS NULL OR TRIM(elective_group_code)=''));
SELECT m.curriculum_course_id FROM curriculum_course m JOIN course_catalog c ON c.course_id=m.course_id
WHERE m.course_category_id<>c.course_category_id;
SELECT m.curriculum_course_id FROM curriculum_course m JOIN curriculum_scheme s ON s.curriculum_scheme_id=m.curriculum_scheme_id
JOIN programme p ON p.programme_id=s.programme_id JOIN semester t ON t.semester_id=m.semester_id
WHERE t.semester_number<1 OR t.semester_number>p.duration_semesters;
SELECT curriculum_scheme_id,semester_id,display_order,COUNT(*) AS n FROM curriculum_course
WHERE display_order IS NOT NULL GROUP BY curriculum_scheme_id,semester_id,display_order HAVING COUNT(*)>1;
SELECT course_id,prerequisite_course_id FROM course_prerequisite WHERE course_id=prerequisite_course_id;
SELECT a.curriculum_scheme_id,b.curriculum_scheme_id FROM curriculum_scheme a JOIN curriculum_scheme b
ON a.curriculum_scheme_id<b.curriculum_scheme_id AND a.programme_id=b.programme_id
AND a.specialization_id <=> b.specialization_id
WHERE a.status='ACTIVE' AND b.status='ACTIVE'
AND (a.effective_to IS NULL OR b.effective_from<=a.effective_to)
AND (b.effective_to IS NULL OR a.effective_from<=b.effective_to);
-- Full cycle detection, complete FK orphan checks and elective-credit reconciliation
-- must also run through reviewed staging validation; zero rows above alone is not acceptance.
