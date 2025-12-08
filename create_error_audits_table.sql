-- Create error_audits table
CREATE TABLE IF NOT EXISTS error_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Error Classification
    error_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    
    -- Context Information
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(100),
    request_id VARCHAR(100),
    
    -- Error Details
    error_code VARCHAR(50),
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    
    -- Request Context
    endpoint VARCHAR(200),
    http_method VARCHAR(10),
    http_status INTEGER,
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),
    
    -- Additional Context
    context_data JSONB,
    environment VARCHAR(20) DEFAULT 'production',
    
    -- Tracking
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_error_type_created ON error_audits(error_type, created_at);
CREATE INDEX IF NOT EXISTS idx_severity_created ON error_audits(severity, created_at);
CREATE INDEX IF NOT EXISTS idx_user_created ON error_audits(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_endpoint_created ON error_audits(endpoint, created_at);
CREATE INDEX IF NOT EXISTS idx_resolved_created ON error_audits(resolved, created_at);
CREATE INDEX IF NOT EXISTS idx_created_at ON error_audits(created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE error_audits IS 'Audit trail for application errors and exceptions';
COMMENT ON COLUMN error_audits.error_type IS 'API_ERROR, UI_ERROR, THIRD_PARTY_ERROR';
COMMENT ON COLUMN error_audits.severity IS 'LOW, MEDIUM, HIGH, CRITICAL';
COMMENT ON COLUMN error_audits.source IS 'BACKEND, FRONTEND, EXTERNAL';
COMMENT ON COLUMN error_audits.context_data IS 'Additional JSON context for debugging';