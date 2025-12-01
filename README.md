# GB Track Specialist Production Trial

Production betting system implementing optimal mid-range and longshot strategies for GB greyhound racing.

## 🎯 Strategy Overview

Based on comprehensive analysis documented in `03_GB_Ensemble/Analysis/OPTIMAL_BETTING_STRATEGY.md`, this system implements two high-ROI strategies:

### Strategy 1: Mid-Range Odds (5.0-10.0)
- **Odds Range:** 5.0 to 10.0
- **Win Probability Threshold:** 35% (calibrated)
- **Stake:** $10 per bet
- **Preferred Categories:** HC, A6, A7, D3, A3, A5, A1, A9
- **Expected Win Rate:** 30-40% (live)
- **Historical ROI:** 544% (backtest)

### Strategy 2: Longshots (10.0-20.0)
- **Odds Range:** 10.0 to 20.0
- **Win Probability Threshold:** 25% (calibrated)
- **Stake:** $5 per bet
- **All Categories:** Accepted
- **Expected Win Rate:** 20-30% (live)
- **Historical ROI:** 1,177% (backtest)

### Betting Rules
✅ **ONLY** bet on the **TOP** predicted runner in each race  
✅ Runner must meet odds range AND probability threshold  
✅ GB greyhound races only  
✅ Processes races at T-1 minute before start

## 📁 System Architecture

```
04_GB_Track_Specialist_Production_Trial/
├── betfair_client.py               # Betfair API connection
├── gb_track_specialist_predictor.py # Strategy implementation
├── gb_betting_system.py            # Betting system core
├── run_continuous_scheduled.py     # Main runner (scheduled)
├── README.md                       # This file
└── .env.example                    # Environment variables template
```

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install dependencies
pip install pandas numpy catboost requests python-dotenv

# Ensure Betfair certificates exist
# Located at: 02_Upset_Prediction/02_Production/certs/
# - client-2048.crt
# - client-2048.key
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
BETFAIR_USERNAME=your_username
BETFAIR_PASSWORD=your_password
BETFAIR_APP_KEY=your_app_key
```

### 3. Run the System

**Dry Run (Recommended for Testing):**
```bash
cd 04_GB_Track_Specialist_Production_Trial
python run_continuous_scheduled.py
```

**Live Betting:**
```bash
python run_continuous_scheduled.py --live
```

**Custom Intervals:**
```bash
# Scan every 10 minutes, process races at T-3 minutes
python run_continuous_scheduled.py --interval 10 --target 3 --live
```

## 📊 System Operation

### Scheduled Processing

The system uses intelligent scheduling to ensure no races are missed:

1. **Scan Phase** (every 15 minutes by default)
   - Searches for GB greyhound races in next 15 minutes
   - Identifies new races not yet scheduled

2. **Scheduling Phase**
   - Schedules each race for processing at T-1 minute
   - Prevents duplicate scheduling with market_id tracking

3. **Processing Phase** (T-1 minute before race)
   - Fetches live odds and race data
   - Runs predictions through GB Track Specialist model
   - Identifies betting opportunities
   - Places bets if criteria met

4. **Result Checking**
   - Automatically checks results 45 minutes after race
   - Updates logs with winners and profits/losses

### Logging

All activity is logged to:
```
logs/gb_track_specialist/
├── session_TIMESTAMP/              # Individual race logs
│   ├── gb_race_Romford_1930_MARKETID_BET.json
│   └── gb_race_Swindon_2000_MARKETID.json
├── gb_all_races_TIMESTAMP.json    # All races processed
├── gb_all_runners_TIMESTAMP.json  # All runners from all races
├── gb_bets_placed_TIMESTAMP.json  # Bets placed only
└── gb_bets_placed_TIMESTAMP.csv   # CSV format for analysis
```

## 🔧 Command Line Options

```
python run_continuous_scheduled.py [OPTIONS]

Options:
  --interval N   Scan interval in minutes (default: 15)
  --target N     Minutes before race to process (default: 1)
  --live         Place real bets (omit for dry run)
  -h, --help     Show help message
```

### Examples

```bash
# Default: Dry run, scan every 15 mins, process at T-1 min
python run_continuous_scheduled.py

# Live betting with default settings
python run_continuous_scheduled.py --live

# Scan every 10 mins, process at T-2 mins (dry run)
python run_continuous_scheduled.py --interval 10 --target 2

# Aggressive: Scan every 5 mins, process at T-1 min (live)
python run_continuous_scheduled.py --interval 5 --live
```

## 📈 Performance Monitoring

### Runtime Statistics

The system displays after each scan:
- Total races logged
- Total bets placed
- Wins / Losses / Pending
- Total staked
- Profit/Loss (for completed bets)

### Log Analysis

Analyze betting performance:
```python
import pandas as pd
import json

