import datetime
import json
import xml.etree.ElementTree as ET
import os
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user
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
    # new_invoice = create_invoice()
    form = GuestForm()
        
    if request.method == 'POST':
        if current_user.is_authenticated:
            print(f'{current_user=} je ulogovoan, nastavi kreiranje porudžbenice')
            return redirect(url_for('transactions.make_order'))
        else:
            form_object = request.form
            new_user_id = register_guest_user(form_object)
            print(f'{new_user_id=}')
        if new_user_id:
            print(f'novi korisnik je kreiran : {new_user_id=}, nastavi kreiranje porudžbenice')
            return redirect(url_for('transactions.make_order'))
        else:
            flash ('Email adresa već postoji', 'danger')
            return redirect(url_for('users.login'))
    if current_user.is_authenticated:
        form.email.data = current_user.email
        form.name.data = current_user.name
        form.surname.data = current_user.surname
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        form.city.data = current_user.city
        form.zip_code.data = current_user.zip_code
    
    
    
    
    return render_template('user_payment_form.html',
                            form=form,
                            )
                            # company_id=company_id,
                            # rnd=rnd,
                            # hash_value=hash_value, 
                            # merchant_order_id=merchant_order_id, 
                            # merchant_order_amount=merchant_order_amount, 
                            # current_date=current_date)


