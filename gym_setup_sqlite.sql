PRAGMA foreign_keys = ON;
CREATE TABLE address (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 street TEXT NOT NULL,
 city TEXT NOT NULL,
 state TEXT NOT NULL,
 zip TEXT NOT NULL
);

CREATE TABLE person (
 person_id INTEGER PRIMARY KEY AUTOINCREMENT,
 address_id INTEGER NULL,
 first_name TEXT NOT NULL,
 last_name TEXT NOT NULL,
 DOB TEXT NULL,
 email TEXT NOT NULL,
 phone TEXT NULL,
 is_deleted INTEGER NOT NULL DEFAULT FALSE,
 CONSTRAINT uq_person_email UNIQUE(email),
 CONSTRAINT fk_person_address FOREIGN KEY(address_id) REFERENCES address(id) ON DELETE SET NULL
);

CREATE TABLE gym_location (
 location_id INTEGER PRIMARY KEY AUTOINCREMENT,
 address_id INTEGER NOT NULL,
 name TEXT NOT NULL,
 phone TEXT NOT NULL,
 size TEXT NULL,
 is_active INTEGER NOT NULL DEFAULT TRUE,
 open_date TEXT NULL,
 CONSTRAINT fk_gym_address FOREIGN KEY(address_id) REFERENCES address(id) ON DELETE RESTRICT
);

CREATE TABLE subscription (
 subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
 subscription_type TEXT NOT NULL,
 status TEXT NOT NULL,
 current_period_end TEXT NULL,
 cost_monthly NUMERIC NULL,
 annual_fee NUMERIC NULL,
 cancellation_fee NUMERIC NULL,
 CONSTRAINT chk_subscription_cost CHECK (cost_monthly IS NULL OR cost_monthly >= 0),
 CONSTRAINT chk_subscription_annual CHECK (annual_fee IS NULL OR annual_fee >= 0),
 CONSTRAINT chk_subscription_cancel CHECK (cancellation_fee IS NULL OR cancellation_fee >= 0)
);

CREATE TABLE employee (
 employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
 person_id INTEGER NOT NULL,
 employee_type TEXT NOT NULL,
 hire_date TEXT NOT NULL,
 termination_date TEXT NULL,
 employment_status TEXT NOT NULL DEFAULT 'active',
 is_hourly INTEGER NOT NULL,
 hours_worked NUMERIC NULL,
 CONSTRAINT uq_employee_person UNIQUE(person_id),
 CONSTRAINT fk_employee_person FOREIGN KEY(person_id) REFERENCES person(person_id) ON DELETE RESTRICT,
 CONSTRAINT chk_employee_dates CHECK (termination_date IS NULL OR termination_date >= hire_date),
 CONSTRAINT chk_employee_hours CHECK (hours_worked IS NULL OR hours_worked >= 0)
);

CREATE TABLE member (
 member_id INTEGER PRIMARY KEY AUTOINCREMENT,
 person_id INTEGER NOT NULL,
 subscription_id INTEGER NULL,
 home_location INTEGER NULL,
 membership_type INTEGER NULL,
 pfp_url TEXT NULL,
 created_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 start_date TEXT NOT NULL,
 end_date TEXT NULL,
 is_inactive INTEGER NOT NULL DEFAULT FALSE,
 is_banned INTEGER NOT NULL DEFAULT FALSE,
 CONSTRAINT uq_member_person UNIQUE(person_id),
 CONSTRAINT fk_member_person FOREIGN KEY(person_id) REFERENCES person(person_id) ON DELETE RESTRICT,
 CONSTRAINT fk_member_subscription FOREIGN KEY(subscription_id) REFERENCES subscription(subscription_id) ON DELETE RESTRICT,
 CONSTRAINT fk_member_location FOREIGN KEY(home_location) REFERENCES gym_location(location_id) ON DELETE SET NULL,
 CONSTRAINT chk_member_dates CHECK(end_date IS NULL OR end_date >= start_date),
 CONSTRAINT fk_member_membership_type FOREIGN KEY(membership_type) REFERENCES membership(membership_id) ON DELETE SET NULL
);

CREATE TABLE membership (
 membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
 subscription_id INTEGER NOT NULL,
 plan_name TEXT NOT NULL,
 access_level INTEGER NOT NULL,
 invited_at TEXT NULL,
 CONSTRAINT fk_membership_subscription FOREIGN KEY(subscription_id) REFERENCES subscription(subscription_id) ON DELETE RESTRICT
);



CREATE TABLE employee_location (
 employee_id INTEGER NOT NULL,
 location_id INTEGER NOT NULL,
 PRIMARY KEY(employee_id, location_id),
 CONSTRAINT fk_el_employee FOREIGN KEY(employee_id) REFERENCES employee(employee_id) ON DELETE CASCADE,
 CONSTRAINT fk_el_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE CASCADE
);

