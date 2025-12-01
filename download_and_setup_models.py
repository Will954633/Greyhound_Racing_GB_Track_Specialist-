#!/usr/bin/env python3
"""
Download ML models on first startup if they don't exist.
This runs before the main application starts.
"""
import os
import sys
from pathlib import Path
import subprocess

# Google Drive file IDs
GOOGLE_DRIVE_IDS = {
    'base_model.cbm': '14DW_4eBzEZ-r3ZBOIgA9LYaLs1ocb-ZR',
    'calibrator_model.cbm': '1oEGiE95Qry6kmEM-D4N8p67aLkrCTppe'
}

ARTIFACTS_DIR = Path('artifacts')
MIN_SIZES = {
    'base_model.cbm': 150_000_000,  # 150MB minimum
    'calibrator_model.cbm': 40_000_000  # 40MB minimum
}

def check_file_valid(filepath, min_size):
    """Check if file exists and is large enough"""
    if not filepath.exists():
        return False
    size = filepath.stat().st_size
    return size >= min_size

def download_from_google_drive(file_id, destination):
    """Download file from Google Drive using gdown"""
    print(f"Downloading {destination.name} from Google Drive...")
    print(f"  File ID: {file_id}")
    
    try:
        # Install gdown if not available
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=True)
        
        # Download using gdown
        import gdown
        url = f'https://drive.google.com/uc?id={file_id}'
        gdown.download(url, str(destination), quiet=False)
        
        size_mb = destination.stat().st_size / (1024 * 1024)
        print(f"  ✓ Downloaded {size_mb:.1f} MB")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("=" * 70)
    print("ML Model Setup")
    print("=" * 70)
    
    # Create artifacts directory
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    
    # Check each model
    all_valid = True
    for model_name, min_size in MIN_SIZES.items():
        model_path = ARTIFACTS_DIR / model_name
        
        if check_file_valid(model_path, min_size):
            size_mb = model_path.stat().st_size / (1024 * 1024)
            print(f"✓ {model_name}: {size_mb:.1f} MB (valid)")
        else:
            print(f"✗ {model_name}: Missing or too small")
            
            # Try to download from Google Drive
            file_id = GOOGLE_DRIVE_IDS.get(model_name)
            if file_id:
                if not download_from_google_drive(file_id, model_path):
                    all_valid = False
            else:
                print(f"  ⚠ No Google Drive ID configured for {model_name}")
                print(f"  Please update GOOGLE_DRIVE_IDS in download_and_setup_models.py")
                all_valid = False
    
    print("=" * 70)
    
    if all_valid:
        print("✓ All models ready!")
        return 0
    else:
        print("✗ Some models are missing")
        return 1

if __name__ == "__main__":
    sys.exit(main())
