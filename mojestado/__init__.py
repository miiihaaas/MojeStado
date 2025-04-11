import os
from datetime import timedelta 
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from celery.schedules import crontab
import logging
from logging.handlers import RotatingFileHandler

# Učitavanje .env konfiguracije
root_path = Path(__file__).resolve().parent.parent
env_path = root_path / '.env'
load_dotenv(env_path)

# Podešavanje logovanja
if not os.path.exists('app_logs'):
    os.mkdir('app_logs')
file_handler = RotatingFileHandler('app_logs/mojestado.log', maxBytes=10240, backupCount=10, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]: %(message)s'
))
file_handler.setLevel(logging.DEBUG)

# Inicijalizacija Flask aplikacije
app = Flask(__name__)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.DEBUG)
app.logger.info('MojeStado startup')

# Osnovne konfiguracije
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_timeout': 20,
    'pool_pre_ping': True
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['FLASK_APP'] = 'run.py'

# Konfiguracija sesije
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = 'flask_session'
app.config['SESSION_FILE_THRESHOLD'] = 500
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=10)
app.config['SESSION_USE_SIGNER'] = False
app.config['SESSION_KEY_PREFIX'] = 'mojestado:'

if not os.path.exists('flask_session'):
    os.mkdir('flask_session')

# Inicijalizacija ekstenzija
db = SQLAlchemy(app)
migrate = Migrate(app, db)
sess = Session()
sess.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Email konfiguracija
app.config['JSON_AS_ASCII'] = False
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() in ['true', 'on', '1']
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['MAIL_ADMIN'] = os.getenv('MAIL_ADMIN')
mail = Mail(app)

# Celery konfiguracija
redis_url = f"redis://:{os.getenv('REDIS_PASSWORD')}@{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/{os.getenv('REDIS_DB', '0')}"
app.config['CELERY_BROKER_URL'] = redis_url
app.config['CELERY_RESULT_BACKEND'] = redis_url
app.config['CELERYBEAT_SCHEDULE'] = {
    'daily-weight-update': {
        'task': 'mojestado.animals.tasks.daily_weight_gain_task',
        'schedule': crontab(hour=1, minute=0)
    },
}

# Registracija blueprint-ova
from mojestado.animals.routes import animals
from mojestado.farms.routes import farms
from mojestado.main.routes import main
from mojestado.marketplace.routes import marketplace
from mojestado.transactions.routes import transactions
from mojestado.users.routes import users
from mojestado.errors.routes import errors

app.register_blueprint(animals)
app.register_blueprint(farms)
app.register_blueprint(main)
app.register_blueprint(marketplace)
app.register_blueprint(transactions)
app.register_blueprint(users)
app.register_blueprint(errors)