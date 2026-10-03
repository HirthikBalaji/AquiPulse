-- AquiPulse Database Schema (TimescaleDB + PostGIS)
-- Matches §8.3 of specification

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis CASCADE;

-- Registered pump units
CREATE TABLE IF NOT EXISTS pump (
    id VARCHAR(64) PRIMARY KEY,
    farmer_id VARCHAR(64) NOT NULL,
    geom GEOMETRY(Point, 4326),
    make VARCHAR(64) NOT NULL,
    model VARCHAR(64) NOT NULL,
    hp NUMERIC(5,2) NOT NULL,
    phase INT NOT NULL,
    rated_head_m NUMERIC(6,2) NOT NULL,
    rated_q_lps NUMERIC(6,2) NOT NULL,
    install_ts TIMESTAMPTZ DEFAULT NOW(),
    owner_consent BOOLEAN DEFAULT TRUE,
    secret_key_hex VARCHAR(128)
);

-- 1 Hz steady-state telemetry hypertable
CREATE TABLE IF NOT EXISTS telemetry_1hz (
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    ts TIMESTAMPTZ NOT NULL,
    v_rms NUMERIC(6,2),
    i_rms NUMERIC(6,2),
    pf NUMERIC(4,3),
    p_kw NUMERIC(6,3),
    freq_hz NUMERIC(5,2),
    signature VARCHAR(128)
);
SELECT create_hypertable('telemetry_1hz', 'ts', if_not_exists => TRUE);

-- 4 kHz start burst transient records
CREATE TABLE IF NOT EXISTS start_burst (
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    ts_start TIMESTAMPTZ NOT NULL,
    samples BYTEA,
    fs_hz INT DEFAULT 4000,
    duration_s NUMERIC(5,2) DEFAULT 60.0,
    metadata JSONB
);

-- Layer 1: PHI state estimates
CREATE TABLE IF NOT EXISTS phi_state (
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    ts TIMESTAMPTZ NOT NULL,
    q_lps NUMERIC(6,3),
    h_dyn_m NUMERIC(6,2),
    z_static_m NUMERIC(6,2),
    eta_overall NUMERIC(4,3),
    sigma_q NUMERIC(6,3),
    sigma_z NUMERIC(6,2),
    is_running BOOLEAN,
    is_dry_run BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('phi_state', 'ts', if_not_exists => TRUE);

-- Layer 2: OPT pumping test estimates
CREATE TABLE IF NOT EXISTS opt_estimate (
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    ts TIMESTAMPTZ NOT NULL,
    log10_t NUMERIC(6,3),
    log10_s NUMERIC(6,3),
    b_formation_loss NUMERIC(8,2),
    c_turbulent_loss NUMERIC(10,2),
    flow_dim NUMERIC(4,2),
    ci_low NUMERIC(6,3),
    ci_high NUMERIC(6,3)
);

-- Layer 3: Aquifer grid cells (privacy-preserving aggregated view)
CREATE TABLE IF NOT EXISTS aquifer_cell (
    cell_id VARCHAR(64) PRIMARY KEY,
    geom GEOMETRY(Polygon, 4326),
    h_post NUMERIC(6,2),
    t_post NUMERIC(8,5),
    sy_post NUMERIC(5,4),
    recharge_post NUMERIC(8,5),
    depl_rate NUMERIC(6,3),
    model_err_var NUMERIC(6,3),
    updated_ts TIMESTAMPTZ DEFAULT NOW()
);

-- Layer 4: Marginal externality prices
CREATE TABLE IF NOT EXISTS extern_price (
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    ts TIMESTAMPTZ NOT NULL,
    lambda_inr_per_m3 NUMERIC(6,3),
    ci_low NUMERIC(6,3),
    ci_high NUMERIC(6,3),
    stress_level VARCHAR(32)
);

-- Ground-truth field audits
CREATE TABLE IF NOT EXISTS audit (
    id SERIAL PRIMARY KEY,
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    ts TIMESTAMPTZ NOT NULL,
    bucket_q_lps NUMERIC(6,3) NOT NULL,
    dip_level_m NUMERIC(6,2) NOT NULL,
    auditor_id VARCHAR(64) NOT NULL
);

-- Layer 5: Settlement ledger entries
CREATE TABLE IF NOT EXISTS settlement (
    entry_id VARCHAR(64) PRIMARY KEY,
    pump_id VARCHAR(64) NOT NULL REFERENCES pump(id),
    period VARCHAR(32) NOT NULL,
    avoided_m3 NUMERIC(10,2) NOT NULL,
    bonus_inr NUMERIC(10,2) NOT NULL,
    guardrail_ok BOOLEAN NOT NULL,
    flags JSONB,
    block_hash VARCHAR(128)
);
