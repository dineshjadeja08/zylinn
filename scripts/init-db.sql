-- Initialize Zylin Database
-- Run automatically by Docker Compose on first startup

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- Create schema
CREATE SCHEMA IF NOT EXISTS zylin;

-- Set search path
SET search_path TO zylin, public;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_call_records_created_at ON call_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_records_status ON call_records(status);
CREATE INDEX IF NOT EXISTS idx_transcript_chunks_call_id ON transcript_chunks(call_id);
CREATE INDEX IF NOT EXISTS idx_agent_replies_call_id ON agent_replies(call_id);
CREATE INDEX IF NOT EXISTS idx_appointments_call_id ON appointments(call_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);

-- Create customers table for multi-tenancy
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_id UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    company_name VARCHAR(200) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    plan_type VARCHAR(50) NOT NULL DEFAULT 'free', -- free, starter, pro, enterprise
    max_calls_per_month INTEGER DEFAULT 100,
    calls_this_month INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- active, suspended, cancelled
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create usage tracking table
CREATE TABLE IF NOT EXISTS usage_logs (
    id SERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    call_id VARCHAR(100) NOT NULL,
    duration_seconds FLOAT,
    stt_characters INTEGER,
    llm_tokens INTEGER,
    tts_characters INTEGER,
    cost_usd DECIMAL(10, 4),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for usage logs
CREATE INDEX IF NOT EXISTS idx_usage_logs_customer ON usage_logs(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at DESC);

-- Create API keys audit log
CREATE TABLE IF NOT EXISTS api_key_audit (
    id SERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    action VARCHAR(50) NOT NULL, -- created, rotated, revoked
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create webhook configurations table
CREATE TABLE IF NOT EXISTS webhook_configs (
    id SERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    webhook_url TEXT NOT NULL,
    events TEXT[] NOT NULL, -- Array of event types to subscribe to
    secret_key VARCHAR(255) NOT NULL, -- For HMAC signature verification
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create users table for customer portal authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'owner', -- owner, admin, member
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255) UNIQUE,
    verification_token_expires TIMESTAMP,
    reset_token VARCHAR(255) UNIQUE,
    reset_token_expires TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_customer ON users(customer_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);
CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(reset_token);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_webhook_configs_updated_at BEFORE UPDATE ON webhook_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default admin customer for testing
INSERT INTO customers (company_name, email, api_key_hash, plan_type, max_calls_per_month, status)
VALUES ('Zylin Admin', 'admin@zylin.ai', 'admin_key_hash_replace_this', 'enterprise', 999999, 'active')
ON CONFLICT (email) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA zylin TO zylin_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA zylin TO zylin_user;