@transactions.route('/make_order', methods=['GET', 'POST'])
def make_order():
    animals = session.get('animals', [])
    products = session.get('products', [])
    fattening = session.get('fattening', [])
    services = session.get('services', [])
    
    new_invoice = create_invoice()
    print(f'{new_invoice=}')
    
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        guest_user = User.query.filter_by(email=session['guest_email']).first()
        user_id = guest_user.id
    user = User.query.get(user_id)
    
    
    
    company_id = os.environ.get('PAYSPOT_COMPANY_ID')
    rnd = generate_random_string()
    merchant_order_id = f'MS-{new_invoice.id:09}'  # Treba da se generiše jedinstveni ID za svaku transakciju
    merchant_order_amount, installment_total, delivery_total = get_cart_total()
    print(f'*** {session["delivery"]["delivery_status"]=}')
    if session['delivery']['delivery_status'] == True:
        merchant_order_amount = merchant_order_amount + delivery_total
    print(f'{merchant_order_amount=}')
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
    
    plaintext = f"{rnd}|{current_date}|{merchant_order_id}|{merchant_order_amount:.2f}|{secret_key}"
    hash_value = calculate_hash(plaintext)
    
    print(f'* view_chart: {rnd=}')
    print(f'* view_chart: {hash_value=}')
    return render_template('make_order.html',
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

        # Čišćenje korpe pre bilo kakvih izmena u bazi
        try:
            if clear_cart_session():  # Ovo čišće sve ključeve korpe
                app.logger.info('Korpa uspešno očišćena pre transakcije')
            else:
                app.logger.warning('Nije uspelo čišćenje korpe pre transakcije')
        except Exception as e:
            app.logger.error(f'Greška pri čišćenju sesije: {str(e)}')
            # Nastavljamo sa izvršavanjem jer greška u čišćenju sesije nije kritična

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
    return redirect(url_for('main.home'))


@transactions.route('/cancel_url', methods=['GET', 'POST'])
def cancel_url():
    flash('Transakcija otkazana', 'danger')
    return redirect(url_for('main.view_cart'))


@transactions.route('/error_url', methods=['GET', 'POST'])
def error_url():
    flash('Došlo je do greške prilikom obrade transakcije. Molimo vas pokušajte ponovo ili kontaktirajte podršku.', 'danger')
    return redirect(url_for('main.view_cart'))


@transactions.route('/process_payment_statment', methods=['POST'])
def process_payment_statment():
    print(f'** *{request.form=}')
    if request.method == 'POST' and ('importButton' in request.form):
        file = request.files['fileUpload']
        if file.filename == '':
            error_message = 'Nije izabran CML fajl.'
            print(error_message)
            flash(error_message, 'danger')
            return render_template('admin_view_slips.html', title='Izvodi')
        tree = ET.parse(file)
        root = tree.getroot()
        
        # Pristupanje atributima u elementu 'Zaglavlje'
        zaglavlje_element = root.find('.//Zaglavlje')
        if zaglavlje_element is not None:
            datum_izvoda_element = zaglavlje_element.attrib.get('DatumIzvoda')
            broj_izvoda_element = zaglavlje_element.attrib.get('BrojIzvoda')
            iznos_potrazuje_element = zaglavlje_element.attrib.get('PotrazniPromet')
        else:
            flash("Greška prilikom čitanja zaglavlja XML fajla.", "danger")
            return redirect(url_for('users.admin_view_slips'))
        # Pronalaženje broja pojavljivanja elementa <Stavka>
        broj_pojavljivanja = len(root.findall('.//Stavke'))
        print(f'** {broj_pojavljivanja=}')
        
        #todo: implementacija provere da li je učitani izvod već u bazi
        
        stavke = []
        for stavka in root.findall('Stavke'):
            podaci = {}
            podaci['RacunZaduzenja'] = stavka.attrib.get('BrojRacunaPrimaocaPosiljaoca') #! onaj ko plaća
            podaci['NazivZaduzenja'] = stavka.attrib.get('NalogKorisnik') #! ime onog ko plaća
            # podaci['MestoZaduzenja'] = stavka.find('MestoZaduzenja').text #? izgleda da ne treba
            # podaci['IzvorInformacije'] = stavka.find('IzvorInformacije').text #? izgleda da ne treba
            # podaci['ModelPozivaZaduzenja'] = stavka.find('ModelPozivaZaduzenja').text #? izgleda da ne treba
            # podaci['PozivZaduzenja'] = stavka.find('PozivZaduzenja').text #? izgleda da ne treba
            # podaci['SifraPlacanja'] = stavka.find('SifraPlacanja').text #? izgleda da ne treba
            podaci['Iznos'] = stavka.attrib.get('Potrazuje')
            # podaci['RacunOdobrenja'] = stavka.find('RacunOdobrenja').text #! onom kome se plaća ||| izgleda da ne treba
            # podaci['NazivOdobrenja'] = stavka.find('NazivOdobrenja').text #? izgleda da ne treba
            # podaci['MestoOdobrenja'] = stavka.find('MestoOdobrenja').text #? izgleda da ne treba
            # podaci['ModelPozivaOdobrenja'] = stavka.find('ModelPozivaOdobrenja').text #? izgleda da ne treba
            # podaci['PozivOdobrenja'] = stavka.find('PozivOdobrenja').text if stavka.find('PozivOdobrenja').text else "-" #! ako nije None onda preuzmi vrednost iz xml, akoj je None onda mu dodeli "-"
            podaci['SvrhaDoznake'] = stavka.attrib.get('Opis') #! ovo je svrha uplate:  isti princip kao gornji red 
            #! jedno od ova dva je svrha uplate: podaci['SvrhaDoznake'] = stavka.attrib.get('Opis') #! ovo je svrha uplate:  isti princip kao gornji red 
            podaci['PozivNaBrojApp'] = stavka.attrib.get('PozivNaBrojKorisnika')
            # podaci['DatumValute'] = stavka.find('DatumValute').text #? izgleda da ne treba
            # podaci['PodatakZaReklamaciju'] = stavka.find('PodatakZaReklamaciju').text #? izgleda da ne treba
            # podaci['VremeUnosa'] = stavka.find('VremeUnosa').text #? izgleda da ne treba
            # podaci['VremeIzvrsenja'] = stavka.find('VremeIzvrsenja').text #? izgleda da ne treba
            # podaci['StatusNaloga'] = stavka.find('StatusNaloga').text #? izgleda da ne treba
            # podaci['TipSloga'] = stavka.find('TipSloga').text #? izgleda da ne treba
            
            provera_validnosti_poziva_na_broj(podaci)
            
            stavke.append(podaci)
        
        print(f'ako je uvezi izvod: vraćaj na istu stranu')
        flash(f'Uspešno učitan XML fajl.', 'success')
        return render_template('admin_view_slips.html', 
                                title='Izvodi',
                                broj_izvoda_element=broj_izvoda_element,
                                datum_izvoda_element=datum_izvoda_element,
                                iznos_potrazuje_element=iznos_potrazuje_element,
                                broj_pojavljivanja=broj_pojavljivanja,
                                stavke=stavke)
    if request.method == 'POST' and ('saveAndProcessButton' in request.form):
        print(f'ako je sačuvaj i rasknjiži: ----')
        print(f'{request.form=}')
        statement_number = int(request.form['statement_number'])
        payment_date = datetime.datetime.strptime(request.form['payment_date'], '%d.%m.%Y')
        total_payment_amount = float(request.form['total_payment_amount'].replace(',', '.'))
        number_of_items = int(request.form['number_of_items'])
        print(f'** {statement_number=}; {payment_date=}')
        existing_payment_statement = PaymentStatement.query.filter_by(payment_date=payment_date, 
                                                                        statement_number=statement_number).first()
        if existing_payment_statement:
            error_message = f'Uplata za dati datum ({payment_date}) i broj računa ({statement_number}) već postoji u bazi. Izaberite novi XML fajl i pokušajte ponovo.'
            flash(error_message, 'danger')
            return redirect(url_for('users.admin_view_slips'))
        new_payment_statement = PaymentStatement(payment_date=payment_date,
                                                statement_number=statement_number,
                                                total_payment_amount=total_payment_amount,
                                                number_of_items=number_of_items,
                                                number_of_errors=0)
        db.session.add(new_payment_statement)
        db.session.commit()
        #TODO: dodati u tabelu pyments svaku stavku
        uplatioci = request.form.getlist('uplatilac')
        iznosi = request.form.getlist('iznos')
        pozivi_na_broj = request.form.getlist('poziv_na_broj')
        svrha_uplate = request.form.getlist('svrha_uplate')
        
        records = []
        for i in range(len(iznosi)):
            records.append({
                'uplatilac': uplatioci[i],
                'iznos': iznosi[i],
                'poziv_na_broj': pozivi_na_broj[i],
                'svrha_uplate': svrha_uplate[i],
                'payment_statement_id': new_payment_statement.id
            })
        number_of_errors = 0
        user_ids = [str(user.id).zfill(4) for user in User.query.filter_by(user_type='user').all()]
        invoice_items_ids = [str(invoice_item.id).zfill(4) for invoice_item in InvoiceItems.query.filter_by(invoice_item_type=4).all()]
        for record in records:
            user_id = record['poziv_na_broj'][-4:] #! provali ovde koji deo iz poziva na broj je user_id
            invoice_item_id = record['poziv_na_broj'][:4] #! provali ovde koji deo iz poziva na broj je invoice_item_id
            amaunt = float(record['iznos'].replace(',', '.'))
            payment_error = False
            if (user_id not in user_ids) or (invoice_item_id not in invoice_items_ids):
                user_id = 1
                invoice_item_id = 0
                payment_error = True
                number_of_errors += 1
            new_payment = Payment(amount=amaunt,
                                user_id=user_id,
                                invoice_item_id=invoice_item_id,
                                payment_statement_id=new_payment_statement.id,
                                purpose_of_payment=record['svrha_uplate'],
                                payer=record['uplatilac'],
                                reference_number=record['poziv_na_broj'],
                                payment_error=payment_error)
            db.session.add(new_payment)
            db.session.commit()
        new_payment_statement.number_of_errors = number_of_errors
        db.session.commit()
        flash(f'Uspešno ste uvezli izvod broj: {new_payment_statement.statement_number}), od datuma {new_payment_statement.payment_date.strftime("%d.%m.%Y.")}', 'success')
        return redirect(url_for('users.admin_view_slips'))
    payment_statements = PaymentStatement.query.all()
    print(f'{payment_statements=}')

    return render_template('admin_view_slips.html', payment_statments=payment_statements)

@transactions.route("/edit_payment_statement/<int:payment_statement_id>", methods=['GET', 'POST'])
def edit_payment_statement(payment_statement_id):
    payment_statement = PaymentStatement.query.get_or_404(payment_statement_id)
    payments = Payment.query.filter_by(payment_statement_id=payment_statement_id).all()
    users = User.query.filter_by(user_type='user').all()
    users_data = [
        {
            'user_id': 0,
            'user_name': 'Ignorisana',
            'user_surname': 'uplata'
        }
    ]
    for user in users:
        user_data = {
            'user_id': user.id,
            'user_name': user.name,
            'user_surname': user.surname
        }
        users_data.append(user_data)
    print(f'** {users_data=}')
    invoice_items = InvoiceItems.query.filter_by(invoice_item_type=4).all()
    invoice_item_ids = []
    invoice_items_data = [
        {
            'invoice_item_id': 0,
            'invoice_item_animal': '',
            'invoice_item_farm': ''
        }
    ]
    for invoice_item in invoice_items:
        invoice_item_data = {
            'invoice_item_id': invoice_item.id,
            'invoice_item_animal': invoice_item.invoice_item_details['category'],
            'invoice_item_farm': invoice_item.invoice_item_details['farm']
            # 'invoice_item_animal': json.loads(invoice_item.invoice_item_details)['category'],
            # 'invoice_item_farm': json.loads(invoice_item.invoice_item_details)['farm']
        }
        invoice_items_data.append(invoice_item_data)
        invoice_item_ids.append(invoice_item.id)
    print(f'** {invoice_items_data=}')
    return render_template('edit_payment_statement.html', 
                            payment_statement=payment_statement,
                            payments=payments,
                            users=json.dumps(users_data),
                            invoice_items=json.dumps(invoice_items_data),
                            invoice_item_ids=invoice_item_ids)


@transactions.route("/submit_records", methods=['POST'])
def submit_records():
    data = request.get_json()
    print(f'{data=}')
    print('izmena postojećeg izvoda')
    payment_statement_id=data['payment_statement_id']
    payments = Payment.query.filter_by(payment_statement_id=payment_statement_id).all()
    debts = Debt.query.all()
    all_reference_numbers = [f'{debt.user_id:05d}-{debt.invoice_item_id:06d}' for debt in debts]
    all_reference_numbers.append('00001-000000')
    print(f'{all_reference_numbers=}')
    
    number_of_errors = 0
    user_ids = [user.id for user in User.query.filter_by(user_type='user').all()]
    invoice_items_ids = [invoice_item.id for invoice_item in InvoiceItems.query.filter_by(invoice_item_type=4).all()]
    print(f'{user_ids=}')
    print(f'{invoice_items_ids=}')
    for i in range(len(data['records'])):
        record_id = data['records'][i]['record_id']
        user_id = data['records'][i]['user_id']
        invoice_item_id = data['records'][i]['invoice_item_id']
        print(f'{record_id=}, {user_id=}, {invoice_item_id=}')
        if (user_id not in user_ids) or (invoice_item_id not in invoice_items_ids):
            print(f'**** debug, nema u listama user_ids i invoice_items_ids, {user_id=} vs {user_ids}, {invoice_item_id=} vs {invoice_items_ids}')
            user_id = 1
            invoice_item_id = 0
        edit_payment = Payment.query.get(record_id)
        edit_payment.user_id = user_id
        edit_payment.invoice_item_id = invoice_item_id
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
    payment_statement = PaymentStatement.query.get(payment_statement_id)
    payment_statement.number_of_errors = number_of_errors
    db.session.commit()
    flash(f'Uspešno su sačuvane izmene u uplati broj: {payment_statement.statement_number}, od datuma {payment_statement.payment_date.strftime("%d.%m.%Y.")}', 'success')

    return str(payment_statement_id)

@transactions.route('/generate_payment_slips/<int:payment_statement_id>', methods=['GET', 'POST'])
def generate_payment_slips(payment_statement_id):
    invoice_item = InvoiceItems.query.get_or_404(payment_statement_id)
    # Ova funkcija vraća apsolutnu putanju
    full_file_path = generate_payment_slips_attach(invoice_item)
    filename = os.path.basename(full_file_path)
    # Generišite relativni URL do fajla za klijentsku stranu
    file_url = url_for('static', filename=f'payment_slips/{filename}', _external=True)
    # current_file_path = os.path.abspath(__file__)
    # project_folder = os.path.dirname(os.path.dirname(current_file_path))
    # filepath = os.path.join(project_folder, 'static', 'payment_slips', filename)
    
    # Relativna putanja do fajla za klijentsku stranu
    file_url = url_for('static', filename=f'payment_slips/{filename}', _external=True)
    
    flash('Generisana uplatnica', 'success')
    
    # Preusmeravanje na generisani PDF fajl
    return redirect(file_url)