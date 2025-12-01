#!/usr/bin/env python3
"""
GB Track Specialist Predictor
Implements Optimal Betting Strategy from OPTIMAL_BETTING_STRATEGY.md

STRATEGY:
- Mid-Range Odds (5.0-10.0): 35% probability threshold, expect 30-40% win rate
- Longshots (10.0-20.0): 25% probability threshold, expect 20-30% win rate
- Only bet on TOP predicted runner in each race
- Category filters for mid-range: HC, A6, A7, D3, A3, A5, A1, A9
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import sys
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Import GB Ensemble Predictor V2
sys.path.append(str(Path(__file__).parent.parent / '03_GB_Ensemble' / 'Production'))
from gb_ensemble_predictor_v2 import GBEnsemblePredictor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GBTrackSpecialistPredictor:
    """
    GB Track Specialist Predictor implementing optimal betting strategy.
    
    Two strategies:
    1. Mid-Range Odds (5.0-10.0): 35% probability threshold
    2. Longshots (10.0-20.0): 25% probability threshold
    """
    
    # Preferred categories for mid-range bets
    MIDRANGE_PREFERRED_CATEGORIES = ['HC', 'A6', 'A7', 'D3', 'A3', 'A5', 'A1', 'A9']
    
    def __init__(self):
        """Initialize GB Track Specialist predictor."""
        logger.info("Initializing GB Track Specialist Predictor...")
        
        # Load GB Ensemble Predictor V2
        self.predictor = GBEnsemblePredictor()
        
        # Strategy configuration
        self.midrange_config = {
            'min_odds': 5.0,
            'max_odds': 10.0,
            'min_probability': 0.35,
            'alternative_probability': 0.30,  # For more volume
            'preferred_categories': self.MIDRANGE_PREFERRED_CATEGORIES,
            'expected_win_rate': 0.35,  # Conservative estimate (vs 99% backtest)
            'expected_roi': 544.0
        }
        
        self.longshot_config = {
            'min_odds': 10.0,
            'max_odds': 20.0,
            'min_probability': 0.25,
            'safer_probability': 0.30,  # For more conservative approach
            'expected_win_rate': 0.25,  # Conservative estimate (vs 100% backtest)
            'expected_roi': 1177.0
        }
        
        logger.info("✓ GB Track Specialist Predictor initialized")
        logger.info(f"  Mid-range odds: {self.midrange_config['min_odds']}-{self.midrange_config['max_odds']}")
        logger.info(f"  Mid-range threshold: {self.midrange_config['min_probability']:.0%}")
        logger.info(f"  Longshot odds: {self.longshot_config['min_odds']}-{self.longshot_config['max_odds']}")
        logger.info(f"  Longshot threshold: {self.longshot_config['min_probability']:.0%}")
    
    def identify_betting_opportunities(self, race_data: Dict) -> List[Dict]:
        """
        Identify betting opportunities based on optimal strategy.
        
        Args:
            race_data: Race data including runners, odds, venue, etc.
            
        Returns:
            List of betting opportunities
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"GB TRACK SPECIALIST: Analyzing betting opportunities")
        logger.info(f"Venue: {race_data['venue']}")
        logger.info(f"Category: {race_data.get('race_grade', 'Unknown')}")
        
        # Get predictions from GB Ensemble
        prediction_results = self.predictor.predict_race(race_data)
        
        if not prediction_results['predictions']:
            logger.info("No predictions available")
            return []
        
        # Find top predicted runner
        predictions = prediction_results['predictions']
        top_runner = max(predictions, key=lambda x: x['win_probability']['calibrated'])
        
        logger.info(f"\nTop predicted runner:")
        logger.info(f"  {top_runner['runner_name']} (Trap {top_runner['trap']})")
        logger.info(f"  LTP: {top_runner['ltp']:.2f}")
        logger.info(f"  Win probability: {top_runner['win_probability']['calibrated']:.1%}")
        
        # Check which strategy applies
        odds = top_runner['ltp']
        probability = top_runner['win_probability']['calibrated']
        category = race_data.get('race_grade', 'Unknown')
        
        opportunity = None
        strategy_type = None
        
        # Strategy 1: Mid-Range Odds (5.0-10.0)
        if self.midrange_config['min_odds'] <= odds <= self.midrange_config['max_odds']:
            strategy_type = 'MIDRANGE'
            
            if probability >= self.midrange_config['min_probability']:
                # Check if in preferred category
                if category in self.MIDRANGE_PREFERRED_CATEGORIES:
                    logger.info(f"\n✓ MIDRANGE BET QUALIFIED (Preferred Category)")
                    logger.info(f"  Category: {category} (in {self.MIDRANGE_PREFERRED_CATEGORIES})")
                    logger.info(f"  Probability: {probability:.1%} >= {self.midrange_config['min_probability']:.1%}")
                    opportunity = self._create_opportunity(top_runner, race_data, 'MIDRANGE_PREFERRED')
                else:
                    # Still bet at 35%+ threshold even if not preferred category
                    logger.info(f"\n✓ MIDRANGE BET QUALIFIED (Non-preferred Category)")
                    logger.info(f"  Category: {category} (not in preferred list)")
                    logger.info(f"  Probability: {probability:.1%} >= {self.midrange_config['min_probability']:.1%}")
                    opportunity = self._create_opportunity(top_runner, race_data, 'MIDRANGE_STANDARD')
            else:
                logger.info(f"\n✗ MIDRANGE: Probability too low ({probability:.1%} < {self.midrange_config['min_probability']:.1%})")
        
        # Strategy 2: Longshots (10.0-20.0)
        elif self.longshot_config['min_odds'] <= odds <= self.longshot_config['max_odds']:
            strategy_type = 'LONGSHOT'
            
            if probability >= self.longshot_config['min_probability']:
                confidence = 'HIGH' if probability >= self.longshot_config['safer_probability'] else 'MEDIUM'
                logger.info(f"\n✓ LONGSHOT BET QUALIFIED ({confidence} confidence)")
                logger.info(f"  Probability: {probability:.1%} >= {self.longshot_config['min_probability']:.1%}")
                opportunity = self._create_opportunity(top_runner, race_data, f'LONGSHOT_{confidence}')
            else:
                logger.info(f"\n✗ LONGSHOT: Probability too low ({probability:.1%} < {self.longshot_config['min_probability']:.1%})")
        
        # Odds outside both strategies
        else:
            if odds < self.midrange_config['min_odds']:
                logger.info(f"\n✗ Odds too low ({odds:.2f} < {self.midrange_config['min_odds']:.2f})")
            else:
                logger.info(f"\n✗ Odds too high ({odds:.2f} > {self.longshot_config['max_odds']:.2f})")
        
        logger.info(f"{'='*70}\n")
        
        return [opportunity] if opportunity else []
    
    def _create_opportunity(self, runner: Dict, race_data: Dict, strategy_subtype: str) -> Dict:
        """Create betting opportunity data structure."""
        odds = runner['ltp']
        probability = runner['win_probability']['calibrated']
        
        # Calculate expected value
        expected_value = (probability * odds) - 1.0
        
        # Determine strategy type
        if 'MIDRANGE' in strategy_subtype:
            stake_recommendation = 10.0  # $10 flat stake for mid-range
            strategy = 'MIDRANGE'
        else:
            stake_recommendation = 5.0   # $5 flat stake for longshots
            strategy = 'LONGSHOT'
        
        opportunity = {
            'market_id': race_data['market_id'],
            'selection_id': runner['selection_id'],
            'runner_name': runner['runner_name'],
            'trap': runner['trap'],
            'runner_odds': odds,
            'win_probability': probability,
            'expected_value': expected_value,
            'strategy': strategy,
            'strategy_subtype': strategy_subtype,
            'stake_recommendation': stake_recommendation,
            'race_info': {
                'venue': race_data['venue'],
                'race_time': race_data['race_time'],
                'distance': race_data.get('distance'),
                'race_grade': race_data.get('race_grade'),
                'country_code': race_data.get('country_code', 'GB')
            },
            'identified_time': datetime.now().isoformat()
        }
        
        return opportunity


