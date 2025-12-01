# 🚀 Deploy GB Track Specialist to Railway - START HERE

**Your automated deployment helper is ready!**

---

## ✅ WHAT'S BEEN AUTOMATED FOR YOU

I've completed all the code integration and setup:
- ✅ Database integration in `gb_betting_system.py`
- ✅ Base64 certificate handling in `betfair_client.py`
- ✅ Git LFS configuration (`.gitattributes`)
- ✅ Deployment script (`deploy.sh`)
- ✅ All deployment files ready

---

## 🎯 YOUR 3-STEP DEPLOYMENT PROCESS

### STEP 1: Encode Your Betfair Certificates (5 minutes)

Navigate to where your Betfair certificates are stored and encode them:

```bash
# Find your certificates (likely in one of these locations):
# - 02_Upset_Prediction/02_Production/certs/
# - Or wherever you stored them

# Encode them to base64
cd /path/to/your/certificates
base64 -i client-2048.crt > ~/Desktop/cert_base64.txt
base64 -i client-2048.key > ~/Desktop/key_base64.txt

# The encoded files are now on your Desktop
```

**Keep these files open** - you'll copy their contents to Railway in Step 3.

---

### STEP 2: Run the Automated Deployment Script (10 minutes)

The script will handle Git LFS setup and push to GitHub:

```bash
cd 04_GB_Track_Specialist_Production_Trial
./deploy.sh
```

This script will:
1. ✅ Check/install Git LFS
2. ✅ Initialize Git repository
3. ✅ Add GitHub remote
4. ✅ Track ML models with LFS
5. ✅ Commit and push to GitHub

**Note:** The first push may take 5-10 minutes as it uploads your ML models to GitHub LFS.

---

### STEP 3: Deploy on Railway (15 minutes)

#### 3.1 Create Railway Project

1. Go to [railway.app](https://railway.app) and log in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose `Greyhound_Racing_GB_Track_Specialist-`

Railway will automatically detect your `Procfile` and start building.

#### 3.2 Add PostgreSQL Database

1. In Railway project, click **"New"** → **"Database"** → **"PostgreSQL"**
2. Railway automatically sets `DATABASE_URL` environment variable

#### 3.3 Set Environment Variables

Click on your service → **"Variables"** tab → **"New Variable"**

Add these one by one:

```bash
# Betfair Credentials
BETFAIR_USERNAME=your_betfair_username
BETFAIR_PASSWORD=your_betfair_password  
BETFAIR_APP_KEY=your_app_key

# SSL Certificates (paste contents from Desktop files)
BETFAIR_CERT_BASE64=<paste entire contents of cert_base64.txt>
BETFAIR_KEY_BASE64=<paste entire contents of key_base64.txt>

# Python (optional but recommended)
PYTHONUNBUFFERED=1
```

**Important:** For the certificate variables, open the `.txt` files from your Desktop and paste the **entire** contents (it will be a long string).

#### 3.4 Deploy!

Railway will automatically redeploy when you add the environment variables.

Monitor the deployment:
- Click on your service
- Go to **"Deployments"** tab
- Click on the active deployment to see logs

---

## ✅ VERIFY DEPLOYMENT

### Check Logs for Success Messages

You should see:
```
✓ Logged in to Betfair
✓ PostgreSQL available, using database
✓ Database schema initialized
✓ GB Track Specialist initialized
```

### Check Database is Collecting Data

Install Railway CLI:
```bash
npm install -g @railway/cli
railway login
railway link
```

Connect to database:
```bash
# Get database connection string
railway variables

# Connect
psql <DATABASE_URL_from_above>

# Check tables exist
\dt

# Check data is being collected
SELECT COUNT(*) FROM predictions;
SELECT COUNT(*) FROM races;
SELECT COUNT(*) FROM bets;
```

---

## 🎉 SUCCESS! WHAT HAPPENS NOW

Your system is now running 24/7 and will:
1. ✅ Process every GB greyhound race
2. ✅ Generate win probabilities for ALL runners
3. ✅ Place bets using your optimal strategy
4. ✅ Log everything to PostgreSQL for grid search
5. ✅ Store data for future optimization

---

## 📊 AFTER 2-4 WEEKS OF DATA COLLECTION

Run grid search queries to optimize your strategy:

```sql
-- Find best performing venue & grade combinations
SELECT 
    venue,
    race_grade,
    AVG(CASE WHEN won THEN 1.0 ELSE 0.0 END) as win_rate,
    COUNT(*) as bets,
    SUM(CASE WHEN won THEN (odds-1)*stake ELSE -stake END) as profit
FROM predictions
WHERE bet_placed = true
GROUP BY venue, race_grade
HAVING COUNT(*) >= 20
ORDER BY profit DESC;
```

---

## 🆘 TROUBLESHOOTING

### "Git LFS not found"
```bash
brew install git-lfs
```

### "Railway not deploying"
Check:
1. Environment variables are set
2. `DATABASE_URL` exists (auto-created by PostgreSQL service)
3. Certificate base64 strings are complete (no truncation)

### "Database connection error"
The system will automatically fallback to JSON logging if PostgreSQL is unavailable.

### Need help?
- Full guide: `RAILWAY_DEPLOYMENT_GUIDE.md`
- Railway docs: https://docs.railway.app

---

## 📁 ALL YOUR DEPLOYMENT FILES

```
04_GB_Track_Specialist_Production_Trial/
├── deploy.sh                         ← Run this script
├── DEPLOY_NOW.md                     ← You are here
├── RAILWAY_DEPLOYMENT_GUIDE.md       ← Full reference
├── database_schema.sql               ← Database schema
├── database_helper.py                ← Database integration
├── gb_betting_system.py              ← Updated with DB logging
├── betfair_client.py                 ← Updated with base64 certs
├── requirements.txt                  ← Python dependencies
├── Procfile                          ← Railway worker config
├── .gitattributes                    ← Git LFS config
└── .gitignore                        ← Git exclusions
```

---

**Ready to deploy? Run `./deploy.sh` from the deployment directory!** 🚀
