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
from mojestado.transactions.functions import calculate_hash, generate_payment_slips_attach, generate_random_string, provera_validnosti_poziva_na_broj, register_guest_user, create_invoice, send_email, deactivate_animals, deactivate_products, send_payment_order_insert, send_payment_order_confirm


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
            
            # Slanje PaymentOrderInsert zahteva (za split transakcije)
            success, error_message = send_payment_order_insert(merchant_order_id, merchant_order_amount, user)
            
            if not success:
                flash(f'Greška pri pripremi podataka za plaćanje: {error_message}.', 'danger')
                return redirect(url_for('main.view_cart'))
            
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
    """
    Callback URL za PaySpot transakcije.
    Prima podatke o transakciji i ažurira status fakture.
    """
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
            order_id=order_id,
            shop_id=shop_id,
            amount=amount,
            result=result,
            hash=received_hash,
            raw_data=json.dumps(data),
            timestamp=datetime.datetime.now()
        )
        db.session.add(callback)

        # Ažuriranje statusa fakture
        if result == '00':  # Uspešna transakcija
            invoice.status = 'paid'
            invoice.payment_date = datetime.datetime.now()
            
            # Slanje PaymentOrderConfirm zahteva za split transakcije
            if data.get('requestType') == '10':
                success, error_message = send_payment_order_confirm(order_id, payspot_order_id, invoice_id)
                if not success:
                    app.logger.error(f'Greška pri slanju PaymentOrderConfirm: {error_message}')
                    # Nastavljamo dalje, ne prekidamo proces jer je plaćanje već uspešno
                    
            # Deaktivacija životinja i proizvoda
            deactivate_animals(invoice_id)
            deactivate_products(invoice_id)
            
            # Slanje email-a korisniku
            user = User.query.get(invoice.user_id)
            if user:
                send_email(user.email, 'Uspešna transakcija', 'transactions/email/transaction_success', 
                          user=user, invoice=invoice)
                
            app.logger.info(f'Callback_url: Uspešna transakcija za fakturu {invoice_id}')
        else:
            invoice.status = 'failed'
            app.logger.warning(f'Callback_url: Neuspešna transakcija za fakturu {invoice_id}, rezultat: {result}')

        db.session.commit()
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        app.logger.error(f'Greška u callback_url funkciji: {str(e)}')
        return jsonify({"error": "Internal server error"}), 500
