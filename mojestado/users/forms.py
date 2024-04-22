from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from mojestado.models import User





class LoginForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    remember = BooleanField('Zapamti me')
    submit = SubmitField('Prijavite se')


class RequestResetForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    submit = SubmitField('Zatražite reset lozinke')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('Ne postoji korisnik sa Vašim emailom. Zatražite od vašeg administratora da Vam otvori nalog.')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova lozinka', validators=[DataRequired()])
    confirm_password = PasswordField('Potvrdite novu lozinku', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Resetujte lozinku')