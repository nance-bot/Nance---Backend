-- 1. Create schema if not exists
CREATE SCHEMA IF NOT EXISTS dev;

-- 2. SubscriptionPlan
CREATE TABLE dev.subscription_plan (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    features JSONB NOT NULL,
    price NUMERIC(8,2) NOT NULL,
    duration_in_days INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. User
CREATE TABLE dev."user" (
    id SERIAL PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    last_login TIMESTAMP WITH TIME ZONE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    username VARCHAR(150) UNIQUE NOT NULL,
    first_name VARCHAR(150) NOT NULL DEFAULT '',
    last_name VARCHAR(150) NOT NULL DEFAULT '',
    email VARCHAR(254) NOT NULL DEFAULT '',
    is_staff BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    date_joined TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    nance_id VARCHAR(12) UNIQUE NOT NULL,
    dob DATE,
    phone VARCHAR(15) UNIQUE NOT NULL,
    occupation VARCHAR(100) DEFAULT '',
    location VARCHAR(100) DEFAULT '',
    profile_picture VARCHAR(255),
    subscription_plan_id INT REFERENCES dev.subscription_plan(id) ON DELETE SET NULL,
    is_contact_synced BOOLEAN DEFAULT FALSE
);

-- 4. BankAccount
CREATE TABLE dev.bank_account (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    bank_name VARCHAR(100) NOT NULL,
    account_number VARCHAR(20) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    balance NUMERIC(12,2) NOT NULL,
    linked_via_aa BOOLEAN DEFAULT TRUE,
    last_synced TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Category
CREATE TABLE dev.category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    is_custom BOOLEAN DEFAULT FALSE,
    user_id INT REFERENCES dev."user"(id) ON DELETE CASCADE
);

-- 6. SubCategory
CREATE TABLE dev.sub_category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    category_id INT NOT NULL REFERENCES dev.category(id) ON DELETE CASCADE
);

-- 7. Transaction
CREATE TABLE dev.transaction (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    bank_account_id INT REFERENCES dev.bank_account(id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    transaction_mode VARCHAR(30) NOT NULL,
    transaction_id VARCHAR(100) UNIQUE NOT NULL,
    narration TEXT DEFAULT '',
    spend_type VARCHAR(10) CHECK (spend_type IN ('income','expense')),
    notes TEXT DEFAULT '',
    category_id INT REFERENCES dev.category(id) ON DELETE SET NULL,
    sub_category_id INT REFERENCES dev.sub_category(id) ON DELETE SET NULL,
    is_saved BOOLEAN DEFAULT FALSE
);

-- 8. SmartGroup
CREATE TABLE dev.smart_group (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    by_contact BOOLEAN DEFAULT FALSE,
    emoji VARCHAR(5) DEFAULT '',
    color VARCHAR(7) DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Junction table for SmartGroup & Transaction
CREATE TABLE dev.smart_group_transactions (
    id SERIAL PRIMARY KEY,
    smart_group_id INT NOT NULL REFERENCES dev.smart_group(id) ON DELETE CASCADE,
    transaction_id INT NOT NULL REFERENCES dev.transaction(id) ON DELETE CASCADE
);

-- 10. Goal
CREATE TABLE dev.goal (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    period VARCHAR(10) CHECK (period IN ('weekly','monthly')),
    category_id INT REFERENCES dev.category(id) ON DELETE SET NULL,
    sub_category_id INT REFERENCES dev.sub_category(id) ON DELETE SET NULL,
    amount NUMERIC(12,2) NOT NULL,
    color VARCHAR(7) DEFAULT '',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- 11. Report
CREATE TABLE dev.report (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    total_income NUMERIC(12,2) DEFAULT 0,
    total_expense NUMERIC(12,2) DEFAULT 0,
    filters_applied JSONB,
    chart_type VARCHAR(50) NOT NULL
);

-- 12. SavedReport
CREATE TABLE dev.saved_report (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    report_id INT NOT NULL REFERENCES dev.report(id) ON DELETE CASCADE,
    saved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. VUICommand
CREATE TABLE dev.vui_command (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    command TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 14. Consent
CREATE TABLE dev.consent (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    given_on TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_on TIMESTAMP WITH TIME ZONE NOT NULL,
    is_renewed BOOLEAN DEFAULT FALSE
);

-- 15. Notification
CREATE TABLE dev.notification (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE
);

-- 16. LinkedAccount
CREATE TABLE dev.linked_account (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES dev."user"(id) ON DELETE CASCADE,
    account_type VARCHAR(20) CHECK (account_type IN ('upi','card','bank')),
    identifier VARCHAR(100) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    linked_on TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
