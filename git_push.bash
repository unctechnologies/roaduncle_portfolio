#!/bin/bash

# 1. Ensure we are on the clean portfolio branch and push it to the public repo
git checkout portfolio-branch
git add .
git commit -m "update public portfolio code"
git push portfolio portfolio-branch:main --force

# 2. Switch back to your main production branch
git checkout main
git merge portfolio-branch --no-edit 
# 3. Force-add the sensitive data files ONLY to the main branch
git add -f mvl_data.json soul.md

# 4. Commit and push the data safely to your private backup (origin)
git commit -m "Automated production data backup"
git push origin main
