import base64
import datetime
import hashlib
import random
from flask_login import current_user
from flask import session
import string
import urllib.parse


from flask import flash, json, redirect, render_template, session, url_for
from mojestado import db
from mojestado.models import Animal, Invoice, InvoiceItems, Product, User


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
    user = User.query.filter_by(email=form_object.get('email')).first()
    if user:
        return None
    # Kada kreirate nalog za gosta, možete sačuvati email u sesiji:
    session['guest_email'] = form_object.get('email')
    
    
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


###########################
### PaySpot integration ###
###########################
def generate_random_string(length=20):
    letters = string.ascii_letters + string.digits
    rnd = ''.join(random.choice(letters) for i in range(length))
    print(f'* generate random string: {rnd=}')
    return rnd

def check_invalid_characters(text):
    return '\\' in str(text) or '|' in str(text)

def calculate_hash(plaintext):
    if any(check_invalid_characters(value) for value in plaintext.split('|')):
        raise ValueError("Nevažeći karakteri: (\\ or |) pronađeni u plaintext-u.")

    print(f'* calculate hash: {plaintext=}')
    sha512_hash = hashlib.sha512(plaintext.encode('utf-8')).hexdigest()
    print(f'* calculate hash: {sha512_hash=}')
    hash_ = base64.b64encode(bytes.fromhex(sha512_hash)).decode('utf-8')
    print(f'** calculate hash: {hash_=}')
    return hash_

# def check_bank_balance() -> dict:
#     i = None
#     print('** PAYSPOT CHECK BANK BALANCE **')
#     company_id = 234075
#     merchant_order_id = f'OrderTest{random.randint(1, 100000)}'  # Treba da se generiše jedinstveni ID za svaku transakciju
#     merchant_order_amount = 1050.05  # Konvertovano u string
#     merchant_currency_code = 941  # ISO code for RSD
#     language = 1  # Default language ID (1 = Serbian)
#     email = 'miiihaaas@gmail.com'  # Treba da bude email kupca
#     customer_id = '2'  # Treba da bude ID kupca, ako je dostupan
#     success_url = url_for('transactions.success_url', _external=True)  # Treba da bude stvarna URL adresa za uspešnu transakciju
#     cancel_url = url_for('transactions.cancel_url', _external=True)  # Treba da bude stvarna URL adresa za otkazanu transakciju
#     error_url = url_for('transactions.error_url', _external=True)  # Treba da bude stvarna URL adresa za grešku u transakciji
#     request_type = 11  # Web shop platform
#     timeout = 300  # Default timeout in seconds

#     rnd = generate_random_string()
#     current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     secret_key = 'R1W4tPq30OU'  # Proverite da li je ovo ispravan ključ dobijen od PaySpot sistema
    
#     plaintext = f"{rnd}|{current_date}|{merchant_order_id}|{merchant_order_amount}|{secret_key}"
#     hash_value = calculate_hash(plaintext)
    
#     data = {
#         'companyId': company_id,
#         'merchantOrderID': merchant_order_id,
#         'merchantOrderAmount': merchant_order_amount,
#         'merchantCurrencyCode': merchant_currency_code,
#         'language': language,
#         'email': email,
#         'customerId': customer_id,
#         'successURL': success_url,
#         'cancelURL': cancel_url,
#         'errorURL': error_url,
#         'hash': hash_value,
#         'rnd': rnd,
#         'currentDate': current_date,
#         'requestType': request_type,
#         'timeout': timeout
#     }
    
#     headers = {
#         'Content-Type': 'application/x-www-form-urlencoded',  # Koristimo form-encoded sadržaj
#         'Accept': 'application/json'
#     }

#     data_encoded = urllib.parse.urlencode(data)  # Kodiramo podatke
    
#     try:
#         response = requests.post('https://test.nsgway.rs:50009/api/ecommerce/submit', data=data_encoded, headers=headers)
#         print(f'Status code: {response.status_code}')
#         print(f'Response headers: {response.headers}')
#         response.raise_for_status()
#         print(f'Response content: {response.content}')
#         return response.json()
#     except requests.exceptions.RequestException as e:
#         print(f'An error occurred: {e}')
#         return None






