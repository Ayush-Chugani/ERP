# M11 local schema and query plans

Database: sims_reference_dev

## feedback_question_category

```sql

CREATE TABLE `feedback_question_category` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `feedback_category_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `category_code` varchar(30) NOT NULL,
  `category_name` varchar(100) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `actor_id` bigint NOT NULL,
  `institution_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`feedback_category_id`),
  UNIQUE KEY `category_code` (`category_code`),
  UNIQUE KEY `category_name` (`category_name`),
  KEY `feedback_question_ca_actor_id_199d2963_fk_user_acco` (`actor_id`),
  KEY `feedback_question_ca_institution_id_f832b01d_fk_instituti` (`institution_id`),
  CONSTRAINT `feedback_question_ca_actor_id_199d2963_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `feedback_question_ca_institution_id_f832b01d_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `feedback_question_category_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_question

```sql

CREATE TABLE `feedback_question` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `feedback_question_id` int unsigned NOT NULL AUTO_INCREMENT,
  `question_text` varchar(1000) NOT NULL,
  `response_type` varchar(15) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `rating_min` decimal(6,2) DEFAULT NULL,
  `rating_max` decimal(6,2) DEFAULT NULL,
  `rating_step` decimal(6,2) DEFAULT NULL,
  `text_limit` smallint unsigned DEFAULT NULL,
  `actor_id` bigint NOT NULL,
  `feedback_category_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`feedback_question_id`),
  KEY `feedback_question_actor_id_95b61a5d_fk_user_account_user_id` (`actor_id`),
  KEY `feedback_question_feedback_category_id_785c8f3e_fk_feedback_` (`feedback_category_id`),
  CONSTRAINT `feedback_question_actor_id_95b61a5d_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `feedback_question_feedback_category_id_785c8f3e_fk_feedback_` FOREIGN KEY (`feedback_category_id`) REFERENCES `feedback_question_category` (`feedback_category_id`),
  CONSTRAINT `chk_m11_response_type` CHECK ((`response_type` in (_utf8mb4'SINGLE_CHOICE',_utf8mb4'MULTIPLE_CHOICE',_utf8mb4'RATING',_utf8mb4'TEXT'))),
  CONSTRAINT `feedback_question_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `feedback_question_chk_2` CHECK ((`text_limit` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_choice

```sql

CREATE TABLE `feedback_choice` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `feedback_choice_id` int unsigned NOT NULL AUTO_INCREMENT,
  `choice_text` varchar(250) NOT NULL,
  `score` decimal(6,2) DEFAULT NULL,
  `display_order` smallint unsigned DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `actor_id` bigint NOT NULL,
  `feedback_question_id` int unsigned NOT NULL,
  PRIMARY KEY (`feedback_choice_id`),
  UNIQUE KEY `uq_feedback_choice` (`feedback_question_id`,`choice_text`),
  KEY `feedback_choice_actor_id_f46ec25a_fk_user_account_user_id` (`actor_id`),
  CONSTRAINT `feedback_choice_actor_id_f46ec25a_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `feedback_choice_feedback_question_id_9fcddc9f_fk_feedback_` FOREIGN KEY (`feedback_question_id`) REFERENCES `feedback_question` (`feedback_question_id`),
  CONSTRAINT `feedback_choice_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `feedback_choice_chk_2` CHECK ((`display_order` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_questionnaire

```sql

CREATE TABLE `feedback_questionnaire` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `questionnaire_id` int unsigned NOT NULL AUTO_INCREMENT,
  `questionnaire_code` varchar(30) NOT NULL,
  `questionnaire_name` varchar(150) NOT NULL,
  `questionnaire_type` varchar(11) NOT NULL,
  `is_anonymous` tinyint(1) NOT NULL,
  `status` varchar(7) NOT NULL,
  `actor_id` bigint NOT NULL,
  `institution_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`questionnaire_id`),
  UNIQUE KEY `questionnaire_code` (`questionnaire_code`),
  KEY `feedback_questionnaire_actor_id_e930d7eb_fk_user_account_user_id` (`actor_id`),
  KEY `feedback_questionnai_institution_id_1dbd37e8_fk_instituti` (`institution_id`),
  CONSTRAINT `feedback_questionnai_institution_id_1dbd37e8_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `feedback_questionnaire_actor_id_e930d7eb_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `chk_m11_questionnaire_state` CHECK ((`status` in (_utf8mb4'DRAFT',_utf8mb4'ACTIVE',_utf8mb4'RETIRED'))),
  CONSTRAINT `chk_m11_questionnaire_type` CHECK ((`questionnaire_type` in (_utf8mb4'COURSE',_utf8mb4'FACULTY',_utf8mb4'PROGRAMME',_utf8mb4'INSTITUTION',_utf8mb4'EXIT',_utf8mb4'OTHER'))),
  CONSTRAINT `feedback_questionnaire_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_questionnaire_item

```sql

CREATE TABLE `feedback_questionnaire_item` (
  `questionnaire_item_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `weightage` decimal(6,2) DEFAULT NULL,
  `display_order` smallint unsigned NOT NULL,
  `is_required` tinyint(1) NOT NULL,
  `feedback_question_id` int unsigned NOT NULL,
  `questionnaire_id` int unsigned NOT NULL,
  PRIMARY KEY (`questionnaire_item_id`),
  UNIQUE KEY `uq_questionnaire_question` (`questionnaire_id`,`feedback_question_id`),
  UNIQUE KEY `uq_m11_question_order` (`questionnaire_id`,`display_order`),
  KEY `feedback_questionnai_feedback_question_id_5da54aaa_fk_feedback_` (`feedback_question_id`),
  CONSTRAINT `feedback_questionnai_feedback_question_id_5da54aaa_fk_feedback_` FOREIGN KEY (`feedback_question_id`) REFERENCES `feedback_question` (`feedback_question_id`),
  CONSTRAINT `feedback_questionnai_questionnaire_id_b3288c78_fk_feedback_` FOREIGN KEY (`questionnaire_id`) REFERENCES `feedback_questionnaire` (`questionnaire_id`),
  CONSTRAINT `chk_m11_weight` CHECK (((`weightage` is null) or (`weightage` >= 0))),
  CONSTRAINT `feedback_questionnaire_item_chk_1` CHECK ((`display_order` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_cycle

```sql

CREATE TABLE `feedback_cycle` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `feedback_cycle_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `cycle_name` varchar(150) NOT NULL,
  `start_at` datetime(6) NOT NULL,
  `end_at` datetime(6) NOT NULL,
  `result_visibility` varchar(10) NOT NULL,
  `status` varchar(9) NOT NULL,
  `minimum_cohort` smallint unsigned NOT NULL,
  `allow_text_review` tinyint(1) NOT NULL,
  `target_policy` varchar(20) NOT NULL,
  `explicit_registrations` json NOT NULL,
  `frozen` json NOT NULL,
  `key_fingerprint` varchar(64) NOT NULL,
  `academic_term_id` int unsigned NOT NULL,
  `actor_id` bigint NOT NULL,
  `programme_id` smallint unsigned DEFAULT NULL,
  `questionnaire_id` int unsigned NOT NULL,
  PRIMARY KEY (`feedback_cycle_id`),
  KEY `ix_m11_cycle_window` (`academic_term_id`,`status`,`start_at`,`end_at`),
  KEY `feedback_cycle_actor_id_c6af24af_fk_user_account_user_id` (`actor_id`),
  KEY `feedback_cycle_programme_id_1d7e1e02_fk_programme_programme_id` (`programme_id`),
  KEY `feedback_cycle_questionnaire_id_af2ed4f1_fk_feedback_` (`questionnaire_id`),
  CONSTRAINT `feedback_cycle_academic_term_id_4b6efec8_fk_academic_` FOREIGN KEY (`academic_term_id`) REFERENCES `academic_term` (`academic_term_id`),
  CONSTRAINT `feedback_cycle_actor_id_c6af24af_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `feedback_cycle_programme_id_1d7e1e02_fk_programme_programme_id` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`),
  CONSTRAINT `feedback_cycle_questionnaire_id_af2ed4f1_fk_feedback_` FOREIGN KEY (`questionnaire_id`) REFERENCES `feedback_questionnaire` (`questionnaire_id`),
  CONSTRAINT `chk_feedback_cycle_dates` CHECK ((`end_at` > `start_at`)),
  CONSTRAINT `chk_m11_cohort` CHECK ((`minimum_cohort` >= 2)),
  CONSTRAINT `chk_m11_cycle_state` CHECK ((`status` in (_utf8mb4'SCHEDULED',_utf8mb4'OPEN',_utf8mb4'CLOSED',_utf8mb4'CANCELLED'))),
  CONSTRAINT `chk_m11_visibility` CHECK ((`result_visibility` in (_utf8mb4'HIDDEN',_utf8mb4'ADMIN_ONLY',_utf8mb4'FACULTY',_utf8mb4'PUBLIC'))),
  CONSTRAINT `feedback_cycle_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `feedback_cycle_chk_2` CHECK ((`minimum_cohort` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_response

```sql

CREATE TABLE `feedback_response` (
  `feedback_response_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `target_key` varchar(80) NOT NULL,
  `submitted_at` datetime(6) NOT NULL,
  `response_token` varchar(36) NOT NULL,
  `course_offering_id` bigint unsigned DEFAULT NULL,
  `faculty_assignment_id` bigint unsigned DEFAULT NULL,
  `feedback_cycle_id` bigint unsigned NOT NULL,
  `term_registration_id` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`feedback_response_id`),
  UNIQUE KEY `response_token` (`response_token`),
  KEY `ix_m11_response_target` (`feedback_cycle_id`,`target_key`),
  KEY `feedback_response_course_offering_id_4d40fc24_fk_course_of` (`course_offering_id`),
  KEY `feedback_response_faculty_assignment_i_8b864cb1_fk_faculty_c` (`faculty_assignment_id`),
  KEY `feedback_response_term_registration_id_0275495b_fk_student_t` (`term_registration_id`),
  CONSTRAINT `feedback_response_course_offering_id_4d40fc24_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`),
  CONSTRAINT `feedback_response_faculty_assignment_i_8b864cb1_fk_faculty_c` FOREIGN KEY (`faculty_assignment_id`) REFERENCES `faculty_course_assignment` (`faculty_assignment_id`),
  CONSTRAINT `feedback_response_feedback_cycle_id_e8f56d32_fk_feedback_` FOREIGN KEY (`feedback_cycle_id`) REFERENCES `feedback_cycle` (`feedback_cycle_id`),
  CONSTRAINT `feedback_response_term_registration_id_0275495b_fk_student_t` FOREIGN KEY (`term_registration_id`) REFERENCES `student_term_registration` (`term_registration_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_response_item

```sql

CREATE TABLE `feedback_response_item` (
  `feedback_response_item_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `numeric_score` decimal(6,2) DEFAULT NULL,
  `text_response` longtext,
  `feedback_choice_id` int unsigned DEFAULT NULL,
  `feedback_response_id` bigint unsigned NOT NULL,
  `questionnaire_item_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`feedback_response_item_id`),
  UNIQUE KEY `uq_feedback_response_item` (`feedback_response_id`,`questionnaire_item_id`),
  KEY `feedback_response_it_feedback_choice_id_897281d7_fk_feedback_` (`feedback_choice_id`),
  KEY `feedback_response_it_questionnaire_item_i_f2dca098_fk_feedback_` (`questionnaire_item_id`),
  CONSTRAINT `feedback_response_it_feedback_choice_id_897281d7_fk_feedback_` FOREIGN KEY (`feedback_choice_id`) REFERENCES `feedback_choice` (`feedback_choice_id`),
  CONSTRAINT `feedback_response_it_feedback_response_id_a7247804_fk_feedback_` FOREIGN KEY (`feedback_response_id`) REFERENCES `feedback_response` (`feedback_response_id`),
  CONSTRAINT `feedback_response_it_questionnaire_item_i_f2dca098_fk_feedback_` FOREIGN KEY (`questionnaire_item_id`) REFERENCES `feedback_questionnaire_item` (`questionnaire_item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## feedback_response_item_choice

```sql

CREATE TABLE `feedback_response_item_choice` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `feedback_choice_id` int unsigned NOT NULL,
  `feedback_response_item_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_m11_multiple_choice` (`feedback_response_item_id`,`feedback_choice_id`),
  KEY `feedback_response_it_feedback_choice_id_1c4e2693_fk_feedback_` (`feedback_choice_id`),
  CONSTRAINT `feedback_response_it_feedback_choice_id_1c4e2693_fk_feedback_` FOREIGN KEY (`feedback_choice_id`) REFERENCES `feedback_choice` (`feedback_choice_id`),
  CONSTRAINT `feedback_response_it_feedback_response_it_eaee4f90_fk_feedback_` FOREIGN KEY (`feedback_response_item_id`) REFERENCES `feedback_response_item` (`feedback_response_item_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## platform_m11_ledger

```sql

CREATE TABLE `platform_m11_ledger` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `fingerprint` varchar(64) NOT NULL,
  `request_digest` varchar(64) NOT NULL,
  `receipt` varchar(36) NOT NULL,
  `cycle_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `receipt` (`receipt`),
  UNIQUE KEY `uq_m11_once` (`cycle_id`,`fingerprint`),
  CONSTRAINT `platform_m11_ledger_cycle_id_d061614e_fk_feedback_` FOREIGN KEY (`cycle_id`) REFERENCES `feedback_cycle` (`feedback_cycle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## platform_m11_audit

```sql

CREATE TABLE `platform_m11_audit` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `action` varchar(60) NOT NULL,
  `resource` varchar(40) NOT NULL,
  `record_id` bigint unsigned NOT NULL,
  `before` json NOT NULL,
  `after` json NOT NULL,
  `reason` varchar(500) NOT NULL,
  `request_key` varchar(100) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `actor_id` bigint NOT NULL,
  `institution_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  KEY `platform_m11_audit_actor_id_fc5f1b08_fk_user_account_user_id` (`actor_id`),
  KEY `platform_m11_audit_institution_id_dc32fd13_fk_instituti` (`institution_id`),
  CONSTRAINT `platform_m11_audit_actor_id_fc5f1b08_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `platform_m11_audit_institution_id_dc32fd13_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `platform_m11_audit_chk_1` CHECK ((`record_id` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## platform_m11_command

```sql

CREATE TABLE `platform_m11_command` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `key` varchar(100) NOT NULL,
  `digest` varchar(64) NOT NULL,
  `result` json NOT NULL,
  `actor_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_m11_command` (`actor_id`,`key`),
  CONSTRAINT `platform_m11_command_actor_id_ceb8b43e_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## Query

```sql

SELECT * FROM feedback_cycle WHERE academic_term_id=1 AND status='OPEN' AND start_at<=NOW() AND end_at>NOW()

```

```

((1, 'SIMPLE', 'feedback_cycle', None, 'range', 'ix_m11_cycle_window', 'ix_m11_cycle_window', '50', None, 1, 100.0, 'Using index condition'),)

```

## Query

```sql

SELECT * FROM feedback_response WHERE feedback_cycle_id=1 AND target_key='course:1'

```

```

((1, 'SIMPLE', 'feedback_response', None, 'ref', 'ix_m11_response_target', 'ix_m11_response_target', '330', 'const,const', 1, 100.0, None),)

```

## Query

```sql

SELECT * FROM feedback_response_item WHERE feedback_response_id=1

```

```

((1, 'SIMPLE', 'feedback_response_item', None, 'ref', 'uq_feedback_response_item', 'uq_feedback_response_item', '8', 'const', 1, 100.0, None),)

```

Empty development database plans do not establish populated load performance or production latency.