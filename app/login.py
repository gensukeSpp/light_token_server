import os

from flask import Flask, render_template, flash, redirect, request
from flask_login import current_user, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask.helpers import url_for
from werkzeug.urls import url_parse

from .forms import LoginForm
from .models import StaffLogin

app = Flask(__name__)

# 日本語文字化け対応
app.json.ensure_ascii = False

db = SQLAlchemy(app)


@app.route("/logout_mes", methods=["GET"])
def logout_mes():
    return render_template("logout_mes.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("select_links"))

    form = LoginForm()
    if form.validate_on_submit():
        user = (
            db.session.query(StaffLogin)
            .filter(StaffLogin.STAFFID == form.STAFFID.data)
            .first()
        )
        print(f"Login directly: {user.STAFFID}")
        if user is None or not user.check_password(form.PASSWORD.data):
            flash("ユーザ名かパスワードが違います")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or url_parse(next_page).netloc != "":
            next_page = url_for("select_links")
        return redirect(next_page)
    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("logout_mes"))


""" WebブラウザのCSSキャッシュ対策 """


@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)


def dated_url_for(endpoint, **values):
    if endpoint == "static":
        filename = values.get("filename", None)
        if filename:
            file_path = os.path.join(app.root_path, endpoint, filename)
            values["q"] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)
