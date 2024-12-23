from datetime import timedelta
import os
from dotenv import load_dotenv
from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_apscheduler import APScheduler


load_dotenv()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
#kod ispod treba da reši problem Internal Server Error - komunikacija sa serverom
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['FLASK_APP'] = 'run.py'

app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=10)

db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db

Session(app)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

app.config['JSON_AS_ASCII'] = False #! da ne bude ascii već utf8
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER') # dodati u .env: 'mail.popis.online'
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT') # dodati u .env: 465
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() in ['true', 'on', '1']
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
mail = Mail(app)


# Dodajte ove linije za inicijalizaciju APScheduler-a
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

from mojestado.animals.routes import animals
from mojestado.farms.routes import farms
from mojestado.main.routes import main
from mojestado.marketplace.routes import marketplace
from mojestado.transactions.routes import transactions
from mojestado.users.routes import users
from mojestado.animals.functions import schedule_daily_weight_gain  # Dodajte ovu liniju

# print('__init__ checkpoint 9')


app.register_blueprint(animals)
app.register_blueprint(farms)
app.register_blueprint(main)
app.register_blueprint(marketplace)
app.register_blueprint(transactions)
app.register_blueprint(users)

# Pozovite funkciju za zakazivanje zadatka
schedule_daily_weight_gain(scheduler)