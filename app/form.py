from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    STAFFID = StringField("社員番号", validators=[DataRequired()])
    PASSWORD = PasswordField("パスワード", validators=[DataRequired()])
    remember_me = BooleanField("記憶させる")
    submit = SubmitField("サインイン")
