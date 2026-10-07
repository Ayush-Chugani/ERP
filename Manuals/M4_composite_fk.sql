--
-- Raw SQL operation
--
ALTER TABLE curriculum_scheme ADD CONSTRAINT fk_scheme_specialization_programme FOREIGN KEY (specialization_id, programme_id) REFERENCES programme_specialization (specialization_id, programme_id);
