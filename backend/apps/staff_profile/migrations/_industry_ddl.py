DDL = [
    "CREATE TABLE industry_sector (\n    industry_sector_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    sector_code VARCHAR(50) NOT NULL UNIQUE,\n    sector_name VARCHAR(150) NOT NULL UNIQUE,\n    description VARCHAR(500) NULL,\n    is_active BOOLEAN NOT NULL DEFAULT TRUE\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
]
