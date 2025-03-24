from extensions import db
from flask_login import UserMixin
from sqlalchemy import Integer, String, Column, exists, select, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(25), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)


class JsonFile(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(
        String(120), nullable=True, unique=True)
    json_data: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)

class PastExchange(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(
        String(120), nullable=True, unique=True)
    json_data: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)