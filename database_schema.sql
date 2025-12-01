-- GB Track Specialist Production - PostgreSQL Database Schema
-- Comprehensive logging for grid search optimization

-- ==============================================================================
-- PREDICTIONS TABLE - ALL CatBoost Features for Every Runner
-- ==============================================================================
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    
    -- Identifiers
    market_id VARCHAR(50) NOT NULL,
    selection_id BIGINT NOT NULL,
    runner_name VARCHAR(100),
    
    -- Race Context
    venue VARCHAR(50),
    venue_abbr VARCHAR(10),
    race_time TIMESTAMP NOT NULL,
    race_date DATE,
    race_hour INTEGER,
    race_day_of_week INTEGER,  -- 0=Monday, 6=Sunday
    is_weekend BOOLEAN,
    distance INTEGER,
    race_grade VARCHAR(20),
    race_category VARCHAR(20),
    country_code VARCHAR(5) DEFAULT 'GB',
    
    -- Runner Basics
    trap INTEGER,
    runner_odds DECIMAL(10,2),
    runner_box INTEGER,  -- Same as trap
    
    -- Probabilities (Model Outputs)
    win_probability DECIMAL(10,6),
    win_probability_raw DECIMAL(10,6),
    base_prob DECIMAL(10,6),
    calibrated_prob DECIMAL(10,6),
    runner_implied_prob DECIMAL(10,6),
    
    -- Field/Market Aggregate Features
    field_size INTEGER,
    favorite_bsp DECIMAL(10,2),
    mean_bsp DECIMAL(10,2),
    bsp_std DECIMAL(10,4),
    second_favorite_bsp DECIMAL(10,2),
    
    -- Runner Position Features
    runner_log_odds DECIMAL(10,4),
    runner_odds_rank INTEGER,
    
    -- Odds Differentials
    odds_vs_favorite_diff DECIMAL(10,2),
    odds_vs_favorite_ratio DECIMAL(10,4),
    odds_vs_mean_diff DECIMAL(10,2),
    odds_vs_mean_ratio DECIMAL(10,4),
    odds_vs_second_diff DECIMAL(10,2),
    odds_vs_second_ratio DECIMAL(10,4),
    
    -- Market Structure Features
    market_compression DECIMAL(10,4),
    favorite_dominance DECIMAL(10,4),
    odds_std DECIMAL(10,4),
    odds_range DECIMAL(10,2),
    odds_cv DECIMAL(10,4),
    
    -- Competitive Field Indicators
    num_competitive INTEGER,
    longshot BOOLEAN,
    weak_favorite BOOLEAN,
    dominant_favorite BOOLEAN,
    competitive_field BOOLEAN,
    
    -- Box Position Features
    box_position_score DECIMAL(10,4),
    box_inside BOOLEAN,
    box_middle BOOLEAN,
    box_outside BOOLEAN,
    
    -- Betting Optimizer Features
    predicted_profit DECIMAL(10,2),
    prob_spread DECIMAL(10,6),
    favorite_prob DECIMAL(10,6),
    prob_odds_gap DECIMAL(10,6),
    rank_by_prob INTEGER,
    rank_discrepancy INTEGER,
    is_favorite BOOLEAN,
    is_longshot BOOLEAN,
    competitive_runners INTEGER,
    is_competitive_field BOOLEAN,
    
    -- Metadata
    prediction_time TIMESTAMP DEFAULT NOW(),
    session_id VARCHAR(50),
    system VARCHAR(50) DEFAULT 'gb_track_specialist',
    
    -- Results (Updated After Race)
    won BOOLEAN,
    actual_winner_selection_id BIGINT,
    actual_winner_name VARCHAR(100),
    actual_winner_odds DECIMAL(10,2),
    result_checked_time TIMESTAMP,
    
    -- Constraints
    UNIQUE(market_id, selection_id),
    CHECK (race_day_of_week >= 0 AND race_day_of_week <= 6),
    CHECK (trap >= 1 AND trap <= 8),
    CHECK (win_probability >= 0 AND win_probability <= 1)
);

