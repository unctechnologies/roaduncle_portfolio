#!/bin/bash

# 1. Sync and push your clean code changes first
git checkout portfolio-branch
git add .  # <--- CRITICAL: This stages your actual code changes
git commit -m "Update public portfolio code"
git push portfolio portfolio-branch:main --force

# 2. Switch to main and pull the new clean code into it
git checkout main
git merge portfolio-branch --no-edit # Bring the fresh code over to main

# 3. Force-add the sensitive data files ONLY to the main branch
git add -f mvl_data.json soul.md git_push.bash
git commit -m "Automated production data backup"

# 4. Push everything safely to your private backup
git push origin main
