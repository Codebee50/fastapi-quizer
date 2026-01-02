web: uvicorn app.main:app --host 0.0.0.0 --port 9000
worker: celery -A app.worker.celery worker --loglevel=info --concurrency=1