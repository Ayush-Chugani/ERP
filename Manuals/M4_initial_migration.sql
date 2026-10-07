--
-- Create model CourseCategory
--
CREATE TABLE `course_category` (`course_category_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `category_code` varchar(30) COLLATE `utf8mb4_unicode_ci` NOT NULL UNIQUE, `category_name` varchar(100) COLLATE `utf8mb4_unicode_ci` NOT NULL UNIQUE, `is_graded` bool DEFAULT b'1' NOT NULL, `contributes_to_gpa` bool DEFAULT b'1' NOT NULL, `is_active` bool DEFAULT b'1' NOT NULL);
--
-- Create model CourseCatalog
--
CREATE TABLE `course_catalog` (`course_id` integer unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `course_code` varchar(30) COLLATE `utf8mb4_unicode_ci` NOT NULL UNIQUE, `course_title` varchar(200) COLLATE `utf8mb4_unicode_ci` NOT NULL, `short_title` varchar(80) COLLATE `utf8mb4_unicode_ci` NULL, `course_type` varchar(10) NOT NULL, `lecture_hours` numeric(4, 1) DEFAULT 0 NOT NULL, `tutorial_hours` numeric(4, 1) DEFAULT 0 NOT NULL, `practical_hours` numeric(4, 1) DEFAULT 0 NOT NULL, `self_study_hours` numeric(4, 1) DEFAULT 0 NOT NULL, `credits` numeric(4, 1) DEFAULT 0 NOT NULL, `effective_from` date NULL, `effective_to` date NULL, `is_active` bool DEFAULT b'1' NOT NULL, `owning_department_id` smallint unsigned NOT NULL, `course_category_id` smallint unsigned NOT NULL);
--
-- Create model CoursePrerequisite
--
CREATE TABLE `course_prerequisite` (`minimum_grade` varchar(5) COLLATE `utf8mb4_unicode_ci` NULL, `course_id` integer unsigned NOT NULL, `prerequisite_course_id` integer unsigned NOT NULL, PRIMARY KEY (`course_id`, `prerequisite_course_id`));
--
-- Create model CurriculumAudit
--
CREATE TABLE `platform_curriculum_audit` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `resource` varchar(32) NOT NULL, `record_key` varchar(50) NOT NULL, `action` varchar(24) NOT NULL, `before` json NOT NULL, `after` json NOT NULL, `reason` varchar(250) NOT NULL, `correlation_id` varchar(64) NOT NULL, `timestamp` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `institution_id` smallint unsigned NULL);
--
-- Create model CurriculumEvent
--
CREATE TABLE `platform_curriculum_event` (`id` char(32) NOT NULL PRIMARY KEY, `event_type` varchar(80) NOT NULL, `schema_version` smallint UNSIGNED NOT NULL CHECK (`schema_version` >= 0), `payload` json NOT NULL, `timestamp` datetime(6) NOT NULL, `audit_id` bigint NOT NULL UNIQUE);
--
-- Create model CurriculumRevision
--
CREATE TABLE `platform_curriculum_revision` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `resource` varchar(32) NOT NULL, `record_key` varchar(50) NOT NULL, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), CONSTRAINT `uq_curriculum_revision` UNIQUE (`resource`, `record_key`));
--
-- Create model CurriculumScheme
--
CREATE TABLE `curriculum_scheme` (`curriculum_scheme_id` integer unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `scheme_code` varchar(30) COLLATE `utf8mb4_unicode_ci` NOT NULL UNIQUE, `scheme_name` varchar(150) COLLATE `utf8mb4_unicode_ci` NOT NULL, `regulation_year` year NOT NULL CHECK (`regulation_year` >= 0), `total_credits` numeric(6, 1) NULL, `effective_from` date NOT NULL, `effective_to` date NULL, `status` varchar(7) DEFAULT 'DRAFT' NOT NULL, `programme_id` smallint unsigned NOT NULL, `specialization_id` smallint unsigned NULL);
--
-- Create model CurriculumCourse
--
CREATE TABLE `curriculum_course` (`curriculum_course_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `is_mandatory` bool DEFAULT b'1' NOT NULL, `elective_group_code` varchar(30) COLLATE `utf8mb4_unicode_ci` NULL, `display_order` smallint UNSIGNED NULL CHECK (`display_order` >= 0), `internal_max_marks` numeric(6, 2) DEFAULT 0 NOT NULL, `external_max_marks` numeric(6, 2) DEFAULT 0 NOT NULL, `passing_marks` numeric(6, 2) NULL, `exam_duration_minutes` smallint UNSIGNED NULL CHECK (`exam_duration_minutes` >= 0), `course_id` integer unsigned NOT NULL, `course_category_id` smallint unsigned NOT NULL, `semester_id` tinyint unsigned NOT NULL, `curriculum_scheme_id` integer unsigned NOT NULL);
--
-- Create index catalog_department_active on field(s) owning_department, is_active, course_code of model coursecatalog
--
CREATE INDEX `catalog_department_active` ON `course_catalog` (`owning_department_id`, `is_active`, `course_code`);
--
-- Create constraint chk_course_nonnegative_values on model coursecatalog
--
ALTER TABLE `course_catalog` ADD CONSTRAINT `chk_course_nonnegative_values` CHECK ((`credits` >= 0 AND `lecture_hours` >= 0 AND `practical_hours` >= 0 AND `self_study_hours` >= 0 AND `tutorial_hours` >= 0));
--
-- Create constraint chk_course_effective_dates on model coursecatalog
--
ALTER TABLE `course_catalog` ADD CONSTRAINT `chk_course_effective_dates` CHECK ((`effective_from` IS NULL OR `effective_to` IS NULL OR `effective_to` >= (`effective_from`)));
--
-- Create constraint chk_catalog_course_type on model coursecatalog
--
ALTER TABLE `course_catalog` ADD CONSTRAINT `chk_catalog_course_type` CHECK (`course_type` IN ('THEORY', 'LAB', 'THEORY_LAB', 'PROJECT', 'SEMINAR', 'INTERNSHIP', 'OTHER'));
--
-- Create constraint chk_prerequisite_not_self on model courseprerequisite
--
ALTER TABLE `course_prerequisite` ADD CONSTRAINT `chk_prerequisite_not_self` CHECK (NOT (`course_id` = (`prerequisite_course_id`)));
--
-- Create index curriculum_audit_record on field(s) resource, record_key of model curriculumaudit
--
CREATE INDEX `curriculum_audit_record` ON `platform_curriculum_audit` (`resource`, `record_key`);
--
-- Create index scheme_effective_lookup on field(s) programme, specialization, status, effective_from of model curriculumscheme
--
CREATE INDEX `scheme_effective_lookup` ON `curriculum_scheme` (`programme_id`, `specialization_id`, `status`, `effective_from`);
--
-- Create constraint chk_scheme_effective_dates on model curriculumscheme
--
ALTER TABLE `curriculum_scheme` ADD CONSTRAINT `chk_scheme_effective_dates` CHECK ((`effective_to` IS NULL OR `effective_to` >= (`effective_from`)));
--
-- Create constraint chk_scheme_total_credits on model curriculumscheme
--
ALTER TABLE `curriculum_scheme` ADD CONSTRAINT `chk_scheme_total_credits` CHECK ((`total_credits` IS NULL OR `total_credits` >= 0));
--
-- Create constraint chk_scheme_status on model curriculumscheme
--
ALTER TABLE `curriculum_scheme` ADD CONSTRAINT `chk_scheme_status` CHECK (`status` IN ('DRAFT', 'ACTIVE', 'RETIRED'));
--
-- Create constraint uq_curriculum_course on model curriculumcourse
--
ALTER TABLE `curriculum_course` ADD CONSTRAINT `uq_curriculum_course` UNIQUE (`curriculum_scheme_id`, `semester_id`, `course_id`);
--
-- Create constraint uq_curriculum_display_order on model curriculumcourse
--
ALTER TABLE `curriculum_course` ADD CONSTRAINT `uq_curriculum_display_order` UNIQUE (`curriculum_scheme_id`, `semester_id`, `display_order`);
--
-- Create constraint chk_curriculum_marks on model curriculumcourse
--
ALTER TABLE `curriculum_course` ADD CONSTRAINT `chk_curriculum_marks` CHECK ((`external_max_marks` >= 0 AND `internal_max_marks` >= 0 AND (`passing_marks` IS NULL OR (`passing_marks` >= 0 AND `passing_marks` <= (`internal_max_marks` + `external_max_marks`)))));
--
-- Create constraint chk_curriculum_elective on model curriculumcourse
--
ALTER TABLE `curriculum_course` ADD CONSTRAINT `chk_curriculum_elective` CHECK (((`elective_group_code` IS NULL AND `is_mandatory` = b'1') OR (`elective_group_code` IS NOT NULL AND `is_mandatory` = b'0' AND NOT (`elective_group_code` IS NULL))));
ALTER TABLE `course_catalog` ADD CONSTRAINT `course_catalog_owning_department_id_cc99cdb7_fk_departmen` FOREIGN KEY (`owning_department_id`) REFERENCES `department` (`department_id`);
ALTER TABLE `course_catalog` ADD CONSTRAINT `course_catalog_course_category_id_ebc36fb7_fk_course_ca` FOREIGN KEY (`course_category_id`) REFERENCES `course_category` (`course_category_id`);
ALTER TABLE `course_prerequisite` ADD CONSTRAINT `course_prerequisite_course_id_eb4de4e5_fk_course_ca` FOREIGN KEY (`course_id`) REFERENCES `course_catalog` (`course_id`);
ALTER TABLE `course_prerequisite` ADD CONSTRAINT `course_prerequisite_prerequisite_course__c493ebf2_fk_course_ca` FOREIGN KEY (`prerequisite_course_id`) REFERENCES `course_catalog` (`course_id`);
ALTER TABLE `platform_curriculum_audit` ADD CONSTRAINT `platform_curriculum__actor_id_8001dee6_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_curriculum_audit` ADD CONSTRAINT `platform_curriculum__institution_id_cf55a7f5_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_curriculum_event` ADD CONSTRAINT `platform_curriculum__audit_id_0a7cf134_fk_platform_` FOREIGN KEY (`audit_id`) REFERENCES `platform_curriculum_audit` (`id`);
ALTER TABLE `curriculum_scheme` ADD CONSTRAINT `curriculum_scheme_programme_id_b663bd0b_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`);
CREATE INDEX `curriculum_scheme_specialization_id_06b5dea8` ON `curriculum_scheme` (`specialization_id`);
ALTER TABLE `curriculum_course` ADD CONSTRAINT `curriculum_course_course_id_7d898ba3_fk_course_catalog_course_id` FOREIGN KEY (`course_id`) REFERENCES `course_catalog` (`course_id`);
ALTER TABLE `curriculum_course` ADD CONSTRAINT `curriculum_course_course_category_id_12cf6d44_fk_course_ca` FOREIGN KEY (`course_category_id`) REFERENCES `course_category` (`course_category_id`);
ALTER TABLE `curriculum_course` ADD CONSTRAINT `curriculum_course_semester_id_4887864b_fk_semester_semester_id` FOREIGN KEY (`semester_id`) REFERENCES `semester` (`semester_id`);
ALTER TABLE `curriculum_course` ADD CONSTRAINT `curriculum_course_curriculum_scheme_id_c074a75f_fk_curriculu` FOREIGN KEY (`curriculum_scheme_id`) REFERENCES `curriculum_scheme` (`curriculum_scheme_id`);
