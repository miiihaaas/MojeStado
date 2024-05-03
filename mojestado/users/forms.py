from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from mojestado.models import User


class RegistrationUserForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    confirm_password = PasswordField('Potvrdite lozinku', validators=[DataRequired(), EqualTo('password')])
    name = StringField('Ime', validators=[DataRequired(), Length(min=2, max=20)])
    surname = StringField('Prezime', validators=[DataRequired(), Length(min=2, max=20)])
    address = StringField('Adresa', validators=[DataRequired(), Length(min=2, max=20)])
    city = StringField('Grad', validators=[DataRequired(), Length(min=2, max=20)])
    zip_code = StringField('Poštanski broj', validators=[DataRequired(), Length(min=5, max=5)])
    jmbg = StringField('JMBG', validators=[DataRequired(), Length(min=13, max=13)])
    submit = SubmitField('Registrujte se')


class RegistrationFarmForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    confirm_password = PasswordField('Potvrdite lozinku', validators=[DataRequired(), EqualTo('password')])
    name = StringField('Ime', validators=[DataRequired(), Length(min=2, max=20)])
    surname = StringField('Prezime', validators=[DataRequired(), Length(min=2, max=20)])
    address = StringField('Adresa', validators=[DataRequired(), Length(min=2, max=20)])
    city = StringField('Grad', validators=[DataRequired(), Length(min=2, max=20)])
    zip_code = StringField('Poštanski broj', validators=[DataRequired(), Length(min=5, max=5)])
    phone = StringField('Telefon', validators=[DataRequired(), Length(min=9, max=10)])
    jmbg = StringField('JMBG', validators=[DataRequired(), Length(min=13, max=13)])
    pbg = StringField('PBG', validators=[DataRequired(), Length(min=9, max=9)])
    mb = StringField('MB', validators=[DataRequired(), Length(min=9, max=9)])
    submit = SubmitField('Registrujte se')


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