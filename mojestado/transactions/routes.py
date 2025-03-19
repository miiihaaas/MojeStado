import datetime
import json
import xml.etree.ElementTree as ET
import os
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from mojestado import app, db
from mojestado.main.functions import clear_cart_session, get_cart_total
from mojestado.models import Animal, Debt, Invoice, PaySpotCallback, InvoiceItems, Payment, PaymentStatement, User
from mojestado.transactions.form import GuestForm
from mojestado.transactions.functions import calculate_hash, generate_payment_slips_attach, generate_random_string, provera_validnosti_poziva_na_broj, register_guest_user, create_invoice, send_email, deactivate_animals, deactivate_products


transactions = Blueprint('transactions', __name__)


# @transactions.route('/make_transaction', methods=['GET', 'POST'])
# def make_transaction():
#     '''
#     ovo će se verovatno ugasiti jer će se sve raditi na callback_url-u
#     '''
#     form_object = request.form
#     print(f'*/*/*{form_object=}')
#     if not current_user.is_authenticated:
#         email = request.form.get('email')
#         user = User.query.filter_by(email=email).first()
#         if user and user.user_type != 'guest':
#             flash('Nalog sa ovim mejlom već postoji. Molim Vas ulogujte se.', 'warning')
#             return redirect(url_for('users.login'))
#         # elif user and user.user_type == 'guest':
#         #     print(f'ako ima u db mejl sa tipom guest, onda treba napraviti fakturu i stavke u fakturi')
#         #     create_invoice()
#         #     pass
#     #! ako ima u db mejl sa tipom guest, onda treba napraviti fakturu i stavke u fakturi
#         elif not user:
#             print(f'nema ovaj mejl u db, kreirati usera sa tipom guest i napraviti fakturu i stavke u fakturi')
#             user_id = register_guest_user(form_object)
#             print(f'{user_id=}')
#             user = User.query.get(user_id)
#     else:
#         user = current_user

#     bank_info = form_object.get('bank_info')
#     print(f'{bank_info=}')
    
#     successful_transaction = check_bank_balance()
#     if successful_transaction:
#         create_invoice()
#         send_email(user, form_object)
#         deactivate_animals()
#         deactivate_products()
#         # clear_cart_session()
#         flash('Transakcija je uspešno izvršena', 'success')
#     else:
#         flash('Transakcija nije uspešno izvršena', 'danger')
#         return redirect(url_for('main.view_cart'))
#     return redirect(url_for('main.home'))


@transactions.route('/user_payment_form', methods=['GET', 'POST'])
def user_payment_form():
    """
    Prikazuje i obrađuje formu za unos podataka o kupcu.
    Podržava i registrovane i neregistrovane korisnike.
    
    Returns:
        GET: Renderovan template sa formom
        POST: Redirect na make_order ili login stranicu
        
    Note:
        - Za ulogovane korisnike, forma se automatski popunjava njihovim podacima
        - Za neulogovane korisnike, kreira se gost nalog
        - Ako email već postoji, korisnik se preusmerava na login
    """
    try:
        app.logger.debug('Pristup formi za unos podataka o kupcu')
        form = GuestForm()
        
        if request.method == 'POST':
            if current_user.is_authenticated:
                app.logger.info(f'Ulogovan korisnik {current_user.id} nastavlja ka kreiranju porudžbine')
                return redirect(url_for('transactions.make_order'))
            
            # Validacija forme za neregistrovane korisnike
            if not form.validate_on_submit():
                app.logger.warning('Nevalidna forma za gost korisnika')
                for field, errors in form.errors.items():
                    for error in errors:
                        flash(f'Greška u polju {field}: {error}', 'danger')
                return render_template('transactions/user_payment_form.html', form=form)
            
            # Pokušaj registracije gost korisnika
            try:
                new_user_id = register_guest_user(form.data)
                if new_user_id:
                    app.logger.info(f'Kreiran novi gost korisnik: {new_user_id}')
                    return redirect(url_for('transactions.make_order'))
                else:
                    app.logger.warning('Pokušaj registracije sa postojećim emailom')
                    flash('Email adresa već postoji. Molimo vas da se prijavite.', 'danger')
                    return redirect(url_for('users.login'))
            except Exception as e:
                app.logger.error(f'Greška pri registraciji gost korisnika: {str(e)}')
                flash('Došlo je do greške pri registraciji. Molimo pokušajte ponovo.', 'danger')
                return render_template('transactions/user_payment_form.html', form=form)
        
        # GET zahtev - priprema forme
        if current_user.is_authenticated:
            app.logger.debug(f'Popunjavanje forme podacima ulogovanog korisnika {current_user.id}')
            form.email.data = current_user.email
            form.name.data = current_user.name
            form.surname.data = current_user.surname
            form.phone.data = current_user.phone
            form.address.data = current_user.address
            form.city.data = current_user.city
            form.zip_code.data = current_user.zip_code
        
        return render_template('transactions/user_payment_form.html', form=form)
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška u user_payment_form: {str(e)}')
        flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@transactions.route('/make_order', methods=['GET', 'POST'])
