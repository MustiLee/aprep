-- Aprep AI Agent System - PostgreSQL Database Schema
-- Version: 1.0
-- Date: 2025-10-17

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Courses table
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id VARCHAR(100) UNIQUE NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    exam_type VARCHAR(50),  -- 'AP', 'SAT', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_courses_course_id ON courses(course_id);

-- Units table
CREATE TABLE units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    unit_id VARCHAR(100) NOT NULL,
    unit_number INTEGER,
    unit_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(course_id, unit_id)
);

CREATE INDEX idx_units_course_id ON units(course_id);
CREATE INDEX idx_units_unit_id ON units(unit_id);

-- Topics table
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id UUID REFERENCES units(id) ON DELETE CASCADE,
    topic_id VARCHAR(100) NOT NULL,
    topic_name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(unit_id, topic_id)
);

CREATE INDEX idx_topics_unit_id ON topics(unit_id);
CREATE INDEX idx_topics_topic_id ON topics(topic_id);

-- Learning Objectives table
CREATE TABLE learning_objectives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    lo_code VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    cognitive_level VARCHAR(50),  -- 'remember', 'understand', 'apply', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic_id, lo_code)
);

CREATE INDEX idx_los_topic_id ON learning_objectives(topic_id);
CREATE INDEX idx_los_lo_code ON learning_objectives(lo_code);

-- ============================================================================
-- TEMPLATE TABLES
-- ============================================================================

-- Question Templates table
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id VARCHAR(255) UNIQUE NOT NULL,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,

    -- Metadata
    created_by VARCHAR(100) DEFAULT 'system',
    task_id VARCHAR(255),
    version INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active',  -- 'active', 'deprecated', 'archived'

    -- Template content
    stem TEXT NOT NULL,
    solution_template TEXT,
    explanation_template TEXT,

    -- Configuration
    difficulty_range JSONB,  -- [min, max] as JSON array
    calculator_policy VARCHAR(50),
    time_estimate_seconds INTEGER,

    -- Metadata
    tags TEXT[],
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_templates_template_id ON templates(template_id);
CREATE INDEX idx_templates_course_id ON templates(course_id);
CREATE INDEX idx_templates_topic_id ON templates(topic_id);
CREATE INDEX idx_templates_status ON templates(status);
CREATE INDEX idx_templates_tags ON templates USING GIN(tags);

-- Template Parameters table
CREATE TABLE template_parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,

    param_name VARCHAR(100) NOT NULL,
    param_type VARCHAR(50) NOT NULL,  -- 'enum', 'range', 'expression'
    definition JSONB NOT NULL,  -- Parameter definition as JSON

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_id, param_name)
);

CREATE INDEX idx_template_params_template_id ON template_parameters(template_id);

-- Distractor Rules table
CREATE TABLE distractor_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,

    rule_id VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    generation_rule TEXT NOT NULL,
    misconception VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_id, rule_id)
);

CREATE INDEX idx_distractor_rules_template_id ON distractor_rules(template_id);

-- Template Learning Objectives junction table
CREATE TABLE template_learning_objectives (
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    lo_id UUID REFERENCES learning_objectives(id) ON DELETE CASCADE,
    PRIMARY KEY (template_id, lo_id)
);

-- ============================================================================
-- VARIANT TABLES
-- ============================================================================

-- Question Variants table
CREATE TABLE variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id VARCHAR(255) UNIQUE NOT NULL,
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,

    -- Content
    stimulus TEXT NOT NULL,
    options TEXT[] NOT NULL,
    answer_index INTEGER NOT NULL CHECK (answer_index >= 0 AND answer_index < 4),
    solution TEXT NOT NULL,
    explanation TEXT,

    -- Parameters
    parameter_values JSONB NOT NULL,
    seed INTEGER,

    -- Metadata
    difficulty_estimate DECIMAL(3, 2),
    discrimination_estimate DECIMAL(3, 2),
    guessing_estimate DECIMAL(3, 2),

    -- Verification
    verification_status VARCHAR(50),  -- 'pending', 'pass', 'fail', 'needs_review'
    verification_confidence DECIMAL(3, 2),
    verification_timestamp TIMESTAMP,
    verification_result JSONB,

    -- Usage tracking
    times_used INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_variants_variant_id ON variants(variant_id);
