CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user','admin')),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT DEFAULT '',
    daily_rate REAL NOT NULL CHECK (daily_rate >= 0),
    deposit_amount REAL NOT NULL CHECK (deposit_amount >= 0),
    stock_total INTEGER NOT NULL CHECK (stock_total >= 0),
    stock_available INTEGER NOT NULL CHECK (stock_available >= 0),
    condition TEXT NOT NULL DEFAULT 'excellent',
    status TEXT NOT NULL DEFAULT 'available',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    deposit_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    purpose TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (equipment_id) REFERENCES equipment(id)
);

CREATE TABLE IF NOT EXISTS equipment_returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    booking_id INTEGER,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    customer_email TEXT DEFAULT '',
    equipment_name TEXT NOT NULL,
    equipment_code TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Camera',
    rental_start_date TEXT NOT NULL,
    return_due_date TEXT NOT NULL,
    actual_return_date TEXT,
    deposit_amount REAL NOT NULL CHECK (deposit_amount >= 0),
    condition TEXT,
    damage_remarks TEXT DEFAULT '',
    repair_cost REAL NOT NULL DEFAULT 0 CHECK (repair_cost >= 0),
    deposit_deduction REAL NOT NULL DEFAULT 0 CHECK (deposit_deduction >= 0),
    recommendation TEXT DEFAULT '',
    owner TEXT NOT NULL DEFAULT 'Rental Admin',
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'due',
    return_request_status TEXT NOT NULL DEFAULT 'pending',
    deduction_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);

CREATE TABLE IF NOT EXISTS action_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (return_id) REFERENCES equipment_returns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_reset_otps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    otp_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_returns_status ON equipment_returns(status);
CREATE INDEX IF NOT EXISTS idx_returns_due_date ON equipment_returns(return_due_date);
CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_otps(user_id, used);
