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
from mojestado.transactions.functions import calculate_hash, define_invoice_user, generate_random_string, register_guest_user, create_invoices, send_email, deactivate_animals, deactivate_products, send_payment_order_insert, send_payment_order_confirm, edit_guest_user


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
        merchant_order_id = None
        success = None
        error_message = None
        
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
                if success:
                    success_animals, error_message = send_payment_order_confirm(merchant_order_id_animals, None, new_invoice_animals.id)
                    if not success_animals:
                        app.logger.error(f'Greška pri slanju PaymentOrderConfirm za životinje preko uplatnice: {error_message}')
                        flash(f'Greška pri slanju PaymentOrderConfirm za životinje preko uplatnice: {error_message}.', 'danger')
                        return redirect(url_for('main.view_cart'))
                    #! Napraviti funkcionalnost za slanje mejla korisniku o uspešnom plaćanju preko uplatnice
                    #! Napraviti funkcionalnost za slanje mejla korisniku o uspešnom plaćanju preko uplatnice
                    #! Napraviti funkcionalnost za slanje mejla korisniku o uspešnom plaćanju preko uplatnice
                else:
                    flash(f'Greška pri pripremi podataka za plaćanje preko uplatnice: {error_message}.', 'danger')
                    return redirect(url_for('main.view_cart'))

            # Uvek dodeljujemo current_date pre render_template
            if not current_date:
                current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                                merchant_order_amount=merchant_order_amount,
                                installment_total=installment_total,
                                delivery_product_total=delivery_product_total,
                                delivery_animal_total=delivery_animal_total,
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
            success, error_message = send_payment_order_confirm(order_id, payspot_order_id, invoice_id)
            if not success:
                app.logger.error(f'Greška pri slanju PaymentOrderConfirm: {error_message}')
                # Nastavljamo dalje, ne prekidamo proces jer je plaćanje već uspešno
                    
            # Deaktivacija životinja i proizvoda
            app.logger.info(f'{invoice_id=}')

            deactivate_animals(invoice_id) #! pošto ide preko uplatnice treba prvo da se bookira određeno vreme pa ako ne uplati onda da se ponovo aktivira, a ako uplati da se deaktivira
            deactivate_products(invoice_id)
            
            # Slanje email-a korisniku
            user = User.query.get(invoice.user_id)
            if user:
                send_email(user, invoice_id)
                
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
    app.logger.info('Uspesno zavrsena transakcija')
    user = User.query.get(current_user.id)
    invoice = Invoice.query.get(session.get('invoice_id')) #?

    # Prvo sačuvaj podatke iz korpe i podatke o kupcu, ako već nisu sačuvani
    if 'cart_data_success' not in session or 'buyer_data_success' not in session:
        cart_data = {
            'products': session.get('products', []),
            'animals': session.get('animals', []),
            'fattening': session.get('fattening', []),
            'services': session.get('services', [])
        }
        session['cart_data_success'] = cart_data

        # Priprema podataka o kupcu
        buyer_data = {
            'id': user.id,
            'email': user.email,
            'ime': user.name,
            'prezime': user.surname,
            'telefon': user.phone,
            'adresa': user.address,
            'mesto': user.city,
            'postanski_broj': user.zip_code,
            'tip_korisnika': user.user_type
        }
        session['buyer_data_success'] = buyer_data
    else:
        cart_data = session['cart_data_success']
        buyer_data = session['buyer_data_success']

    total_price = 0
    for item in cart_data.get('products', []):
        total_price += item['total_price']
    for item in cart_data.get('animals', []):
        total_price += item['total_price']
    for item in cart_data.get('fattening', []):
        total_price += item['total_price']
    for item in cart_data.get('services', []):
        total_price += item['total_price']

    clear_cart_session()  # Brisanje korpe iz sesije
    # Očisti i privremeno sačuvane podatke nakon prikaza
    session.pop('cart_data_success', None)
    session.pop('buyer_data_success', None)

    flash('Transakcija je uspešna. Račun vaše platne kartice je zadužen.', 'success')
    return render_template('transactions/success_url.html',
                            user=user,
                            invoice=invoice,
                            cart_data=cart_data,
                            buyer_data=buyer_data,
                            total_price=total_price
                            )


@transactions.route('/error_url', methods=['GET'])
def error_url():
    app.logger.error('Neuspešna transakcija')
    flash('Transakcija je neuspešna. Račun vaše platne kartice nije zadužen.', 'danger')
    return render_template('transactions/error_url.html')


@transactions.route('/cancel_url', methods=['GET'])
def cancel_url():
    app.logger.warning('Transakcija je otkazana')
    flash('Transakcija je otkazana. Račun vaše platne kartice nije zadužen.', 'warning')
    return render_template('transactions/cancel_url.html')
