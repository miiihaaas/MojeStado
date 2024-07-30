import datetime

from flask import flash, json, redirect, session, url_for
from mojestado import db
from mojestado.models import Animal, Product, User


def generate_payment_slips(fattening_list):
    '''
    generiše 2+ uplatnice na jednom dokumentu (A4) u fpdf, qr kod/api iz nbs
    '''
    print('generisane uplatnice na jednom dokumentu (A4). dokument će biti attachovan u email')
    pass


def generate_invoice():
    '''
    generiše fakturu. dokument će biti attachovan u emali.
    '''
    print('generisana faktura. dokument bi trebao biti attachovan u email')
    pass


def register_guest_user(form_object):
    if not form_object.get('email'):
        flash ('Niste uneli email', 'danger')
        return redirect(url_for('transactions.guest_form'))
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
    '''
    čuva podaatke u db (faktura i stavke)
    '''
    print('wip: Faktura kreirana')
    pass


def send_email(user, form_object):
    '''
    ako je na rate šalje fakturu i sve uplatnice
    ako nije na rate šalje samo fakturu
    '''
    cart_data = json.loads(form_object.get('cartData'))
    print(f'{cart_data=}')
    fattening_list = cart_data['fattening']
    na_rate = False
    print(f'{fattening_list=}')
    for fattening in fattening_list:
        if int(fattening['br_rata']) > 1:
            na_rate = True
            break
    if na_rate:
        print('wip: faktura i uplatnice')
        payment_slips = generate_payment_slips(fattening_list) # generiše 2+ uplatnice na jednom dokumentu (A4)
    else:
        print('wip: samo faktura')
    invoice_file = generate_invoice()
    to = user.email
    subject = "Potvrda transakcije"
    body = f"Poštovani/a {user.name},\n\nVaša transakcija je uspešno izvršena.\n\nDetalji kupovine:\n{cart_data}\n\nHvala na poverenju!"
    
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    
    # TODO: Implement actual email sending logic here
    # For now, we'll just print the email details
    print('wip: Email poslat')


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
        product_to_edit.quantity = float(product_to_edit.quantity) - float(product['quantity'])
        db.session.commit()
    pass
