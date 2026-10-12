CREATE DATABASE IF NOT EXISTS gym_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gym_management;

CREATE TABLE address (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 street VARCHAR(255) NOT NULL,
 city VARCHAR(100) NOT NULL,
 state CHAR(2) NOT NULL,
 zip VARCHAR(10) NOT NULL
);

CREATE TABLE person (
 person_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 address_id BIGINT UNSIGNED NULL,
 first_name VARCHAR(100) NOT NULL,
 last_name VARCHAR(100) NOT NULL,
 DOB DATE NULL,
 email VARCHAR(255) NOT NULL,
 phone VARCHAR(20) NULL,
 is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
 CONSTRAINT uq_person_email UNIQUE(email),
 CONSTRAINT fk_person_address FOREIGN KEY(address_id) REFERENCES address(id) ON DELETE SET NULL
);

CREATE TABLE gym_location (
 location_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 address_id BIGINT UNSIGNED NOT NULL,
 name VARCHAR(150) NOT NULL,
 phone VARCHAR(20) NOT NULL,
 size VARCHAR(50) NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 open_date DATE NULL,
 CONSTRAINT fk_gym_address FOREIGN KEY(address_id) REFERENCES address(id) ON DELETE RESTRICT
);

CREATE TABLE subscription (
 subscription_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 subscription_type VARCHAR(80) NOT NULL,
 status VARCHAR(30) NOT NULL,
 current_period_end TIMESTAMP NULL,
 cost_monthly DECIMAL(10,2) NULL,
 annual_fee DECIMAL(10,2) NULL,
 cancellation_fee DECIMAL(10,2) NULL,
 CONSTRAINT chk_subscription_cost CHECK (cost_monthly IS NULL OR cost_monthly >= 0),
 CONSTRAINT chk_subscription_annual CHECK (annual_fee IS NULL OR annual_fee >= 0),
 CONSTRAINT chk_subscription_cancel CHECK (cancellation_fee IS NULL OR cancellation_fee >= 0)
);

CREATE TABLE employee (
 employee_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 person_id BIGINT UNSIGNED NOT NULL,
 employee_type VARCHAR(80) NOT NULL,
 hire_date DATE NOT NULL,
 termination_date DATE NULL,
 employment_status VARCHAR(30) NOT NULL DEFAULT 'active',
 is_hourly BOOLEAN NOT NULL,
 hours_worked DECIMAL(10,2) NULL,
 UNIQUE KEY uq_employee_person (person_id),
 CONSTRAINT fk_employee_person FOREIGN KEY(person_id) REFERENCES person(person_id) ON DELETE RESTRICT,
 CONSTRAINT chk_employee_dates CHECK (termination_date IS NULL OR termination_date >= hire_date),
 CONSTRAINT chk_employee_hours CHECK (hours_worked IS NULL OR hours_worked >= 0)
);