def create_invoice():
    '''
    čuva podaatke u db (faktura i stavke)
    -faktura treba da sadrži:
    -- datum i vreme transakcije
    -- broj fakture (2024-000001, 2024-000002, ...)
    -- customer_id (user, guest)
    
    - stavka treba da sadrži:
    -- farm_id
    -- animal_id + usluge(tov, klanje, obrada, dostava ako je izabrano)
    -- product_id + količina
    -- tov?
    -- usluga? (klanje, obrada, dostava)
    '''
    print('wip: Faktura kreirana')
    # Generisanje broja fakture (primer: 2024-000001)
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    if last_invoice:
        last_invoice_number = int(last_invoice.invoice_number.split('-')[1])
        new_invoice_number = f'{datetime.datetime.now().year}-{last_invoice_number + 1:06d}'
    else:
        new_invoice_number = f'{datetime.datetime.now().year}-000001'
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        print(f'{session=}')
        print(f'wip: Guest user: {session.get("guest_email")=}')
        guest_user = User.query.filter_by(email=session['guest_email']).first()
        user_id = guest_user.id
        
    new_invoice = Invoice(
        datetime=datetime.datetime.now(),
        invoice_number=new_invoice_number,
        user_id=user_id,
        status='unconfirmed'
    )
    db.session.add(new_invoice)
    db.session.commit()
    
    #! Nastavi kod koji će iz session kopre da doda svaku stavku u fakturu
    #! Nastavi kod koji će iz session kopre da doda svaku stavku u fakturu
    #! Nastavi kod koji će iz session kopre da doda svaku stavku u fakturu
    
    for product in session.get('products', []):
        new_invoice_item = InvoiceItems(
            farm_id=product['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=json.dumps(product),
            invoice_item_type=1
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    
    for animal in session.get('animals', []):
        new_invoice_item = InvoiceItems(
            farm_id=animal['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=json.dumps(animal),
            invoice_item_type=2
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    
    for service in session.get('services', []):
        new_invoice_item = InvoiceItems(
            farm_id=service['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=json.dumps(service),
            invoice_item_type=3
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    
    for fattening in session.get('fattening', []):
        new_invoice_item = InvoiceItems(
            farm_id=fattening['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=json.dumps(fattening),
            invoice_item_type=4
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    return new_invoice


def deactivate_animals(invoice_id):
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 2:
            animal_id = json.loads(invoice_item.invoice_item_details)['id']
            animal_to_edit = Animal.query.get(animal_id)
            animal_to_edit.active = False
            db.session.commit()
    # print(f'wip: {session.get("animals", [])=}')
    # for animal in session.get('animals', []):
    #     print(f'wip: deaktivirane kupljene životinje')
    #     print(f'{animal["id"]=}')
    #     animal_to_edit = Animal.query.get(animal['id'])
    #     animal_to_edit.active = False
    #     db.session.commit()
    pass


def deactivate_products(invoice_id):
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 1:
            product_id = json.loads(invoice_item.invoice_item_details)['id']
            product_to_edit = Product.query.get(product_id)
            product_to_edit.quantity = float(product_to_edit.quantity) - float(json.loads(invoice_item.invoice_item_details)['quantity'])
            db.session.commit()
    # for product in session.get('products', []):
    #     print(f'wip: deaktivirane kupljene proizvode')
    #     print(f'{product["id"]=}')
    #     product_to_edit = Product.query.get(product['id'])
    #     product_to_edit.quantity = float(product_to_edit.quantity) - float(product['quantity'])
    #     db.session.commit()
    pass


def send_email(user, form_object):
    '''
    - ako je na rate šalje fiskalni račun (dobija od firme Fiscomm) i sve uplatnice (generiše portal)
    -- fiskalni račnu obugvata ukupnu sumu novca za plaćanje, stim što se odmah sa računa skida suma koja nije za tov (preko PaySpot firma), a ostatak se plaća preko uplatnica (koje generiše portal)
    - ako nije na rate šalje samo fiskalni račun (dobija od firme Fiscomm)
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
    bcc = ['admin@example.com']
    subject = "Potvrda transakcije"
    body = f"Poštovani/a {user.name},\n\nVaša transakcija je uspešno izvršena.\n\nDetalji kupovine:\n{cart_data}\n\nHvala na poverenju!"
    
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    
    # TODO: Implement actual email sending logic here
    # For now, we'll just print the email details
    print('wip: Email poslat')