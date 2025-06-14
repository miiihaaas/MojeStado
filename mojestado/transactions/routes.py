import datetime, time
import json
import xml.etree.ElementTree as ET
import os
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from mojestado import app, db
from mojestado.main.functions import clear_cart_session, get_cart_total
from mojestado.models import AnimalCategory, Debt, Invoice, PaySpotCallback, InvoiceItems, PaySpotTransaction, User
from mojestado.transactions.form import GuestForm
from mojestado.transactions.functions import calculate_hash, define_invoice_user, generate_random_string, \
    register_guest_user, create_invoices, populate_item_data, send_email, send_success_email, send_payments_email, \
    deactivate_animals, deactivate_products, send_payment_order_insert, send_payment_order_confirm, edit_guest_user, get_fiskom_data


transactions = Blueprint('transactions', __name__)


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
                app.logger.debug(f'Form errors after validate_on_submit: {form.errors}')
                # Provera specifično za email koji već postoji
                email_error = False
                if 'email' in form.errors:
                    app.logger.debug(f'Email errors: {form.errors["email"]}')
                    for error in form.errors['email']:
                        app.logger.debug(f'Obrađujem grešku za email: {error}')
                        if 'već postoji' in error:
                            user = User.query.filter_by(email=form.email.data).first()
                            app.logger.debug(f'Nađen korisnik za email {form.email.data}: {user}, user_type: {getattr(user, "user_type", None) if user else None}')
                            if user and getattr(user, 'user_type', None) == 'guest':
                                app.logger.info('Email pripada gostu, uklanjam grešku i nastavljam.')
                                form.errors['email'] = [e for e in form.errors['email'] if 'već postoji' not in e]
                                if not form.errors['email']:
                                    del form.errors['email']
                                email_error = True
                app.logger.debug(f'email_error: {email_error}, preostale greške: {form.errors}')
                if email_error and not form.errors:
                    app.logger.info('Nema više grešaka, nastavljam proces za gosta.')
                    pass  # Dozvoli nastavak procesa
                else:
                    app.logger.warning('Nevalidna forma za gost korisnika')
                    for field, errors in form.errors.items():
                        for error in errors:
                            app.logger.debug(f'Flashujem grešku: Greška u polju {field}: {error}')
                            flash(f'Greška u polju {field}: {error}', 'danger')
                    return render_template('transactions/user_payment_form.html', form=form)

            # Pokušaj registracije ili ažuriranja gost korisnika
            try:
                user = User.query.filter_by(email=form.email.data).first()
                if user and getattr(user, 'user_type', None) == 'guest':
                    # Ažuriraj podatke gosta
                    new_user_id = edit_guest_user(form.data)
                    app.logger.info(f'Ažuriran gost korisnik: {new_user_id}')
                    return redirect(url_for('transactions.make_order'))
                else:
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
        
        # Inicijalizacija svih promenjivih koje se koriste kasnije
        new_invoice_products = None
        new_invoice_animals = None
        merchant_order_amount = None
        installment_total = None
        delivery_product_total = None
        delivery_animal_total = None
        user = None
        rnd = None
        hash_value = None
        hash_value_products = None
        current_date = None
        merchant_order_id = None
        success = None
        error_message = None
        merchant_order_id_animals = None
        
        #! Provera da li ima stavki u korpi
        animals = session.get('animals', [])
        products = session.get('products', [])
        fattening = session.get('fattening', [])
        services = session.get('services', [])
        
        if not any([animals, products, fattening, services]):
            app.logger.warning('Pokušaj kreiranja prazne porudžbine')
            flash('Vaša korpa je prazna.', 'warning')
            return redirect(url_for('main.home'))
            
        # Provera da li je kupovina na rate #! gost ne može na rate da kupuje => samo može GP da kupuje, za ostalo mora da napravi nalog
        _, installment_total, _, _ = get_cart_total()
        if installment_total > 0 and not current_user.is_authenticated:
            app.logger.warning('Gost korisnik pokušao kupovinu na rate')
            flash('Za kupovinu na rate potrebno je da se registrujete.', 'warning')
            return redirect(url_for('users.register'))
            
        #! Kreiranje faktura (i stavki faktura) za proizvode i životinje
        try:
            new_invoice_products, new_invoice_animals = create_invoices()
            app.logger.info(f'Kreirana nova faktura proizvoda: {new_invoice_products.id}') if new_invoice_products else app.logger.info(f'Nije kreirana nova faktura proizvoda')
            app.logger.info(f'Kreirana nova faktura životinja: {new_invoice_animals.id}') if new_invoice_animals else app.logger.info(f'Nije kreirana nova faktura životinja')
        except Exception as e:
            app.logger.error(f'Greška pri kreiranju fakture: {str(e)}')
            flash('Došlo je do greške pri kreiranju porudžbine. Molimo pokušajte ponovo.', 'danger')
            return redirect(url_for('main.home'))
            
        #! Učitavanje korisnika
        user = define_invoice_user()
        if isinstance(user, tuple):
            return user
            
        #! Priprema podataka za plaćanje preko kartice (samo proizvodi)
        try:
            # Računanje ukupnog iznosa 
            #! merchant_order_amount je ukupan iznos za naplatu preko kartice
            #! installment_total je ukupan iznos za naplatu preko uplatnice
            #! delivery_product_total je trošak dostave za proizvode
            #! delivery_animal_total je trošak dostave za životinje
            merchant_order_amount, installment_total, delivery_product_total, delivery_animal_total = get_cart_total() 
            company_id = os.environ.get('PAYSPOT_COMPANY_ID')
            if not company_id:
                raise ValueError('Nedostaje PAYSPOT_COMPANY_ID')
            
            # Dodavanje troškova dostave ako je izabrana
            delivery_product_status = session.get('delivery', {}).get('delivery_product_status', False)
            if delivery_product_status:
                merchant_order_amount += delivery_product_total #! preko kartice mogu samo biti proizvodi i trošak dostave za proizvode
            
            #? nastaviti podatke za plaćanje preko uplatnice (samo životinje i usluge vezane za životinje)
            delivery_animal_status = session.get('delivery', {}).get('delivery_animal_status', False)
            if delivery_animal_status:
                installment_total += delivery_animal_total #! preko uplatnice mogu samo biti životinje i trošak dostave za životinje
            
            if new_invoice_products:
                rnd = generate_random_string()
                merchant_order_id = f'PMS-{new_invoice_products.id:09}'
                app.logger.debug(f'Ukupan iznos za naplatu preko kartice: {merchant_order_amount}')
                
                # Slanje PaymentOrderInsert zahteva (za split transakcije)
                success, error_message = send_payment_order_insert(merchant_order_id, merchant_order_amount, 'kartica', user, new_invoice_products)
            
                if not success:
                    #! napraviti kod da samo kreira uplatnicu bez da se ide na proveru stanja kartice
                    #! napraviti kod da samo kreira uplatnicu bez da se ide na proveru stanja kartice
                    #! napraviti kod da samo kreira uplatnicu bez da se ide na proveru stanja kartice
                    flash(f'Greška pri pripremi podataka za plaćanje preko kartice: {error_message}.', 'danger')
                    return redirect(url_for('main.view_cart'))
            
                # Generisanje hash vrednosti
                current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
                if not secret_key:
                    raise ValueError('Nedostaje PAYSPOT_SECRET_KEY')
                    
                plaintext = f"{rnd}|{current_date}|{merchant_order_id}|{merchant_order_amount:.2f}|{secret_key}"
                hash_value_products = calculate_hash(plaintext)
                
                
                app.logger.debug(f'Uspešno pripremljeni podaci za plaćanje: {hash_value_products=}')
            
            if new_invoice_animals:
                # rnd_animals = generate_random_string()
                merchant_order_id_animals = f'ZMS-{new_invoice_animals.id:09}'
                app.logger.debug(f'Ukupan iznos za naplatu preko uplatnice: {installment_total}')
                
                #? Slanje PaymentOrderInsert zahteva (za uplatnice)
                success, error_message = send_payment_order_insert(merchant_order_id_animals, installment_total, 'uplatnica', user, new_invoice_animals)
                # if success:
                #     # time.sleep(30)
                #     success_animals, error_message = send_payment_order_confirm(merchant_order_id_animals, None, new_invoice_animals.id)
                #     if not success_animals:
                #         app.logger.error(f'Greška pri slanju PaymentOrderConfirm za životinje preko uplatnice: {error_message}')
                #         flash(f'Greška pri slanju PaymentOrderConfirm za životinje preko uplatnice: {error_message}.', 'danger')
                #         return redirect(url_for('main.view_cart'))
                    #! Napraviti funkcionalnost za slanje mejla korisniku o uspešnom plaćanju preko uplatnice
                    #! Napraviti funkcionalnost za slanje mejla korisniku o uspešnom plaćanju preko uplatnice
                    #! Napraviti funkcionalnost za slanje mejla korisniku o uspešnom plaćanju preko uplatnice
                    #? donja funkcija treba da se pozove na drugom mesetu kada se potvrdi plaćanje korpe...
                    # send_payments_email(user, new_invoice_animals.id)

                # else:
                #     flash(f'Greška pri pripremi podataka za plaćanje preko uplatnice: {error_message}.', 'danger')
                #     return redirect(url_for('main.view_cart'))

            # Uvek dodeljujemo current_date pre render_template
            if not current_date:
                current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            environment = os.environ.get('ENVIRONMENT')
            if environment == 'development':
                action = 'https://test.nsgway.rs:50009/api/ecommerce/submit'
            elif environment == 'production':
                action = 'https://www.nsgway.rs:50010/api/ecommerce/submit'
            return render_template('transactions/make_order.html',
                                animals=animals,
                                products=products,
                                fattening=fattening,
                                services=services,
                                user=user,
                                company_id=company_id,
                                rnd=rnd,
                                hash_value=hash_value_products, 
                                merchant_order_id=merchant_order_id, 
                                merchant_order_id_animals=merchant_order_id_animals,
                                new_invoice_animals_id=new_invoice_animals.id if new_invoice_animals else None,
                                merchant_order_amount=merchant_order_amount,
                                installment_total=installment_total,
                                delivery_product_total=delivery_product_total,
                                delivery_animal_total=delivery_animal_total,
                                current_date=current_date,
                                action=action)
                                
        except ValueError as e:
            app.logger.error(f'Nedostaje konfiguracija za plaćanje: {str(e)}')
            flash('Sistem za plaćanje nije ispravno konfigurisan. Molimo kontaktirajte podršku.', 'danger')
            return redirect(url_for('main.home'))
            
    except Exception as e:
        app.logger.error(f'Neočekivana greška u make_order: {str(e)}')
        flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@transactions.route('/confirm_animals_order/<int:invoice_id>', methods=['GET', 'POST'])
