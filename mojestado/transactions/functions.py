import datetime

from flask import session
from mojestado import db
from mojestado.models import Animal, Product, User


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


def check_bank_balance() -> bool:
    return True


def create_invoice():
    print('wip: Faktura kreirana')
    pass


def send_email(user, form_object):
    cart_data = form_object.get('cartData')
    print(f'{cart_data=}')
    # ako je na rate šaleje fakturu i uplatnice za sve rate
    # ako nije na rate, šalje fakturu
    print('wip: Email poslat')
    pass


def deactivate_animals():
    for animal in session.get('animals', []):
        print(f'wip: deaktivirane kupljene životinje')
        print(f'{animal["id"]=}')
        animal_to_edit = Animal.query.get(animal['id'])
        animal_to_edit.active = False
        db.session.commit()
    pass


def deactivate_products():
    for product in session.get('products', []):
        print(f'wip: deaktivirane kupljene proizvode')
        print(f'{product["id"]=}')
        product_to_edit = Product.query.get(product['id'])
        product_to_edit.quantity = float(product_to_edit.quantity) - float(product['quantity']) #! ne smanjuje količinu?
        db.session.commit()
    pass