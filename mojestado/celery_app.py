from celery import Celery
from mojestado import app
import os
from dotenv import load_dotenv
import pathlib
from celery.schedules import crontab

# Dinamički pronađi putanju do .env fajla
current_file = pathlib.Path(__file__)
project_root = current_file.parent.parent  # Ovo je MojeStado direktorijum
env_path = project_root / '.env'

# Učitaj .env fajl ako postoji
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

def make_celery(app):
    redis_url = f"redis://:{os.getenv('REDIS_PASSWORD')}@{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/{os.getenv('REDIS_DB', '0')}"
    celery = Celery(
        app.import_name,
        backend=redis_url,
        broker=redis_url
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
                
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# Inicijalizacija: Učitavanje taskova
from mojestado.animals import tasks  # Eksplicitni import

# Podešavanje za izvršavanje svakog dana u 2:00 AM
celery.conf.beat_schedule = {
    'daily-weight-update': {
        'task': 'mojestado.animals.tasks.daily_weight_gain_task',
        'schedule': crontab(hour=2, minute=0),  # Svakog dana u 2:00 AM
        'options': {'expires': 3600}  # istekne ako se ne izvrši u roku od sat vremena
    },
}