def confirm_animals_order(invoice_id):
    try:
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            flash('Faktura nije pronađena.', 'danger')
            return redirect(url_for('main.home'))
        merchant_order_id_animals = invoice.invoice_number
        try:
            invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
        except Exception as e:
            flash('Greška pri učitavanju stavki fakture.', 'danger')
            return redirect(url_for('main.home'))
        try:
            user = User.query.get(invoice.user_id)
            if not user:
                flash('Korisnik nije pronađen.', 'danger')
                return redirect(url_for('main.home'))
        except Exception as e:
            flash('Greška pri učitavanju korisnika.', 'danger')
            return redirect(url_for('main.home'))
        item_data = []
        for invoice_item in invoice_items:
            try:
                data = populate_item_data(invoice_item)
                item_data.append(data)
            except Exception as e:
                flash('Greška pri obradi stavke fakture.', 'danger')
                continue
        total_price = sum(item['total_price'] for item in item_data)
        try:
            payspot_transactions = PaySpotTransaction.query.filter_by(invoice_id=invoice.id).all()
            if not payspot_transactions:
                flash('Nema PaySpot transakcija za datu fakturu.', 'danger')
                return redirect(url_for('main.home'))
            success, error_message = send_payment_order_confirm(merchant_order_id_animals, 'uplatnica', invoice.id)
        except Exception as e:
            flash('Greška pri slanju zahteva za potvrdu uplate.', 'danger')
            return render_template('transactions/confirm_animals_order.html', invoice=invoice, user=user, item_data=item_data, total_price=total_price)
        if success and invoice.status == 'unconfirmed':
            try:
                send_payments_email(user, invoice.id)
                invoice.status = 'sent_invoice'
                db.session.commit()
                deactivate_animals(invoice_id) #! pošto ide preko uplatnice treba prvo da se bookira određeno vreme pa ako ne uplati onda da se ponovo aktivira, a ako uplati da se deaktivira
                clear_cart_session(product=False, animal=True)
                flash('Uplatnice su poslate na mejl.', 'success')
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri slanju uplatnica na mejl: {str(e)}')
                flash('Greška pri slanju uplatnica na mejl', 'danger')
        else:
            flash('Uplatnice su već poslate na mejl.', 'warning')
        return render_template('transactions/confirm_animals_order.html', 
                                invoice=invoice,
                                user=user,
                                item_data=item_data,
                                total_price=total_price)
    except Exception as e:
        flash('Neočekivana greška. Pokušajte ponovo.', 'danger')
        return redirect(url_for('transactions.make_order'))


