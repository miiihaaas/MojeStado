from datetime import timedelta
import os
from dotenv import load_dotenv
from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail


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
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER') # https://www.youtube.com/watch?v=IolxqkL7cD8&ab_channel=CoreySchafer   ////// os.environ.get vs os.getenv
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS') # https://www.youtube.com/watch?v=IolxqkL7cD8&ab_channel=CoreySchafer -- za 2 step verification: https://support.google.com/accounts/answer/185833

mail = Mail(app)


from mojestado.animals.routes import animals
from mojestado.farms.routes import farms
from mojestado.main.routes import main
from mojestado.marketplace.routes import marketplace
from mojestado.transactions.routes import transactions
from mojestado.users.routes import users
# print('__init__ checkpoint 9')


app.register_blueprint(animals)
app.register_blueprint(farms)
app.register_blueprint(main)
app.register_blueprint(marketplace)
app.register_blueprint(transactions)
app.register_blueprint(users)
