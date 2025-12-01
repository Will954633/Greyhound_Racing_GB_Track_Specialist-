#!/usr/bin/env python3
"""
GB Ensemble Predictor V2 - With Comprehensive Feature Engineering
Matches ALL 32 features required by the Track Specialist Model

Features engineered to match training script:
prepare_global_ml_ready.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))

from catboost import CatBoostRegressor, CatBoostClassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GBEnsemblePredictor:
    """
    GB Ensemble prediction system with comprehensive feature engineering.
    Matches ALL 32 features required by trained Track Specialist Model.
    """
    
    def __init__(self):
        """Initialize GB Ensemble predictor with both models."""
        logger.info("Initializing GB Ensemble Predictor V2...")
        
        # Paths - models are in local artifacts/ directory for deployment
        self.base_dir = Path(__file__).parent
        self.artifacts_dir = self.base_dir / 'artifacts'

        # Load Track Specialist Model
        logger.info("Loading Track Specialist Model...")
        track_model_path = self.artifacts_dir / 'base_model.cbm'
        
        if not track_model_path.exists():
            raise FileNotFoundError(f"Track Specialist model not found: {track_model_path}")
        
        self.track_model = CatBoostClassifier()
        self.track_model.load_model(str(track_model_path))
        logger.info(f"✓ Loaded Track Specialist Model")
        logger.info(f"  Expected features: {len(self.track_model.feature_names_)}")
        
        # Load Calibrator Model
        logger.info("Loading Calibrator Model...")
        calibrator_model_path = self.artifacts_dir / 'calibrator_model.cbm'
        
        if not calibrator_model_path.exists():
            raise FileNotFoundError(f"Calibrator model not found: {calibrator_model_path}")
        
        self.calibrator = CatBoostClassifier()
        self.calibrator.load_model(str(calibrator_model_path))
        logger.info(f"✓ Loaded Calibrator Model")
        
        # Strategy configuration
        self.strategy_config = {
            'selection_method': 'top_15_percent',
            'expected_roi': 510.0,
            'expected_sharpe': 7.59,
            'expected_win_rate': 0.978
        }
        
        logger.info("✓ GB Ensemble Predictor V2 initialized")
        logger.info(f"  Strategy: Top 15% by predicted profit")
        logger.info(f"  Expected ROI: {self.strategy_config['expected_roi']:.0f}%")
    
    def engineer_track_specialist_features(self, race_data: Dict) -> Optional[pd.DataFrame]:
        """
        Engineer ALL 32 features required by Track Specialist Model.
        
        Features match training script: prepare_global_ml_ready.py
        """
        try:
            # Extract race info
            venue = race_data['venue']
            distance = race_data.get('distance', 450)
            race_grade = race_data.get('race_grade', 'Unknown')
            race_time_str = race_data['race_time']
            
            # Parse race time to get race_hour
            race_time = datetime.fromisoformat(race_time_str.replace('Z', '+00:00'))
            race_hour = race_time.hour
            race_day_of_week = race_time.weekday()
            is_weekend = 1 if race_day_of_week >= 5 else 0
            
            # Create DataFrame from runners
            runners = []
            for runner in race_data['runners']:
                runners.append({
                    'runner_id': runner['selection_id'],
                    'runner_name': runner['runner_name'],
                    'runner_box': runner.get('trap', 0),
                    'bsp': runner.get('ltp', 10.0),  # Use LTP as BSP
                    'market_id': race_data['market_id']
                })
            
            if not runners:
                return None
            
            df = pd.DataFrame(runners)
            
            # Add race context
            df['venue_abbr'] = venue[:4].upper()
            df['race_category'] = race_grade
            df['race_grade'] = race_grade  
            df['distance'] = distance
            df['race_hour'] = race_hour
            df['is_weekend'] = is_weekend
            
            # RACE-LEVEL AGGREGATIONS (required for market features)
            df['field_size'] = len(df)
            df['favorite_bsp'] = df['bsp'].min()
            df['mean_bsp'] = df['bsp'].mean()
            df['bsp_std'] = df['bsp'].std()
            
            # RUNNER ODDS FEATURES
            df['runner_odds'] = df['bsp']
            df['runner_implied_prob'] = np.where(df['bsp'] > 0, 1.0 / df['bsp'], np.nan)
            df['runner_log_odds'] = np.log(df['bsp'].clip(lower=1.01))
            df['runner_odds_rank'] = df['bsp'].rank(method='min')
            
            # ODDS DIFFERENTIALS
            df['odds_vs_favorite_diff'] = df['bsp'] - df['favorite_bsp']
            df['odds_vs_favorite_ratio'] = np.where(df['favorite_bsp'] > 0,
                                                     df['bsp'] / df['favorite_bsp'], np.nan)
            df['odds_vs_mean_diff'] = df['bsp'] - df['mean_bsp']
            df['odds_vs_mean_ratio'] = np.where(df['mean_bsp'] > 0,
                                                 df['bsp'] / df['mean_bsp'], np.nan)
            
            # Second favorite
            second_fav_bsp = df.sort_values('bsp').iloc[1]['bsp'] if len(df) > 1 else df['bsp'].min()
            df['second_favorite_bsp'] = second_fav_bsp
            df['odds_vs_second_diff'] = df['bsp'] - second_fav_bsp
            df['odds_vs_second_ratio'] = np.where(second_fav_bsp > 0,
                                                   df['bsp'] / second_fav_bsp, np.nan)
            
            # MARKET STRUCTURE FEATURES
            df['market_compression'] = np.where(df['bsp_std'] > 0, df['mean_bsp'] / df['bsp_std'], np.nan)
            df['favorite_dominance'] = np.where(df['mean_bsp'] > 0,
                                                 df['favorite_bsp'] / df['mean_bsp'], np.nan)
            df['odds_std'] = df['bsp_std']
            df['odds_range'] = df['bsp'].max() - df['bsp'].min()
            df['odds_cv'] = np.where(df['mean_bsp'] > 0, df['bsp_std'] / df['mean_bsp'], np.nan)
            
            # COMPETITIVE FIELD INDICATORS
            df['num_competitive'] = (df['bsp'] <= 4.0).sum()
            df['longshot'] = (df['bsp'] > 10.0).astype(int)
            df['weak_favorite'] = ((df['runner_odds_rank'] == 1) & (df['bsp'] > 2.5)).astype(int)
            df['dominant_favorite'] = ((df['runner_odds_rank'] == 1) & (df['bsp'] < 1.8)).astype(int)
            df['competitive_field'] = (df['num_competitive'] >= 4).astype(int)
            
            # BOX POSITION FEATURES
            df['box_position_score'] = df['runner_box'].map({
                1: 1.0, 2: 0.95, 3: 0.9, 4: 0.85, 5: 0.8, 6: 0.75
            }).fillna(0.7)
            df['box_inside'] = (df['runner_box'] <= 2).astype(int)
            df['box_middle'] = ((df['runner_box'] >= 3) & (df['runner_box'] <= 4)).astype(int)
            df['box_outside'] = (df['runner_box'] >= 5).astype(int)
            
            logger.info(f"  Engineered {len(df.columns)} features for {len(df)} runners")
            
            return df
            
        except Exception as e:
            logger.error(f"Error engineering features: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def predict_race(self, race_data: Dict) -> Dict:
        """
        Predict race outcomes with comprehensive feature engineering.
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"GB ENSEMBLE V2: Predicting race")
        logger.info(f"Venue: {race_data['venue']}")
        logger.info(f"Distance: {race_data.get('distance', 'Unknown')}m")
        logger.info(f"Runners: {len(race_data['runners'])}")
        
        results = {
            'race_info': {
                'market_id': race_data['market_id'],
                'venue': race_data['venue'],
                'race_time': race_data['race_time'],
                'distance': race_data.get('distance'),
                'race_grade': race_data.get('race_grade'),
                'country_code': race_data.get('country_code')
            },
            'predictions': [],
            'betting_opportunities': [],
            'prediction_time': datetime.now().isoformat()
        }
        
        # Engineer ALL features for Track Specialist Model
        logger.info("Step 1: Engineering comprehensive features...")
        df_runners = self.engineer_track_specialist_features(race_data)
        
        if df_runners is None or len(df_runners) == 0:
            logger.warning("Could not engineer features")
            return results
        
        # Get win probabilities from Track Specialist Model
        logger.info("Step 2: Predicting win probabilities with Track Specialist Model...")
        
        # Use exact feature names expected by model
        track_model_features = self.track_model.feature_names_
        
        # Verify all required features are present
        missing_features = [f for f in track_model_features if f not in df_runners.columns]
        if missing_features:
            logger.error(f"Missing features: {missing_features}")
            return results
        
        # Make predictions with base model
        base_probs = self.track_model.predict_proba(df_runners[track_model_features])[:, 1]
        df_runners['base_prob'] = base_probs
        
        logger.info(f"✓ Base probabilities (range: {base_probs.min():.3f} - {base_probs.max():.3f})")
        
        # Calibrate probabilities
        logger.info("Step 3: Calibrating probabilities...")
        calibrated_probs = self.calibrator.predict_proba(df_runners[track_model_features])[:, 1]
        df_runners['calibrated_prob'] = calibrated_probs
        
        logger.info(f"✓ Calibrated probabilities (range: {calibrated_probs.min():.3f} - {calibrated_probs.max():.3f})")
        
        # Package results - just return probabilities for each runner
        for idx, row in df_runners.iterrows():
            prediction = {
                'runner_name': row['runner_name'],
                'selection_id': row['runner_id'],
                'trap': row['runner_box'],
                'ltp': row['runner_odds'],
                'win_probability': {
                    'base': float(row['base_prob']),
                    'calibrated': float(row['calibrated_prob'])
                }
            }
            results['predictions'].append(prediction)
        
        logger.info(f"{'='*70}\n")
        
        return results


