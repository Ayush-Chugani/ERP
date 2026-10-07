-- Reference DDL only. Execute Django migrations, including the Python status seed.
-- teaching_timetable 0006
--
-- Create constraint uq_m9_occurrence_section on model publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `uq_m9_occurrence_section` UNIQUE (`id`, `course_offering_section_id`);
--
-- Create constraint uq_m9_timetable_section on model timetablesession
--
ALTER TABLE `timetable_session` ADD CONSTRAINT `uq_m9_timetable_section` UNIQUE (`timetable_session_id`, `course_offering_section_id`);

-- attendance_lesson_plan 0001
--
-- Create model AttendanceStatus
--
CREATE TABLE `attendance_status` (`attendance_status_id` tinyint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `status_code` varchar(20) NOT NULL UNIQUE, `status_name` varchar(50) NOT NULL UNIQUE, `counts_as_present` bool NOT NULL, `is_active` bool NOT NULL);
--
-- Create model AuditEvent
--
CREATE TABLE `platform_m9_audit` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `authority` json NOT NULL, `action` varchar(50) NOT NULL, `resource` varchar(50) NOT NULL, `record_id` bigint UNSIGNED NOT NULL CHECK (`record_id` >= 0), `reason` varchar(1000) NOT NULL, `request_key` varchar(100) NOT NULL, `before` json NOT NULL, `after` json NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `section_id` bigint unsigned NOT NULL);
--
-- Create model CommandReceipt
--
CREATE TABLE `platform_m9_receipt` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `key` varchar(100) NOT NULL, `digest` varchar(64) NOT NULL, `result` json NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL);
--
-- Create model LessonRevision
--
CREATE TABLE `platform_m9_lesson_revision` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `number` integer UNSIGNED NOT NULL CHECK (`number` >= 0), `topics` json NOT NULL, `reason` varchar(500) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `section_id` bigint unsigned NOT NULL);
--
-- Create model OutboxEvent
--
CREATE TABLE `platform_m9_outbox` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `topic` varchar(80) NOT NULL, `payload` json NOT NULL, `created_at` datetime(6) NOT NULL, `audit_id` bigint NOT NULL UNIQUE);
--
-- Create model Delivery
--
CREATE TABLE `platform_m9_delivery` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `consumer` varchar(80) NOT NULL, `created_at` datetime(6) NOT NULL, `event_id` bigint NOT NULL);
--
-- Create model PolicyRevision
--
CREATE TABLE `platform_m9_policy` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `number` integer UNSIGNED NOT NULL CHECK (`number` >= 0), `basis` varchar(8) NOT NULL, `rules` json NOT NULL, `threshold` numeric(5, 2) NOT NULL, `edit_days` smallint UNSIGNED NOT NULL CHECK (`edit_days` >= 0), `correction_days` smallint UNSIGNED NOT NULL CHECK (`correction_days` >= 0), `reason` varchar(500) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `section_id` bigint unsigned NOT NULL);
--
-- Create model ClassSession
--
CREATE TABLE `class_session` (`class_session_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `occurrence_sequence` integer UNSIGNED NOT NULL CHECK (`occurrence_sequence` >= 0), `session_date` date NOT NULL, `start_time` time(6) NOT NULL, `end_time` time(6) NOT NULL, `session_type` varchar(9) COLLATE `utf8mb4_unicode_ci` NOT NULL, `planned_topic` longtext NOT NULL, `topic_covered` longtext NOT NULL, `class_number` smallint UNSIGNED NOT NULL CHECK (`class_number` >= 0), `session_status` varchar(11) NOT NULL, `register_status` varchar(9) NOT NULL, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `finalized_at` datetime(6) NULL, `calendar_reference` varchar(200) NOT NULL, `course_offering_section_id` bigint unsigned NOT NULL, `created_by_id` bigint NOT NULL, `faculty_assignment_id` bigint unsigned NOT NULL, `occurrence_id` bigint NULL UNIQUE, `room_id` integer unsigned NOT NULL, `source_session_id` bigint unsigned NULL, `timetable_session_id` bigint unsigned NULL, `updated_by_id` bigint NOT NULL, `policy_id` bigint NOT NULL);
--
-- Create model StudentAttendance
--
CREATE TABLE `student_attendance` (`attendance_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `marked_at` datetime(6) NULL, `remarks` varchar(500) NOT NULL, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `credit` numeric(12, 4) NULL, `denominator` numeric(12, 4) NULL, `attendance_status_id` tinyint unsigned NULL, `class_session_id` bigint unsigned NOT NULL, `course_offering_section_id` bigint unsigned NOT NULL, `course_offering_section_student_id` bigint unsigned NOT NULL, `marked_by_user_id` bigint NULL, `student_id` bigint unsigned NOT NULL);
--
-- Create model CorrectionRequest
--
CREATE TABLE `attendance_correction_request` (`attendance_correction_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `attendance_version` bigint UNSIGNED NOT NULL CHECK (`attendance_version` >= 0), `reason` varchar(1000) NOT NULL, `evidence_reference` varchar(200) NOT NULL, `request_status` varchar(9) NOT NULL, `resolution_remarks` varchar(1000) NOT NULL, `requested_at` datetime(6) NOT NULL, `resolved_at` datetime(6) NULL, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `pending_key` bigint UNSIGNED GENERATED ALWAYS AS (CASE WHEN `request_status` = 'PENDING' THEN `attendance_id` ELSE NULL END) STORED UNIQUE, `old_status_id` tinyint unsigned NOT NULL, `requested_by_id` bigint NOT NULL, `requested_status_id` tinyint unsigned NOT NULL, `resolved_by_id` bigint NULL, `attendance_id` bigint unsigned NOT NULL);
--
-- Create model TopicCoverage
--
CREATE TABLE `platform_m9_coverage` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `topic_key` varchar(50) NOT NULL, `percent` numeric(5, 2) NOT NULL, `minutes` smallint UNSIGNED NOT NULL CHECK (`minutes` >= 0), `remarks` varchar(500) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `lesson_revision_id` bigint NOT NULL, `session_id` bigint unsigned NOT NULL);
--
-- Create index ix_m9_history on field(s) resource, record_id, id of model auditevent
--
CREATE INDEX `ix_m9_history` ON `platform_m9_audit` (`resource`, `record_id`, `id`);
--
-- Create constraint uq_m9_receipt on model commandreceipt
--
ALTER TABLE `platform_m9_receipt` ADD CONSTRAINT `uq_m9_receipt` UNIQUE (`actor_id`, `key`);
--
-- Create constraint uq_m9_lesson_number on model lessonrevision
--
ALTER TABLE `platform_m9_lesson_revision` ADD CONSTRAINT `uq_m9_lesson_number` UNIQUE (`section_id`, `number`);
--
-- Create constraint uq_m9_delivery on model delivery
--
ALTER TABLE `platform_m9_delivery` ADD CONSTRAINT `uq_m9_delivery` UNIQUE (`event_id`, `consumer`);
--
-- Create constraint uq_m9_policy_number on model policyrevision
--
ALTER TABLE `platform_m9_policy` ADD CONSTRAINT `uq_m9_policy_number` UNIQUE (`section_id`, `number`);
--
-- Create constraint chk_m9_threshold on model policyrevision
--
ALTER TABLE `platform_m9_policy` ADD CONSTRAINT `chk_m9_threshold` CHECK ((`threshold` >= 0 AND `threshold` <= 100));
--
-- Create constraint chk_m9_basis on model policyrevision
--
ALTER TABLE `platform_m9_policy` ADD CONSTRAINT `chk_m9_basis` CHECK (`basis` IN ('SESSION', 'DURATION'));
--
-- Create index ix_m9_section_date on field(s) course_offering_section, session_date, register_status of model classsession
--
CREATE INDEX `ix_m9_section_date` ON `class_session` (`course_offering_section_id`, `session_date`, `register_status`);
--
-- Create constraint uq_class_session on model classsession
--
ALTER TABLE `class_session` ADD CONSTRAINT `uq_class_session` UNIQUE (`course_offering_section_id`, `session_date`, `start_time`);
--
-- Create constraint uq_class_session_owner on model classsession
--
ALTER TABLE `class_session` ADD CONSTRAINT `uq_class_session_owner` UNIQUE (`class_session_id`, `course_offering_section_id`);
--
-- Create constraint uq_m9_class_number on model classsession
--
ALTER TABLE `class_session` ADD CONSTRAINT `uq_m9_class_number` UNIQUE (`course_offering_section_id`, `class_number`);
--
-- Create constraint chk_class_session_time on model classsession
--
ALTER TABLE `class_session` ADD CONSTRAINT `chk_class_session_time` CHECK (`end_time` > (`start_time`));
--
-- Create constraint chk_m9_session_status on model classsession
--
ALTER TABLE `class_session` ADD CONSTRAINT `chk_m9_session_status` CHECK (`session_status` IN ('PLANNED', 'CONDUCTED', 'CANCELLED', 'RESCHEDULED'));
--
-- Create constraint chk_m9_register_status on model classsession
--
ALTER TABLE `class_session` ADD CONSTRAINT `chk_m9_register_status` CHECK (`register_status` IN ('UNOPENED', 'OPEN', 'FINALIZED', 'REOPENED'));
--
-- Create index ix_m9_student_session on field(s) student, class_session of model studentattendance
--
CREATE INDEX `ix_m9_student_session` ON `student_attendance` (`student_id`, `class_session_id`);
--
-- Create constraint uq_m9_attendance_roster on model studentattendance
--
ALTER TABLE `student_attendance` ADD CONSTRAINT `uq_m9_attendance_roster` UNIQUE (`class_session_id`, `course_offering_section_student_id`);
--
-- Create constraint uq_m9_attendance_student on model studentattendance
--
ALTER TABLE `student_attendance` ADD CONSTRAINT `uq_m9_attendance_student` UNIQUE (`class_session_id`, `student_id`);
--
-- Create constraint chk_m9_contribution on model studentattendance
--
ALTER TABLE `student_attendance` ADD CONSTRAINT `chk_m9_contribution` CHECK (((`credit` IS NULL AND `denominator` IS NULL) OR (`credit` >= 0 AND `denominator` >= (`credit`))));
--
-- Create index ix_m9_correction_queue on field(s) request_status, requested_at of model correctionrequest
--
CREATE INDEX `ix_m9_correction_queue` ON `attendance_correction_request` (`request_status`, `requested_at`);
--
-- Create constraint chk_m9_correction_state on model correctionrequest
--
ALTER TABLE `attendance_correction_request` ADD CONSTRAINT `chk_m9_correction_state` CHECK (`request_status` IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'));
--
-- Create constraint chk_m9_coverage on model topiccoverage
--
ALTER TABLE `platform_m9_coverage` ADD CONSTRAINT `chk_m9_coverage` CHECK ((`minutes` > 0 AND `percent` > 0 AND `percent` <= 100));
ALTER TABLE `platform_m9_audit` ADD CONSTRAINT `platform_m9_audit_actor_id_8b41afc8_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m9_audit` ADD CONSTRAINT `platform_m9_audit_section_id_b7e6ba1f_fk_course_of` FOREIGN KEY (`section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `platform_m9_receipt` ADD CONSTRAINT `platform_m9_receipt_actor_id_e0798a8e_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m9_lesson_revision` ADD CONSTRAINT `platform_m9_lesson_r_actor_id_8247b233_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m9_lesson_revision` ADD CONSTRAINT `platform_m9_lesson_r_section_id_f3a80a69_fk_course_of` FOREIGN KEY (`section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `platform_m9_outbox` ADD CONSTRAINT `platform_m9_outbox_audit_id_6086dcc8_fk_platform_m9_audit_id` FOREIGN KEY (`audit_id`) REFERENCES `platform_m9_audit` (`id`);
ALTER TABLE `platform_m9_delivery` ADD CONSTRAINT `platform_m9_delivery_event_id_4e285102_fk_platform_m9_outbox_id` FOREIGN KEY (`event_id`) REFERENCES `platform_m9_outbox` (`id`);
ALTER TABLE `platform_m9_policy` ADD CONSTRAINT `platform_m9_policy_actor_id_173dfe85_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m9_policy` ADD CONSTRAINT `platform_m9_policy_section_id_f78a2138_fk_course_of` FOREIGN KEY (`section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_course_offering_sect_7c2287d2_fk_course_of` FOREIGN KEY (`course_offering_section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_created_by_id_5f564ae3_fk_user_account_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_faculty_assignment_i_4f531bbb_fk_faculty_c` FOREIGN KEY (`faculty_assignment_id`) REFERENCES `faculty_course_assignment` (`faculty_assignment_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_occurrence_id_4db04247_fk_platform_` FOREIGN KEY (`occurrence_id`) REFERENCES `platform_m8_occurrence` (`id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_room_id_f536b85e_fk_room_room_id` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_source_session_id_18c375de_fk_class_ses` FOREIGN KEY (`source_session_id`) REFERENCES `class_session` (`class_session_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_timetable_session_id_efb99205_fk_timetable` FOREIGN KEY (`timetable_session_id`) REFERENCES `timetable_session` (`timetable_session_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_updated_by_id_c4284cf0_fk_user_account_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `class_session` ADD CONSTRAINT `class_session_policy_id_70e46716_fk_platform_m9_policy_id` FOREIGN KEY (`policy_id`) REFERENCES `platform_m9_policy` (`id`);
ALTER TABLE `student_attendance` ADD CONSTRAINT `student_attendance_attendance_status_id_8251c200_fk_attendanc` FOREIGN KEY (`attendance_status_id`) REFERENCES `attendance_status` (`attendance_status_id`);
ALTER TABLE `student_attendance` ADD CONSTRAINT `student_attendance_class_session_id_1a1a3a96_fk_class_ses` FOREIGN KEY (`class_session_id`) REFERENCES `class_session` (`class_session_id`);
ALTER TABLE `student_attendance` ADD CONSTRAINT `student_attendance_course_offering_sect_cf5d485c_fk_course_of` FOREIGN KEY (`course_offering_section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `student_attendance` ADD CONSTRAINT `student_attendance_course_offering_sect_06991b2b_fk_course_of` FOREIGN KEY (`course_offering_section_student_id`) REFERENCES `course_offering_section_student` (`course_offering_section_student_id`);
ALTER TABLE `student_attendance` ADD CONSTRAINT `student_attendance_marked_by_user_id_0f88e083_fk_user_acco` FOREIGN KEY (`marked_by_user_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `student_attendance` ADD CONSTRAINT `student_attendance_student_id_04f80790_fk_student_student_id` FOREIGN KEY (`student_id`) REFERENCES `student` (`student_id`);
ALTER TABLE `attendance_correction_request` ADD CONSTRAINT `attendance_correctio_old_status_id_28042dba_fk_attendanc` FOREIGN KEY (`old_status_id`) REFERENCES `attendance_status` (`attendance_status_id`);
ALTER TABLE `attendance_correction_request` ADD CONSTRAINT `attendance_correctio_requested_by_id_1512e723_fk_user_acco` FOREIGN KEY (`requested_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `attendance_correction_request` ADD CONSTRAINT `attendance_correctio_requested_status_id_c5b91404_fk_attendanc` FOREIGN KEY (`requested_status_id`) REFERENCES `attendance_status` (`attendance_status_id`);
ALTER TABLE `attendance_correction_request` ADD CONSTRAINT `attendance_correctio_resolved_by_id_db2af7e5_fk_user_acco` FOREIGN KEY (`resolved_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `attendance_correction_request` ADD CONSTRAINT `attendance_correctio_attendance_id_2674aaee_fk_student_a` FOREIGN KEY (`attendance_id`) REFERENCES `student_attendance` (`attendance_id`);
ALTER TABLE `platform_m9_coverage` ADD CONSTRAINT `platform_m9_coverage_actor_id_e188562d_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m9_coverage` ADD CONSTRAINT `platform_m9_coverage_lesson_revision_id_09ff0d8d_fk_platform_` FOREIGN KEY (`lesson_revision_id`) REFERENCES `platform_m9_lesson_revision` (`id`);
ALTER TABLE `platform_m9_coverage` ADD CONSTRAINT `platform_m9_coverage_session_id_d1b8fc0f_fk_class_ses` FOREIGN KEY (`session_id`) REFERENCES `class_session` (`class_session_id`);

-- attendance_lesson_plan 0002
--
-- Raw SQL operation
--
ALTER TABLE class_session ADD CONSTRAINT fk_m9_faculty_section FOREIGN KEY (faculty_assignment_id, course_offering_section_id) REFERENCES faculty_course_assignment (faculty_assignment_id, course_offering_section_id);
--
-- Raw SQL operation
--
ALTER TABLE class_session ADD CONSTRAINT fk_m9_timetable_section FOREIGN KEY (timetable_session_id, course_offering_section_id) REFERENCES timetable_session (timetable_session_id, course_offering_section_id);
--
-- Raw SQL operation
--
ALTER TABLE class_session ADD CONSTRAINT fk_m9_occurrence_section FOREIGN KEY (occurrence_id, course_offering_section_id) REFERENCES platform_m8_occurrence (id, course_offering_section_id);
--
-- Raw SQL operation
--
ALTER TABLE class_session ADD CONSTRAINT fk_m9_session_type FOREIGN KEY (course_offering_section_id, session_type) REFERENCES course_offering_section (course_offering_section_id, session_type);
--
-- Raw SQL operation
--
ALTER TABLE student_attendance ADD CONSTRAINT fk_m9_attendance_session FOREIGN KEY (class_session_id, course_offering_section_id) REFERENCES class_session (class_session_id, course_offering_section_id);
--
-- Raw SQL operation
--
ALTER TABLE student_attendance ADD CONSTRAINT fk_m9_attendance_roster FOREIGN KEY (course_offering_section_student_id, course_offering_section_id) REFERENCES course_offering_section_student (course_offering_section_student_id, course_offering_section_id);
--
-- Raw Python operation
--
-- THIS OPERATION CANNOT BE WRITTEN AS SQL

-- attendance_lesson_plan 0003
--
-- Add field exclusion_reason to studentattendance
--
ALTER TABLE `student_attendance` ADD COLUMN `exclusion_reason` varchar(500) DEFAULT '' NOT NULL;
ALTER TABLE `student_attendance` ALTER COLUMN `exclusion_reason` DROP DEFAULT;
--
-- Add field is_eligible to studentattendance
--
ALTER TABLE `student_attendance` ADD COLUMN `is_eligible` bool DEFAULT b'1' NOT NULL;
ALTER TABLE `student_attendance` ALTER COLUMN `is_eligible` DROP DEFAULT;

-- tenancy 0008
--
-- Add field attendance_lesson_plan to institutionmodule
--
ALTER TABLE `platform_institution_module` ADD COLUMN `attendance_lesson_plan` bool DEFAULT b'0' NOT NULL;
ALTER TABLE `platform_institution_module` ALTER COLUMN `attendance_lesson_plan` DROP DEFAULT;
