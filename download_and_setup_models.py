#!/usr/bin/env python3
"""
Download ML models on first startup if they don't exist.
This runs before the main application starts.
"""
import os
import sys
from pathlib import Path
import urllib.request
import hashlib

# TODO: Replace these URLs with your uploaded model URLs
MODEL_URLS = {
    'base_model.cbm': 'YOUR_BASE_MODEL_URL_HERE',  # Replace with actual URL
    'calibrator_model.cbm': 'YOUR_CALIBRATOR_URL_HERE'  # Replace with actual URL
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

def download_file(url, destination):
    """Download file with progress"""
    print(f"Downloading {destination.name}...")
    print(f"  From: {url}")
    
    try:
        urllib.request.urlretrieve(url, destination)
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
            
            # Try to download
            url = MODEL_URLS.get(model_name)
            if url and url != f'YOUR_{model_name.upper().replace(".", "_")}_URL_HERE':
                if not download_file(url, model_path):
                    all_valid = False
            else:
                print(f"  ⚠ No download URL configured for {model_name}")
                print(f"  Please upload {model_name} manually or set URL in download_and_setup_models.py")
                all_valid = False
    
    print("=" * 70)
    
    if all_valid:
        print("✓ All models ready!")
        return 0
    else:
        print("✗ Some models are missing")
        print("\nTo fix this:")
        print("1. Upload your models to Dropbox/Google Drive/S3")
        print("2. Get public/pre-signed URLs")
        print("3. Update MODEL_URLS in download_and_setup_models.py")
        print("4. Redeploy to Railway")
        return 1

if __name__ == "__main__":
    sys.exit(main())
