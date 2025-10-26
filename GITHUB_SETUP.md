# How to Upload to GitHub

## Step 1: Create a GitHub Repository

1. Go to https://github.com and sign in
2. Click the "+" icon in the top right corner
3. Select "New repository"
4. Name it "SensorVisualization" (or any name you prefer)
5. Choose Public or Private
6. **DO NOT** initialize with README, .gitignore, or license (we already have these)
7. Click "Create repository"

## Step 2: Upload Your Code

After creating the repository, GitHub will show you commands. Run these in your terminal:

```bash
cd /home/nikhilshokeen/SensorVisualization

# Add the remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/SensorVisualization.git

# Rename branch to main (GitHub uses 'main' instead of 'master')
git branch -M main

# Push your code to GitHub
git push -u origin main
```

If it asks for credentials, use a GitHub Personal Access Token instead of your password.

## Step 3: Create Personal Access Token (if needed)

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token"
3. Name it something like "SensorVisualization"
4. Check "repo" scope
5. Generate and copy the token
6. Use this token when prompted for password

## Done!

Your repository will be live at: `https://github.com/YOUR_USERNAME/SensorVisualization`

People can now:
1. Clone it: `git clone https://github.com/YOUR_USERNAME/SensorVisualization`
2. Install dependencies: `pip install -r requirements.txt`
3. Run it: `python sensor_visualizer.py`

