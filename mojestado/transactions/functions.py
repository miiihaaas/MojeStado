import base64, hashlib
import datetime, os
import random, string

from mojestado import db, mail
from mojestado.models import Animal, Invoice, InvoiceItems, Product, User

from flask import flash, json, redirect, render_template, session, url_for
from flask_login import current_user
from flask_mail import Message

from fpdf import FPDF


def generate_payment_slips_attach(fattening_list):
    '''
    generiše 2+ uplatnice na jednom dokumentu (A4) u fpdf, qr kod/api iz nbs
    '''
    print('generisane uplatnice na jednom dokumentu (A4). dokument će biti attachovan u email')
    pass


def generate_invoice_attach(invoice_id):
    '''
    generiše fakturu. dokument će biti attachovan u emali.
    '''
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    invoice = Invoice.query.get(invoice_id)
    
    filename = f'{invoice.invoice_number}.pdf'
    
    products = [invoice_item for invoice_item in invoice_items if invoice_item.invoice_item_type == 1]
    animals = [invoice_item for invoice_item in invoice_items if invoice_item.invoice_item_type == 2]
    services = [invoice_item for invoice_item in invoice_items if invoice_item.invoice_item_type == 3]
    fattening = [invoice_item for invoice_item in invoice_items if invoice_item.invoice_item_type == 4]
    
    #! generisi fakturu uz pomoć fpdf
    current_file_path = os.path.abspath(__file__)
    project_folder = os.path.dirname(os.path.dirname((current_file_path)))
    font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
    font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')
    class PDF(FPDF):
        def __init__(self, **kwargs):
            super(PDF, self).__init__(**kwargs)
            self.add_font('DejaVuSansCondensed', '', font_path, uni=True)
            self.add_font('DejaVuSansCondensed', 'B', font_path_B, uni=True)
        def header(self):
            self.set_font('DejaVuSansCondensed', 'B', 16)
            self.cell(0, 10, f'Faktura {invoice.invoice_number}', new_y='NEXT', align='C')
    
    pdf = PDF()
    pdf.add_page()
    #! proizvodi
    pdf.cell(30, 10, f'Kategorija', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Potkategorija', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Sektor', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Naziv', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Količina', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Jedinica mere', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Cena po jedinici mere', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Cena po kg', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Ukupna cena', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'PG', new_y='LAST', align='L', border=1)
    pdf.cell(30, 10, f'Lokacija', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
    for product in products:
        pdf.cell(30, 10, f'{product["category"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["subcategory"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["section"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["product_name"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["quantity"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["unit_of_measurement"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["product_price_per_unit"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["product_price_per_kg"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["total_price"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["farm"]}', new_y='LAST', align='L', border=1)
        pdf.cell(30, 10, f'{product["location"]}', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
    
    #! živa vaga
    #! usluge
    #! tov (samo koji NIJE na rate?)
    
    path = os.path.join(project_folder, 'static', 'invoices')
    if not os.path.exists(path):
        os.mkdir(path)
    pdf.output(os.path.join(path, filename))
    return os.path.join(path, filename)


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
                phone=form_object.get('phone'),
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


def deactivate_products(invoice_id):
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 1:
            product_id = json.loads(invoice_item.invoice_item_details)['id']
            product_to_edit = Product.query.get(product_id)
            product_to_edit.quantity = float(product_to_edit.quantity) - float(json.loads(invoice_item.invoice_item_details)['quantity'])
            db.session.commit()


def send_email(user, invoice_id):
    '''
    - ako je na rate šalje fiskalni račun (dobija od firme Fiscomm) i sve uplatnice (generiše portal)
    -- fiskalni račnu obugvata ukupnu sumu novca za plaćanje, stim što se odmah sa računa skida suma koja nije za tov (preko PaySpot firma), a ostatak se plaća preko uplatnica (koje generiše portal)
    - ako nije na rate šalje samo fiskalni račun (dobija od firme Fiscomm)
    '''
    
    #! proveravam da li je na rate
    #! invoice_items čiji je type = 4 (fattening)
    
    payment_slips = [] #! ako je prazna lista onda NIJE na rate
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 4:
            fattening = json.loads(invoice_item.invoice_item_details)
            if fattening['installment_options'] > 1:
                print('wip: ova usluga je na rate')
                new_payment_slip = generate_payment_slips_attach(fattening)
                payment_slips.append(new_payment_slip) #! ako lista NIJE prazna onda je na rate
    print(f'{payment_slips=}')
    
    invoice_attach = generate_invoice_attach(invoice_id)

    to = [user.email]
    bcc = ['admin@example.com']
    subject = "Potvrda kupovine"
    if payment_slips:
        body = f"Poštovani/a {user.name},\n\nVaša kupovina je uspešno izvršena.\n\nDetalji kupovine i uplatnice možete da vidite u prilogu.\n\nHvala na poverenju!"
        message = Message(subject=subject, sender='Wqo2M@example.com', recipients=to, bcc=bcc, attachments=[invoice_attach] + payment_slips)
    else:
        body = f"Poštovani/a {user.name},\n\nVaša kupovina je uspešno izvršena.\n\nDetalje kupovine možete da vidite u prilogu.\n\nHvala na poverenju!"
        message = Message(subject=subject, sender='Wqo2M@example.com', recipients=to, bcc=bcc, attachments=[invoice_attach])
    
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    
    # TODO: Implement actual email sending logic here
    # For now, we'll just print the email details
    message.html = body
    
    try:
        mail.send(message)
        print('wip: Email poslat')
    except Exception as e:
        print(f'Error sending email: {e}')
    