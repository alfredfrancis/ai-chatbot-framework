from datetime import timedelta

BROKER_URL = 'mongodb://localhost:27017/workspace'
CELERY_RESULT_BACKEND = "mongodb"
CELERY_MONGODB_BACKEND_SETTINGS = {
    "host": "127.0.0.1",
    "port": 27017,
    "database": "celery",
    "taskmeta_collection": "checking_log",
}

CELERYBEAT_SCHEDULE = {
    'every-minute': {
        'task': 'ikyMainframe.listener.listen',
        'schedule': timedelta(seconds=5)
    },
}