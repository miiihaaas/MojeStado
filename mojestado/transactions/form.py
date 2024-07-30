from mojestado import db
from flask_wtf import FlaskForm
from wtforms import EmailField, StringField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Email

from mojestado.models import User

class GuestForm(FlaskForm):
    email = EmailField('Mejl', validators=[DataRequired(), Email()])
    name = StringField('Ime', validators=[DataRequired()])
    surname = StringField('Prezime', validators=[DataRequired()])
    address = StringField('Adresa', validators=[DataRequired()])
    city = StringField('Mesto', validators=[DataRequired()])
    zip_code = StringField('ZIP', validators=[DataRequired()])

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email adresa već postoji.')

    def validate_name(self, name):
        if len(name.data) < 2:
            raise ValidationError('Ime mora da sadrži bar dva slova.')

    def validate_surname(self, surname):
        if len(surname.data) < 2:
            raise ValidationError('Prezime mora da sadrži bar dva slova.')

    def validate_address(self, address):
        if len(address.data) < 2:
            raise ValidationError('Adresa mora da sadrži bar dva slova.')

    def validate_city(self, city):
        if len(city.data) < 2:
            raise ValidationError('Mesto mora da sadrži bar dva slova.')

    def validate_zip_code(self, zip_code):
        if len(zip_code.data) != 5:
            raise ValidationError('ZIP kod mora da sadrži pet znamenki.')

    def validate_bank_info(self, bank_info):
        if len(bank_info.data) < 2:
            raise ValidationError('Podaci bankovne kartice moraju sadržati bar dva slova.')
    bank_info = StringField('Podaci bankovne kartice', validators=[DataRequired()])
