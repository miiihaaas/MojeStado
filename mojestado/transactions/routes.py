import datetime
import hashlib
import hmac
import os
import random
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from mojestado import app, db
from mojestado.main.functions import clear_cart_session, get_cart_total
from mojestado.models import Animal, Invoice, PaySpotCallback, User
from mojestado.transactions.form import GuestForm
from mojestado.transactions.functions import calculate_hash, generate_random_string, register_guest_user, create_invoice, send_email, deactivate_animals, deactivate_products


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
    merchant_order_amount, installment_total = get_cart_total()
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
    secret_key_callback = os.getenv('PAYSPOT_SECRET_KEY_CALLBACK')
    data = request.json  # Dobijanje JSON podataka iz POST zahteva
    if data:
        print(f'Received Callback Data: {data}')
        
        # Sada možeš obraditi podatke, sačuvati ih u bazi, validirati itd.
        order_id = data.get('orderID')
        invoice_id = int(data.get('orderID').split('-')[1])
        shop_id = data.get('shopID')
        auth_number = data.get('authNumber')
        amount = data.get('amount')
        currency = data.get('currency')
        transaction_id = data.get('transactionID')
        result = data.get('result')
        received_hash = data.get('hash')
        masked_pan = data.get('maskedPan')
        expiry_date = data.get('expiryDate')
        card_brand = data.get('cardBrand')
        
        # Implementacija logike za validaciju ili obradu podataka
        # Kreiranje stringa za hash verifikaciju
        plantext = f"{order_id}|{shop_id}|{amount}|{result}|{secret_key_callback}"
        print(f'{plantext=}')
        
        # Izračunavanje hash-a
        calculated_hash_value = calculate_hash(plantext)
        print(f'** {calculated_hash_value=}')
        print(f'** {received_hash=}')
        
        if received_hash != calculated_hash_value:
            print(f'callback_url: Hash verification failed!')
            return 'Invalid hash!', 400
        if result != '00':
            print(f'callback_url: {result=} Transaction failed!')
            return 'Transaction failed!', 400
        print(f'callback_url: {result=} Transaction success!')
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
        # send_email(user, form_object)
        # clear_cart_session()
        return jsonify({"status": "success"}), 200  # Vrati odgovor serveru

    return jsonify({"error": "No data received"}), 400


@transactions.route('/success_url', methods=['GET'])
def success_url():
    flash('Uspešna transakcija', 'success')
    return redirect(url_for('main.view_cart'))


@transactions.route('/cancel_url', methods=['GET', 'POST'])
def cancel_url():
    flash('Transakcija otkazana', 'danger')
    return redirect(url_for('main.view_cart'))


@transactions.route('/error_url', methods=['GET', 'POST'])
def error_url():
    flash('Transakcija neuspešna', 'danger')
    return redirect(url_for('main.view_cart'))