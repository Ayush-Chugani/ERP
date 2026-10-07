--
-- Change Meta options on programmetermoffering
--
-- (no-op)
--
-- Create model RegistrationEvent
--
CREATE TABLE `platform_registration_event` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `event_type` varchar(60) NOT NULL, `payload` json NOT NULL, `created_at` datetime(6) NOT NULL, `audit_id` bigint NOT NULL UNIQUE);
--
-- Create model CommandReceipt
--
CREATE TABLE `platform_registration_receipt` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `key` varchar(100) NOT NULL, `digest` varchar(64) NOT NULL, `result` json NOT NULL, `created_at` datetime(6) NOT NULL, `actor_id` bigint NOT NULL, CONSTRAINT `uq_m7_command_receipt` UNIQUE (`actor_id`, `key`));
--
-- Create model EventDelivery
--
CREATE TABLE `platform_registration_delivery` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `consumer` varchar(80) NOT NULL, `delivered_at` datetime(6) NOT NULL, `event_id` bigint NOT NULL, CONSTRAINT `uq_m7_delivery` UNIQUE (`event_id`, `consumer`));
--
-- Create model RegistrationPolicy
--
CREATE TABLE `platform_registration_policy` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `maximum_credits` numeric(6, 1) NOT NULL, `minimum_credits` numeric(6, 1) NOT NULL, `version` bigint UNSIGNED NOT NULL CHECK (`version` >= 0), `updated_at` datetime(6) NOT NULL, `programme_id` smallint unsigned NOT NULL UNIQUE, `updated_by_id` bigint NOT NULL, CONSTRAINT `chk_m7_credit_policy` CHECK ((`maximum_credits` > 0 AND `minimum_credits` >= 0 AND `minimum_credits` <= (`maximum_credits`))));
ALTER TABLE `platform_registration_event` ADD CONSTRAINT `platform_registratio_audit_id_72018d0c_fk_platform_` FOREIGN KEY (`audit_id`) REFERENCES `platform_registration_audit` (`id`);
ALTER TABLE `platform_registration_receipt` ADD CONSTRAINT `platform_registratio_actor_id_48f973a5_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`);
ALTER TABLE `platform_registration_delivery` ADD CONSTRAINT `platform_registratio_event_id_b6f41a9b_fk_platform_` FOREIGN KEY (`event_id`) REFERENCES `platform_registration_event` (`id`);
ALTER TABLE `platform_registration_policy` ADD CONSTRAINT `platform_registratio_programme_id_11e030f3_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`);
ALTER TABLE `platform_registration_policy` ADD CONSTRAINT `platform_registratio_updated_by_id_28626498_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`);