# Load bets log
with open('logs/gb_track_specialist/gb_bets_placed_TIMESTAMP.json') as f:
    bets = json.load(f)

df = pd.DataFrame(bets)

# Win rate
win_rate = df['won'].sum() / len(df)

# ROI
total_stake = df['stake'].sum()
total_profit = df['profit'].sum()
roi = (total_profit / total_stake) * 100

print(f"Win Rate: {win_rate:.1%}")
print(f"ROI: {roi:.1f}%")
print(f"Profit: ${total_profit:.2f}")
```

## ⚠️ Risk Management

### Important Warnings

🚨 **Historical vs Live Performance**
- Backtest win rates (99-100%) are IN-SAMPLE only
- Realistic live expectations: 20-40% win rates
- ROI will be lower in live betting
- Use for WHERE to bet, not WHAT returns to expect

### Bankroll Rules

1. **Never bet more than 5% of bankroll on single race**
2. **Stop if down 20% of starting bankroll in a session**
3. **Re-evaluate after 50+ bets show negative ROI**
4. **Track calibration:** Are actual results close to predicted probabilities?

### Variance Expectations

- Expect losing streaks of 5-10 bets
- Longshots especially prone to variance (small sample size)
- Need 100+ bets to evaluate true performance

## 🔍 Strategy Components

### 1. GB Ensemble Predictor V2
Located: `03_GB_Ensemble/Production/gb_ensemble_predictor_v2.py`

- Comprehensive feature engineering (32 features)
- Track Specialist Model predictions
- Betting Optimizer profit predictions

### 2. Optimal Strategy Implementation
Located: `gb_track_specialist_predictor.py`

- Mid-range odds filter (5.0-10.0)
- Longshot odds filter (10.0-20.0)
- Probability threshold enforcement
- Category preference weighting
- Top-runner-only selection

### 3. Betfair Integration
Located: `betfair_client.py`

- SSL certificate authentication
- Persistent session management
- Auto re-login on session expiry
- Rate limiting (20 req/sec)

## 📞 Support & Troubleshooting

### Common Issues

**"Certificate file not found"**
- Ensure certificates exist at: `02_Upset_Prediction/02_Production/certs/`
- Generate if needed using the certificates generation script

**"Failed to login to Betfair"**
- Check credentials in `.env` file
- Verify app key is valid
- Ensure account has API access

**"No races found"**
- GB racing may not be active at current time
- Try increasing scan interval
- Check country_codes setting

**"Model not found"**
- Ensure Track Specialist model exists at:
  `03_GB_Ensemble/Models/Track_Specialist_Model/01_Track_Specialist_Model_Global_Training/artifacts_global/base_model.cbm`

## 🛠️ Development

### Testing

Test individual components:

```bash
# Test Betfair connection
cd 04_GB_Track_Specialist_Production_Trial
python betfair_client.py

# Test predictor
python gb_track_specialist_predictor.py

# Test betting system (dry run, 2 hours ahead)
python gb_betting_system.py --hours 2
```

### Customization

**Adjust Probability Thresholds:**
Edit `gb_track_specialist_predictor.py`:
```python
self.midrange_config = {
    'min_probability': 0.40,  # Increase from 0.35 for more conservative
    ...
}
```

**Change Stake Amounts:**
Edit `gb_track_specialist_predictor.py` in `_create_opportunity()`:
```python
stake_recommendation = 20.0  # Increase from $10
```

**Add More Categories:**
Edit `MIDRANGE_PREFERRED_CATEGORIES` list

## 📚 Related Documentation

- **Strategy Analysis:** `03_GB_Ensemble/Analysis/OPTIMAL_BETTING_STRATEGY.md`
- **Model Training:** `03_GB_Ensemble/Models/Track_Specialist_Model/IMPLEMENTATION_COMPLETE.md`
- **Reference System:** `02_Upset_Prediction/02_Production/iteration_2/`

## 📝 Version History

- **v1.0** (18 Nov 2025): Initial production trial implementation
  - Mid-range & longshot strategies
  - Scheduled race processing
  - Comprehensive logging
  - GB races only

## 🎓 Strategy Reference

### Quick Reference Card

**Mid-Range Strategy**
```
✓ Odds: 5.0 - 10.0
✓ Probability: ≥ 35%
✓ Top pick in race
✓ Prefer: HC, A6, A7, D3, A3, A5, A1, A9
→ Stake: $10 flat
```

**Longshot Strategy**
```
✓ Odds: 10.0 - 20.0  
✓ Probability: ≥ 25% (or 30% for safety)
✓ Top pick in race
✓ All categories OK
→ Stake: $5 flat
```

---

**Last Updated:** 18 November 2025  
**Status:** Production Trial  
**Country:** GB Only  
**Model:** Track Specialist + Betting Optimizer