CREATE INDEX idx_variants_template_id ON variants(template_id);
CREATE INDEX idx_variants_verification_status ON variants(verification_status);
CREATE INDEX idx_variants_difficulty ON variants(difficulty_estimate);
CREATE INDEX idx_variants_created_at ON variants(created_at);

-- ============================================================================
-- VERIFICATION TABLES
-- ============================================================================

-- Verification Results table (detailed logs)
CREATE TABLE verification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID REFERENCES variants(id) ON DELETE CASCADE,

    verification_status VARCHAR(50) NOT NULL,

    -- Method results
    symbolic_result JSONB,
    numerical_result JSONB,
    claude_result JSONB,

    -- Consensus
    consensus JSONB,

    -- Distractor analysis
    distractor_analysis JSONB,

    -- Issues and warnings
    issues JSONB,
    warnings JSONB,

    -- Performance
    duration_ms INTEGER,
    cost_usd DECIMAL(10, 6),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_verification_logs_variant_id ON verification_logs(variant_id);
CREATE INDEX idx_verification_logs_status ON verification_logs(verification_status);
CREATE INDEX idx_verification_logs_created_at ON verification_logs(created_at);

-- ============================================================================
-- USAGE TABLES
-- ============================================================================

-- Test Sessions table
CREATE TABLE test_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL,

    user_id VARCHAR(255),
    test_type VARCHAR(50),  -- 'practice', 'diagnostic', 'mock_exam'
    course_id UUID REFERENCES courses(id),

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    metadata JSONB
);

CREATE INDEX idx_test_sessions_session_id ON test_sessions(session_id);
CREATE INDEX idx_test_sessions_user_id ON test_sessions(user_id);
CREATE INDEX idx_test_sessions_course_id ON test_sessions(course_id);

-- Responses table (student answers)
CREATE TABLE responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES test_sessions(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES variants(id),

    selected_option INTEGER CHECK (selected_option >= 0 AND selected_option < 4),
    is_correct BOOLEAN,
    response_time_ms INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_responses_session_id ON responses(session_id);
CREATE INDEX idx_responses_variant_id ON responses(variant_id);
CREATE INDEX idx_responses_is_correct ON responses(is_correct);

-- ============================================================================
-- ANALYTICS TABLES
-- ============================================================================

-- Variant Statistics table (aggregated stats)
CREATE TABLE variant_statistics (
    variant_id UUID PRIMARY KEY REFERENCES variants(id) ON DELETE CASCADE,

    -- Usage stats
    times_administered INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    times_incorrect INTEGER DEFAULT 0,

    -- Performance metrics
    p_value DECIMAL(5, 4),  -- Proportion correct
    point_biserial DECIMAL(5, 4),  -- Discrimination

    -- Option analysis
    option_frequencies JSONB,  -- Frequency of each option selection

    -- IRT parameters (Item Response Theory)
    irt_difficulty DECIMAL(5, 3),  -- b parameter
    irt_discrimination DECIMAL(5, 3),  -- a parameter
    irt_guessing DECIMAL(5, 3),  -- c parameter
    irt_last_calibrated TIMESTAMP,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Template Statistics table
CREATE TABLE template_statistics (
    template_id UUID PRIMARY KEY REFERENCES templates(id) ON DELETE CASCADE,

    total_variants INTEGER DEFAULT 0,
    verified_variants INTEGER DEFAULT 0,

    avg_difficulty DECIMAL(5, 4),
    avg_discrimination DECIMAL(5, 4),

    times_used INTEGER DEFAULT 0,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- AGENT WORKFLOW TABLES
-- ============================================================================

-- Workflows table (orchestrator tracking)
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id VARCHAR(255) UNIQUE NOT NULL,

    workflow_type VARCHAR(100),  -- 'template_creation', 'variant_generation', etc.
    status VARCHAR(50),  -- 'pending', 'running', 'completed', 'failed'

    input_data JSONB,
    output_data JSONB,

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    error_message TEXT
);

CREATE INDEX idx_workflows_workflow_id ON workflows(workflow_id);
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_workflow_type ON workflows(workflow_type);

-- Agent Tasks table (individual agent executions)
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,

    agent_name VARCHAR(100) NOT NULL,
    stage_number INTEGER,

    status VARCHAR(50),
    input_data JSONB,
    output_data JSONB,

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    error_message TEXT
);

CREATE INDEX idx_agent_tasks_workflow_id ON agent_tasks(workflow_id);
CREATE INDEX idx_agent_tasks_agent_name ON agent_tasks(agent_name);
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);

