#!/usr/bin/env python3
"""
Continuous Scheduled Runner for GB Track Specialist
Scans for upcoming races and schedules them for processing at T-1 minute

SCHEDULING STRATEGY:
- Scans for upcoming races every N minutes (default: 15 mins)
- Looks ahead for races in the next N minutes
- Schedules each race to be processed at T-1 minute before start
- Prevents missing races due to timing issues
- Tracks scheduled races to avoid duplicates

Based on: 02_Upset_Prediction/02_Production/iteration_2/run_continuous_scheduled_iteration_2.py
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import signal
import sys
import threading
from typing import Dict, Set

from gb_betting_system import GBBettingSystem

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScheduledGBBettingRunner:
    """Runs GB Track Specialist system with scheduled race processing."""
    
    def __init__(self, 
                 scan_interval_minutes: int = 15,
                 target_minutes_before_race: int = 1,
                 dry_run: bool = True):
        """
        Initialize scheduled GB betting runner.
        
        Args:
            scan_interval_minutes: How often to scan for new races (default: 15 min)
            target_minutes_before_race: When to process race before start (default: 1 min)
            dry_run: If True, don't place real bets
        """
        self.scan_interval_minutes = scan_interval_minutes
        self.target_minutes_before_race = target_minutes_before_race
        self.dry_run = dry_run
        self.running = True
        self.system = None
        
        # Track scheduled races to prevent duplicates
        self.scheduled_races: Set[str] = set()  # market_ids that are scheduled
        self.scheduled_races_lock = threading.Lock()
        
        # Track active timers for cleanup
        self.active_timers: Dict[str, threading.Timer] = {}
        self.timers_lock = threading.Lock()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"\n[GB TRACK SPECIALIST] Received signal {signum}. Shutting down gracefully...")
        self.running = False
        
    def _schedule_race(self, race: Dict):
        """
        Schedule a race to be processed at T-1 minute before start.
        
        Args:
            race: Race dictionary with market_id, venue, race_time
        """
        market_id = race['market_id']
        
        # Check if already scheduled
        with self.scheduled_races_lock:
            if market_id in self.scheduled_races:
                logger.debug(f"[GB] Race {race['venue']} already scheduled, skipping")
                return
            self.scheduled_races.add(market_id)
        
        # Calculate when to process (T-1 minute by default)
        race_time = datetime.fromisoformat(race['race_time'].replace('Z', '+00:00'))
        process_time = race_time - timedelta(minutes=self.target_minutes_before_race)
        now = datetime.now(timezone.utc)
        
        # Calculate delay in seconds
        delay_seconds = (process_time - now).total_seconds()
        
        if delay_seconds < 0:
            # Race is too close, process immediately
            logger.warning(f"[GB] Race {race['venue']} at {race_time.strftime('%H:%M:%S')} is already within {self.target_minutes_before_race} mins, processing now")
            self._process_scheduled_race(market_id, race)
        elif delay_seconds > (self.scan_interval_minutes * 60):
            # Race is too far ahead, will be picked up in next scan
            logger.debug(f"[GB] Race {race['venue']} at {race_time.strftime('%H:%M:%S')} is {delay_seconds/60:.1f} mins away, will reschedule")
            with self.scheduled_races_lock:
                self.scheduled_races.discard(market_id)
        else:
            # Schedule for processing at target time before race
            logger.info(f"[GB] 📅 SCHEDULED: {race['venue']} at {race_time.strftime('%H:%M:%S')} → Processing in {delay_seconds/60:.1f} mins ({process_time.strftime('%H:%M:%S')})")
            
            timer = threading.Timer(
                delay_seconds,
                self._process_scheduled_race,
                args=(market_id, race)
            )
            
            with self.timers_lock:
                self.active_timers[market_id] = timer
            
            timer.start()
    
    def _process_scheduled_race(self, market_id: str, race_info: Dict):
        """
        Process a scheduled race at the designated time.
        
        Args:
            market_id: Market ID of the race
            race_info: Race information dict
        """
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"[GB TRACK SPECIALIST] ⏰ PROCESSING SCHEDULED RACE")
            logger.info(f"{'='*70}")
            logger.info(f"Venue: {race_info['venue']}")
            logger.info(f"Race time: {race_info['race_time']}")
            logger.info(f"Market ID: {market_id}")
            
            # Process the race
            result = self.system.process_race(market_id)
            
            logger.info(f"{'='*70}\n")
            
        except Exception as e:
            logger.error(f"[GB] Error processing scheduled race {market_id}: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up tracking
            with self.scheduled_races_lock:
                self.scheduled_races.discard(market_id)
            with self.timers_lock:
                self.active_timers.pop(market_id, None)
    
    def _scan_and_schedule_races(self):
        """Scan for upcoming races and schedule them for processing."""
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"[GB TRACK SPECIALIST] SCANNING FOR RACES TO SCHEDULE")
            logger.info(f"{'='*70}")
            logger.info(f"Looking ahead: {self.scan_interval_minutes} minutes")
            logger.info(f"Target processing: T-{self.target_minutes_before_race} minutes before race")
            
            # Get GB races in the next scan_interval minutes
            races = self.system.betfair_client.get_upcoming_greyhound_races(
                hours_ahead=self.scan_interval_minutes / 60.0,
                country_codes=['GB']
            )
            
            if not races:
                logger.info("[GB] No upcoming GB races found in scan window")
                return
            
            logger.info(f"[GB] Found {len(races)} GB races in next {self.scan_interval_minutes} minutes\n")
            
            # Schedule each race
            scheduled_count = 0
            already_scheduled_count = 0
            
            for race in races:
                race_time = datetime.fromisoformat(race['race_time'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                minutes_until = (race_time - now).total_seconds() / 60
                
                with self.scheduled_races_lock:
                    if race['market_id'] in self.scheduled_races:
                        already_scheduled_count += 1
                        continue
                
                self._schedule_race(race)
                scheduled_count += 1
            
            logger.info(f"\n{'='*70}")
            logger.info(f"[GB TRACK SPECIALIST] SCAN SUMMARY")
            logger.info(f"{'='*70}")
            logger.info(f"  GB races found: {len(races)}")
            logger.info(f"  Newly scheduled: {scheduled_count}")
            logger.info(f"  Already scheduled: {already_scheduled_count}")
            logger.info(f"  Total scheduled races: {len(self.scheduled_races)}")
            logger.info(f"  Active timers: {len(self.active_timers)}")
            
        except Exception as e:
            logger.error(f"[GB] Error during race scan: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """Run the GB Track Specialist scheduled betting system continuously."""
        logger.info("="*70)
        logger.info("[GB TRACK SPECIALIST] STARTING SCHEDULED BETTING SYSTEM")
        logger.info("="*70)
        logger.info(f"Strategy: Mid-Range (5-10 odds) & Longshots (10-20 odds)")
        logger.info(f"Mode: {'LIVE' if not self.dry_run else 'DRY RUN'}")
        logger.info(f"Scan interval: {self.scan_interval_minutes} minutes")
        logger.info(f"Target processing: T-{self.target_minutes_before_race} minutes")
        logger.info(f"Country: GB only")
        logger.info(f"Press Ctrl+C to stop gracefully")
        logger.info("="*70 + "\n")
        
        scan_count = 0
        
        try:
            # Initialize GB betting system once
            logger.info("[GB] Initializing betting system...")
            self.system = GBBettingSystem(dry_run=self.dry_run)
            logger.info("[GB] ✓ System initialized\n")
            
            while self.running:
                scan_count += 1
                scan_start = datetime.now()
                
                logger.info(f"\n{'='*70}")
                logger.info(f"[GB TRACK SPECIALIST] SCAN #{scan_count} - {scan_start.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*70}")
                
                # Scan and schedule races
                self._scan_and_schedule_races()
                
                # Save logs every scan
                try:
                    self.system.save_logs()
                    logger.info(f"\n[GB] ✓ Logs saved")
                    
                    # Summary stats
                    if self.system.bets_placed_log:
                        total_stake = sum(b.get('stake', 0) for b in self.system.bets_placed_log)
                        wins = sum(1 for b in self.system.bets_placed_log if b.get('won'))
                        losses = sum(1 for b in self.system.bets_placed_log if b.get('won') == False)
                        pending = len(self.system.bets_placed_log) - wins - losses
                        
                        logger.info(f"  Total races logged: {len(self.system.all_races_log)}")
                        logger.info(f"  Total bets placed: {len(self.system.bets_placed_log)}")
                        logger.info(f"  Bets won: {wins} | Lost: {losses} | Pending: {pending}")
                        logger.info(f"  Total staked: ${total_stake:.2f}")
                        
                        # Calculate P&L for completed bets
                        if wins > 0 or losses > 0:
                            completed_bets = [b for b in self.system.bets_placed_log if 'won' in b]
                            if completed_bets:
                                total_profit = sum(b.get('profit', 0) for b in completed_bets)
                                logger.info(f"  Profit/Loss: ${total_profit:+.2f}")
                    
                except Exception as e:
                    logger.error(f"[GB] Error saving logs: {str(e)}")
                
                # Calculate next scan time
                if self.running:
                    next_scan = scan_start.timestamp() + (self.scan_interval_minutes * 60)
                    now = datetime.now().timestamp()
                    sleep_time = max(0, next_scan - now)
                    
                    next_scan_time = datetime.fromtimestamp(next_scan).strftime('%H:%M:%S')
                    logger.info(f"\n{'='*70}")
                    logger.info(f"[GB] Next scan in {sleep_time/60:.1f} minutes at {next_scan_time}")
                    logger.info(f"Scheduled races: {len(self.scheduled_races)} | Active timers: {len(self.active_timers)}")
                    logger.info(f"{'='*70}\n")
                    
                    # Sleep in small intervals to check for shutdown signal
                    sleep_intervals = int(sleep_time / 10) + 1
                    for i in range(sleep_intervals):
                        if not self.running:
                            break
                        time.sleep(min(10, sleep_time))
                        sleep_time -= 10
                        
        except KeyboardInterrupt:
            logger.info("\n\n[GB] Received keyboard interrupt")
        except Exception as e:
            logger.error(f"[GB] Fatal error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self._shutdown()
    
    def _shutdown(self):
        """Perform graceful shutdown."""
        logger.info("\n" + "="*70)
        logger.info("[GB TRACK SPECIALIST] SHUTTING DOWN")
        logger.info("="*70)
        
        # Cancel all active timers
        logger.info(f"[GB] Cancelling {len(self.active_timers)} active timers...")
        with self.timers_lock:
            for market_id, timer in self.active_timers.items():
                timer.cancel()
            self.active_timers.clear()
        
        if self.system:
            try:
                # Save final logs
                logger.info("[GB] Saving final logs...")
                self.system.save_logs()
                
                # Cleanup
                logger.info("[GB] Cleaning up...")
                self.system.cleanup()
                
                logger.info("[GB] ✓ Shutdown complete")
            except Exception as e:
                logger.error(f"[GB] Error during shutdown: {str(e)}")
        
        logger.info("="*70 + "\n")


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description='Run GB Track Specialist with scheduled race processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
GB TRACK SPECIALIST: MID-RANGE & LONGSHOT STRATEGY
- Mid-Range (5.0-10.0 odds): 35%% probability threshold, $10 stakes
- Longshots (10.0-20.0 odds): 25%% probability threshold, $5 stakes
- Only bet on TOP predicted runner per race
- Category preferences for mid-range: HC, A6, A7, D3, A3, A5, A1, A9
- GB greyhound races only

Examples:
  # Dry run, scan every 15 mins, process at T-1 min
  python run_continuous_scheduled.py
  
  # Live mode, scan every 10 mins
  python run_continuous_scheduled.py --interval 10 --live
  
  # Scan every 5 mins, process at T-3 mins
  python run_continuous_scheduled.py --interval 5 --target 3
        """
    )
    parser.add_argument('--interval', type=int, default=15, 
                       help='Scan interval in minutes (default: 15)')
    parser.add_argument('--target', type=int, default=1, 
                       help='Minutes before race to process (default: 1)')
    parser.add_argument('--live', action='store_true', 
                       help='Place real bets (default is dry run)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.target >= args.interval:
        logger.error(f"Error: Target time ({args.target} mins) must be less than scan interval ({args.interval} mins)")
        sys.exit(1)
    
    # Create and run scheduled GB betting system
    runner = ScheduledGBBettingRunner(
        scan_interval_minutes=args.interval,
        target_minutes_before_race=args.target,
        dry_run=not args.live
    )
    
    runner.run()
