--
-- Raw Python operation
--
-- THIS OPERATION CANNOT BE WRITTEN AS SQL
--
-- Create model AdmissionCategory
--
CREATE TABLE `admission_category` (`is_active` bool DEFAULT b'1' NOT NULL, `admission_category_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `category_code` varchar(30) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `category_name` varchar(100) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `description` varchar(500) COLLATE `utf8mb4_0900_ai_ci` NULL);
--
-- Create model BloodGroup
--
CREATE TABLE `blood_group` (`is_active` bool DEFAULT b'1' NOT NULL, `blood_group_id` tinyint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `blood_group_code` varchar(5) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE);
--
-- Create model Country
--
CREATE TABLE `country` (`is_active` bool DEFAULT b'1' NOT NULL, `country_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `iso_code` char(2) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `country_name` varchar(100) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE);
--
-- Create model DocumentType
--
CREATE TABLE `document_type` (`is_active` bool DEFAULT b'1' NOT NULL, `document_type_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `document_code` varchar(30) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `document_name` varchar(100) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `requires_verification` bool DEFAULT b'1' NOT NULL);
--
-- Create model Gender
--
CREATE TABLE `gender` (`is_active` bool DEFAULT b'1' NOT NULL, `gender_id` tinyint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `gender_code` varchar(20) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `gender_name` varchar(50) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE);
--
-- Create model Religion
--
CREATE TABLE `religion` (`is_active` bool DEFAULT b'1' NOT NULL, `religion_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `religion_code` varchar(20) COLLATE `utf8mb4_0900_ai_ci` NULL UNIQUE, `religion_name` varchar(100) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE);
--
-- Create model SocialCategory
--
CREATE TABLE `social_category` (`is_active` bool DEFAULT b'1' NOT NULL, `social_category_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `category_code` varchar(20) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE, `category_name` varchar(100) COLLATE `utf8mb4_0900_ai_ci` NOT NULL UNIQUE);
--
-- Create model Caste
--
CREATE TABLE `caste` (`is_active` bool DEFAULT b'1' NOT NULL, `caste_id` integer unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `caste_code` varchar(30) COLLATE `utf8mb4_0900_ai_ci` NULL UNIQUE, `caste_name` varchar(150) COLLATE `utf8mb4_0900_ai_ci` NOT NULL, `uncategorized_caste_name` varchar(150) COLLATE `utf8mb4_0900_ai_ci` GENERATED ALWAYS AS (CASE WHEN `social_category_id` IS NULL THEN `caste_name` ELSE NULL END) STORED, `social_category_id` smallint unsigned NULL);
--
-- Create model State
--
CREATE TABLE `state` (`is_active` bool DEFAULT b'1' NOT NULL, `state_id` smallint unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `state_code` varchar(10) COLLATE `utf8mb4_0900_ai_ci` NOT NULL, `state_name` varchar(100) COLLATE `utf8mb4_0900_ai_ci` NOT NULL, `country_id` smallint unsigned NOT NULL);
--
-- Create model SubCaste
--
CREATE TABLE `sub_caste` (`is_active` bool DEFAULT b'1' NOT NULL, `sub_caste_id` integer unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, `sub_caste_code` varchar(30) COLLATE `utf8mb4_0900_ai_ci` NULL, `sub_caste_name` varchar(150) COLLATE `utf8mb4_0900_ai_ci` NOT NULL, `caste_id` integer unsigned NOT NULL);
--
-- Create constraint uq_caste_name_category on model caste
--
ALTER TABLE `caste` ADD CONSTRAINT `uq_caste_name_category` UNIQUE (`social_category_id`, `caste_name`);
--
-- Create constraint uq_caste_uncategorized_name on model caste
--
ALTER TABLE `caste` ADD CONSTRAINT `uq_caste_uncategorized_name` UNIQUE (`uncategorized_caste_name`);
--
-- Create constraint uq_state_country_code on model state
--
ALTER TABLE `state` ADD CONSTRAINT `uq_state_country_code` UNIQUE (`country_id`, `state_code`);
--
-- Create constraint uq_state_country_name on model state
--
ALTER TABLE `state` ADD CONSTRAINT `uq_state_country_name` UNIQUE (`country_id`, `state_name`);
--
-- Create constraint uq_sub_caste on model subcaste
--
ALTER TABLE `sub_caste` ADD CONSTRAINT `uq_sub_caste` UNIQUE (`caste_id`, `sub_caste_name`);
ALTER TABLE `caste` ADD CONSTRAINT `caste_social_category_id_378dd6e2_fk_social_ca` FOREIGN KEY (`social_category_id`) REFERENCES `social_category` (`social_category_id`);
ALTER TABLE `state` ADD CONSTRAINT `state_country_id_6b36f831_fk_country_country_id` FOREIGN KEY (`country_id`) REFERENCES `country` (`country_id`);
ALTER TABLE `sub_caste` ADD CONSTRAINT `sub_caste_caste_id_bc95f10f_fk_caste_caste_id` FOREIGN KEY (`caste_id`) REFERENCES `caste` (`caste_id`);