CREATE TABLE person_address (
 person_id INTEGER NOT NULL,
 address_id INTEGER NOT NULL,
 PRIMARY KEY(person_id, address_id),
 CONSTRAINT fk_pa_person FOREIGN KEY(person_id) REFERENCES person(person_id) ON DELETE CASCADE,
 CONSTRAINT fk_pa_address FOREIGN KEY(address_id) REFERENCES address(id) ON DELETE CASCADE
);

CREATE TABLE equipment (
 equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
 location_id INTEGER NOT NULL,
 name TEXT NOT NULL,
 item_number INTEGER NOT NULL,
 brand TEXT NULL,
 status TEXT NOT NULL DEFAULT 'operational',
 CONSTRAINT uq_equipment_location_item UNIQUE(location_id, item_number),
 CONSTRAINT fk_equipment_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE RESTRICT
);

CREATE TABLE hours (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 location_id INTEGER NOT NULL,
 day_of_week INTEGER NOT NULL,
 open_time TEXT NULL,
 close_time TEXT NULL,
 is_closed INTEGER NOT NULL DEFAULT FALSE,
 CONSTRAINT uq_hours_location_day UNIQUE(location_id, day_of_week),
 CONSTRAINT fk_hours_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE CASCADE,
 CONSTRAINT chk_day_of_week CHECK(day_of_week BETWEEN 0 AND 6),
 CONSTRAINT chk_hours_closed CHECK(is_closed = TRUE OR (open_time IS NOT NULL AND close_time IS NOT NULL))
);

CREATE TABLE check_in (
 check_in_id INTEGER PRIMARY KEY AUTOINCREMENT,
 location_id INTEGER NOT NULL,
 member_id INTEGER NOT NULL,
 time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 is_clear INTEGER NOT NULL DEFAULT TRUE,
 entry_method TEXT NOT NULL,
 CONSTRAINT fk_checkin_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE RESTRICT,
 CONSTRAINT fk_checkin_member FOREIGN KEY(member_id) REFERENCES member(member_id) ON DELETE RESTRICT
);

CREATE TABLE maintenance (
 maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
 employee_id INTEGER NULL,
 location_id INTEGER NOT NULL,
 equipment_id INTEGER NULL,
 reported_date TEXT NOT NULL,
 notes TEXT NULL,
 is_resolved INTEGER NOT NULL DEFAULT FALSE,
 CONSTRAINT fk_maintenance_employee FOREIGN KEY(employee_id) REFERENCES employee(employee_id) ON DELETE SET NULL,
 CONSTRAINT fk_maintenance_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE RESTRICT,
 CONSTRAINT fk_maintenance_equipment FOREIGN KEY(equipment_id) REFERENCES equipment(equipment_id) ON DELETE SET NULL
);

CREATE TABLE employee_account (
 account_id INTEGER PRIMARY KEY AUTOINCREMENT,
 employee_id INTEGER NOT NULL,
 employment_type TEXT NOT NULL,
 pay_rate NUMERIC NOT NULL,
 pay_frequency TEXT NOT NULL,
 payroll_date TEXT NULL,
 YTD_salary NUMERIC NOT NULL DEFAULT 0,
 bank_routing_number TEXT NULL,
 SSN TEXT NULL,
 available_PTO INTEGER NOT NULL DEFAULT 0,
 CONSTRAINT uq_employee_account_employee UNIQUE(employee_id),
 CONSTRAINT fk_account_employee FOREIGN KEY(employee_id) REFERENCES employee(employee_id) ON DELETE RESTRICT,
 CONSTRAINT chk_pay_rate CHECK(pay_rate >= 0),
 CONSTRAINT chk_ytd_salary CHECK(YTD_salary >= 0)
);

CREATE TABLE `transaction` (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 location_id INTEGER NULL,
 member_id INTEGER NOT NULL,
 transaction_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 amount NUMERIC NOT NULL,
 is_deposit INTEGER NOT NULL DEFAULT FALSE,
 subscription_id INTEGER NULL,
 maintenance_id INTEGER NULL,
 equipment_id INTEGER NULL,
 CONSTRAINT fk_transaction_location FOREIGN KEY(location_id) REFERENCES gym_location(location_id) ON DELETE SET NULL,
 CONSTRAINT fk_transaction_member FOREIGN KEY(member_id) REFERENCES member(member_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transaction_subscription FOREIGN KEY(subscription_id) REFERENCES subscription(subscription_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transaction_maintenance FOREIGN KEY(maintenance_id) REFERENCES maintenance(maintenance_id) ON DELETE RESTRICT,
 CONSTRAINT fk_transaction_equipment FOREIGN KEY(equipment_id) REFERENCES equipment(equipment_id) ON DELETE RESTRICT
);
