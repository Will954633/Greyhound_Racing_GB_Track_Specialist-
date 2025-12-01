#!/usr/bin/env python3
"""
Database Helper for GB Track Specialist
PostgreSQL integration with fallback to JSON logging
"""

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from typing import Dict, List, Optional
import logging
import os
from datetime import datetime
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseHelper:
    """
    PostgreSQL database helper with connection pooling and JSON fallback.
    """
    
    def __init__(self, database_url: Optional[str] = None, pool_size: int = 5):
        """
        Initialize database connection.
        
        Args:
            database_url: PostgreSQL connection string (or from env)
            pool_size: Connection pool size
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.pool = None
        self.connected = False
        
        if self.database_url:
            try:
                self.pool = SimpleConnectionPool(1, pool_size, self.database_url)
                self.connected = True
                logger.info("✓ Connected to PostgreSQL database")
                self._initialize_schema()
            except Exception as e:
                logger.warning(f"Could not connect to database: {str(e)}")
                logger.warning("Falling back to JSON-only logging")
                self.connected = False
        else:
            logger.warning("No DATABASE_URL found - using JSON-only logging")
    
    def _initialize_schema(self):
        """Initialize database schema if needed."""
        try:
            schema_file = Path(__file__).parent / 'database_schema.sql'
            if schema_file.exists():
                conn = self.pool.getconn()
                try:
                    with conn.cursor() as cur:
                        with open(schema_file, 'r') as f:
                            cur.execute(f.read())
                        conn.commit()
                    logger.info("✓ Database schema initialized")
                finally:
                    self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error initializing schema: {str(e)}")
    
    def log_session_start(self, session_data: Dict) -> bool:
        """Log session start."""
        if not self.connected:
            return False
        
        try:
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO sessions (
                            session_id, dry_run, scan_interval_minutes,
                            target_minutes_before_race, system_version,
                            python_version, deployment_env
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (session_id) DO NOTHING
                    """, (
                        session_data['session_id'],
                        session_data.get('dry_run', True),
                        session_data.get('scan_interval_minutes'),
                        session_data.get('target_minutes_before_race'),
                        session_data.get('system_version'),
                        session_data.get('python_version'),
                        session_data.get('deployment_env', 'local')
                    ))
                    conn.commit()
                return True
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error logging session start: {str(e)}")
            return False
    
    def log_race(self, race_data: Dict) -> bool:
        """Log race metadata."""
        if not self.connected:
            return False
        
        try:
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Parse race time
                    race_time = datetime.fromisoformat(race_data['race_time'].replace('Z', '+00:00'))
                    
                    cur.execute("""
                        INSERT INTO races (
                            market_id, market_name, event_name, venue, country_code,
                            race_time, race_date,  race_hour, race_day_of_week, is_weekend,
                            distance, race_grade, num_runners, status, session_id, system
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (market_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            updated_at = NOW()
                    """, (
                        race_data['market_id'],
                        race_data.get('market_name'),
                        race_data.get('event_name'),
                        race_data['venue'],
                        race_data.get('country_code', 'GB'),
                        race_time,
                        race_time.date(),
                        race_time.hour,
                        race_time.weekday(),
                        race_time.weekday() >= 5,
                        race_data.get('distance'),
                        race_data.get('race_grade'),
                        len(race_data.get('runners', [])),
                        race_data.get('status'),
                        race_data.get('session_id'),
                        race_data.get('system', 'gb_track_specialist')
                    ))
                    conn.commit()
                return True
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error logging race: {str(e)}")
            return False
    
    def log_predictions(self, predictions_df, session_id: str) -> bool:
        """
        Log ALL predictions with complete feature set.
        
        Args:
            predictions_df: DataFrame with ALL CatBoost features
            session_id: Session identifier
        """
        if not self.connected or predictions_df is None or len(predictions_df) == 0:
            return False
        
        try:
            conn = self.pool.getconn()
            try:
                # Convert DataFrame to records
                records = []
                for _, row in predictions_df.iterrows():
                    # Parse race time
                    race_time = datetime.fromisoformat(row['race_time'].replace('Z', '+00:00'))
                    
                    record = (
                        row['market_id'],
                        row['runner_id'],
                        row['runner_name'],
                        row.get('venue'),
                        row.get('venue_abbr'),
                        race_time,
                        race_time.date(),
                        race_time.hour,
                        race_time.weekday(),
                        race_time.weekday() >= 5,
                        row.get('distance'),
                        row.get('race_grade'),
                        row.get('race_category'),
                        row.get('country_code', 'GB'),
                        row.get('runner_box'),
                        row.get('runner_odds'),
                        row.get('runner_box'),
                        row.get('calibrated_prob'),
                        row.get('base_prob'),
                        row.get('base_prob'),
                        row.get('calibrated_prob'),
                        row.get('runner_implied_prob'),
                        row.get('field_size'),
                        row.get('favorite_bsp'),
                        row.get('mean_bsp'),
                        row.get('bsp_std'),
                        row.get('second_favorite_bsp'),
                        row.get('runner_log_odds'),
                        row.get('runner_odds_rank'),
                        row.get('odds_vs_favorite_diff'),
                        row.get('odds_vs_favorite_ratio'),
                        row.get('odds_vs_mean_diff'),
                        row.get('odds_vs_mean_ratio'),
                        row.get('odds_vs_second_diff'),
                        row.get('odds_vs_second_ratio'),
                        row.get('market_compression'),
                        row.get('favorite_dominance'),
                        row.get('odds_std'),
                        row.get('odds_range'),
                        row.get('odds_cv'),
                        row.get('num_competitive'),
                        row.get('longshot', False),
                        row.get('weak_favorite', False),
                        row.get('dominant_favorite', False),
                        row.get('competitive_field', False),
                        row.get('box_position_score'),
                        row.get('box_inside', False),
                        row.get('box_middle', False),
                        row.get('box_outside', False),
                        row.get('predicted_profit'),
                        row.get('prob_spread'),
                        row.get('favorite_prob'),
                        row.get('prob_odds_gap'),
                        row.get('rank_by_prob'),
                        row.get('rank_discrepancy'),
                        row.get('is_favorite', False),
                        row.get('is_longshot', False),
                        row.get('competitive_runners'),
                        row.get('is_competitive_field', False),
                        session_id,
                        row.get('system', 'gb_track_specialist')
                    )
                    records.append(record)
                
                # Bulk insert
                with conn.cursor() as cur:
                    execute_values(cur, """
                        INSERT INTO predictions (
                            market_id, selection_id, runner_name,
                            venue, venue_abbr, race_time, race_date, race_hour, race_day_of_week, is_weekend,
                            distance, race_grade, race_category, country_code,
                            trap, runner_odds, runner_box,
                            win_probability, win_probability_raw, base_prob, calibrated_prob, runner_implied_prob,
                            field_size, favorite_bsp, mean_bsp, bsp_std, second_favorite_bsp,
                            runner_log_odds, runner_odds_rank,
                            odds_vs_favorite_diff, odds_vs_favorite_ratio,
                            odds_vs_mean_diff, odds_vs_mean_ratio,
                            odds_vs_second_diff, odds_vs_second_ratio,
                            market_compression, favorite_dominance, odds_std, odds_range, odds_cv,
                            num_competitive, longshot, weak_favorite, dominant_favorite, competitive_field,
                            box_position_score, box_inside, box_middle, box_outside,
                            predicted_profit, prob_spread, favorite_prob, prob_odds_gap,
                            rank_by_prob, rank_discrepancy, is_favorite, is_longshot,
                            competitive_runners, is_competitive_field,
                            session_id, system
                        ) VALUES %s
                        ON CONFLICT (market_id, selection_id) DO NOTHING
                    """, records)
                    conn.commit()
                
                logger.info(f"✓ Logged {len(records)} predictions to database")
                return True
                
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error logging predictions: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def log_bet(self, bet_data: Dict) -> bool:
        """Log a placed bet."""
        if not self.connected:
            return False
        
        try:
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    race_time = datetime.fromisoformat(bet_data['race_time'].replace('Z', '+00:00')) if 'race_time' in bet_data else None
                    
                    cur.execute("""
                        INSERT INTO bets (
                            bet_id, market_id, selection_id, runner_name, runner_odds, trap,
                            stake, status, strategy, strategy_subtype,
                            win_probability, expected_value,
                            venue, race_time, race_grade, distance,
                            session_id, system, dry_run
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (bet_id) DO NOTHING
                    """, (
                        bet_data['bet_id'],
                        bet_data['market_id'],
                        bet_data['selection_id'],
                        bet_data.get('runner_name'),
                        bet_data.get('runner_odds'),
                        bet_data.get('trap'),
                        bet_data['stake'],
                        bet_data.get('status'),
                        bet_data.get('strategy'),
                        bet_data.get('strategy_subtype'),
                        bet_data.get('win_probability'),
                        bet_data.get('expected_value'),
                        bet_data.get('venue'),
                        race_time,
                        bet_data.get('race_grade'),
                        bet_data.get('distance'),
                        bet_data.get('session_id'),
                        bet_data.get('system', 'gb_track_specialist'),
                        bet_data.get('dry_run', True)
                    ))
                    conn.commit()
                return True
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error logging bet: {str(e)}")
            return False
    
    def update_race_result(self, market_id: str, winner_data: Dict) -> bool:
        """Update race with result."""
        if not self.connected:
            return False
        
        try:
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    # Update race table
                    cur.execute("""
                        UPDATE races SET
                            winner_selection_id = %s,
                            winner_name = %s,
                            winner_odds = %s,
                            result_checked_time = NOW(),
                            updated_at = NOW()
                        WHERE market_id = %s
                    """, (
                        winner_data.get('selection_id'),
                        winner_data.get('runner_name'),
                        winner_data.get('odds'),
                        market_id
                    ))
                    
                    # Update predictions table
                    cur.execute("""
                        UPDATE predictions SET
                            won = (selection_id = %s),
                            actual_winner_selection_id = %s,
                            actual_winner_name = %s,
                            actual_winner_odds = %s,
                            result_checked_time = NOW()
                        WHERE market_id = %s
                    """, (
                        winner_data.get('selection_id'),
                        winner_data.get('selection_id'),
                        winner_data.get('runner_name'),
                        winner_data.get('odds'),
                        market_id
                    ))
                    
                    # Update bets table
                    cur.execute("""
                        UPDATE bets SET
                            won = (selection_id = %s),
                            winner_selection_id = %s,
                            returns = CASE WHEN selection_id = %s THEN stake * runner_odds ELSE 0 END,
                            profit = CASE WHEN selection_id = %s THEN (stake * runner_odds) - stake ELSE -stake END,
                            result_checked_time = NOW()
                        WHERE market_id = %s
                    """, (
                        winner_data.get('selection_id'),
                        winner_data.get('selection_id'),
                        winner_data.get('selection_id'),
                        winner_data.get('selection_id'),
                        market_id
                    ))
                    
                    conn.commit()
                return True
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error updating race result: {str(e)}")
            return False
    
    def update_session_stats(self, session_id: str) -> bool:
        """Update session statistics."""
        if not self.connected:
            return False
        
        try:
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT update_session_stats(%s)", (session_id,))
                    conn.commit()
                return True
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error updating session stats: {str(e)}")
            return False
    
    def close_session(self, session_id: str) -> bool:
        """Mark session as ended."""
        if not self.connected:
            return False
        
        try:
            self.update_session_stats(session_id)
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE sessions SET ended_at = NOW()
                        WHERE session_id = %s
                    """, (session_id,))
                    conn.commit()
                return True
            finally:
                self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error closing session: {str(e)}")
            return False
    
    def cleanup(self):
        """Cleanup database connections."""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connections closed")


if __name__ == "__main__":
    """Test database helper."""
    print("Testing Database Helper...")
    
    db = DatabaseHelper()
    
    if db.connected:
        print("✓ Database connected")
        
        # Test session logging
        session_data = {
            'session_id': f'test_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'dry_run': True,
            'scan_interval_minutes': 15,
            'target_minutes_before_race': 1,
            'system_version': '1.0.0',
            'python_version': '3.9',
            'deployment_env': 'test'
        }
        
        if db.log_session_start(session_data):
            print("✓ Session logged")
        
        db.cleanup()
        print("✓ Test complete")
    else:
        print("✗ Database not connected - JSON only mode")
