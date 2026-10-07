-- M8 reviewed deployment DDL generated from Django migrations. Apply through migrate, not in addition to migrate. Requires existing M1-M7 schema.
--
-- Create model FacultyAssignment
--
CREATE TABLE `faculty_course_assignment` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `faculty_assignment_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `assignment_role` varchar(18) NOT NULL, `workload_hours` numeric(6, 2) NULL, `start_date` date NOT NULL, `end_date` date NULL, `assignment_status` varchar(9) NOT NULL, `course_offering_section_id` bigint unsigned NOT NULL, `created_by_id` bigint NOT NULL, `employee_id` bigint unsigned NOT NULL, `updated_by_id` bigint NOT NULL);
--
-- Create model OutboxEvent
--
CREATE TABLE `platform_m8_outbox` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `event_id` char(32) NOT NULL UNIQUE, `topic` varchar(60) NOT NULL, `payload` json NOT NULL, `created_at` datetime(6) NOT NULL, `institution_id` smallint unsigned NOT NULL);
--
-- Create model EventReceipt
--
CREATE TABLE `platform_m8_event_receipt` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `consumer` varchar(80) NOT NULL, `processed_at` datetime(6) NOT NULL, `event_id` bigint NOT NULL);
--
-- Create model PublishedOccurrence
--
CREATE TABLE `platform_m8_occurrence` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `date` date NOT NULL, `start_time` time(6) NOT NULL, `end_time` time(6) NOT NULL, `student_ids` json NOT NULL, `course_offering_section_id` bigint unsigned NOT NULL, `employee_id` bigint unsigned NOT NULL, `room_id` integer unsigned NOT NULL);
--
-- Create model OccurrenceException
--
CREATE TABLE `platform_m8_exception` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `sequence` integer UNSIGNED NOT NULL CHECK (`sequence` >= 0), `kind` varchar(10) NOT NULL, `date` date NOT NULL, `start_time` time(6) NOT NULL, `end_time` time(6) NOT NULL, `reason` varchar(500) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `faculty_assignment_id` bigint unsigned NOT NULL, `room_id` integer unsigned NOT NULL, `occurrence_id` bigint NOT NULL);
--
-- Create model ResourceAvailability
--
CREATE TABLE `platform_m8_availability` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `effective_from` date NOT NULL, `effective_to` date NOT NULL, `day_of_week` smallint UNSIGNED NOT NULL CHECK (`day_of_week` >= 0), `start_time` time(6) NOT NULL, `end_time` time(6) NOT NULL, `reason` varchar(500) NOT NULL, `created_by_id` bigint NOT NULL, `employee_id` bigint unsigned NULL, `institution_id` smallint unsigned NOT NULL, `room_id` integer unsigned NULL, `updated_by_id` bigint NOT NULL);
--
-- Create model SchedulingPolicy
--
CREATE TABLE `platform_m8_policy` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `weekly_limit` numeric(6, 2) NOT NULL, `require_competency` bool NOT NULL, `max_sessions` smallint UNSIGNED NOT NULL CHECK (`max_sessions` >= 0), `max_solver_jobs` smallint UNSIGNED NOT NULL CHECK (`max_solver_jobs` >= 0), `created_by_id` bigint NOT NULL, `institution_id` smallint unsigned NOT NULL UNIQUE, `updated_by_id` bigint NOT NULL);
--
-- Create model TimetableAudit
--
CREATE TABLE `platform_m8_audit` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `action` varchar(60) NOT NULL, `resource` varchar(60) NOT NULL, `record_id` bigint UNSIGNED NOT NULL CHECK (`record_id` >= 0), `before` json NOT NULL, `after` json NOT NULL, `authority` json NOT NULL, `reason` varchar(500) NOT NULL, `correlation_id` varchar(64) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `institution_id` smallint unsigned NOT NULL);
--
-- Create model TimetablePlan
--
CREATE TABLE `platform_m8_plan` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `name` varchar(150) NOT NULL, `created_by_id` bigint NOT NULL, `programme_term_offering_id` bigint unsigned NOT NULL UNIQUE, `updated_by_id` bigint NOT NULL);
--
-- Create model TimetableRevision
--
CREATE TABLE `platform_m8_revision` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `number` integer UNSIGNED NOT NULL CHECK (`number` >= 0), `status` varchar(10) NOT NULL, `created_by_id` bigint NOT NULL, `plan_id` bigint NOT NULL, `updated_by_id` bigint NOT NULL);
--
-- Create model SolverJob
--
CREATE TABLE `platform_m8_solver_job` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `status` varchar(10) NOT NULL, `seed` integer UNSIGNED NOT NULL CHECK (`seed` >= 0), `input_snapshot` json NOT NULL, `input_digest` varchar(64) NOT NULL, `result` json NOT NULL, `started_at` datetime(6) NULL, `finished_at` datetime(6) NULL, `created_by_id` bigint NOT NULL, `updated_by_id` bigint NOT NULL, `revision_id` bigint NOT NULL);
--
-- Add field revision to publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD COLUMN `revision_id` bigint NOT NULL , ADD CONSTRAINT `platform_m8_occurren_revision_id_2695866f_fk_platform_` FOREIGN KEY (`revision_id`) REFERENCES `platform_m8_revision`(`id`);
--
-- Create model TimetableSession
--
CREATE TABLE `timetable_session` (`version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `created_at` datetime(6) NOT NULL, `updated_at` datetime(6) NOT NULL, `timetable_session_id` bigint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `day_of_week` smallint UNSIGNED NOT NULL CHECK (`day_of_week` >= 0), `effective_from` date NOT NULL, `effective_to` date NOT NULL, `course_offering_section_id` bigint unsigned NOT NULL, `created_by_id` bigint NOT NULL, `faculty_assignment_id` bigint unsigned NULL, `revision_id` bigint NOT NULL, `room_id` integer unsigned NULL, `time_slot_id` smallint unsigned NOT NULL, `updated_by_id` bigint NOT NULL);
--
-- Add field session to publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD COLUMN `session_id` bigint unsigned NOT NULL , ADD CONSTRAINT `platform_m8_occurren_session_id_42eec02d_fk_timetable` FOREIGN KEY (`session_id`) REFERENCES `timetable_session`(`timetable_session_id`);
--
-- Create model CommandReceipt
--
CREATE TABLE `platform_m8_command_receipt` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `key` varchar(100) NOT NULL, `digest` varchar(64) NOT NULL, `result` json NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, CONSTRAINT `uq_m8_command_receipt` UNIQUE (`actor_id`, `key`));
--
-- Create index ix_m8_employee_dates on field(s) employee, assignment_status, start_date, end_date of model facultyassignment
--
CREATE INDEX `ix_m8_employee_dates` ON `faculty_course_assignment` (`employee_id`, `assignment_status`, `start_date`, `end_date`);
--
-- Create constraint uq_faculty_course_assignment on model facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `uq_faculty_course_assignment` UNIQUE (`course_offering_section_id`, `employee_id`, `assignment_role`, `start_date`);
--
-- Create constraint uq_m8_faculty_section on model facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `uq_m8_faculty_section` UNIQUE (`faculty_assignment_id`, `course_offering_section_id`);
--
-- Create constraint chk_m8_assignment_dates on model facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `chk_m8_assignment_dates` CHECK ((`end_date` IS NULL OR `end_date` >= (`start_date`)));
--
-- Create constraint chk_m8_workload on model facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `chk_m8_workload` CHECK ((`workload_hours` IS NULL OR `workload_hours` > 0));
--
-- Create constraint chk_m8_assignment_role on model facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `chk_m8_assignment_role` CHECK (`assignment_role` IN ('PRIMARY_INSTRUCTOR', 'CO_INSTRUCTOR', 'LAB_INSTRUCTOR', 'TUTOR', 'COORDINATOR', 'OTHER'));
--
-- Create constraint chk_m8_assignment_status on model facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `chk_m8_assignment_status` CHECK (`assignment_status` IN ('PLANNED', 'ACTIVE', 'COMPLETED', 'CANCELLED'));
--
-- Create constraint uq_m8_event_consumer on model eventreceipt
--
ALTER TABLE `platform_m8_event_receipt` ADD CONSTRAINT `uq_m8_event_consumer` UNIQUE (`event_id`, `consumer`);
--
-- Create constraint uq_m8_exception_sequence on model occurrenceexception
--
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `uq_m8_exception_sequence` UNIQUE (`occurrence_id`, `sequence`);
--
-- Create constraint chk_m8_exception_kind on model occurrenceexception
--
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `chk_m8_exception_kind` CHECK (`kind` IN ('CANCEL', 'MOVE', 'SUBSTITUTE'));
--
-- Create constraint chk_m8_exception_clock on model occurrenceexception
--
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `chk_m8_exception_clock` CHECK (`end_time` > (`start_time`));
--
-- Create constraint chk_m8_availability_resource on model resourceavailability
--
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `chk_m8_availability_resource` CHECK (((`employee_id` IS NULL AND `room_id` IS NOT NULL) OR (`employee_id` IS NOT NULL AND `room_id` IS NULL)));
--
-- Create constraint chk_m8_availability_dates on model resourceavailability
--
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `chk_m8_availability_dates` CHECK (`effective_to` >= (`effective_from`));
--
-- Create constraint chk_m8_availability_clock on model resourceavailability
--
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `chk_m8_availability_clock` CHECK (`end_time` > (`start_time`));
--
-- Create constraint chk_m8_availability_day on model resourceavailability
--
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `chk_m8_availability_day` CHECK ((`day_of_week` >= 1 AND `day_of_week` <= 7));
--
-- Create constraint chk_m8_weekly_limit on model schedulingpolicy
--
ALTER TABLE `platform_m8_policy` ADD CONSTRAINT `chk_m8_weekly_limit` CHECK (`weekly_limit` > 0);
--
-- Create constraint chk_m8_session_limit on model schedulingpolicy
--
ALTER TABLE `platform_m8_policy` ADD CONSTRAINT `chk_m8_session_limit` CHECK ((`max_sessions` >= 1 AND `max_sessions` <= 500));
--
-- Create constraint chk_m8_job_limit on model schedulingpolicy
--
ALTER TABLE `platform_m8_policy` ADD CONSTRAINT `chk_m8_job_limit` CHECK ((`max_solver_jobs` >= 1 AND `max_solver_jobs` <= 10));
--
-- Create constraint uq_m8_revision_number on model timetablerevision
--
ALTER TABLE `platform_m8_revision` ADD CONSTRAINT `uq_m8_revision_number` UNIQUE (`plan_id`, `number`);
--
-- Create constraint chk_m8_revision_status on model timetablerevision
--
ALTER TABLE `platform_m8_revision` ADD CONSTRAINT `chk_m8_revision_status` CHECK (`status` IN ('DRAFT', 'REVIEW', 'APPROVED', 'PUBLISHED', 'SUPERSEDED', 'WITHDRAWN', 'ARCHIVED'));
--
-- Create index ix_m8_solver_queue on field(s) status, created_at of model solverjob
--
CREATE INDEX `ix_m8_solver_queue` ON `platform_m8_solver_job` (`status`, `created_at`);
--
-- Create constraint chk_m8_solver_status on model solverjob
--
ALTER TABLE `platform_m8_solver_job` ADD CONSTRAINT `chk_m8_solver_status` CHECK (`status` IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'ACCEPTED'));
--
-- Create index ix_m8_room_interval on field(s) room, day_of_week, effective_from, effective_to of model timetablesession
--
CREATE INDEX `ix_m8_room_interval` ON `timetable_session` (`room_id`, `day_of_week`, `effective_from`, `effective_to`);
--
-- Create index ix_m8_faculty_interval on field(s) faculty_assignment, day_of_week, effective_from of model timetablesession
--
CREATE INDEX `ix_m8_faculty_interval` ON `timetable_session` (`faculty_assignment_id`, `day_of_week`, `effective_from`);
--
-- Create index ix_m8_revision_section on field(s) revision, course_offering_section of model timetablesession
--
CREATE INDEX `ix_m8_revision_section` ON `timetable_session` (`revision_id`, `course_offering_section_id`);
--
-- Create constraint chk_day_of_week on model timetablesession
--
ALTER TABLE `timetable_session` ADD CONSTRAINT `chk_day_of_week` CHECK ((`day_of_week` >= 1 AND `day_of_week` <= 7));
--
-- Create constraint chk_m8_session_dates on model timetablesession
--
ALTER TABLE `timetable_session` ADD CONSTRAINT `chk_m8_session_dates` CHECK (`effective_to` >= (`effective_from`));
--
-- Create index ix_m8_occurrence_room on field(s) date, room, start_time of model publishedoccurrence
--
CREATE INDEX `ix_m8_occurrence_room` ON `platform_m8_occurrence` (`date`, `room_id`, `start_time`);
--
-- Create index ix_m8_occurrence_faculty on field(s) date, employee, start_time of model publishedoccurrence
--
CREATE INDEX `ix_m8_occurrence_faculty` ON `platform_m8_occurrence` (`date`, `employee_id`, `start_time`);
--
-- Create constraint uq_m8_occurrence on model publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `uq_m8_occurrence` UNIQUE (`session_id`, `date`);
--
-- Create constraint chk_m8_occurrence_clock on model publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `chk_m8_occurrence_clock` CHECK (`end_time` > (`start_time`));
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `faculty_course_assig_course_offering_sect_922189bc_fk_course_of` FOREIGN KEY (`course_offering_section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `faculty_course_assig_created_by_id_50e53e37_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `faculty_course_assig_employee_id_6a6f8d32_fk_employee_` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`);
ALTER TABLE `faculty_course_assignment` ADD CONSTRAINT `faculty_course_assig_updated_by_id_cedab5d3_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_outbox` ADD CONSTRAINT `platform_m8_outbox_institution_id_2f7daa4b_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_m8_event_receipt` ADD CONSTRAINT `platform_m8_event_re_event_id_0427b61a_fk_platform_` FOREIGN KEY (`event_id`) REFERENCES `platform_m8_outbox` (`id`);
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `platform_m8_occurren_course_offering_sect_01b0143f_fk_course_of` FOREIGN KEY (`course_offering_section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `platform_m8_occurren_employee_id_38731deb_fk_employee_` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`);
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `platform_m8_occurrence_room_id_2c0d3eb4_fk_room_room_id` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`);
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `platform_m8_exception_actor_id_886c4d60_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `platform_m8_exceptio_faculty_assignment_i_74bbdfb7_fk_faculty_c` FOREIGN KEY (`faculty_assignment_id`) REFERENCES `faculty_course_assignment` (`faculty_assignment_id`);
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `platform_m8_exception_room_id_108f02f1_fk_room_room_id` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`);
ALTER TABLE `platform_m8_exception` ADD CONSTRAINT `platform_m8_exceptio_occurrence_id_f08311bf_fk_platform_` FOREIGN KEY (`occurrence_id`) REFERENCES `platform_m8_occurrence` (`id`);
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `platform_m8_availabi_created_by_id_6adeddd4_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `platform_m8_availabi_employee_id_5a28f454_fk_employee_` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`);
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `platform_m8_availabi_institution_id_d8ef172d_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `platform_m8_availability_room_id_d613ed32_fk_room_room_id` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`);
ALTER TABLE `platform_m8_availability` ADD CONSTRAINT `platform_m8_availabi_updated_by_id_19ab4705_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_policy` ADD CONSTRAINT `platform_m8_policy_created_by_id_7fb8ec50_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_policy` ADD CONSTRAINT `platform_m8_policy_institution_id_9090d7bc_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_m8_policy` ADD CONSTRAINT `platform_m8_policy_updated_by_id_16a49692_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_audit` ADD CONSTRAINT `platform_m8_audit_actor_id_653e335c_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_audit` ADD CONSTRAINT `platform_m8_audit_institution_id_d9f1c596_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
ALTER TABLE `platform_m8_plan` ADD CONSTRAINT `platform_m8_plan_created_by_id_0d114e37_fk_user_account_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_plan` ADD CONSTRAINT `platform_m8_plan_programme_term_offer_f743773d_fk_programme` FOREIGN KEY (`programme_term_offering_id`) REFERENCES `programme_term_offering` (`programme_term_offering_id`);
ALTER TABLE `platform_m8_plan` ADD CONSTRAINT `platform_m8_plan_updated_by_id_a5e23467_fk_user_account_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_revision` ADD CONSTRAINT `platform_m8_revision_created_by_id_99fb5542_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_revision` ADD CONSTRAINT `platform_m8_revision_plan_id_e93455f3_fk_platform_m8_plan_id` FOREIGN KEY (`plan_id`) REFERENCES `platform_m8_plan` (`id`);
ALTER TABLE `platform_m8_revision` ADD CONSTRAINT `platform_m8_revision_updated_by_id_5ebe8c34_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_solver_job` ADD CONSTRAINT `platform_m8_solver_j_created_by_id_31bd2f04_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_solver_job` ADD CONSTRAINT `platform_m8_solver_j_updated_by_id_36f0a74d_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_solver_job` ADD CONSTRAINT `platform_m8_solver_j_revision_id_671a62d5_fk_platform_` FOREIGN KEY (`revision_id`) REFERENCES `platform_m8_revision` (`id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_course_offering_sect_9efda599_fk_course_of` FOREIGN KEY (`course_offering_section_id`) REFERENCES `course_offering_section` (`course_offering_section_id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_created_by_id_ad0f7f4e_fk_user_account_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_faculty_assignment_i_489557f3_fk_faculty_c` FOREIGN KEY (`faculty_assignment_id`) REFERENCES `faculty_course_assignment` (`faculty_assignment_id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_revision_id_51d48d0e_fk_platform_` FOREIGN KEY (`revision_id`) REFERENCES `platform_m8_revision` (`id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_room_id_33ab747f_fk_room_room_id` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_time_slot_id_e7b64de8_fk_time_slot` FOREIGN KEY (`time_slot_id`) REFERENCES `time_slot` (`time_slot_id`);
ALTER TABLE `timetable_session` ADD CONSTRAINT `timetable_session_updated_by_id_97152a70_fk_user_account_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_command_receipt` ADD CONSTRAINT `platform_m8_command__actor_id_495bf352_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
--
-- Raw SQL operation
--
ALTER TABLE timetable_session ADD CONSTRAINT fk_m8_session_faculty_owner FOREIGN KEY (faculty_assignment_id, course_offering_section_id) REFERENCES faculty_course_assignment (faculty_assignment_id, course_offering_section_id);
--
-- Alter field finished_at on solverjob
--
-- (no-op)
--
-- Alter field started_at on solverjob
--
-- (no-op)
--
-- Change Meta options on facultyassignment
--
-- (no-op)
--
-- Add field cross_department_authorized to facultyassignment
--
ALTER TABLE `faculty_course_assignment` ADD COLUMN `cross_department_authorized` bool DEFAULT b'0' NOT NULL;
ALTER TABLE `faculty_course_assignment` ALTER COLUMN `cross_department_authorized` DROP DEFAULT;
--
-- Create model WorkloadOverride
--
CREATE TABLE `platform_m8_workload_override` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `effective_from` date NOT NULL, `effective_to` date NOT NULL, `weekly_limit` numeric(6, 2) NOT NULL, `reason` varchar(500) NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, `employee_id` bigint unsigned NOT NULL, CONSTRAINT `chk_m8_override_dates` CHECK (`effective_to` >= (`effective_from`)), CONSTRAINT `chk_m8_override_limit` CHECK (`weekly_limit` > 0));
ALTER TABLE `platform_m8_workload_override` ADD CONSTRAINT `platform_m8_workload_actor_id_b1d4d611_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_m8_workload_override` ADD CONSTRAINT `platform_m8_workload_employee_id_7cb87e5a_fk_employee_` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`);
--
-- Add field class_section to publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD COLUMN `class_section_id` bigint unsigned NULL , ADD CONSTRAINT `platform_m8_occurren_class_section_id_62c04553_fk_class_sec` FOREIGN KEY (`class_section_id`) REFERENCES `class_section`(`class_section_id`);
--
-- Add field class_batch to publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` ADD COLUMN `class_batch_id` bigint unsigned NULL , ADD CONSTRAINT `platform_m8_occurren_class_batch_id_cb3f9073_fk_class_bat` FOREIGN KEY (`class_batch_id`) REFERENCES `class_batch`(`class_batch_id`);
--
-- Raw SQL operation
--
UPDATE platform_m8_occurrence o JOIN course_offering_section s ON o.course_offering_section_id = s.course_offering_section_id SET o.class_section_id = s.class_section_id, o.class_batch_id = s.class_batch_id;
--
-- Alter field class_section on publishedoccurrence
--
ALTER TABLE `platform_m8_occurrence` DROP FOREIGN KEY `platform_m8_occurren_class_section_id_62c04553_fk_class_sec`;
ALTER TABLE `platform_m8_occurrence` MODIFY `class_section_id` bigint unsigned NOT NULL;
ALTER TABLE `platform_m8_occurrence` ADD CONSTRAINT `platform_m8_occurren_class_section_id_62c04553_fk_class_sec` FOREIGN KEY (`class_section_id`) REFERENCES `class_section` (`class_section_id`);
--
-- Add field teaching_timetable to institutionmodule
--
ALTER TABLE `platform_institution_module` ADD COLUMN `teaching_timetable` bool DEFAULT b'0' NOT NULL;
ALTER TABLE `platform_institution_module` ALTER COLUMN `teaching_timetable` DROP DEFAULT;