CREATE TABLE member (
 member_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 person_id BIGINT UNSIGNED NOT NULL,
 subscription_id BIGINT UNSIGNED NULL,
 home_location BIGINT UNSIGNED NULL,
 membership_type BIGINT UNSIGNED NULL,
 pfp_url VARCHAR(2048) NULL,
 created_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 start_date DATE NOT NULL,
 end_date DATE NULL,
 is_inactive BOOLEAN NOT NULL DEFAULT FALSE,
 is_banned BOOLEAN NOT NULL DEFAULT FALSE,
 UNIQUE KEY uq_member_person(person_id),
 CONSTRAINT fk_member_person FOREIGN KEY(person_id) REFERENCES person(person_id) ON DELETE RESTRICT,
 CONSTRAINT fk_member_subscription FOREIGN KEY(subscription_id) REFERENCES subscription(subscription_id) ON DELETE RESTRICT,
 CONSTRAINT fk_member_location FOREIGN KEY(home_location) REFERENCES gym_location(location_id) ON DELETE SET NULL,
 CONSTRAINT chk_member_dates CHECK(end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE membership (
 membership_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 subscription_id BIGINT UNSIGNED NOT NULL,
 plan_name VARCHAR(100) NOT NULL,
 access_level SMALLINT UNSIGNED NOT NULL,
 invited_at TIMESTAMP NULL,
 CONSTRAINT fk_membership_subscription FOREIGN KEY(subscription_id) REFERENCES subscription(subscription_id) ON DELETE RESTRICT
);

ALTER TABLE member
 ADD CONSTRAINT fk_member_membership_type FOREIGN KEY(membership_type) REFERENCES membership(membership_id) ON DELETE SET NULL;

CREATE TABLE employee_location (
 employee_id BIGINT UNSIGNED NOT NULL,
 location_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY(employee_id, location_id),
 CONSTRAINT fk_el_employee FOREIGN KEY(employee_id) REFERENCES employee(employee_id) ON DELETE CASCADE,
 CONSTRAINT fk_el_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE CASCADE
);

CREATE TABLE person_address (
 person_id BIGINT UNSIGNED NOT NULL,
 address_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY(person_id, address_id),
 CONSTRAINT fk_pa_person FOREIGN KEY(person_id) REFERENCES person(person_id) ON DELETE CASCADE,
 CONSTRAINT fk_pa_address FOREIGN KEY(address_id) REFERENCES address(id) ON DELETE CASCADE
);

CREATE TABLE equipment (
 equipment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 location_id BIGINT UNSIGNED NOT NULL,
 name VARCHAR(150) NOT NULL,
 item_number BIGINT UNSIGNED NOT NULL,
 brand VARCHAR(100) NULL,
 status VARCHAR(40) NOT NULL DEFAULT 'operational',
 UNIQUE KEY uq_equipment_location_item(location_id, item_number),
 CONSTRAINT fk_equipment_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE RESTRICT
);

CREATE TABLE hours (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 location_id BIGINT UNSIGNED NOT NULL,
 day_of_week SMALLINT UNSIGNED NOT NULL,
 open_time TIME NULL,
 close_time TIME NULL,
 is_closed BOOLEAN NOT NULL DEFAULT FALSE,
 UNIQUE KEY uq_hours_location_day(location_id, day_of_week),
 CONSTRAINT fk_hours_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE CASCADE,
 CONSTRAINT chk_day_of_week CHECK(day_of_week BETWEEN 0 AND 6),
 CONSTRAINT chk_hours_closed CHECK(is_closed = TRUE OR (open_time IS NOT NULL AND close_time IS NOT NULL))
);

CREATE TABLE check_in (
 check_in_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 location_id BIGINT UNSIGNED NOT NULL,
 member_id BIGINT UNSIGNED NOT NULL,
 time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 is_clear BOOLEAN NOT NULL DEFAULT TRUE,
 entry_method VARCHAR(50) NOT NULL,
 CONSTRAINT fk_checkin_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE RESTRICT,
 CONSTRAINT fk_checkin_member FOREIGN KEY(member_id) REFERENCES member(member_id) ON DELETE RESTRICT
);

CREATE TABLE maintenance (
 maintenance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 employee_id BIGINT UNSIGNED NULL,
 location_id BIGINT UNSIGNED NOT NULL,
 equipment_id BIGINT UNSIGNED NULL,
 reported_date DATE NOT NULL,
 notes TEXT NULL,
 is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
 CONSTRAINT fk_maintenance_employee FOREIGN KEY(employee_id) REFERENCES employee(employee_id) ON DELETE SET NULL,
 CONSTRAINT fk_maintenance_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE RESTRICT,
 CONSTRAINT fk_maintenance_equipment FOREIGN KEY(equipment_id) REFERENCES equipment(equipment_id) ON DELETE SET NULL
);

CREATE TABLE employee_account (
 account_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 employee_id BIGINT UNSIGNED NOT NULL,
 employment_type VARCHAR(50) NOT NULL,
 pay_rate DECIMAL(10,2) NOT NULL,
 pay_frequency VARCHAR(30) NOT NULL,
 payroll_date DATE NULL,
 YTD_salary DECIMAL(12,2) NOT NULL DEFAULT 0,
 bank_routing_number VARCHAR(9) NULL,
 SSN VARCHAR(11) NULL,
 available_PTO MEDIUMINT UNSIGNED NOT NULL DEFAULT 0,
 UNIQUE KEY uq_employee_account_employee(employee_id),
 CONSTRAINT fk_account_employee FOREIGN KEY(employee_id) REFERENCES employee(employee_id) ON DELETE RESTRICT,
 CONSTRAINT chk_pay_rate CHECK(pay_rate >= 0),
 CONSTRAINT chk_ytd_salary CHECK(YTD_salary >= 0)
);

CREATE TABLE `transaction` (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 location_id BIGINT UNSIGNED NULL,
 member_id BIGINT UNSIGNED NOT NULL,
 transaction_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 amount DECIMAL(12,2) NOT NULL,
 is_deposit BOOLEAN NOT NULL DEFAULT FALSE,
 subscription_id BIGINT UNSIGNED NULL,
 maintenance_id BIGINT UNSIGNED NULL,
 equipment_id BIGINT UNSIGNED NULL,
 CONSTRAINT fk_transaction_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE SET NULL,
 CONSTRAINT fk_transaction_member FOREIGN KEY(member_id) REFERENCES member(member_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transaction_subscription FOREIGN KEY(subscription_id) REFERENCES subscription(subscription_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transaction_maintenance FOREIGN KEY(maintenance_id) REFERENCES maintenance(maintenance_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transaction_equipment FOREIGN KEY(equipment_id) REFERENCES equipment(equipment_id) ON DELETE RESTRICT
);