-- ============================================================================
-- SYSTEM TABLES
-- ============================================================================

-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash VARCHAR(255) UNIQUE NOT NULL,

    name VARCHAR(255),
    description TEXT,

    scopes TEXT[],  -- Permissions: 'read:templates', 'write:variants', etc.

    rate_limit_per_hour INTEGER DEFAULT 1000,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);

-- Audit Log table
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    action VARCHAR(100) NOT NULL,  -- 'create', 'update', 'delete'
    resource_type VARCHAR(100),  -- 'template', 'variant', etc.
    resource_id UUID,

    user_id VARCHAR(255),
    api_key_id UUID REFERENCES api_keys(id),

    changes JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_resource_type ON audit_log(resource_type);
CREATE INDEX idx_audit_log_resource_id ON audit_log(resource_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_courses_updated_at BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_templates_updated_at BEFORE UPDATE ON templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_variants_updated_at BEFORE UPDATE ON variants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Template summary with statistics
CREATE VIEW template_summary AS
SELECT
    t.id,
    t.template_id,
    t.course_id,
    c.course_name,
    t.topic_id,
    tp.topic_name,
    t.status,
    t.difficulty_range,
    ts.total_variants,
    ts.verified_variants,
    ts.avg_difficulty,
    ts.times_used,
    t.created_at,
    t.updated_at
FROM templates t
LEFT JOIN courses c ON t.course_id = c.id
LEFT JOIN topics tp ON t.topic_id = tp.id
LEFT JOIN template_statistics ts ON t.id = ts.template_id;

-- View: Variant summary with verification status
CREATE VIEW variant_summary AS
SELECT
    v.id,
    v.variant_id,
    v.template_id,
    t.template_id as template_name,
    v.stimulus,
    v.answer_index,
    v.difficulty_estimate,
    v.verification_status,
    v.verification_confidence,
    vs.p_value,
    vs.times_administered,
    v.created_at
FROM variants v
LEFT JOIN templates t ON v.template_id = t.id
LEFT JOIN variant_statistics vs ON v.id = vs.variant_id;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default courses
INSERT INTO courses (course_id, course_name, exam_type) VALUES
    ('ap_calculus_bc', 'AP Calculus BC', 'AP'),
    ('ap_calculus_ab', 'AP Calculus AB', 'AP'),
    ('ap_statistics', 'AP Statistics', 'AP'),
    ('ap_physics_c_mechanics', 'AP Physics C: Mechanics', 'AP'),
    ('ap_chemistry', 'AP Chemistry', 'AP')
ON CONFLICT (course_id) DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE templates IS 'Parametric question templates created by Template Crafter';
COMMENT ON TABLE variants IS 'Specific question instances generated from templates';
COMMENT ON TABLE verification_logs IS 'Detailed logs of Solution Verifier results';
COMMENT ON TABLE responses IS 'Student responses to question variants';
COMMENT ON TABLE variant_statistics IS 'Aggregated performance statistics for variants';

-- ============================================================================
-- GRANTS (for application role)
-- ============================================================================

-- Create application role
-- CREATE ROLE aprep_app WITH LOGIN PASSWORD 'your_secure_password_here';

-- Grant permissions
-- GRANT CONNECT ON DATABASE aprep_db TO aprep_app;
-- GRANT USAGE ON SCHEMA public TO aprep_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aprep_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aprep_app;