def make_order():
    """
    Kreira novu porudžbinu i priprema podatke za plaćanje.
    
    Returns:
        GET: Renderovan template sa pregledom porudžbine i formom za plaćanje
        
    Note:
        - Podržava i registrovane i gost korisnike
        - Za kupovinu na rate potrebna je registracija
        - Podržava korpu sa životinjama, proizvodima, uslugama tova i drugim uslugama
        - Automatski računa ukupan iznos sa dostavom
        - Generiše hash vrednost za sigurno plaćanje
    """
    try:
        app.logger.debug('Pristup kreiranju porudžbine')
        
        # Provera da li ima stavki u korpi
        animals = session.get('animals', [])
        products = session.get('products', [])
        fattening = session.get('fattening', [])
        services = session.get('services', [])
        
        if not any([animals, products, fattening, services]):
            app.logger.warning('Pokušaj kreiranja prazne porudžbine')
            flash('Vaša korpa je prazna.', 'warning')
            return redirect(url_for('main.home'))
            
        # Provera da li je kupovina na rate
        _, installment_total, _ = get_cart_total()
        if installment_total > 0 and not current_user.is_authenticated:
            app.logger.warning('Gost korisnik pokušao kupovinu na rate')
            flash('Za kupovinu na rate potrebno je da se registrujete.', 'warning')
            return redirect(url_for('users.register'))
            
        # Kreiranje fakture
        try:
            new_invoice = create_invoice()
            app.logger.info(f'Kreirana nova faktura: {new_invoice.id}')
        except Exception as e:
            app.logger.error(f'Greška pri kreiranju fakture: {str(e)}')
            flash('Došlo je do greške pri kreiranju porudžbine. Molimo pokušajte ponovo.', 'danger')
            return redirect(url_for('main.home'))
            
        # Učitavanje korisnika
        try:
            if current_user.is_authenticated:
                user_id = current_user.id
            else:
                guest_email = session.get('guest_email')
                if not guest_email:
                    app.logger.error('Nedostaje email gost korisnika')
                    flash('Došlo je do greške sa vašom sesijom. Molimo prijavite se ponovo.', 'danger')
                    return redirect(url_for('users.login'))
                    
                guest_user = User.query.filter_by(email=guest_email).first()
                if not guest_user:
                    app.logger.error(f'Gost korisnik nije pronađen: {guest_email}')
                    flash('Došlo je do greške sa vašim nalogom. Molimo prijavite se ponovo.', 'danger')
                    return redirect(url_for('users.login'))
                user_id = guest_user.id
                
            user = User.query.get_or_404(user_id)
            app.logger.debug(f'Učitan korisnik: {user_id}')
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju korisnika: {str(e)}')
            flash('Došlo je do greške pri učitavanju vaših podataka. Molimo pokušajte ponovo.', 'danger')
            return redirect(url_for('main.home'))
            
        # Priprema podataka za plaćanje
        try:
            company_id = os.environ.get('PAYSPOT_COMPANY_ID')
            if not company_id:
                raise ValueError('Nedostaje PAYSPOT_COMPANY_ID')
                
            rnd = generate_random_string()
            merchant_order_id = f'MS-{new_invoice.id:09}'
            
            # Računanje ukupnog iznosa
            merchant_order_amount, installment_total, delivery_total = get_cart_total()
            
            # Dodavanje troškova dostave ako je izabrana
            delivery_status = session.get('delivery', {}).get('delivery_status', False)
            if delivery_status:
                merchant_order_amount += delivery_total
                
            app.logger.debug(f'Ukupan iznos za naplatu: {merchant_order_amount}')
            
            # Generisanje hash vrednosti
            current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
            if not secret_key:
                raise ValueError('Nedostaje PAYSPOT_SECRET_KEY')
                
            plaintext = f"{rnd}|{current_date}|{merchant_order_id}|{merchant_order_amount:.2f}|{secret_key}"
            hash_value = calculate_hash(plaintext)
            
            app.logger.debug('Uspešno pripremljeni podaci za plaćanje')
            
            return render_template('transactions/make_order.html',
                                animals=animals,
                                products=products,
                                fattening=fattening,
                                services=services,
                                user=user,
                                company_id=company_id,
                                rnd=rnd,
                                hash_value=hash_value, 
                                merchant_order_id=merchant_order_id, 
                                merchant_order_amount=merchant_order_amount, 
                                current_date=current_date)
                                
        except ValueError as e:
            app.logger.error(f'Nedostaje konfiguracija za plaćanje: {str(e)}')
            flash('Sistem za plaćanje nije ispravno konfigurisan. Molimo kontaktirajte podršku.', 'danger')
            return redirect(url_for('main.home'))
            
    except Exception as e:
        app.logger.error(f'Neočekivana greška u make_order: {str(e)}')
        flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@transactions.route('/callback_url', methods=['POST'])