if __name__ == "__main__":
    """Test the predictor."""
    print("\n" + "="*70)
    print("GB TRACK SPECIALIST PREDICTOR - TEST MODE")
    print("="*70 + "\n")
    
    predictor = GBTrackSpecialistPredictor()
    
    # Test 1: Mid-range bet (A6 category, good probability)
    print("\n" + "="*70)
    print("TEST 1: Mid-Range Bet Candidate (A6, 7.5 odds)")
    print("="*70)
    
    test_race_1 = {
        'market_id': 'TEST_MID_001',
        'venue': 'Romford',
        'distance': 400,
        'race_grade': 'A6',
        'race_time': '2024-01-15T19:30:00.000Z',
        'country_code': 'GB',
        'runners': [
            {'runner_name': 'Favorite Dog', 'selection_id': 1, 'trap': 1, 'ltp': 2.5},
            {'runner_name': 'Mid-Range Dog', 'selection_id': 2, 'trap': 2, 'ltp': 7.5},  # Target
            {'runner_name': 'Outsider', 'selection_id': 3, 'trap': 3, 'ltp': 15.0},
        ]
    }
    
    opps_1 = predictor.identify_betting_opportunities(test_race_1)
    print(f"\nResult: {len(opps_1)} opportunity/opportunities identified")
    if opps_1:
        for opp in opps_1:
            print(f"  → ${opp['stake_recommendation']:.2f} on {opp['runner_name']} @ {opp['runner_odds']:.2f}")
            print(f"     Strategy: {opp['strategy_subtype']}")
    
    # Test 2: Longshot bet
    print("\n" + "="*70)
    print("TEST 2: Longshot Bet Candidate (D3, 12.0 odds)")
    print("="*70)
    
    test_race_2 = {
        'market_id': 'TEST_LONG_001',
        'venue': 'Swindon',
        'distance': 450,
        'race_grade': 'D3',
        'race_time': '2024-01-15T20:00:00.000Z',
        'country_code': 'GB',
        'runners': [
            {'runner_name': 'Favorite', 'selection_id': 1, 'trap': 1, 'ltp': 3.0},
            {'runner_name': 'Second Fav', 'selection_id': 2, 'trap': 2, 'ltp': 5.0},
            {'runner_name': 'Longshot Dog', 'selection_id': 3, 'trap': 3, 'ltp': 12.0},  # Target
        ]
    }
    
    opps_2 = predictor.identify_betting_opportunities(test_race_2)
    print(f"\nResult: {len(opps_2)} opportunity/opportunities identified")
    if opps_2:
        for opp in opps_2:
            print(f"  → ${opp['stake_recommendation']:.2f} on {opp['runner_name']} @ {opp['runner_odds']:.2f}")
            print(f"     Strategy: {opp['strategy_subtype']}")
    
    print("\n" + "="*70)
    print("✓ Tests complete")
    print("="*70 + "\n")
