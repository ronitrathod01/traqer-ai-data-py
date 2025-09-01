# traqer-ai-data-py
git branch
git branch temp_proch
git checkout temp_pro
git add -A
git commit -a -m "intial commit"
git push -u origin temp_pro

- New things used
# Celery
pip install celery[redis]
pip install redis

create file ---> project_root/celery.py
---> your_project/init.py
---> settings.py -> CELERY_BROKER_URL = "redis://localhost:6379/0"
                    CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# Install deps (Playwright + DRF)
pip install djangorestframework playwright
python -m playwright install chromium