# auth/login.py
# 인증 기능 전담: Flask-Login + SQLite(user DB)

import os
import sqlite3
from dataclasses import dataclass

from flask import render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.getenv("AUTH_DB_PATH", "users.db")


@dataclass
class User(UserMixin):
    id: int
    username: str
    password_hash: str


def _get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db(app):
    # 앱 시작 시 DB 테이블 생성
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()


def init_auth(app):
    # LoginManager 세팅
    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return User(id=row[0], username=row[1], password_hash=row[2])
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
            row = cur.fetchone()
            conn.close()

            if not row:
                flash("User not found.")
                return redirect(url_for("login"))

            if not check_password_hash(row[2], password):
                flash("Wrong password.")
                return redirect(url_for("login"))

            user = User(id=row[0], username=row[1], password_hash=row[2])
            login_user(user)
            # 로그인 성공 후 대시보드로 이동
            return redirect("/dashboard/")

        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if not username or not password:
                flash("Username/password required.")
                return redirect(url_for("signup"))

            conn = _get_conn()
            cur = conn.cursor()
            try:
                password_hash = generate_password_hash(password)
                cur.execute("INSERT INTO users(username, password) VALUES (?, ?)", (username, password_hash))
                conn.commit()
            except sqlite3.IntegrityError:
                conn.close()
                flash("Username already exists.")
                return redirect(url_for("signup"))

            conn.close()
            flash("Signup success. Please login.")
            return redirect(url_for("login"))

        return render_template("signup.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/account")
    @login_required
    def account():
        return render_template("account.html", username=current_user.username)
