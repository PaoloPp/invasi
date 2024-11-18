from flask import request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from http import HTTPStatus
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

@login_manager.unauthorized_handler
def unauthorized():
    if request.blueprint == 'api':
        abort(HTTPStatus.UNAUTHORIZED)
    return redirect(url_for('auth.login'))