@transactions.route('/callback_url', methods=['POST'])
def callback_url():
    """
    Callback URL za PaySpot transakcije.
    Prima podatke o transakciji i ažurira status fakture.
    """
    app.logger.debug('###################################')
    app.logger.debug('Pristup callback_url')
    app.logger.debug('Callback_url: ' + str(request.json))
    app.logger.debug('###################################')
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
        payspot_order_id = data.get('payspotOrderID')
        
        app.logger.info(f'Primljeni PaySpot callback podaci: OrderID={order_id}, Amount={amount}, Result={result}')

        # Validacija hash-a
        secret_key = os.environ.get('PAYSPOT_SECRET_KEY_CALLBACK')
        if not secret_key:
            app.logger.error('Callback_url: Nedostaje PAYSPOT_SECRET_KEY_CALLBACK')
            return jsonify({"error": "Missing secret key"}), 500
            
        plaintext = f"{order_id}|{shop_id}|{amount}|{result}|{secret_key}"
        calculated_hash = calculate_hash(plaintext)
        
        if calculated_hash != received_hash:
            app.logger.error(f'Callback_url: Neispravan hash. Primljeno: {received_hash}, Izračunato: {calculated_hash}')
            return jsonify({"error": "Invalid hash"}), 400

        # Pronalaženje fakture
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            app.logger.error(f'Callback_url: Faktura sa ID {invoice_id} nije pronađena')
            return jsonify({"error": "Invoice not found"}), 404

        # Čuvanje callback podataka
        callback = PaySpotCallback(
            invoice_id=invoice_id,
            amount=amount,
            recived_at=datetime.datetime.now(),
            callback_data=json.dumps(data)
        )
        db.session.add(callback)

        # Ažuriranje statusa fakture
        if result == '00':  # Uspešna transakcija
            invoice.status = 'paid'
            invoice.payment_date = datetime.datetime.now()
            
            # Slanje PaymentOrderConfirm zahteva za split transakcije
            success, error_message = send_payment_order_confirm(order_id, 'uplatnica', invoice_id)
            if not success:
                app.logger.error(f'Greška pri slanju PaymentOrderConfirm: {error_message}')
                return jsonify({"error": "Greška pri slanju PaymentOrderConfirm"}), 500
                    
            # Deaktivacija životinja i proizvoda
            app.logger.info(f'{invoice_id=}')

            deactivate_products(invoice_id)
            
            #! Slanje email-a PG o kupovini proizvoda preko kartice
            send_email(invoice_id)
            app.logger.info(f'Callback_url: Uspešna transakcija za fakturu {invoice_id}')
        else:
            invoice.status = 'failed'
            app.logger.warning(f'Callback_url: Neuspešna transakcija za fakturu {invoice_id}, rezultat: {result}')

        db.session.commit()
        return jsonify({"status": "success", "message": "Transakcija uspešno obrađena"}), 200
        
    except Exception as e:
        app.logger.error(f'Greška u callback_url funkciji: {str(e)}')
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@transactions.route('/success_url', methods=['GET'])
def success_url():
    time.sleep(10)
    # Izvlačenje svih parametara iz PaySpot response URL-a
    order_id = request.args.get('ORDERID')  # ID narudžbine, koristi se za identifikaciju transakcije
    shop_id = request.args.get('SHOPID')  # ID prodavnice, koristi se za proveru prodavca
    auth_number = request.args.get('AUTHNUMBER')  # Broj autorizacije, može se koristiti za evidenciju autorizacije
    amount = request.args.get('AMOUNT')  # Iznos transakcije, koristi se za proveru naplaćenog iznosa
    currency = request.args.get('CURRENCY')  # Valuta transakcije, koristi se za proveru valute (941 = RSD)
    transaction_id = request.args.get('TRANSACTIONID')  # Jedinstveni ID transakcije, koristi se za praćenje transakcije
    accounting_mode = request.args.get('ACCOUNTINGMODE')  # Mod obračuna, koristi se za internu obradu
    author_mode = request.args.get('AUTHORMODE')  # Mod autorizacije, koristi se za internu evidenciju
    result = request.args.get('RESULT')  # Rezultat transakcije (00 = uspeh), koristi se za proveru statusa
    transaction_type = request.args.get('TRANSACTIONTYPE')  # Tip transakcije, koristi se za analitiku ili evidenciju
    masked_pan = request.args.get('MASKEDPAN')  # Maskirani broj kartice, koristi se za prikaz korisniku
    trecurr = request.args.get('TRECURR')  # Tip rekurentne transakcije, koristi se za pretplate
    crecurr = request.args.get('CRECURR')  # ID rekurentne kartice, koristi se za vezivanje kartice
    pantail = request.args.get('PANTAIL')  # Poslednje cifre kartice, koristi se za prikaz korisniku
    pan_expiry_date = request.args.get('PANEXPIRYDATE')  # Datum isteka kartice, može se koristiti za proveru
    network = request.args.get('NETWORK')  # Mreža kartice, koristi se za statistiku (01 = Visa/Master)
    mac = request.args.get('MAC')  # Kriptografski potpis, koristi se za proveru integriteta
    
    invoice_id = int(order_id.split('-')[1])
    invoice = Invoice.query.get(invoice_id)
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    total_price = sum(item.invoice_item_details["total_price"] for item in invoice_items)
    user = User.query.get(invoice.user_id)

    
    app.logger.info(f'Uspesno zavrsena transakcija')

    clear_cart_session(product=True, animal=False)  # Brisanje korpe iz sesije
    fiskom_data = get_fiskom_data(invoice, invoice_items)
    send_success_email(invoice, auth_number, transaction_id, total_price, fiskom_data)

    flash('Transakcija je uspešna. Račun vaše platne kartice je zadužen.', 'success')
    return render_template('transactions/success_url.html',
                            user=user,
                            invoice=invoice,
                            invoice_items=invoice_items,
                            auth_number=auth_number,
                            transaction_id=transaction_id,
                            total_price=total_price
                            )


