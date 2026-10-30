# app.py
# Flask(로그인) + Dash(대시보드) 조립/실행 엔트리포인트

import os
import secrets
from flask import Flask, redirect, url_for, request
from flask_login import login_required, current_user

from auth.login import init_auth, init_db
from dashboard.dash_app import init_dash


def create_app():
    # Flask 앱 생성
    flask_app = Flask(__name__, template_folder="templates")
    flask_app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

    # SQLite 유저 DB 초기화
    init_db(flask_app)

    # 로그인/회원가입/로그아웃 라우트 등록 + LoginManager 등록
    init_auth(flask_app)

    # Dash 화면·콜백·에셋 경로 모두 로그인 후 접근
    @flask_app.before_request
    def protect_dashboard():
        if request.path == "/dashboard" or request.path.startswith("/dashboard/"):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))

    # Dash 앱을 Flask에 mount
    # url_prefix는 대시보드 URL 루트. 예: /dashboard/
    init_dash(flask_app, url_prefix="/dashboard/")

    # 루트 요청을 로그인 화면으로 이동
    @flask_app.route("/")
    def root():
        return redirect(url_for("login"))

    # 로그인한 사용자를 대시보드로 이동
    @flask_app.route("/go_dashboard")
    @login_required
    def go_dashboard():
        return redirect("/dashboard/")

    return flask_app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=8888, debug=False, use_reloader=False)
