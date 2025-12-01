# Railway Deployment Guide - GB Track Specialist

## 🎯 Overview

This guide walks you through deploying the GB Track Specialist betting system to Railway with PostgreSQL database integration for comprehensive data collection and grid search optimization.

## ✅ What's Been Prepared

### Core Files Created:
1. **database_schema.sql** - Complete PostgreSQL schema with ~60 column predictions table
2. **database_helper.py** - PostgreSQL integration with automatic schema initialization
3. **requirements.txt** - All Python dependencies
4. **Procfile** - Railway worker process configuration
5. **.gitignore** - Proper exclusions for deployment
6. **Database Integration** - Added to `gb_betting_system.py`

### Database Features:
- ✅ Captures ALL 32+ CatBoost model features for every runner
- ✅ Logs races, predictions, bets, and results
- ✅ Optimized indexes for grid search queries
- ✅ Automatic fallback to JSON if database unavailable

---

## 📋 Pre-Deployment Checklist

### 1. Prepare ML Model Files

ML model files are too large for Git. Choose one option:

#### Option A: Git LFS (Recommended)
```bash
cd 04_GB_Track_Specialist_Production_Trial
git lfs install
git lfs track "*.cbm"
git lfs track "*.pkl"
git add .gitattributes
```

#### Option B: Railway Volumes
- Upload models to Railway volumes after deployment
- Update code to load from volume path

#### Option C: Cloud Storage
- Upload to S3/GCS
- Download on startup in `run_continuous_scheduled.py`

### 2. Handle SSL Certificates

Your Betfair certificates need to be accessible on Railway:

#### Option A: Base64 Encoding (Recommended)
```bash
# Encode certificates
base64 -i /path/to/client-2048.crt > cert_base64.txt
base64 -i /path/to/client-2048.key > key_base64.txt

# Add to Railway environment variables:
# BETFAIR_CERT_BASE64=<contents of cert_base64.txt>
# BETFAIR_KEY_BASE64=<contents of key_base64.txt>
```

Then update `betfair_client.py` to decode and write certificates on startup.

#### Option B: Railway Volumes
- Mount certificates as Railway volume
- Update `betfair_client.py` with volume path

---

## 🚀 Deployment Steps

### Step 1: Initialize Git Repository

```bash
cd 04_GB_Track_Specialist_Production_Trial

# Initialize repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: GB Track Specialist with database integration"

# Add remote
git remote add origin git@github.com:Will954633/Greyhound_Racing_GB_Track_Specialist-.git

# Push to GitHub
git push -u origin main
```

### Step 2: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account if not already connected
5. Select `Greyhound_Racing_GB_Track_Specialist-` repository
6. Railway will detect the `Procfile` and deploy automatically

### Step 3: Add PostgreSQL Database

1. In Railway dashboard, click **"New"** → **"Database"** → **"PostgreSQL"**
2. Railway will automatically:
   - Create PostgreSQL instance
   - Set `DATABASE_URL` environment variable
   - Connect it to your service

### Step 4: Set Environment Variables

In Railway dashboard → **Variables** tab:

```bash
# Betfair Credentials
BETFAIR_USERNAME=your_username
BETFAIR_PASSWORD=your_password
BETFAIR_APP_KEY=your_app_key

# SSL Certificates (if using base64 encoding)
BETFAIR_CERT_BASE64=<base64 encoded certificate>
BETFAIR_KEY_BASE64=<base64 encoded key>

# Or certificate paths (if using volumes)
BETFAIR_CERT_PATH=/app/certs/client-2048.crt
BETFAIR_KEY_PATH=/app/certs/client-2048.key

# Database (auto-set by Railway)
DATABASE_URL=postgresql://... (automatically provided)

# Optional: Python environment
PYTHONUNBUFFERED=1
```

### Step 5: Deploy ML Models

Choose your approach from Pre-Deployment Checklist above.

If using Git LFS:
```bash
# Models will be automatically pulled during deployment
```

If using Railway volumes:
1. Create volume in Railway
2. Upload model files via Railway CLI or dashboard
3. Mount volume to `/app/models`

### Step 6: Verify Deployment

1. Check Railway logs for successful startup
2. Verify database schema created
3. Confirm Betfair login successful
4. Monitor first race processing

---

## 🔧 Post-Deployment

