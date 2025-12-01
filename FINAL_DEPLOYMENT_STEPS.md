# 🎯 FINAL DEPLOYMENT STEPS - COMPLETE THIS TO GET SYSTEM RUNNING

## ✅ WHAT'S ALREADY DONE:

- ✓ All code ready and tested locally
- ✓ Database schema created
- ✓ Railway project configured
- ✓ PostgreSQL database added
- ✓ Download script created
- ✓ Everything pushed to GitHub

## 📋 YOU NEED TO DO (3 SIMPLE STEPS):

### **STEP 1: Upload Models to Public Storage** (5 minutes)

Upload your 2 model files to a service that provides public URLs:

**Option A - Dropbox (Easiest):**
1. Go to https://dropbox.com
2. Upload these files:
   - `04_GB_Track_Specialist_Production_Trial/artifacts/base_model.cbm` (172MB)
   - `04_GB_Track_Specialist_Production_Trial/artifacts/calibrator_model.cbm` (43MB)
3. Right-click each file → "Share" → "Create Link"
4. Change the URL from `?dl=0` to `?dl=1` (forces direct download)

**Option B - Google Drive:**
1. Upload files to Google Drive
2. Right-click → "Get link" → "Anyone with the link"
3. Get the file ID from URL: `https://drive.google.com/file/d/FILE_ID_HERE/view`
4. Use download URL: `https://drive.google.com/uc?export=download&id=FILE_ID_HERE`

**Option C - AWS S3 (If you have it):**
1. Upload to S3 bucket
2. Make objects public or create pre-signed URLs (valid for 7 days)

---

### **STEP 2: Update the Download Script** (30 seconds)

Edit this file on GitHub:
`04_GB_Track_Specialist_Production_Trial/download_and_setup_models.py`

**Find these lines (around line 13):**
```python
MODEL_URLS = {
    'base_model.cbm': 'YOUR_BASE_MODEL_URL_HERE',  # Replace with actual URL
    'calibrator_model.cbm': 'YOUR_CALIBRATOR_URL_HERE'  # Replace with actual URL
}
```

**Replace with your URLs:**
```python
MODEL_URLS = {
    'base_model.cbm': 'https://www.dropbox.com/s/abc123/base_model.cbm?dl=1',
    'calibrator_model.cbm': 'https://www.dropbox.com/s/xyz789/calibrator_model.cbm?dl=1'
}
```

How to edit on GitHub:
1. Go to: https://github.com/Will954633/Greyhound_Racing_GB_Track_Specialist-
2. Navigate to: `download_and_setup_models.py`
3. Click the pencil icon (✏️) to edit
4. Update the URLs
5. Click "Commit changes"

---

### **STEP 3: Railway Will Auto-Deploy** (2-3 minutes)

Railway detects the GitHub commit and automatically:
1. Builds Docker image
2. Runs `download_and_setup_models.py`
3. Downloads your models (215MB)
4. Starts the betting system!

---

## 📊 VERIFY IT'S WORKING:

### In Railway Dashboard → Deploy Logs:

**You'll see:**
```
======================================================================
ML Model Setup
======================================================================
✓ base_model.cbm: 172.0 MB (valid)
✓ calibrator_model.cbm: 43.0 MB (valid)
======================================================================
✓ All models ready!

INFO:gb_ensemble_predictor_v2:Initializing GB Ensemble Predictor V2...
INFO:gb_ensemble_predictor_v2:Loading Track Specialist Model...
INFO:gb_ensemble_predictor_v2:✓ Loaded Track Specialist Model
INFO:gb_ensemble_predictor_v2:  Expected features: 32
INFO:gb_ensemble_predictor_v2:✓ Loaded Calibrator Model
INFO:gb_betting_system:✓ GB Track Specialist Betting System ready
INFO:__main__:[GB] System initialized successfully!
INFO:__main__:[GB] Starting scheduled race monitoring...
```

---

## 🎉 WHAT HAPPENS NEXT:

Your system will:
- ✅ Monitor GB greyhound races every 15 minutes
- ✅ Generate predictions for ALL runners
- ✅ Log bets using current methodology
- ✅ Store everything in PostgreSQL for grid search
- ✅ Run 24/7 continuously

---

## 🔧 TROUBLESHOOTING:

### If models don't download:

**Check Railway logs for errors like:**
- "✗ Error: HTTP Error 403" → URL is not public
- "✗ Error: HTTP Error 404" → URL is wrong

**Fix:**
1. Make sure Dropbox URLs end with `?dl=1`
2. For Google Drive, use the `uc?export=download&id=` format
3. Test URLs in your browser first - they should download immediately

### If models download but are corrupted:

**Check file sizes in logs:**
- base_model.cbm should be ~172MB
- calibrator_model.cbm should be ~43MB

If too small, the URL is probably a webpage not the file.

---

## 📞 READY TO GO:

**Just do these 3 things:**
1. Upload models to Dropbox/Drive → Get URLs
2. Edit `download_and_setup_models.py` on GitHub → Add URLs
3. Wait 2-3 minutes → System starts!

**That's it! Your system will be live and collecting data for grid search optimization.**

---

## 📊 AFTER IT'S RUNNING:

Access your data for grid search:

```sql
-- Connect to Railway PostgreSQL (get DATABASE_URL from Railway dashboard)

-- See recent predictions
SELECT * FROM predictions ORDER BY created_at DESC LIMIT 10;

-- Analyze win rates by venue
SELECT venue, COUNT(*), 
       AVG(CASE WHEN won THEN 1.0 ELSE 0.0 END) as win_rate
FROM predictions
WHERE was_bet = true
GROUP BY venue;
```

All your grid search data will be there! 🎯