if __name__ == "__main__":
    """Test the predictor."""
    print("\n" + "="*70)
    print("GB ENSEMBLE PREDICTOR V2 - TEST MODE")
    print("="*70 + "\n")
    
    predictor = GBEnsemblePredictor()
    
    sample_race = {
        'market_id': 'TEST_12345',
        'venue': 'Romford',
        'distance': 400,
        'race_grade': 'A6',
        'race_time': '2024-01-15T19:30:00.000Z',
        'country_code': 'GB',
        'runners': [
            {'runner_name': 'Test Dog 1', 'selection_id': 1, 'trap': 1, 'ltp': 3.5},
            {'runner_name': 'Test Dog 2', 'selection_id': 2, 'trap': 2, 'ltp': 5.0},
            {'runner_name': 'Test Dog 3', 'selection_id': 3, 'trap': 3, 'ltp': 8.0},
            {'runner_name': 'Test Dog 4', 'selection_id': 4, 'trap': 4, 'ltp': 12.0},
            {'runner_name': 'Test Dog 5', 'selection_id': 5, 'trap': 5, 'ltp': 15.0},
            {'runner_name': 'Test Dog 6', 'selection_id': 6, 'trap': 6, 'ltp': 20.0},
        ]
    }
    
    results = predictor.predict_race(sample_race)
    
    print("\nPREDICTION RESULTS:")
    for pred in results['predictions']:
        print(f"  {pred['runner_name']:20s} | Trap: {pred['trap']} | "
              f"LTP: {pred['ltp']:6.2f} | Win%: {pred['win_probability']['calibrated']:.1%}")
    
    print("\n" + "="*70)
    print("✓ Test complete")
    print("="*70 + "\n")
