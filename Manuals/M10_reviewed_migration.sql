-- Reference DDL. Apply migrations using Django. No production grades are seeded.
-- assessments_results 0001
--
-- Create model AssessmentComponent
--
CREATE TABLE `assessment_component` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `updated_at` datetime(6) NOT NULL, `assessment_component_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `component_code` varchar(30) NOT NULL, `component_name` varchar(100) NOT NULL, `component_type` varchar(20) NOT NULL, `maximum_marks` numeric(7, 2) NOT NULL, `weightage_percent` numeric(5, 2) NULL, `is_mandatory` bool NOT NULL, `actor_id` bigint NOT NULL, `course_offering_id` bigint unsigned NOT NULL);
--
-- Create model Audit
--
CREATE TABLE `platform_m10_audit` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `authority` json NOT NULL, `action` varchar(50) NOT NULL, `resource` varchar(30) NOT NULL, `record_id` bigint UNSIGNED NOT NULL CHECK (`record_id` >= 0), `before` json NOT NULL, `after` json NOT NULL, `reason` varchar(500) NOT NULL, `request_key` varchar(100) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `course_offering_id` bigint unsigned NULL, `institution_id` smallint unsigned NOT NULL);
--
-- Create model CalculationPolicy
--
CREATE TABLE `platform_m10_policy` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `number` integer UNSIGNED NOT NULL CHECK (`number` >= 0), `rules` json NOT NULL, `reason` varchar(500) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `course_offering_id` bigint unsigned NOT NULL);
--
-- Create model AssessmentEvent
--
CREATE TABLE `assessment_event` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `updated_at` datetime(6) NOT NULL, `assessment_event_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `attempt_number` smallint UNSIGNED NOT NULL CHECK (`attempt_number` >= 0), `event_number` smallint UNSIGNED NULL CHECK (`event_number` >= 0), `event_title` varchar(150) NOT NULL, `assessment_date` date NOT NULL, `start_time` time(6) NULL, `end_time` time(6) NULL, `maximum_marks` numeric(7, 2) NOT NULL, `reduced_maximum_marks` numeric(7, 2) NULL, `details` longtext NOT NULL, `status` varchar(9) NOT NULL, `roster` json NOT NULL, `actor_id` bigint NOT NULL, `assessment_component_id` bigint unsigned NOT NULL, `course_offering_id` bigint unsigned NOT NULL, `policy_id` bigint NOT NULL);
--
-- Create model GradeScale
--
CREATE TABLE `grade_scale` (`grade_scale_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `scale_name` varchar(100) NOT NULL UNIQUE, `effective_from` date NOT NULL, `effective_to` date NULL, `is_active` bool NOT NULL, `actor_id` bigint NOT NULL, `institution_id` smallint unsigned NOT NULL);
--
-- Create model GradeRule
--
CREATE TABLE `grade_rule` (`grade_rule_id` integer unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `grade_letter` varchar(5) NOT NULL, `grade_point` numeric(4, 2) NOT NULL, `minimum_percentage` numeric(5, 2) NOT NULL, `maximum_percentage` numeric(5, 2) NOT NULL, `result_status` varchar(8) NOT NULL, `grade_scale_id` smallint unsigned NOT NULL);
--
-- Add field grade_scale to calculationpolicy
--
ALTER TABLE `platform_m10_policy` ADD COLUMN `grade_scale_id` smallint unsigned NOT NULL , ADD CONSTRAINT `platform_m10_policy_grade_scale_id_639fba3d_fk_grade_sca` FOREIGN KEY (`grade_scale_id`) REFERENCES `grade_scale`(`grade_scale_id`);
--
-- Create model Publication
--
CREATE TABLE `platform_m10_publication` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `resource` varchar(30) NOT NULL, `record_id` bigint UNSIGNED NOT NULL CHECK (`record_id` >= 0), `number` integer UNSIGNED NOT NULL CHECK (`number` >= 0), `data` json NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `institution_id` smallint unsigned NOT NULL);
--
-- Create model Receipt
--
CREATE TABLE `platform_m10_receipt` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `key` varchar(100) NOT NULL, `digest` varchar(64) NOT NULL, `result` json NOT NULL, `actor_id` bigint NOT NULL);
--
-- Create model StudentAssessmentMark
--
CREATE TABLE `student_assessment_mark` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `updated_at` datetime(6) NOT NULL, `student_assessment_mark_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `attendance_status` varchar(11) NOT NULL, `marks_obtained` numeric(7, 2) NULL, `reduced_marks` numeric(7, 2) NULL, `remarks` varchar(500) NOT NULL, `evaluated_at` datetime(6) NULL, `actor_id` bigint NOT NULL, `assessment_event_id` bigint unsigned NOT NULL, `course_offering_id` bigint unsigned NOT NULL, `course_registration_id` bigint unsigned NOT NULL);
--
-- Create model StudentCourseResult
--
CREATE TABLE `student_course_result` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `updated_at` datetime(6) NOT NULL, `student_course_result_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `attempt_number` smallint UNSIGNED NOT NULL CHECK (`attempt_number` >= 0), `internal_marks` numeric(7, 2) NULL, `external_marks` numeric(7, 2) NULL, `total_marks` numeric(7, 2) NULL, `grade_letter` varchar(5) NOT NULL, `grade_point` numeric(4, 2) NULL, `credits_earned` numeric(4, 1) NOT NULL, `result_status` varchar(10) NOT NULL, `result_date` date NULL, `remarks` varchar(500) NOT NULL, `evidence` json NOT NULL, `state` varchar(10) NOT NULL, `actor_id` bigint NOT NULL, `course_registration_id` bigint unsigned NOT NULL, `policy_id` bigint NOT NULL);
--
-- Create model StudentTermResult
--
CREATE TABLE `student_term_result` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `updated_at` datetime(6) NOT NULL, `student_term_result_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `credits_registered` numeric(6, 1) NOT NULL, `credits_earned` numeric(6, 1) NOT NULL, `sgpa` numeric(4, 2) NULL, `cgpa` numeric(4, 2) NULL, `result_status` varchar(10) NOT NULL, `published_at` datetime(6) NULL, `state` varchar(10) NOT NULL, `evidence` json NOT NULL, `actor_id` bigint NOT NULL, `term_registration_id` bigint unsigned NOT NULL UNIQUE);
--
-- Create constraint uq_assessment_component on model assessmentcomponent
--
ALTER TABLE `assessment_component` ADD CONSTRAINT `uq_assessment_component` UNIQUE (`course_offering_id`, `component_code`);
--
-- Create constraint uq_assessment_component_owner on model assessmentcomponent
--
ALTER TABLE `assessment_component` ADD CONSTRAINT `uq_assessment_component_owner` UNIQUE (`assessment_component_id`, `course_offering_id`);
--
-- Create constraint chk_m10_component_max on model assessmentcomponent
--
ALTER TABLE `assessment_component` ADD CONSTRAINT `chk_m10_component_max` CHECK (`maximum_marks` > 0);
--
-- Create constraint chk_m10_component_weight on model assessmentcomponent
--
ALTER TABLE `assessment_component` ADD CONSTRAINT `chk_m10_component_weight` CHECK ((`weightage_percent` IS NULL OR (`weightage_percent` >= 0 AND `weightage_percent` <= 100)));
--
-- Create index ix_m10_audit_object on field(s) resource, record_id, id of model audit
--
CREATE INDEX `ix_m10_audit_object` ON `platform_m10_audit` (`resource`, `record_id`, `id`);
--
-- Create index ix_m10_offering_events on field(s) course_offering, assessment_date, status of model assessmentevent
--
CREATE INDEX `ix_m10_offering_events` ON `assessment_event` (`course_offering_id`, `assessment_date`, `status`);
--
-- Create constraint uq_assessment_event_owner on model assessmentevent
--
ALTER TABLE `assessment_event` ADD CONSTRAINT `uq_assessment_event_owner` UNIQUE (`assessment_event_id`, `course_offering_id`);
--
-- Create constraint chk_m10_event_marks on model assessmentevent
--
ALTER TABLE `assessment_event` ADD CONSTRAINT `chk_m10_event_marks` CHECK ((`maximum_marks` > 0 AND (`reduced_maximum_marks` IS NULL OR (`reduced_maximum_marks` > 0 AND `reduced_maximum_marks` <= (`maximum_marks`)))));
--
-- Create constraint chk_m10_event_time on model assessmentevent
--
ALTER TABLE `assessment_event` ADD CONSTRAINT `chk_m10_event_time` CHECK ((`start_time` IS NULL OR `end_time` IS NULL OR `end_time` > (`start_time`)));
--
-- Create constraint chk_m10_event_attempt on model assessmentevent
--
ALTER TABLE `assessment_event` ADD CONSTRAINT `chk_m10_event_attempt` CHECK ((`attempt_number` >= 1 AND `attempt_number` <= 255));
--
-- Create constraint chk_m10_scale_dates on model gradescale
--
ALTER TABLE `grade_scale` ADD CONSTRAINT `chk_m10_scale_dates` CHECK ((`effective_to` IS NULL OR `effective_to` >= (`effective_from`)));
--
-- Create constraint uq_grade_rule on model graderule
--
ALTER TABLE `grade_rule` ADD CONSTRAINT `uq_grade_rule` UNIQUE (`grade_scale_id`, `grade_letter`);
--
-- Create constraint chk_m10_grade_range on model graderule
--
ALTER TABLE `grade_rule` ADD CONSTRAINT `chk_m10_grade_range` CHECK ((`grade_point` >= 0 AND `maximum_percentage` > (`minimum_percentage`) AND `maximum_percentage` <= 100 AND `minimum_percentage` >= 0));
--
-- Create constraint uq_m10_policy_revision on model calculationpolicy
--
ALTER TABLE `platform_m10_policy` ADD CONSTRAINT `uq_m10_policy_revision` UNIQUE (`course_offering_id`, `number`);
--
-- Create constraint uq_m10_publication on model publication
--
ALTER TABLE `platform_m10_publication` ADD CONSTRAINT `uq_m10_publication` UNIQUE (`resource`, `record_id`, `number`);
--
-- Create constraint uq_m10_receipt on model receipt
--
ALTER TABLE `platform_m10_receipt` ADD CONSTRAINT `uq_m10_receipt` UNIQUE (`actor_id`, `key`);
--
-- Create constraint uq_student_assessment on model studentassessmentmark
--
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `uq_student_assessment` UNIQUE (`assessment_event_id`, `course_registration_id`);
--
-- Create constraint chk_m10_mark_raw on model studentassessmentmark
--
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `chk_m10_mark_raw` CHECK ((`marks_obtained` IS NULL OR `marks_obtained` >= 0));
--
-- Create constraint chk_m10_mark_reduced on model studentassessmentmark
--
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `chk_m10_mark_reduced` CHECK ((`reduced_marks` IS NULL OR `reduced_marks` >= 0));
--
-- Create constraint uq_course_result_attempt on model studentcourseresult
--
ALTER TABLE `student_course_result` ADD CONSTRAINT `uq_course_result_attempt` UNIQUE (`course_registration_id`, `attempt_number`);
--
-- Create constraint chk_m10_course_result on model studentcourseresult
--
ALTER TABLE `student_course_result` ADD CONSTRAINT `chk_m10_course_result` CHECK ((`attempt_number` >= 1 AND `attempt_number` <= 255 AND `credits_earned` >= 0));
ALTER TABLE `assessment_component` ADD CONSTRAINT `assessment_component_actor_id_57c141aa_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `assessment_component` ADD CONSTRAINT `assessment_component_course_offering_id_a6722a30_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`);
ALTER TABLE `platform_m10_audit` ADD CONSTRAINT `platform_m10_audit_actor_id_5e2df263_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m10_audit` ADD CONSTRAINT `platform_m10_audit_course_offering_id_057ac455_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`);
ALTER TABLE `platform_m10_audit` ADD CONSTRAINT `platform_m10_audit_institution_id_5b43e70f_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_m10_policy` ADD CONSTRAINT `platform_m10_policy_actor_id_9621d19a_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m10_policy` ADD CONSTRAINT `platform_m10_policy_course_offering_id_c4c0ce46_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`);
ALTER TABLE `assessment_event` ADD CONSTRAINT `assessment_event_actor_id_4d11f235_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `assessment_event` ADD CONSTRAINT `assessment_event_assessment_component_3152bdf8_fk_assessmen` FOREIGN KEY (`assessment_component_id`) REFERENCES `assessment_component` (`assessment_component_id`);
ALTER TABLE `assessment_event` ADD CONSTRAINT `assessment_event_course_offering_id_dc58e12d_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`);
ALTER TABLE `assessment_event` ADD CONSTRAINT `assessment_event_policy_id_b4f889e1_fk_platform_m10_policy_id` FOREIGN KEY (`policy_id`) REFERENCES `platform_m10_policy` (`id`);
ALTER TABLE `grade_scale` ADD CONSTRAINT `grade_scale_actor_id_d7e96c46_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `grade_scale` ADD CONSTRAINT `grade_scale_institution_id_1d17d268_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `grade_rule` ADD CONSTRAINT `grade_rule_grade_scale_id_39a312f0_fk_grade_scale_grade_scale_id` FOREIGN KEY (`grade_scale_id`) REFERENCES `grade_scale` (`grade_scale_id`);
ALTER TABLE `platform_m10_publication` ADD CONSTRAINT `platform_m10_publica_actor_id_c5050684_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m10_publication` ADD CONSTRAINT `platform_m10_publica_institution_id_e4e90ce2_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_m10_receipt` ADD CONSTRAINT `platform_m10_receipt_actor_id_518bc555_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `student_assessment_m_actor_id_473965ad_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `student_assessment_m_assessment_event_id_b51552dc_fk_assessmen` FOREIGN KEY (`assessment_event_id`) REFERENCES `assessment_event` (`assessment_event_id`);
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `student_assessment_m_course_offering_id_7113739b_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`);
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `student_assessment_m_course_registration__32ff3428_fk_student_c` FOREIGN KEY (`course_registration_id`) REFERENCES `student_course_registration` (`course_registration_id`);
ALTER TABLE `student_course_result` ADD CONSTRAINT `student_course_result_actor_id_1550352f_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `student_course_result` ADD CONSTRAINT `student_course_resul_course_registration__12652408_fk_student_c` FOREIGN KEY (`course_registration_id`) REFERENCES `student_course_registration` (`course_registration_id`);
ALTER TABLE `student_course_result` ADD CONSTRAINT `student_course_resul_policy_id_6138a661_fk_platform_` FOREIGN KEY (`policy_id`) REFERENCES `platform_m10_policy` (`id`);
ALTER TABLE `student_term_result` ADD CONSTRAINT `student_term_result_actor_id_ea60d1ed_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `student_term_result` ADD CONSTRAINT `student_term_result_term_registration_id_5b0e3b21_fk_student_t` FOREIGN KEY (`term_registration_id`) REFERENCES `student_term_registration` (`term_registration_id`);

