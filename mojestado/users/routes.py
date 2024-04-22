from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail
from mojestado.users.forms import LoginForm, RequestResetForm, ResetPasswordForm
from mojestado.models import User
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message


users = Blueprint('users', __name__)


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


@users.route("/register_farm")
def register_farm(): #! Registracija poljoprivrednog gazdinstva
    return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva')


@users.route("/register_user")
def register_user(): #! Registracija korisnika
    pass


@users.route("/my_user")
def my_user(): #! Moj nalog za korisnika
    pass
