import datetime
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from mojestado import app, db
from mojestado.main.functions import clear_cart_session
from mojestado.models import Animal, User
from mojestado.transactions.form import GuestForm
from mojestado.transactions.functions import register_guest_user, create_invoice, send_email, check_bank_balance, deactivate_animals, deactivate_products


transactions = Blueprint('transactions', __name__)


@transactions.route('/make_transaction', methods=['GET', 'POST'])
def make_transaction():
    form_object = request.form
    print(f'*/*/*{form_object=}')
    if not current_user.is_authenticated:
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user and user.user_type != 'guest':
            flash('Nalog sa ovim mejlom već postoji. Molim Vas ulogujte se.', 'warning')
            return redirect(url_for('users.login'))
        # elif user and user.user_type == 'guest':
        #     print(f'ako ima u db mejl sa tipom guest, onda treba napraviti fakturu i stavke u fakturi')
        #     create_invoice()
        #     pass
            #! ako ima u db mejl sa tipom guest, onda treba napraviti fakturu i stavke u fakturi
        elif not user:
            print(f'nema ovaj mejl u db, kreirati usera sa tipom guest i napraviti fakturu i stavke u fakturi')
            user_id = register_guest_user(form_object)
            print(f'{user_id=}')
            user = User.query.get(user_id)
    else:
        user = current_user

    bank_info = form_object.get('bank_info')
    print(f'{bank_info=}')
    
    successful_transaction = check_bank_balance()
    if successful_transaction:
        create_invoice()
        send_email(user, form_object)
        deactivate_animals()
        deactivate_products()
        # clear_cart_session()
        flash('Transakcija je uspešno izvršena', 'success')
    else:
        flash('Transakcija nije uspešno izvršena', 'danger')
        return redirect(url_for('main.view_cart'))
    return redirect(url_for('main.home'))


@transactions.route('/guest_form', methods=['GET', 'POST'])
def guest_form():
    form = GuestForm()
    
    if current_user.is_authenticated:
        form.email.data = current_user.email
        form.name.data = current_user.name
        form.surname.data = current_user.surname
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.zip_code.data = current_user.zip_code
        
    if form.validate_on_submit():
        # Process the form data
        # For example, you might create a new transaction or save the guest information
        flash('Kupovina uspešno obavljena!', 'success')
        return redirect(url_for('transactions.make_transaction'))
    
    return render_template('guest_form.html', form=form)