-- Applied within evidence.0001 after the exact source tables; never run twice.
ALTER TABLE evidence_document_version
 ADD COLUMN current_document_id BIGINT UNSIGNED GENERATED ALWAYS AS
   (CASE WHEN is_current THEN evidence_document_id ELSE NULL END) STORED,
 ADD CONSTRAINT uq_m33_current_document UNIQUE (current_document_id);
-- evidence.0002 installs append-only audit/version guards. No speculative indexes.
-- Existing production tables require explicit schema adoption review before migration.
