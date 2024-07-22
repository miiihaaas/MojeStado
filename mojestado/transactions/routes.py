import datetime
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from mojestado import app, db
from mojestado.models import Animal, User

transactions = Blueprint('transactions', __name__)


def register_guest_user(form_object):
    user = User(email=form_object.get('email'),
                name=form_object.get('name'),
                surname=form_object.get('surname'),
                address=form_object.get('address'),
                city=form_object.get('city'),
                zip_code=form_object.get('zip_code'),
                user_type='guest',
                registration_date=datetime.date.today())
    db.session.add(user)
    db.session.commit()
    return user.id


def create_invoice():
    pass


def check_bank_balance() -> bool:
    return True


@transactions.route('/make_transaction', methods=['GET', 'POST'])
def make_transaction():
    form_object = request.form
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
            #! nema ovaj mejl u db, kreirati usera sa tipom guest i napraviti fakturu i stavke u fakturi
    

    bank_info = form_object.get('bank_info')
    print(f'{bank_info=}')
    transaction_possible = check_bank_balance()
    if transaction_possible:
        flash('Transakcija je uspješno izvršena', 'success')
        create_invoice()
    # animals = session.get('animals', [])
    # products = session.get('products', [])
    # if not current_user.is_authenticated:
    #     flash('Da bi ste dovršili kupovinu potrebno je da se prijavite!', 'warning')
    #     return redirect(url_for('users.login'))
    # total_price = 0.0

    # for animal in animals:
    #     total_price += float(animal['total_price'])
    # print(f'{total_price=}')

    #! ovo tek kada se iz banke potvrdi da je transakcija izvršena
    # for animal in animals:
    #     print(f'{animal["id"]=}')
    #     animal_to_edit = Animal.query.get(animal['id'])
    #     animal_to_edit.active = False
    #     db.session.commit()
    
    # Ispis podataka radi provere
    # print(f'Animals in session: {animals}')
    # print(f'Products in session: {products}')
    return redirect(url_for('main.home'))


@transactions.route('/guest_form', methods=['GET', 'POST'])
def guest_form():
    
    return render_template('guest_form.html')