def callback_url():
    '''
    kada se digne na server PaySpotu treba dati tačan link za callback koji će se koristiti za validaciju na našem server
    koristi ovaj link za instrukcije lokalnog testiranja: https://chatgpt.com/share/03c306c0-724a-4039-bfc7-74b38f6b123e
$uri = "http://127.0.0.1:5000/callback_url"
$body = @{
    "orderID": "MS-000000012",
    "shopID": "80729SE00124301",
    "authNumber": "904284",
    "amount": "50230",
    "currency": "941",
    "transactionID": "8032180729SL4ehgbn396mqp8",
    "result": "00",
    "paySpotOrderID": null,
    "rnd": null,
    "hash": "ZXmXALHw9PFIoMY6znmxp7oIsx+hylPuMQGB3JfYOpyBeOPNlBGWnot4JA/3qQ4/JF+SjrDOoWoeNzg6WwGHbA==",
    "maskedPan": "534223xxxxxx1234",
    "expiryDate": "2512",
    "cardBrand": "MASTERCARD",
    "panAlias": null,
    "merchantPanAlias": null,
    "responseCode": null,
    "responseMsg": null,
    "redemptionCode": null,
}

$response = Invoke-RestMethod -Uri $uri -Method Post -Body ($body | ConvertTo-Json) -ContentType "application/json"
$response
    '''
    try:
        data = request.json
        if not data:
            app.logger.error('Callback_url: Nisu primljeni podaci')
            return jsonify({"error": "No data received"}), 400

        # Izvlačenje osnovnih podataka
        order_id = data.get('orderID')
        invoice_id = int(order_id.split('-')[1])
        shop_id = data.get('shopID')
        amount = data.get('amount')
        result = data.get('result')
        received_hash = data.get('hash')
        
        app.logger.info(f'Primljeni PaySpot callback podaci: OrderID={order_id}, Amount={amount}, Result={result}')

        # Validacija hash-a
        secret_key_callback = os.getenv('PAYSPOT_SECRET_KEY_CALLBACK')
        plantext = f"{order_id}|{shop_id}|{amount}|{result}|{secret_key_callback}"
        calculated_hash_value = calculate_hash(plantext)
        
        if received_hash != calculated_hash_value:
            app.logger.error('Callback_url: Neuspešna hash validacija')
            return jsonify({"error": "Invalid hash"}), 400

        # Započinjemo transakciju
        try:
            # Čuvanje callback podataka
            new_payspot_callback = PaySpotCallback(
                invoice_id=invoice_id,
                amount=amount,
                recived_at=datetime.datetime.now(),
                callback_data=data
            )
            db.session.add(new_payspot_callback)
            
            # Pronalaženje fakture
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                db.session.rollback()
                app.logger.error(f'Callback_url: Faktura {invoice_id} nije pronađena')
                return jsonify({"error": "Invoice not found"}), 404

            user = User.query.get(invoice.user_id)
            
            # Obrada različitih rezultata transakcije
            if result == '00':  # Uspešna transakcija
                invoice.status = 'paid'
                db.session.flush()  # Flush pre deaktivacije
                
                try:
                    # Dodatne akcije za uspešnu transakciju
                    deactivate_animals(invoice_id)
                    deactivate_products(invoice_id)
                    
                    # Commit pre slanja email-a
                    db.session.commit()
                    
                    # Slanje email-a nakon commit-a
                    send_email(user, invoice_id)
                    
                    app.logger.info(f'Uspešna transakcija za fakturu {invoice_id}')
                except Exception as e:
                    app.logger.error(f'Greška pri obradi uspešne transakcije: {str(e)}')
                    db.session.rollback()
                    return jsonify({"error": "Transaction processing error"}), 500
                
                return jsonify({"status": "success"}), 200
                
            elif result == '01':  # Otkazana transakcija
                invoice.status = 'cancelled'
                db.session.commit()
                app.logger.info(f'Otkazana transakcija za fakturu {invoice_id}')
                return jsonify({"status": "cancelled"}), 200
                
            else:  # Greška u transakciji
                invoice.status = 'error'
                error_message = data.get('responseMsg', 'Nepoznata greška')
                
                error_details = {
                    'invoice_id': invoice_id,
                    'user_email': user.email if user else 'Unknown',
                    'error_code': result,
                    'error_message': error_message,
                    'transaction_id': data.get('transactionID')
                }
                app.logger.error(f'Greška u transakciji: {error_details}')
                
                db.session.commit()
                return jsonify({"status": "error", "message": error_message}), 400

        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Greška u transakciji: {str(e)}', exc_info=True)
            return jsonify({"error": "Transaction error"}), 500

    except Exception as e:
        app.logger.error(f'Neočekivana greška u callback_url: {str(e)}', exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@transactions.route('/callback_local_test', methods=['GET', 'POST'])
def callback_local_test():
    print(f'callback_local_test: {request.form=}')  # Promena: koristimo request.form umesto request.args
    invoice_id = int(request.form.get('merchantOrderID').split('-')[1])
    amount = float(request.form.get('merchantOrderAmount'))
    data = {
        'test': 'test'
    }
    new_payspot_callback = PaySpotCallback(invoice_id=invoice_id,
                                        amount=amount,
                                        recived_at=datetime.datetime.now(),
                                        callback_data=data)
    print(f'** {new_payspot_callback=}')
    db.session.add(new_payspot_callback)
    print(f'** {invoice_id=}')
    invoice = Invoice.query.get(invoice_id)
    invoice.status = 'paid'

    db.session.commit()

    user_id = invoice.user_id
    user = User.query.get(user_id)


    deactivate_animals(invoice_id)
    deactivate_products(invoice_id)
    send_email(user, invoice_id)
    # clear_cart_session()
    return redirect(url_for('main.view_cart'))


@transactions.route('/success_url', methods=['GET'])
def success_url():
    flash('Uspešna transakcija', 'success')
    # return redirect(url_for('main.home'))
    return redirect(url_for('main.clear_cart'))


@transactions.route('/cancel_url', methods=['GET', 'POST'])
def cancel_url():
    flash('Transakcija otkazana', 'danger')
    return redirect(url_for('main.view_cart'))


@transactions.route('/error_url', methods=['GET', 'POST'])
def error_url():
    flash('Došlo je do greške prilikom obrade transakcije. Molimo vas pokušajte ponovo ili kontaktirajte podršku.', 'danger')
    return redirect(url_for('main.view_cart'))


@transactions.route('/process_payment_statment', methods=['POST'])
@login_required
def process_payment_statment():
    """
    Obrađuje XML fajl bankovnog izvoda i kreira odgovarajuće zapise u bazi.
    Zahteva admin privilegije.
    
    Returns:
        POST (importButton): Renderovan template sa pregledom učitanog izvoda
        POST (saveAndProcessButton): Redirect na admin_view_slips nakon obrade
        
    Note:
        - Podržava dva tipa akcija: učitavanje XML fajla i čuvanje podataka
        - Proverava da li izvod već postoji u bazi
        - Validira pozive na broj i beleži greške u obradi
    """
    if current_user.user_type != 'admin':
        flash('Pristup nije dozvoljen. Potrebne su admin privilegije.', 'danger')
        return redirect(url_for('main.home'))
        
    if request.method == 'POST' and ('importButton' in request.form):
        # Učitavanje i validacija XML fajla
        file = request.files['fileUpload']
        if file.filename == '':
            flash('Nije izabran XML fajl.', 'danger')
            return render_template('transactions/admin_view_slips.html', title='Izvodi')
            
        # Parsiranje XML fajla
        tree = ET.parse(file)
        root = tree.getroot()
        
        # Učitavanje zaglavlja izvoda
        zaglavlje_element = root.find('.//Zaglavlje')
        if zaglavlje_element is not None:
            datum_izvoda_element = zaglavlje_element.attrib.get('DatumIzvoda')
            broj_izvoda_element = zaglavlje_element.attrib.get('BrojIzvoda')
            iznos_potrazuje_element = zaglavlje_element.attrib.get('PotrazniPromet')
        else:
            flash("Greška prilikom čitanja zaglavlja XML fajla.", "danger")
            return redirect(url_for('users.admin_view_slips'))
            
        # Učitavanje stavki izvoda
        broj_pojavljivanja = len(root.findall('.//Stavke'))
        stavke = []
        
        for stavka in root.findall('Stavke'):
            podaci = {
                'RacunZaduzenja': stavka.attrib.get('BrojRacunaPrimaocaPosiljaoca'),
                'NazivZaduzenja': stavka.attrib.get('NalogKorisnik'),
                'Iznos': stavka.attrib.get('Potrazuje'),
                'SvrhaDoznake': stavka.attrib.get('Opis'),
                'PozivNaBrojApp': stavka.attrib.get('PozivNaBrojKorisnika')
            }
            
            provera_validnosti_poziva_na_broj(podaci)
            stavke.append(podaci)
            
        flash('Uspešno učitan XML fajl.', 'success')
        return render_template('transactions/admin_view_slips.html', 
                            title='Izvodi',
                            broj_izvoda_element=broj_izvoda_element,
                            datum_izvoda_element=datum_izvoda_element,
                            iznos_potrazuje_element=iznos_potrazuje_element,
                            broj_pojavljivanja=broj_pojavljivanja,
                            stavke=stavke)
                            
    if request.method == 'POST' and ('saveAndProcessButton' in request.form):
        # Učitavanje podataka iz forme
        statement_number = int(request.form['statement_number'])
        payment_date = datetime.datetime.strptime(request.form['payment_date'], '%d.%m.%Y')
        total_payment_amount = float(request.form['total_payment_amount'].replace(',', '.'))
        number_of_items = int(request.form['number_of_items'])
        
        # Provera da li izvod već postoji
        existing_payment_statement = PaymentStatement.query.filter_by(
            payment_date=payment_date, 
            statement_number=statement_number
        ).first()
        
        if existing_payment_statement:
            flash(f'Uplata za dati datum ({payment_date}) i broj računa ({statement_number}) već postoji u bazi.', 'danger')
            return redirect(url_for('users.admin_view_slips'))
            
        # Kreiranje novog izvoda
        new_payment_statement = PaymentStatement(
            payment_date=payment_date,
            statement_number=statement_number,
            total_payment_amount=total_payment_amount,
            number_of_items=number_of_items,
            number_of_errors=0
        )
        db.session.add(new_payment_statement)
        db.session.commit()
        
        # Učitavanje podataka o uplatama
        uplatioci = request.form.getlist('uplatilac')
        iznosi = request.form.getlist('iznos')
        pozivi_na_broj = request.form.getlist('poziv_na_broj')
        svrha_uplate = request.form.getlist('svrha_uplate')
        
        # Priprema podataka za obradu
        records = []
        for i in range(len(iznosi)):
            records.append({
                'uplatilac': uplatioci[i],
                'iznos': iznosi[i],
                'poziv_na_broj': pozivi_na_broj[i],
                'svrha_uplate': svrha_uplate[i],
                'payment_statement_id': new_payment_statement.id
            })
            
        # Obrada uplata i validacija
        number_of_errors = 0
        user_ids = [str(user.id).zfill(5) for user in User.query.filter_by(user_type='user').all()]
        invoice_items_ids = [str(invoice_item.id).zfill(6) 
                            for invoice_item in InvoiceItems.query.filter_by(invoice_item_type=4).all()]
        
        for record in records:
            user_id = record['poziv_na_broj'][:5]
            invoice_item_id = (record['poziv_na_broj'].split('-')[1] 
                                if '-' in record['poziv_na_broj'] 
                                else record['poziv_na_broj'][5:])
            amount = float(record['iznos'].replace(',', '.'))
            
            payment_error = False
            if (user_id not in user_ids) or (invoice_item_id not in invoice_items_ids):
                user_id = 1
                invoice_item_id = 0
                payment_error = True
                number_of_errors += 1
                
            new_payment = Payment(
                amount=amount,
                user_id=user_id,
                invoice_item_id=invoice_item_id,
                payment_statement_id=new_payment_statement.id,
                purpose=record['svrha_uplate'],
                payer=record['uplatilac'],
                reference_number=record['poziv_na_broj'],
                payment_error=payment_error
            )
            db.session.add(new_payment)
            
        # Ažuriranje broja grešaka i čuvanje promena
        new_payment_statement.number_of_errors = number_of_errors
        db.session.commit()
        
        flash('Uspešno proknjižene uplate.', 'success')
        payment_statements = PaymentStatement.query.all()
        return render_template('transactions/admin_view_slips.html', payment_statements=payment_statements)

    payment_statements = PaymentStatement.query.all()
    return render_template('transactions/admin_view_slips.html', payment_statements=payment_statements)


@transactions.route("/edit_payment_statement/<int:payment_statement_id>", methods=['GET', 'POST'])
@login_required
def edit_payment_statement(payment_statement_id):
    """
    Prikazuje formu za izmenu izvoda i pripadajućih uplata.
    Zahteva admin privilegije.
    
    Args:
        payment_statement_id: ID izvoda koji se menja
        
    Returns:
        GET: Renderovan template sa formom za izmenu
        
    Note:
        - Učitava podatke o izvodu, uplatama, korisnicima i stavkama faktura
        - Priprema podatke za JavaScript obradu na frontendu
        - Podržava ignorisane uplate (user_id=0)
    """
    if current_user.user_type != 'admin':
        flash('Pristup nije dozvoljen. Potrebne su admin privilegije.', 'danger')
        return redirect(url_for('main.home'))
        
    # Učitavanje izvoda i uplata
    payment_statement = PaymentStatement.query.get_or_404(payment_statement_id)
    payments = Payment.query.filter_by(payment_statement_id=payment_statement_id).all()
    
    # Priprema podataka o korisnicima
    users = User.query.filter_by(user_type='user').all()
    users_data = [
        {
            'user_id': 0,
            'user_name': 'Ignorisana',
            'user_surname': 'uplata'
        }
    ]
    
    for user in users:
        users_data.append({
            'user_id': user.id,
            'user_name': user.name,
            'user_surname': user.surname
        })
        
    # Priprema podataka o stavkama faktura
    invoice_items = InvoiceItems.query.filter_by(invoice_item_type=4).all()
    invoice_items_data = [
        {
            'invoice_item_id': 0,
            'invoice_item_animal': '',
            'invoice_item_farm': ''
        }
    ]
    invoice_item_ids = []
    
    for invoice_item in invoice_items:
        invoice_items_data.append({
            'invoice_item_id': invoice_item.id,
            'invoice_item_animal': invoice_item.invoice_item_details['category'],
            'invoice_item_farm': invoice_item.invoice_item_details['farm']
        })
        invoice_item_ids.append(invoice_item.id)
        
    return render_template('transactions/edit_payment_statement.html', 
                            payment_statement=payment_statement,
                            payments=payments,
                            users=json.dumps(users_data),
                            invoice_items=json.dumps(invoice_items_data),
                            invoice_item_ids=invoice_item_ids)


@transactions.route("/submit_records", methods=['POST'])
@login_required
def submit_records():
    """
    Obrađuje izmene u postojećem izvodu i ažurira uplate.
    Zahteva admin privilegije.
    
    Returns:
        POST: ID obrađenog izvoda
        
    Note:
        - Prima JSON podatke sa izmenama uplata
        - Validira reference brojeve sa postojećim dugovima
        - Ažurira status grešaka za svaku uplatu
        - Ažurira ukupan broj grešaka u izvodu
    """
    if current_user.user_type != 'admin':
        flash('Pristup nije dozvoljen. Potrebne su admin privilegije.', 'danger')
        return redirect(url_for('main.home'))
        
    # Učitavanje podataka iz zahteva
    data = request.get_json()
    payment_statement_id = data['payment_statement_id']
    
    # Učitavanje postojećih uplata i dugova
    payments = Payment.query.filter_by(payment_statement_id=payment_statement_id).all()
    debts = Debt.query.all()
    
    # Priprema validnih referenci brojeva
    all_reference_numbers = [
        f'{debt.user_id:05d}-{debt.invoice_item_id:06d}' 
        for debt in debts
    ]
    all_reference_numbers.append('00001-000000')
    
    # Priprema validnih ID-jeva
    user_ids = [user.id for user in User.query.filter_by(user_type='user').all()]
    invoice_items_ids = [
        invoice_item.id 
        for invoice_item in InvoiceItems.query.filter_by(invoice_item_type=4).all()
    ]
    
    # Obrada svake izmene
    number_of_errors = 0
    for record in data['records']:
        record_id = record['record_id']
        user_id = record['user_id']
        invoice_item_id = record['invoice_item_id']
        
        # Validacija ID-jeva
        if (user_id not in user_ids) or (invoice_item_id not in invoice_items_ids):
            user_id = 1
            invoice_item_id = 0
            
        # Ažuriranje uplate
        edit_payment = Payment.query.get(record_id)
        edit_payment.user_id = user_id
        edit_payment.invoice_item_id = invoice_item_id
        
        # Provera reference broja
        reference_number = f'{user_id:05d}-{invoice_item_id:06d}'
        if reference_number == '00001-000000':
            number_of_errors += 1
            edit_payment.payment_error = True
        elif reference_number in all_reference_numbers:
            edit_payment.payment_error = False
        else:
            number_of_errors += 1
            edit_payment.payment_error = True
            
        db.session.commit()
        
    # Ažuriranje broja grešaka u izvodu
    payment_statement = PaymentStatement.query.get(payment_statement_id)
    payment_statement.number_of_errors = number_of_errors
    db.session.commit()
    
    flash(f'Uspešno su sačuvane izmene u uplati broj: {payment_statement.statement_number}, od datuma {payment_statement.payment_date.strftime("%d.%m.%Y.")}', 'success')

    return str(payment_statement_id)


@transactions.route('/generate_payment_slips/<int:payment_statement_id>', methods=['GET', 'POST'])
def generate_payment_slips(payment_statement_id):
    """
    Generiše PDF uplatnicu za zadati izvod i vraća URL do generisanog fajla.
    
    Args:
        payment_statement_id: ID izvoda za koji se generiše uplatnica
        
    Returns:
        GET/POST: Redirect na URL generisanog PDF fajla
        
    Note:
        - Generiše PDF uplatnicu koristeći generate_payment_slips_attach funkciju
        - Čuva PDF u static/payment_slips direktorijumu
        - Vraća public URL do generisanog fajla
    """
    # Učitavanje stavke fakture
    invoice_item = InvoiceItems.query.get_or_404(payment_statement_id)
    
    # Generisanje PDF uplatnice
    full_file_path = generate_payment_slips_attach(invoice_item)
    filename = os.path.basename(full_file_path)
    
    # Kreiranje URL-a za pristup fajlu
    file_url = url_for('static', 
                        filename=f'payment_slips/{filename}', 
                        _external=True)
    
    flash('Generisana uplatnica', 'success')
    return redirect(file_url)