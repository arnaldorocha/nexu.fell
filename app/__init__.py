# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

app = Flask(__name__)
# secret key should come from environment in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mude_esta_chave_em_producao')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'          # rota de login
login_manager.login_message_category = 'info'

from app.models import Usuario

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# importa routes no final para evitar circular imports
from app import routes