-- assessments_results 0002
--
-- Raw SQL operation
--
ALTER TABLE assessment_event ADD CONSTRAINT fk_m10_event_component FOREIGN KEY (assessment_component_id,course_offering_id) REFERENCES assessment_component (assessment_component_id,course_offering_id);
--
-- Raw SQL operation
--
ALTER TABLE student_assessment_mark ADD CONSTRAINT fk_m10_mark_event FOREIGN KEY (assessment_event_id,course_offering_id) REFERENCES assessment_event (assessment_event_id,course_offering_id);
--
-- Raw SQL operation
--
ALTER TABLE student_assessment_mark ADD CONSTRAINT fk_m10_mark_registration FOREIGN KEY (course_registration_id,course_offering_id) REFERENCES student_course_registration (course_registration_id,course_offering_id);

-- assessments_results 0003
--
-- Add field is_withheld to studentcourseresult
--
ALTER TABLE `student_course_result` ADD COLUMN `is_withheld` bool DEFAULT b'0' NOT NULL;
ALTER TABLE `student_course_result` ALTER COLUMN `is_withheld` DROP DEFAULT;
--
-- Add field is_withheld to studenttermresult
--
ALTER TABLE `student_term_result` ADD COLUMN `is_withheld` bool DEFAULT b'0' NOT NULL;
ALTER TABLE `student_term_result` ALTER COLUMN `is_withheld` DROP DEFAULT;

