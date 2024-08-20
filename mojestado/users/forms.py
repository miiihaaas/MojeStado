from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from flask_wtf.file import FileField, FileRequired, FileAllowed
from mojestado.models import User


class RegistrationUserForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    confirm_password = PasswordField('Potvrdite lozinku', validators=[DataRequired(), EqualTo('password')])
    name = StringField('Ime', validators=[DataRequired(), Length(min=2, max=20)])
    surname = StringField('Prezime', validators=[DataRequired(), Length(min=2, max=20)])
    phone = StringField('Telefon', validators=[DataRequired(), Length(min=9, max=10)])
    address = StringField('Adresa', validators=[DataRequired(), Length(min=2, max=20)])
    city = StringField('Grad', validators=[DataRequired(), Length(min=2, max=20)])
    zip_code = StringField('Poštanski broj', validators=[DataRequired(), Length(min=5, max=5)])
    jmbg = StringField('JMBG', validators=[DataRequired(), Length(min=13, max=13)])
    submit = SubmitField('Registrujte se')


class EditProfileForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    name = StringField('Ime', validators=[DataRequired(), Length(min=2, max=20)])
    surname = StringField('Prezime', validators=[DataRequired(), Length(min=2, max=20)])
    address = StringField('Adresa', validators=[DataRequired(), Length(min=2, max=20)])
    city = StringField('Grad', validators=[DataRequired(), Length(min=2, max=20)])
    zip_code = StringField('Poštanski broj', validators=[DataRequired(), Length(min=5, max=5)])
    jmbg = StringField('JMBG', validators=[DataRequired(), Length(min=13, max=13)])
    submit = SubmitField('Sačuvaj izmene')


class RegistrationFarmForm(FlaskForm):
    email = StringField('Mejl', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    confirm_password = PasswordField('Potvrdite lozinku', validators=[DataRequired(), EqualTo('password')])
    name = StringField('Ime', validators=[DataRequired(), Length(min=2, max=20)])
    surname = StringField('Prezime', validators=[DataRequired(), Length(min=2, max=20)])
    address = StringField('Adresa', validators=[DataRequired(), Length(min=2, max=20)])
    city = StringField('Mesto', validators=[DataRequired(), Length(min=2, max=20)])
    # zip_code = StringField('Poštanski broj', validators=[DataRequired(), Length(min=5, max=5)])
    municipality = SelectField('Opština', choices=[])
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


class AddAnimalForm(FlaskForm):
    category = SelectField('Kategorija', choices=[])
    subcategory = SelectField('Podkategorija', choices=[])
    race = SelectField('Rasa', choices=[])
    intended_for = SelectField('Namena', choices=['tov', 'priplod'])
    weight = FloatField('Težina (kg)', validators=[DataRequired()])
    price = FloatField('Cena po kg', validators=[DataRequired()])
    insured = BooleanField('Osigurano')
    organic = BooleanField('Organska proizvodnja')
    cardboard = FileField('Karton', validators=[])
    animal_gender = SelectField('Pol', choices=['','m', 'z'])
    submit = SubmitField('Dodajte novu zivotinju')


class AddProductForm(FlaskForm):
    category = SelectField('Kategorija', choices=[])
    subcategory = SelectField('Potkategorija', choices=[])
    section = SelectField('Sekcija', choices=[])
    product_name = StringField('Naziv proizvoda', validators=[DataRequired(), Length(min=2, max=50)])
    product_description = TextAreaField('Opis proizvoda', validators=[DataRequired(), Length(min=2, max=500)])
    unit_of_measurement = SelectField('Jedinica mere', choices=["kg", "kom"])
    weight_conversion = FloatField('Konverzija', validators=[])
    product_price_per_unit = FloatField('Cena po jedinici', validators=[])
    organic_product = BooleanField('Organska proizvodnja')
    quantity = FloatField('Kolicina', validators=[])
    
    submit = SubmitField('Dodajte proizvod')
    