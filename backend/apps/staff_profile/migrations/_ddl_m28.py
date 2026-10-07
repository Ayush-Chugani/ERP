DDL = [
    "CREATE TABLE cocurricular_category (\n    cocurricular_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    category_code VARCHAR(50) NOT NULL UNIQUE,\n    category_name VARCHAR(150) NOT NULL UNIQUE,\n    is_active BOOLEAN NOT NULL DEFAULT TRUE\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
]