-- assessments_results 0004
--
-- Alter field attempt_number on studentcourseresult
--
ALTER TABLE `student_course_result` MODIFY `attempt_number` tinyint unsigned NOT NULL;
--
-- Create constraint chk_m10_event_status on model assessmentevent
--
ALTER TABLE `assessment_event` ADD CONSTRAINT `chk_m10_event_status` CHECK (`status` IN ('PLANNED', 'CONDUCTED', 'CANCELLED', 'PUBLISHED'));
--
-- Create constraint chk_m10_mark_status on model studentassessmentmark
--
ALTER TABLE `student_assessment_mark` ADD CONSTRAINT `chk_m10_mark_status` CHECK (`attendance_status` IN ('PRESENT', 'ABSENT', 'EXEMPTED', 'MALPRACTICE'));
--
-- Create constraint chk_m10_course_status on model studentcourseresult
--
ALTER TABLE `student_course_result` ADD CONSTRAINT `chk_m10_course_status` CHECK (`result_status` IN ('PASS', 'FAIL', 'ABSENT', 'WITHHELD', 'EXEMPTED', 'INCOMPLETE'));
--
-- Create constraint chk_m10_course_state on model studentcourseresult
--
ALTER TABLE `student_course_result` ADD CONSTRAINT `chk_m10_course_state` CHECK (`state` IN ('CALCULATED', 'PUBLISHED', 'WITHHELD'));
--
-- Create constraint chk_m10_term_status on model studenttermresult
--
ALTER TABLE `student_term_result` ADD CONSTRAINT `chk_m10_term_status` CHECK (`result_status` IN ('PASS', 'FAIL', 'PROMOTED', 'WITHHELD', 'INCOMPLETE'));
--
-- Create constraint chk_m10_term_credits on model studenttermresult
--
ALTER TABLE `student_term_result` ADD CONSTRAINT `chk_m10_term_credits` CHECK ((`credits_earned` >= 0 AND `credits_earned` <= (`credits_registered`) AND `credits_registered` >= 0));
--
-- Create constraint chk_m10_term_state on model studenttermresult
--
ALTER TABLE `student_term_result` ADD CONSTRAINT `chk_m10_term_state` CHECK (`state` IN ('CALCULATED', 'PUBLISHED', 'WITHHELD'));

-- tenancy 0009
--
-- Add field assessments_results to institutionmodule
--
ALTER TABLE `platform_institution_module` ADD COLUMN `assessments_results` bool DEFAULT b'0' NOT NULL;
ALTER TABLE `platform_institution_module` ALTER COLUMN `assessments_results` DROP DEFAULT;
