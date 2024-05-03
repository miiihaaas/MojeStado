from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail
from mojestado.users.forms import LoginForm, RequestResetForm, ResetPasswordForm, RegistrationUserForm, RegistrationFarmForm
from mojestado.models import User
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message


users = Blueprint('users', __name__)


@users.route("/register_farm")
def register_farm(): #! Registracija poljoprivrednog gazdinstva
    form = RegistrationFarmForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, 
                    password=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
                    name=form.name.data,
                    surname=form.surname.data,
                    address=form.address.data,
                    city=form.city.data,
                    zip_code=form.zip_code.data,
                    phone=form.phone.data,
                    pbg=form.pbg.data,
                    jmbg=form.jmbg.data,
                    mb=form.mb.data,
                    user_type='farm_inactive', #! definisati tipove korisnika (farm, user, admin), razraditi za farm neaktivan dok ne potpiše ugovor, pa posle toga ga admin premesti u aktivan
                    )
        db.session.add(user)
        db.session.commit()
        flash(f'Uspesno ste poslali zahtev za registraciju. Na Vaš mejl je poslat ugovor pomoću koga se završava registracija.', 'success')
        #! napisati kod za generisanje ugovora i slanje ugovora na mejl
        return redirect(url_for('main.home'))
    return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva',
                            form=form)


@users.route("/register_user", methods=['GET', 'POST'])
def register_user(): #! Registracija korisnika
    form = RegistrationUserForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, 
                    password=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
                    name=form.name.data,
                    surname=form.surname.data,
                    address=form.address.data,
                    city=form.city.data,
                    zip_code=form.zip_code.data,
                    jmbg=form.jmbg.data,
                    user_type='user' #! definisati tipove korisnika (farm, user, admin), razraditi za farm neaktivan dok ne potpiše ugovor, pa posle toga ga admin premesti u aktivan
                    )
        db.session.add(user)
        db.session.commit()
        flash(f'Uspesno ste se poslali zahtev za registraciju. Na Vašu mejl adresu je poslat link za potvrdu registracije.', 'success')
        #! nastaviti kod za slanje mejla korisniku
        return redirect(url_for('main.home'))
    return render_template('register_user.html', title='Registracija korisnika',
                            form=form)

@users.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Dobro došli, {user.name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash(f'Email ili lozinka nisu odgovarajući.', 'danger')
    return render_template('login.html', title='Prijavljivanje', form=form, legend='Prijavljivanje')


@users.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))


@users.route("/my_user")
def my_user(): #! Moj nalog za korisnika
    pass