### Monitor Logs

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# View logs
railway logs
```

### Connect to Database

```bash
# Get database URL from Railway dashboard
railway variables

# Connect with psql
psql <DATABASE_URL>

# Or use Railway's built-in database browser
```

### Query Examples

```sql
-- Check data collection
SELECT COUNT(*) FROM predictions;
SELECT COUNT(*) FROM bets;
SELECT COUNT(*) FROM races;

-- View recent predictions
SELECT * FROM predictions 
ORDER BY created_at DESC 
LIMIT 10;

-- Grid search example: optimal venue & grade combinations
SELECT 
    venue,
    race_grade,
    AVG(CASE WHEN won THEN 1.0 ELSE 0.0 END) as win_rate,
    COUNT(*) as sample_size,
    AVG(odds) as avg_odds
FROM predictions  
WHERE calibrated_prob >= 0.30
GROUP BY venue, race_grade
HAVING COUNT(*) >= 20
ORDER BY win_rate DESC;
```

---

## 🛠️ Troubleshooting

### Common Issues:

#### 1. Database Connection Errors
```python
# database_helper.py automatically handles this with JSON fallback
# Check logs for: "PostgreSQL available, using database"
```

#### 2. Missing Model Files
```bash
# Verify in Railway logs
ls -la /app/03_GB_Ensemble/Models/Track_Specialist_Model/
```

#### 3. Betfair Authentication
```bash
# Check certificate paths in logs
# Verify environment variables are set
railway variables
```

#### 4. Memory Issues
- Upgrade Railway plan if needed
- ML models (~100MB each) require adequate RAM

### Debug Mode

Add to environment variables:
```bash
LOG_LEVEL=DEBUG
```

---

## 📊 Data Collection & Grid Search

### Understanding the Data

The database captures everything needed for optimization:

**Race Context:**
- venue, race_grade, distance
- race_time, race_hour, day_of_week

**Market Features (32+ columns):**
- All runner odds
- Market compression metrics
- Competitive field indicators
- Box positions
- Odds differentials
- Win probabilities (raw + calibrated)

**Results:**
- Winner details
- Bet outcomes
- Profit/loss

### Grid Search Workflow

1. **Collect Data** (Current Phase)
   - Let system run for 2-4 weeks
   - Gather diverse race conditions
   - Minimum ~500 races recommended

2. **Analyze Performance**
   ```sql
   -- Example: Find best performing segments
   SELECT 
       venue,
       race_grade,
       CASE 
           WHEN odds BETWEEN 5 AND 10 THEN 'MID_RANGE'
           WHEN odds BETWEEN 10 AND 20 THEN 'LONGSHOT'
       END as odds_range,
       AVG(CASE WHEN won THEN 1.0 ELSE 0.0 END) as win_rate,
       COUNT(*) as bets,
       SUM(CASE WHEN won THEN (odds - 1) * stake ELSE -stake END) as profit
   FROM predictions
   WHERE bet_placed = true
   GROUP BY venue, race_grade, odds_range
   HAVING COUNT(*) >= 20
   ORDER BY profit DESC;
   ```

3. **Optimize Strategy**
   - Adjust probability thresholds per venue
   - Fine-tune odds ranges
   - Identify optimal race grades
   - Optimize stake sizing

---

## 🔄 Continuous Operation

Railway will keep your service running 24/7:

- Automatic restarts on crashes
- Persistent database
- Scalable resources
- Monitoring & alerts

### Scaling

If needed, upgrade Railway plan for:
- More CPU/RAM
- Increased database storage
- Higher network bandwidth

---

## 📞 Support

- **Railway Docs**: https://docs.railway.app
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Project Issues**: Open issue on GitHub repository

---

## ✅ Deployment Checklist

- [ ] ML models prepared (LFS/volumes/cloud)
- [ ] SSL certificates configured
- [ ] Git repository initialized
- [ ] Pushed to GitHub
- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Environment variables set
- [ ] Models deployed
- [ ] System running successfully
- [ ] Database collecting data
- [ ] Monitoring logs

**Once deployed, the system will:**
- Run continuously
- Process every GB greyhound race
- Generate win probabilities for ALL runners
- Log bets using current methodology
- Store comprehensive data for grid search optimization
- Enable future strategy optimization based on collected data

Good luck with your deployment! 🚀