@transactions.route('/error_url', methods=['GET'])
def error_url():
    app.logger.error('Neuspešna transakcija')
    flash('Transakcija je neuspešna. Račun vaše platne kartice nije zadužen.', 'danger')
    now = datetime.datetime.now()
    return render_template('transactions/error_url.html', now=now)


@transactions.route('/cancel_url', methods=['GET'])
def cancel_url():
    app.logger.warning('Transakcija je otkazana')
    flash('Transakcija je otkazana. Račun vaše platne kartice nije zadužen.', 'warning')
    now = datetime.datetime.now()

    return render_template('transactions/cancel_url.html', 
                            now=now)


@transactions.route('/fiskom_test', methods=['GET'])
def fiskom_test():
    
    import requests

    url = "https://us-central1-fiscal-38558.cloudfunctions.net/api/invoices/normal/sale"
    payload = {
        "cashier": "test_portal_mojestado",
        "payment": [
            {
                "paymentType": "Card",
                "amount": 1000
            }
        ],
        "invoiceNumber": "MS-00000507",
        "items": [
            {
                "name": "test proizvod",
                "unitPrice": 1000,
                "labels": ["Ж"],
                "quantity": 1,
                "totalAmount": 1000
            }
        ]
    }
    if os.environ.get('ENVIRONMENT') == 'development':
        fiskom_api_key = os.environ.get('FISKOM_SANDBOX_API_KEY')
    else:
        fiskom_api_key = os.environ.get('FISKOM_PRODUCTION_API_KEY')
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {fiskom_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)
    
    #? data koji treba da se sačuva u db?
    data = {
        "invoice_number": response.json().get("invoiceNumber"),
        "pdf_url": response.json().get("invoicePdfUrl"),
        "qr_code_url": response.json().get("qrCodeFileURL"),
        "verification_url": response.json().get("verificationUrl"),
        "total_amount": response.json().get("totalAmount"),
        "created_at": response.json().get("sdcDateTime")
    }
    
    print(f'{data=}')
    return response.text


