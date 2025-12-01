#!/bin/bash
# Railway Deployment Script for GB Track Specialist
# Automates Git LFS setup and GitHub deployment

set -e  # Exit on error

echo "=================================="
echo "GB Track Specialist - Railway Deployment"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check Git LFS is installed
echo "Step 1: Checking Git LFS..."
if ! command -v git-lfs &> /dev/null; then
    echo -e "${RED}✗ Git LFS not found!${NC}"
    echo "Installing Git LFS..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install git-lfs
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get install git-lfs
    else
        echo -e "${RED}Please install Git LFS manually: https://git-lfs.github.com${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Git LFS installed${NC}"
echo ""

# Step 2: Initialize Git LFS
echo "Step 2: Initializing Git LFS..."
git lfs install
echo -e "${GREEN}✓ Git LFS initialized${NC}"
echo ""

# Step 3: Check if .gitattributes exists
echo "Step 3: Checking .gitattributes..."
if [ ! -f ".gitattributes" ]; then
    echo -e "${YELLOW}Creating .gitattributes...${NC}"
    cat > .gitattributes << 'EOF'
# Git LFS Configuration for ML Models
*.cbm filter=lfs diff=lfs merge=lfs -text
**/*.cbm filter=lfs diff=lfs merge=lfs -text
*.pkl filter=lfs diff=lfs merge=lfs -text
**/*.pkl filter=lfs diff=lfs merge=lfs -text
*.joblib filter=lfs diff=lfs merge=lfs -text
**/*.joblib filter=lfs diff=lfs merge=lfs -text
EOF
fi
echo -e "${GREEN}✓ .gitattributes configured${NC}"
echo ""

# Step 4: Initialize Git repository if needed
echo "Step 4: Checking Git repository..."
if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
    echo -e "${GREEN}✓ Git repository initialized${NC}"
else
    echo -e "${GREEN}✓ Git repository exists${NC}"
fi
echo ""

# Step 5: Check for remote
echo "Step 5: Checking Git remote..."
if ! git remote get-url origin &> /dev/null; then
    echo -e "${YELLOW}No remote found. Adding GitHub remote...${NC}"
    read -p "Enter GitHub repository URL (e.g., git@github.com:Will954633/Greyhound_Racing_GB_Track_Specialist-.git): " REPO_URL
    git remote add origin "$REPO_URL"
    echo -e "${GREEN}✓ Remote added${NC}"
else
    ORIGIN=$(git remote get-url origin)
    echo -e "${GREEN}✓ Remote exists: ${ORIGIN}${NC}"
fi
echo ""

# Step 6: Add files to Git
echo "Step 6: Adding files to Git..."
echo "This may take a moment as ML models are tracked with LFS..."

# Add deployment directory files
git add .

# Add parent directory ML models
git add ../03_GB_Ensemble/Models/Track_Specialist_Model/ 2>/dev/null || echo "Track Specialist models not found"
git add ../03_GB_Ensemble/Production/ 2>/dev/null || echo "Production predictor not found"

echo -e "${GREEN}✓ Files added${NC}"
echo ""

# Step 7: Show what will be committed
echo "Step 7: Files to be committed:"
git status --short
echo ""

# Step 8: Commit
echo "Step 8: Committing changes..."
COMMIT_MSG="Deploy GB Track Specialist to Railway with database integration"
git commit -m "$COMMIT_MSG" || echo "Nothing to commit or already committed"
echo -e "${GREEN}✓ Changes committed${NC}"
echo ""

# Step 9: Push to GitHub
echo "Step 9: Pushing to GitHub (this will upload ML models to LFS)..."
echo -e "${YELLOW}This may take several minutes depending on model sizes...${NC}"

git push -u origin main || git push -u origin master

echo -e "${GREEN}✓ Pushed to GitHub successfully!${NC}"
echo ""

# Summary
echo "=================================="
echo -e "${GREEN}DEPLOYMENT PREPARATION COMPLETE!${NC}"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Encode your Betfair certificates (see DEPLOYMENT_STEPS.md)"
echo "2. Create Railway project from GitHub"
echo "3. Add PostgreSQL database"
echo "4. Set environment variables"
echo "5. Deploy!"
echo ""
echo "For detailed instructions, see: DEPLOYMENT_STEPS.md"
echo "=================================="
