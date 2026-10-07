--
-- Create model AcademicYear
--
CREATE TABLE `academic_year` (`academic_year_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `year_code` varchar(9) COLLATE `utf8mb4_unicode_ci` NOT NULL UNIQUE, `start_date` date NOT NULL, `end_date` date NOT NULL, `status` varchar(7) DEFAULT 'PLANNED' NOT NULL);
--
-- Create model Semester
--
CREATE TABLE `semester` (`semester_id` tinyint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `semester_number` tinyint unsigned NOT NULL UNIQUE CHECK (`semester_number` >= 0), `semester_name` varchar(50) COLLATE `utf8mb4_unicode_ci` NOT NULL UNIQUE, CONSTRAINT `chk_semester_number` CHECK (`semester_number` > 0));
--
-- Create model AcademicTerm
--
CREATE TABLE `academic_term` (`academic_term_id` integer unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `term_code` varchar(20) COLLATE `utf8mb4_unicode_ci` NOT NULL, `term_name` varchar(100) COLLATE `utf8mb4_unicode_ci` NOT NULL, `term_type` varchar(6) NOT NULL, `start_date` date NOT NULL, `end_date` date NOT NULL, `registration_start_date` date NULL, `registration_end_date` date NULL, `status` varchar(17) DEFAULT 'PLANNED' NOT NULL, `academic_year_id` smallint unsigned NOT NULL);
--
-- Create model CalendarAudit
--
CREATE TABLE `platform_calendar_audit` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `action` varchar(24) NOT NULL, `resource` varchar(32) NOT NULL, `record_id` bigint UNSIGNED NOT NULL CHECK (`record_id` >= 0), `timestamp` datetime(6) NOT NULL, `correlation_id` varchar(64) NOT NULL, `reason` varchar(250) NOT NULL, `before` json NOT NULL, `after` json NOT NULL, `actor_id` bigint NOT NULL, `institution_id` smallint unsigned NULL);
--
-- Create model TimeSlot
--
CREATE TABLE `time_slot` (`time_slot_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `slot_code` varchar(20) COLLATE `utf8mb4_unicode_ci` NOT NULL, `start_time` time(6) NOT NULL, `end_time` time(6) NOT NULL, `is_break` bool DEFAULT b'0' NOT NULL, `is_active` bool DEFAULT b'1' NOT NULL, `campus_id` smallint unsigned NOT NULL);
ALTER TABLE `academic_year` ADD CONSTRAINT `chk_academic_year_dates` CHECK (`end_date` > (`start_date`));
ALTER TABLE `academic_year` ADD CONSTRAINT `chk_academic_year_status` CHECK (`status` IN ('PLANNED', 'ACTIVE', 'CLOSED'));
CREATE INDEX `calendar_year_status` ON `academic_year` (`status`, `start_date`);
ALTER TABLE `academic_term` ADD CONSTRAINT `academic_term_academic_year_id_b69e46f3_fk_academic_` FOREIGN KEY (`academic_year_id`) REFERENCES `academic_year` (`academic_year_id`);
ALTER TABLE `academic_term` ADD CONSTRAINT `uq_term_code` UNIQUE (`academic_year_id`, `term_code`);
ALTER TABLE `academic_term` ADD CONSTRAINT `chk_term_dates` CHECK (`end_date` >= (`start_date`));
ALTER TABLE `academic_term` ADD CONSTRAINT `chk_term_registration_dates` CHECK ((`registration_start_date` IS NULL OR `registration_end_date` IS NULL OR `registration_end_date` >= (`registration_start_date`)));
ALTER TABLE `academic_term` ADD CONSTRAINT `chk_academic_term_status` CHECK (`status` IN ('PLANNED', 'REGISTRATION_OPEN', 'ACTIVE', 'CLOSED'));
ALTER TABLE `academic_term` ADD CONSTRAINT `chk_academic_term_type` CHECK (`term_type` IN ('ODD', 'EVEN', 'SUMMER', 'ANNUAL', 'OTHER'));
CREATE INDEX `calendar_term_status` ON `academic_term` (`status`, `start_date`);
ALTER TABLE `platform_calendar_audit` ADD CONSTRAINT `platform_calendar_au_actor_id_f187fa7e_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_calendar_audit` ADD CONSTRAINT `platform_calendar_au_institution_id_8d94ca54_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`);
CREATE INDEX `calendar_audit_record` ON `platform_calendar_audit` (`resource`, `record_id`);
ALTER TABLE `time_slot` ADD CONSTRAINT `time_slot_campus_id_8f2f4728_fk_campus_campus_id` FOREIGN KEY (`campus_id`) REFERENCES `campus` (`campus_id`);
ALTER TABLE `time_slot` ADD CONSTRAINT `uq_time_slot` UNIQUE (`campus_id`, `slot_code`);
ALTER TABLE `time_slot` ADD CONSTRAINT `chk_time_slot` CHECK (`end_time` > (`start_time`));
CREATE INDEX `calendar_slot_available` ON `time_slot` (`campus_id`, `is_active`, `start_time`);
