"""Frozen canonical DDL."""
DDL = ['CREATE TABLE membership_type (\n    membership_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    type_code VARCHAR(50) NOT NULL UNIQUE,\n    type_name VARCHAR(150) NOT NULL UNIQUE,\n    is_active BOOLEAN NOT NULL DEFAULT TRUE\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;']