-- Indexes for Grid Search Performance
CREATE INDEX IF NOT EXISTS idx_pred_market ON predictions(market_id);
CREATE INDEX IF NOT EXISTS idx_pred_venue ON predictions(venue);
CREATE INDEX IF NOT EXISTS idx_pred_race_grade ON predictions(race_grade);
CREATE INDEX IF NOT EXISTS idx_pred_race_time ON predictions(race_time);
CREATE INDEX IF NOT EXISTS idx_pred_day_of_week ON predictions(race_day_of_week);
CREATE INDEX IF NOT EXISTS idx_pred_field_size ON predictions(field_size);
CREATE INDEX IF NOT EXISTS idx_pred_distance ON predictions(distance);
CREATE INDEX IF NOT EXISTS idx_pred_hour ON predictions(race_hour);
CREATE INDEX IF NOT EXISTS idx_pred_session ON predictions(session_id);
CREATE INDEX IF NOT EXISTS idx_pred_won ON predictions(won) WHERE won IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pred_composite ON predictions(venue, race_grade, field_size);

-- ==============================================================================
-- RACES TABLE - Race-Level Metadata
-- ==============================================================================
CREATE TABLE IF NOT EXISTS races (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(50) UNIQUE NOT NULL,
    market_name VARCHAR(200),
    event_name VARCHAR(200),
    venue VARCHAR(50) NOT NULL,
    country_code VARCHAR(5) DEFAULT 'GB',
    race_time TIMESTAMP NOT NULL,
    race_date DATE,
    race_hour INTEGER,
    race_day_of_week INTEGER,
    is_weekend BOOLEAN,
    distance INTEGER,
    race_grade VARCHAR(20),
    num_runners INTEGER,
    status VARCHAR(20),
    
    -- Results
    winner_selection_id BIGINT,
    winner_name VARCHAR(100),
    winner_odds DECIMAL(10,2),
    result_checked_time TIMESTAMP,
    
    -- Metadata
    fetch_time TIMESTAMP DEFAULT NOW(),
    session_id VARCHAR(50),
    system VARCHAR(50) DEFAULT 'gb_track_specialist',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_race_market ON races(market_id);
CREATE INDEX IF NOT EXISTS idx_race_venue ON races(venue);
CREATE INDEX IF NOT EXISTS idx_race_time ON races(race_time);
CREATE INDEX IF NOT EXISTS idx_race_session ON races(session_id);

-- ==============================================================================
-- BETS TABLE - Actual Bets Placed
-- ==============================================================================
CREATE TABLE IF NOT EXISTS bets (
    id SERIAL PRIMARY KEY,
    
    -- Bet Identifiers
    bet_id VARCHAR(100) UNIQUE,
    market_id VARCHAR(50) NOT NULL,
    selection_id BIGINT NOT NULL,
    
    -- Runner Info
    runner_name VARCHAR(100),
    runner_odds DECIMAL(10,2),
    trap INTEGER,
    
    -- Bet Details
    stake DECIMAL(10,2) NOT NULL,
    status VARCHAR(50),
    
    -- Strategy
    strategy VARCHAR(50),  -- MIDRANGE or LONGSHOT
    strategy_subtype VARCHAR(50),  -- e.g., MIDRANGE_PREFERRED, LONGSHOT_HIGH
    win_probability DECIMAL(10,6),
    expected_value DECIMAL(10,4),
    
    -- Race Context
    venue VARCHAR(50),
    race_time TIMESTAMP,
    race_grade VARCHAR(20),
    distance INTEGER,
    
    -- Results
    won BOOLEAN,
    returns DECIMAL(10,2),
    profit DECIMAL(10,2),
    winner_selection_id BIGINT,
    result_checked_time TIMESTAMP,
    
    -- Metadata
    placed_time TIMESTAMP DEFAULT NOW(),
    session_id VARCHAR(50),
    system VARCHAR(50) DEFAULT 'gb_track_specialist',
    dry_run BOOLEAN DEFAULT TRUE,
    
    -- Foreign Keys
    FOREIGN KEY (market_id) REFERENCES races(market_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bet_market ON bets(market_id);
CREATE INDEX IF NOT EXISTS idx_bet_session ON bets(session_id);
CREATE INDEX IF NOT EXISTS idx_bet_strategy ON bets(strategy);
CREATE INDEX IF NOT EXISTS idx_bet_won ON bets(won) WHERE won IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bet_time ON bets(placed_time);

-- ==============================================================================
-- SESSIONS TABLE - Track Each Runtime Session
-- ==============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    
    -- Configuration
    dry_run BOOLEAN DEFAULT TRUE,
    scan_interval_minutes INTEGER,
    target_minutes_before_race INTEGER,
    
    -- Statistics
    total_races_processed INTEGER DEFAULT 0,
    total_predictions_made INTEGER DEFAULT 0,
    total_bets_placed INTEGER DEFAULT 0,
    
    -- Summary Stats (Updated on session end)
    bets_won INTEGER DEFAULT 0,
    bets_lost INTEGER DEFAULT 0,
    total_staked DECIMAL(10,2) DEFAULT 0,
    total_profit DECIMAL(10,2) DEFAULT 0,
    roi_percent DECIMAL(10,2),
    
    -- Metadata
    system VARCHAR(50) DEFAULT 'gb_track_specialist',
    system_version VARCHAR(20),
    python_version VARCHAR(20),
    deployment_env VARCHAR(50)  -- 'local', 'railway', etc.
);

CREATE INDEX IF NOT EXISTS idx_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_session_started ON sessions(started_at);

-- ==============================================================================
-- HELPER VIEWS FOR ANALYSIS
-- ==============================================================================

-- View: Complete prediction data with race results
CREATE OR REPLACE VIEW v_predictions_with_results AS
SELECT 
    p.*,
    r.winner_name as race_winner_name,
    r.winner_odds as race_winner_odds,
    CASE WHEN p.selection_id = r.winner_selection_id THEN TRUE ELSE FALSE END as would_have_won
FROM predictions p
LEFT JOIN races r ON p.market_id = r.market_id;

-- View: Betting performance summary
CREATE OR REPLACE VIEW v_betting_performance AS
SELECT 
    session_id,
    strategy,
    venue,
    race_grade,
    COUNT(*) as num_bets,
    SUM(stake) as total_staked,
    SUM(CASE WHEN won THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN won = FALSE THEN 1 ELSE 0 END) as losses,
    ROUND(AVG(CASE WHEN won THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate_pct,
    SUM(profit) as total_profit,
    ROUND((SUM(profit) / NULLIF(SUM(stake), 0)) * 100, 2) as roi_pct
FROM bets
WHERE won IS NOT NULL
GROUP BY session_id, strategy, venue, race_grade;

-- View: Grid search ready data
CREATE OR REPLACE VIEW v_grid_search_data AS
SELECT 
    p.market_id,
    p.selection_id,
    p.runner_name,
    p.venue,
    p.race_grade,
    p.distance,
    p.race_hour,
    p.race_day_of_week,
    p.is_weekend,
    p.field_size,
    p.trap,
    p.runner_odds,
    p.win_probability,
    p.calibrated_prob,
    p.predicted_profit,
    -- All market features
    p.market_compression,
    p.favorite_dominance,
    p.competitive_field,
    p.num_competitive,
    p.longshot,
    p.weak_favorite,
    p.dominant_favorite,
    -- Results
    p.won,
    -- Bet info if bet was placed
    b.stake,
    b.strategy,
    b.profit
FROM predictions p
LEFT JOIN bets b ON p.market_id = b.market_id AND p.selection_id = b.selection_id;

-- ==============================================================================
-- MAINTENANCE FUNCTIONS
-- ==============================================================================

-- Function to update session statistics
CREATE OR REPLACE FUNCTION update_session_stats(p_session_id VARCHAR(50))
RETURNS VOID AS $$
BEGIN
    UPDATE sessions SET
        total_races_processed = (SELECT COUNT(DISTINCT market_id) FROM races WHERE session_id = p_session_id),
        total_predictions_made = (SELECT COUNT(*) FROM predictions WHERE session_id = p_session_id),
        total_bets_placed = (SELECT COUNT(*) FROM bets WHERE session_id = p_session_id),
        bets_won = (SELECT COUNT(*) FROM bets WHERE session_id = p_session_id AND won = TRUE),
        bets_lost = (SELECT COUNT(*) FROM bets WHERE session_id = p_session_id AND won = FALSE),
        total_staked = (SELECT COALESCE(SUM(stake), 0) FROM bets WHERE session_id = p_session_id),
        total_profit = (SELECT COALESCE(SUM(profit), 0) FROM bets WHERE session_id = p_session_id AND won IS NOT NULL),
        roi_percent = (SELECT ROUND((COALESCE(SUM(profit), 0) / NULLIF(SUM(stake), 0)) * 100, 2) 
                      FROM bets WHERE session_id = p_session_id AND won IS NOT NULL),
        updated_at = NOW()
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- COMMENTS
-- ==============================================================================
COMMENT ON TABLE predictions IS 'Complete feature set for all runners in all races - optimized for grid search';
COMMENT ON TABLE races IS 'Race-level metadata and results';
COMMENT ON TABLE bets IS 'Actual bets placed with results';
COMMENT ON TABLE sessions IS 'Runtime session tracking';
COMMENT ON VIEW v_grid_search_data IS 'Denormalized view ready for grid search analysis';
