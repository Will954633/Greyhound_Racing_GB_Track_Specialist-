#!/usr/bin/env python3
"""
GB Track Specialist Betting System
Production trial implementing optimal mid-range & longshot strategy

STRATEGY:
- Mid-Range (5.0-10.0 odds): 35% probability threshold, $10 stakes
- Longshots (10.0-20.0 odds): 25% probability threshold, $5 stakes
- Only bet on top predicted runner per race
- Category preferences for mid-range: HC, A6, A7, D3, A3, A5, A1, A9

LOGGING:
- Individual race logs: logs/gb_track_specialist/session_TIMESTAMP/
- Comprehensive session logs with all races and bets
- Winner updates via background thread
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import logging
import time
import threading
import sys
import re

from betfair_client import BetfairClient
from gb_track_specialist_predictor import GBTrackSpecialistPredictor
from database_helper import DatabaseHelper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GBBettingSystem:
    """
    Complete betting system for GB Track Specialist strategy.
    """
    
    def __init__(self, dry_run: bool = True):
        """
        Initialize GB betting system.
        
        Args:
            dry_run: If True, don't place real bets (log only)
        """
        self.dry_run = dry_run
        self.system_name = "gb_track_specialist"
        
        # Initialize components
        logger.info("="*70)
        logger.info("Initializing GB Track Specialist Betting System")
        logger.info("="*70)
        
        self.predictor = GBTrackSpecialistPredictor()
        self.betfair_client = BetfairClient()
        self.db = DatabaseHelper()
        
        # Login to Betfair
        if not self.betfair_client.session_token:
            logger.info("Logging in to Betfair...")
            if not self.betfair_client.login():
                raise RuntimeError("Failed to login to Betfair")
            logger.info("✓ Logged in to Betfair")
        
        # Betting configuration
        self.result_check_delay_minutes = 45  # Check results 45min after race
        
        # Initialize comprehensive tracking
        self.all_races_log = []  # ALL races processed
        self.all_runners_log = []  # ALL runners from all races
        self.all_predictions_log = []  # ALL model predictions for ALL runners  **NEW**
        self.bets_placed_log = []  # ONLY actual bets placed
        self.pending_results = {}  # Market_id -> race data for result checking
        
        # Session tracking
        self.session_start = datetime.now()
        self.session_id = self.session_start.strftime("%Y%m%d_%H%M%S")
        self.session_dir = Path("logs") / self.system_name / f"session_{self.session_id}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.race_logs = {}  # market_id -> race log data
        
        logger.info(f"✓ GB Track Specialist initialized")
        logger.info(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE BETTING'}")
        logger.info(f"  Session directory: {self.session_dir}")
        logger.info("="*70 + "\n")
        
        # Start result checking thread
        self.result_checker_running = True
        self.result_checker_thread = threading.Thread(target=self._result_checker_loop, daemon=True)
        self.result_checker_thread.start()
    
    def get_race_data(self, market_id: str) -> Optional[Dict]:
        """Fetch complete race data from Betfair."""
        try:
            # Get market catalogue
            market_catalogue = self.betfair_client._make_api_request(
                self.betfair_client.BETTING_URL,
                'SportsAPING/v1.0/listMarketCatalogue',
                params={
                    'filter': {'marketIds': [market_id]},
                    'maxResults': 1,
                    'marketProjection': [
                        'COMPETITION', 'EVENT', 'EVENT_TYPE',
                        'MARKET_START_TIME', 'RUNNER_DESCRIPTION', 'RUNNER_METADATA'
                    ]
                }
            )
            
            if not market_catalogue:
                return None
            
            market = market_catalogue[0]
            
            # Get current prices
            market_book = self.betfair_client.get_market_book([market_id])
            if not market_book:
                return None
            
            prices = market_book[0]
            
            # Extract race data
            race_data = {
                'market_id': market_id,
                'market_name': market.get('marketName', ''),
                'event_name': market['event']['name'],
                'venue': market['event'].get('venue', 'Unknown'),
                'country_code': market['event'].get('countryCode', 'GB'),
                'race_time': market.get('marketStartTime', ''),
                'status': prices.get('status', 'UNKNOWN'),
                'fetch_time': datetime.now().isoformat(),
                'runners': []
            }
            
            # Extract distance
            distance_match = re.search(r'(\d+)m', race_data['market_name'])
            race_data['distance'] = int(distance_match.group(1)) if distance_match else 450
            
            # Extract grade (comprehensive UK/Irish patterns)
            race_data['race_grade'] = self._extract_race_grade(
                race_data['market_name'], race_data['event_name']
            )
            
            # Extract ALL runner data
            for catalogue_runner in market.get('runners', []):
                selection_id = catalogue_runner['selectionId']
                
                price_runner = next(
                    (r for r in prices['runners'] if r['selectionId'] == selection_id),
                    None
                )
                
                if price_runner:
                    back_prices = price_runner.get('ex', {}).get('availableToBack', [])
                    best_back = back_prices[0]['price'] if back_prices else None
                    
                    runner_name = catalogue_runner['runnerName']
                    
                    # Try to get trap from metadata first
                    metadata = catalogue_runner.get('metadata', {})
                    trap = metadata.get('CLOTH_NUMBER') or metadata.get('STALL_DRAW')
                    
                    # If no trap in metadata, extract from runner name
                    if trap is None:
                        name_match = re.match(r'^(\d+)\.\s*(.+)$', runner_name)
                        if name_match:
                            trap = int(name_match.group(1))
                            runner_name = name_match.group(2)
                    
                    runner_data = {
                        'selection_id': selection_id,
                        'runner_name': runner_name,
                        'trap': int(trap) if trap else None,
                        'ltp': best_back,  # Use best back as LTP
                        'status': price_runner.get('status'),
                        'market_id': market_id
                    }
                    
                    race_data['runners'].append(runner_data)
            
            return race_data
            
        except Exception as e:
            logger.error(f"Error fetching race data: {str(e)}")
            return None
    
    def _extract_race_grade(self, market_name: str, event_name: str) -> str:
        """Extract race grade from market or event name."""
        # Comprehensive grade patterns for UK/Irish greyhounds
        grade_patterns = [
            # Australian/NZ grades
            (r'Gr(\d+/\d+)', lambda m: f"Gr{m.group(1)}"),
            (r'Gr\s*(\d+)', lambda m: f"Grade{m.group(1)}"),
            (r'Grade\s*(\d+/\d+)', lambda m: f"Gr{m.group(1)}"),
            (r'Grade\s*(\d+)', lambda m: f"Grade{m.group(1)}"),
            
            # Maiden/Novice/Heat
            (r'\b(Mdn|MDN|Maiden)\b', lambda m: 'Mdn'),
            (r'\b(NVC|Novice|Nvc|Nov)\b', lambda m: 'Novice'),
            (r'\b(Heat|HT)\b', lambda m: 'Heat'),
            (r'\b(Juvenile|Juv|JUV)\b', lambda m: 'Juvenile'),
            
            # UK/Irish A-grades (A0-A11+)
            (r'\bA(\d{1,2})\b', lambda m: f"A{m.group(1)}"),
            
            # UK/Irish D-grades (D0-D9)
            (r'\bD(\d)\b', lambda m: f"D{m.group(1)}"),
            
            # UK/Irish C-grades (C0-C9)
            (r'\bC(\d)\b', lambda m: f"C{m.group(1)}"),
            
            # UK/Irish G-grades (G5-G7)
            (r'\bG([567])\b', lambda m: f"G{m.group(1)}"),
            
            # UK/Irish M-grades (M0-M9)
            (r'\bM(\d)\b', lambda m: f"M{m.group(1)}"),
            
            # UK/Irish P-grades (P0-P9)
            (r'\bP(\d)\b', lambda m: f"P{m.group(1)}"),
            
            # Open Race / Restricted / Handicap
            (r'\b(OR\d*)\b', lambda m: f"{m.group(1)}"),
            (r'\b(HC)\b', lambda m: 'HC'),
            (r'\b(Rest|Restricted|RST)\b', lambda m: 'Rest'),
        ]
        
        # Check market_name first
        for pattern, extractor in grade_patterns:
            grade_match = re.search(pattern, market_name, re.IGNORECASE)
            if grade_match:
                return extractor(grade_match)
        
        # If not found in market_name, check event_name
        for pattern, extractor in grade_patterns:
            grade_match = re.search(pattern, event_name, re.IGNORECASE)
            if grade_match:
                return extractor(grade_match)
        
        return 'Unknown'
    
    def process_race(self, market_id: str) -> Dict:
        """Process a single race with comprehensive logging."""
        logger.info(f"\n{'='*70}")
        logger.info(f"[GB TRACK SPECIALIST] PROCESSING RACE")
        logger.info(f"{'='*70}")
        logger.info(f"Market ID: {market_id}")
        
        # Fetch race data
        race_data = self.get_race_data(market_id)
        if not race_data:
            return {'status': 'ERROR', 'message': 'Could not fetch race data'}
        
        logger.info(f"Venue: {race_data['venue']}")
        logger.info(f"Race time: {race_data['race_time']}")
        logger.info(f"Distance: {race_data.get('distance', 'Unknown')}m")
        logger.info(f"Category/Grade: {race_data.get('race_grade', 'Unknown')}")
        logger.info(f"Event: {race_data.get('event_name', 'Unknown')}")
        logger.info(f"Runners: {len(race_data['runners'])}")
        
        # Log race (ALL races logged)
        race_log_entry = {
            **race_data,
            'system': self.system_name,
            'session_id': self.session_id
        }
        self.all_races_log.append(race_log_entry)
        
        # Log all runners
        for runner in race_data['runners']:
            runner_log = {
                **runner,
                'venue': race_data['venue'],
                'race_time': race_data['race_time'],
                'system': self.system_name,
                'logged_time': datetime.now().isoformat()
            }
            self.all_runners_log.append(runner_log)
        
        # DATABASE: Log race to database
        race_id = self.db.log_race(
            market_id=race_data['market_id'],
            venue=race_data['venue'],
            race_time=race_data['race_time'],
            distance=race_data.get('distance'),
            race_grade=race_data.get('race_grade'),
            num_runners=len(race_data['runners']),
            session_id=self.session_id
        )
        
        # Get betting opportunities (this also generates predictions for ALL runners)
        opportunities = self.predictor.identify_betting_opportunities(race_data)
        
        # **NEW: Get complete feature DataFrame and log ALL model predictions to DATABASE**
        prediction_results = self.predictor.predictor.predict_race(race_data)
        features_df = self.predictor.predictor.engineer_track_specialist_features(race_data)
        
        if features_df is not None:
            # Add race_time column for database
            features_df['race_time'] = race_data['race_time']
            features_df['market_id'] = race_data['market_id']
            
            # Merge with prediction results to get win probabilities
            for idx, row in features_df.iterrows():
                runner_id = row['runner_id']
                # Find matching prediction
                matching_pred = next(
                    (p for p in prediction_results['predictions'] if p['selection_id'] == runner_id),
                    None
                )
                if matching_pred:
                    win_prob = matching_pred['win_probability']
                    features_df.at[idx, 'win_probability'] = win_prob.get('calibrated', win_prob) if isinstance(win_prob, dict) else win_prob
                    features_df.at[idx, 'win_probability_raw'] = win_prob.get('base') if isinstance(win_prob, dict) else None
            
            # DATABASE: Log all predictions with complete features
            self.db.log_predictions(features_df, self.session_id)
        
        # Log predictions to in-memory logs as well
        for runner_pred in prediction_results.get('predictions', []):
            win_prob = runner_pred.get('win_probability', {})
            prediction_log = {
                'market_id': race_data['market_id'],
                'selection_id': runner_pred['selection_id'],
                'runner_name': runner_pred['runner_name'],
                'trap': runner_pred['trap'],
                'odds': runner_pred['ltp'],
                'win_probability': win_prob.get('calibrated', win_prob) if isinstance(win_prob, dict) else win_prob,
                'win_probability_raw': win_prob.get('base') if isinstance(win_prob, dict) else None,
                'venue': race_data['venue'],
                'race_time': race_data['race_time'],
                'distance': race_data.get('distance'),
                'race_grade': race_data.get('race_grade'),
                'num_runners': len(race_data['runners']),
                'system': self.system_name,
                'prediction_time': datetime.now().isoformat()
            }
            self.all_predictions_log.append(prediction_log)
        
        result = {
            'market_id': market_id,
            'venue': race_data['venue'],
            'race_time': race_data['race_time'],
            'system': self.system_name,
            'opportunities_identified': len(opportunities),
            'bets_placed': []
        }
        
        # Place bets on identified opportunities
        bets_placed = []
        for opp in opportunities:
            bet_result = self.place_bet(opp)
            self.bets_placed_log.append(bet_result)
            result['bets_placed'].append(bet_result)
            bets_placed.append(bet_result)
            
            # DATABASE: Log bet to database
            if bet_result.get('status') not in ['ERROR']:
                self.db.log_bet(
                    market_id=bet_result['market_id'],
                    selection_id=bet_result['selection_id'],
                    runner_name=bet_result['runner_name'],
                    odds=bet_result['runner_odds'],
                    stake=bet_result['stake'],
                    strategy=bet_result.get('strategy'),
                    win_probability=bet_result.get('win_probability'),
                    session_id=self.session_id
                )
        
        # Create individual race log
        self._create_individual_race_log(race_data, opportunities, bets_placed)
        
        # Add to pending results for later checking
        self.pending_results[market_id] = {
            'race_data': race_data,
            'opportunities': opportunities,
            'check_time': datetime.fromisoformat(race_data['race_time'].replace('Z', '+00:00')) + 
                         timedelta(minutes=self.result_check_delay_minutes)
        }
        
        # Terminal feedback
        if opportunities:
            logger.info(f"\n✓ PLACED {len(opportunities)} BET(S) [GB TRACK SPECIALIST]")
            for opp in opportunities:
                logger.info(f"  → ${opp['stake_recommendation']:.2f} on {opp['runner_name']} "
                          f"@ {opp['runner_odds']:.2f} ({opp['strategy_subtype']})")
        else:
            logger.info(f"\n✗ NO BET: No runners qualified for strategy")
        
        logger.info(f"{'='*70}\n")
        
        return result
    
    def place_bet(self, opportunity: Dict) -> Dict:
        """Place a bet (or simulate in dry run)."""
        stake = opportunity['stake_recommendation']
        
        if self.dry_run:
            bet_result = {
                'market_id': opportunity['market_id'],
                'selection_id': opportunity['selection_id'],
                'runner_name': opportunity['runner_name'],
                'runner_odds': opportunity['runner_odds'],
                'stake': stake,
                'status': 'SIMULATED',
                'bet_id': f"DRY_GB_{datetime.now().timestamp()}",
                'placed_time': datetime.now().isoformat(),
                'system': self.system_name,
                'strategy': opportunity['strategy'],
                'strategy_subtype': opportunity['strategy_subtype'],
                'win_probability': opportunity['win_probability'],
                'expected_value': opportunity['expected_value']
            }
            logger.info(f"[DRY RUN - GB] Would bet ${stake:.2f} on {opportunity['runner_name']} "
                       f"@ {opportunity['runner_odds']:.2f} ({opportunity['strategy_subtype']})")
        else:
            logger.info(f"[GB TRACK SPECIALIST] Placing ${stake:.2f} bet on {opportunity['runner_name']} "
                       f"@ {opportunity['runner_odds']:.2f}")
            
            try:
                result = self.betfair_client._make_api_request(
                    self.betfair_client.BETTING_URL,
                    'SportsAPING/v1.0/placeOrders',
                    params={
                        'marketId': opportunity['market_id'],
                        'instructions': [{
                            'selectionId': opportunity['selection_id'],
                            'handicap': 0,
                            'side': 'BACK',
                            'orderType': 'LIMIT',
                            'limitOrder': {
                                'size': stake,
                                'price': opportunity['runner_odds'],
                                'persistenceType': 'LAPSE'
                            }
                        }]
                    }
                )
                
                bet_result = {
                    'market_id': opportunity['market_id'],
                    'selection_id': opportunity['selection_id'],
                    'runner_name': opportunity['runner_name'],
                    'runner_odds': opportunity['runner_odds'],
                    'stake': stake,
                    'status': result.get('status', 'UNKNOWN'),
                    'bet_id': result.get('betId', 'UNKNOWN'),
                    'placed_time': datetime.now().isoformat(),
                    'system': self.system_name,
                    'strategy': opportunity['strategy'],
                    'strategy_subtype': opportunity['strategy_subtype'],
                    'win_probability': opportunity['win_probability'],
                    'expected_value': opportunity['expected_value'],
                    'api_response': result
                }
                
                if result.get('status') == 'SUCCESS':
                    logger.info(f"✓ Bet placed successfully")
                else:
                    logger.error(f"Bet placement failed: {result}")
                    
            except Exception as e:
                logger.error(f"Error placing bet: {str(e)}")
                bet_result = {
                    'status': 'ERROR',
                    'message': str(e),
                    'placed_time': datetime.now().isoformat(),
                    'system': self.system_name
                }
        
        return bet_result
    
    def _create_individual_race_log(self, race_data: Dict, opportunities: List[Dict], 
                                     bets_placed: List[Dict]):
        """Create individual race log file."""
        market_id = race_data['market_id']
        
        race_log = {
            'system': self.system_name,
            'session_id': self.session_id,
            'race_info': {
                'market_id': market_id,
                'venue': race_data['venue'],
                'country_code': race_data['country_code'],
                'race_time': race_data['race_time'],
                'distance': race_data.get('distance'),
                'race_grade': race_data.get('race_grade'),
                'num_runners': len(race_data['runners']),
                'logged_time': datetime.now().isoformat()
            },
            'all_runners': race_data['runners'],
            'betting_logic': {
                'system': self.system_name,
                'midrange_odds': [5.0, 10.0],
                'midrange_threshold': 0.35,
                'longshot_odds': [10.0, 20.0],
                'longshot_threshold': 0.25,
                'opportunities_identified': len(opportunities),
                'betting_decision': 'BET_PLACED' if bets_placed else 'NO_BET'
            },
            'opportunities': opportunities,
            'bets_placed': bets_placed,
            'race_result': None  # Will be updated later
        }
        
        # Store in memory
        self.race_logs[market_id] = race_log
        
        # Save to file
        self._save_individual_race_log(race_data, race_log, has_bet=len(bets_placed) > 0)
    
    def _save_individual_race_log(self, race_data: Dict, race_log: Dict, has_bet: bool = False):
        """Save individual race log to file."""
        # Clean venue name for filename
        venue_clean = race_data['venue'].replace(' ', '_').replace('/', '_')
        
        # Parse race time for filename
        race_time = datetime.fromisoformat(race_data['race_time'].replace('Z', '+00:00'))
        time_str = race_time.strftime('%H%M')
        
        # Build filename
        filename = f"gb_race_{venue_clean}_{time_str}_{race_data['market_id']}"
        
        if has_bet:
            filename += "_BET"
        
        if race_log.get('race_result') is not None:
            filename += "_RESULT"
        
        filename += ".json"
        
        filepath = self.session_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(race_log, f, indent=2)
    
    def _result_checker_loop(self):
        """Background thread to check race results."""
        while self.result_checker_running:
            try:
                now = datetime.now(timezone.utc)
                
                # Check for races that need result checking
                markets_to_check = [
                    market_id for market_id, data in self.pending_results.items()
                    if data['check_time'] <= now
                ]
                
                for market_id in markets_to_check:
                    self._check_race_result(market_id)
                    del self.pending_results[market_id]
                
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in result checker: {str(e)}")
                time.sleep(60)
    
    def _check_race_result(self, market_id: str):
        """Check the result of a completed race."""
        try:
            logger.info(f"[GB TRACK SPECIALIST] Checking result for market {market_id}")
            
            market_book = self.betfair_client.get_market_book([market_id])
            
            if not market_book:
                logger.warning(f"Could not get result for {market_id}")
                return
            
            # Find winner
            winner_id = None
            for runner in market_book[0].get('runners', []):
                if runner.get('status') == 'WINNER':
                    winner_id = runner['selectionId']
                    break
            
            # DATABASE: Update race result in database
            if winner_id:
                self.db.update_race_result(market_id, winner_id)
            
            # Update logs with result
            for race in self.all_races_log:
                if race['market_id'] == market_id:
                    race['winner_selection_id'] = winner_id
                    race['result_checked_time'] = datetime.now().isoformat()
                    
                    for runner in race['runners']:
                        if runner['selection_id'] == winner_id:
                            race['winner_name'] = runner['runner_name']
                            race['winner_odds'] = runner['ltp']
                            logger.info(f"[GB] Winner: {runner['runner_name']} @ {runner['ltp']:.2f}")
                            break
            
            # Update bet logs with result
            for bet in self.bets_placed_log:
                if bet['market_id'] == market_id:
                    bet['winner_selection_id'] = winner_id
                    bet['won'] = (bet['selection_id'] == winner_id)
                    bet['result_checked_time'] = datetime.now().isoformat()
                    
                    if bet['won']:
                        bet['returns'] = bet['stake'] * bet['runner_odds']
                        bet['profit'] = bet['returns'] - bet['stake']
                        logger.info(f"[GB] ✓ BET WON: {bet['runner_name']} - Profit: ${bet['profit']:.2f}")
                    else:
                        bet['returns'] = 0
                        bet['profit'] = -bet['stake']
                        logger.info(f"[GB] ✗ BET LOST: {bet['runner_name']}")
                        
        except Exception as e:
            logger.error(f"Error checking result for {market_id}: {str(e)}")
    
    def save_logs(self, output_dir: str = "logs"):
        """Save comprehensive logs."""
        output_path = Path(output_dir) / self.system_name
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. ALL RACES LOG
        if self.all_races_log:
            races_file = output_path / f"gb_all_races_{timestamp}.json"
            with open(races_file, 'w') as f:
                json.dump(self.all_races_log, f, indent=2)
            logger.info(f"[GB] Saved {len(self.all_races_log)} races to {races_file}")
        
        # 2. ALL RUNNERS LOG
        if self.all_runners_log:
            runners_file = output_path / f"gb_all_runners_{timestamp}.json"
            with open(runners_file, 'w') as f:
                json.dump(self.all_runners_log, f, indent=2)
            logger.info(f"[GB] Saved {len(self.all_runners_log)} runners to {runners_file}")
        
        # 3. ALL PREDICTIONS LOG **NEW**
        if self.all_predictions_log:
            predictions_file = output_path / f"gb_predictions_{timestamp}.json"
            with open(predictions_file, 'w') as f:
                json.dump(self.all_predictions_log, f, indent=2)
            logger.info(f"[GB] Saved {len(self.all_predictions_log)} predictions to {predictions_file}")
            
            # Also save as CSV for easy analysis
            predictions_csv = output_path / f"gb_predictions_{timestamp}.csv"
            df = pd.DataFrame(self.all_predictions_log)
            df.to_csv(predictions_csv, index=False)
            logger.info(f"[GB] Saved predictions CSV to {predictions_csv}")
        
        # 4. BETS PLACED LOG
        if self.bets_placed_log:
            bets_file = output_path / f"gb_bets_placed_{timestamp}.json"
            with open(bets_file, 'w') as f:
                json.dump(self.bets_placed_log, f, indent=2)
            logger.info(f"[GB] Saved {len(self.bets_placed_log)} bets to {bets_file}")
            
            # Also save as CSV
            bets_csv = output_path / f"gb_bets_placed_{timestamp}.csv"
            df = pd.DataFrame(self.bets_placed_log)
            df.to_csv(bets_csv, index=False)
            logger.info(f"[GB] Saved bets CSV to {bets_csv}")
    
    def cleanup(self):
        """Cleanup resources."""
        self.result_checker_running = False
        if self.betfair_client:
            self.betfair_client.logout()
            logger.info("[GB TRACK SPECIALIST] Logged out from Betfair")


if __name__ == "__main__":
    """Test the betting system."""
    import argparse
    from dotenv import load_dotenv
    
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='Run GB Track Specialist Betting System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--hours', type=int, default=2, help='Hours ahead to scan')
    parser.add_argument('--live', action='store_true', help='Place real bets (default is dry run)')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("GB TRACK SPECIALIST BETTING SYSTEM")
    print("="*70)
    print(f"Mode: {'LIVE' if args.live else 'DRY RUN'}")
    print(f"Strategy: Mid-Range & Longshots")
    print(f"Looking ahead: {args.hours} hours")
    print("="*70 + "\n")
    
    try:
        # Initialize system
        system = GBBettingSystem(dry_run=not args.live)
        
        # Get upcoming races
        races = system.betfair_client.get_upcoming_greyhound_races(
            hours_ahead=args.hours,
            country_codes=['GB']
        )
        
        if races:
            logger.info(f"Found {len(races)} upcoming GB races\n")
            
            for race in races:
                system.process_race(race['market_id'])
                time.sleep(0.5)
        
        # Save logs
        system.save_logs()
        
        # Cleanup
        system.cleanup()
        
        print("\n✓ GB Track Specialist session complete")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        if 'system' in locals():
            system.save_logs()
            system.cleanup()
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
