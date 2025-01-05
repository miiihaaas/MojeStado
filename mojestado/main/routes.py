import datetime
import os
import random
from flask import Blueprint, jsonify, session
from flask import  render_template, flash, redirect, url_for, request
from flask_login import current_user
from mojestado import app, db
from mojestado.main.functions import clear_cart_session, get_cart_total, send_faq_email
from mojestado.models import FAQ, Animal, AnimalCategory, Product
from mojestado.transactions.functions import calculate_hash, generate_random_string


main = Blueprint('main', __name__)


@main.route('/')
@main.route('/home')
def home():
    route_name = request.endpoint
    faq = FAQ.query.all()
    faq = [question for question in faq if question.id < 4]
    animal_categories = AnimalCategory.query.all()
    return render_template('home.html', title='Početna strana',
                            route_name=route_name,
                            faq=faq,
                            animal_categories=animal_categories)


@main.route('/about')
def about():
    route_name = request.endpoint
    return render_template('about.html', 
                            route_name=route_name,
                            title='O portalu')


@main.route('/faq', methods=['GET', 'POST'])
def faq():
    route_name = request.endpoint
    faq = FAQ.query.all()
    if request.method == 'POST':
        print(f'{request.form=}')
        flash('Uspesno ste poslali pitanje timu portala "Moje stado"!', 'success')
        #! razviti funkciju koja će da pošalje mejl sa pitanjem vlasniku portala
        email = request.form['email']
        question = request.form['question']
        send_faq_email(email, question)
        return render_template('faq.html', title='Najžešće postavljena pitanja',
                                faq=faq)
    return render_template('faq.html', 
                            route_name=route_name, 
                            title='Najčešće postavljena pitanja',
                            faq=faq)


@main.route('/contact')
def contact():
    route_name = request.endpoint
    return render_template('contact.html', 
                            route_name=route_name,
                            title='Kontakt strana')


@main.route('/set/<value>')
def set(value):
    session['value'] = value
    return f'vrednost koja je postavljena je: {value}'

@main.route('/get')
def get():
    if 'value' not in session:
        return 'nije postavljena ni jedna vrednost...'
    return f'vrednost koja je postavljena je: {session["value"]}. ovo je get vrednost.'


@main.route('/add_services_to_chart', methods=['POST'])
def add_services_to_chart():
    print(f'**** {request.form=}')
    animal_id = request.form.get('animalId')
    animal = Animal.query.get_or_404(animal_id)
    # povlači cene svih usluga za farmu iz koje se kupuje životinja
    farm_services = animal.farm_animal.services
    print(f'**** {farm_services=}')
    
    if request.form.get('slaughterService') == 'on':
        slaughter_service = farm_services['klanje']
        print(f'**** {slaughter_service=}')
        slaughter_service_price_per_kg = slaughter_service[f'{animal.animal_category_id}']
        print(f'**** {slaughter_service_price_per_kg=}')
    if request.form.get('processingService') == 'on':
        processing_service = farm_services['obrada']
        processing_service_price_per_kg = processing_service[f'{animal.animal_category_id}']
    
    
    add_animal_to_cart(animal_id)
    
    if 'services' not in session:
        session['services'] = []
    if request.form.get('slaughterService') == 'on' or request.form.get('processingService') == 'on':
        new_service = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
        new_service['category'] = animal.animal_category.animal_category_name
        new_service['subcategory'] = animal.animal_categorization.subcategory
        new_service['race'] = animal.animal_race.animal_race_name
        new_service['farm'] = animal.farm_animal.farm_name
        new_service['location'] = animal.farm_animal.farm_city
        if request.form.get('slaughterService') == 'on':
            new_service['slaughterService'] = True
            new_service['slaughterPrice'] = float(animal.current_weight) * float(slaughter_service_price_per_kg)
        else:
            new_service['slaughterPrice'] = 0
        if request.form.get('processingService') == 'on':
            new_service['processingService'] = True
            new_service['processingPrice'] = float(animal.current_weight) * float(processing_service_price_per_kg)
        else:
            new_service['processingPrice'] = 0
        session['services'].append(new_service)
    flash('Uspesno ste dodali uslugu u korpu!', 'success')
    return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))


@main.route('/add_fattening_to_chart', methods=['POST'])
def add_fattening_to_chart():
    print(f'**** {request.form=}')
    animal_id = request.form.get('animalId') or request.form.get('animalId_')
    animal = Animal.query.get_or_404(animal_id)
    add_animal_to_cart(animal_id)
    
    if 'fattening' not in session:
        session['fattening'] = []
    # Pronađi da li životinja sa ovim ID-jem već postoji u fattening listi
    existing_fattening = next((f for f in session['fattening'] if f['id'] == int(animal_id)), None)
    
    new_fattening = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
    new_fattening['category'] = animal.animal_category.animal_category_name
    new_fattening['subcategory'] = animal.animal_categorization.subcategory
    new_fattening['race'] = animal.animal_race.animal_race_name
    new_fattening['farm'] = animal.farm_animal.farm_name
    new_fattening['location'] = animal.farm_animal.farm_city
    new_fattening['current_weight'] = request.form.get('currentWeight') or request.form.get('currentWeight_')
    new_fattening['desired_weight'] = request.form.get('desiredWeight') or request.form.get('desiredWeight_')
    new_fattening['fattening_price'] = request.form.get('calculatedPrice') or request.form.get('calculatedPrice_')
    new_fattening['feeding_days'] = request.form.get('feedingDays') or request.form.get('feedingDays_')
    print(f'**** {request.form.get("installmentPayment")=}')
    if request.form.get('installmentPayment') or request.form.get('installmentPayment_') == 'on':
        new_fattening['installment_options'] = int(request.form.get('installmentOptions')) or int(request.form.get('installmentOptions_'))
    else:
        new_fattening['installment_options'] = 1
    new_fattening['installment_price'] = request.form.get('installmentPrice')
    
    if existing_fattening:
        # Ažuriraj postojeću stavku
        existing_fattening.update(new_fattening)
        flash('Uspesno ste ažurirali ovu zivotinju u korpi za tov!', 'success')
    else:
        # Dodaj novu stavku
        session['fattening'].append(new_fattening)
        flash('Uspesno ste dodali ovu zivotinju u korpu za tov!', 'success')
    session.modified = True
    
    #! dodavanje usluge klajna/obrade u korpu uz izabranu uslugu tova
    if request.form.get('slaughterService') == 'on' or request.form.get('processingService') == 'on':
        farm_services = animal.farm_animal.services
        if request.form.get('slaughterService') == 'on':
            slaughter_service = farm_services['klanje']
            print(f'**** {slaughter_service=}')
            slaughter_service_price_per_kg = slaughter_service[f'{animal.animal_category_id}']
            print(f'**** {slaughter_service_price_per_kg=}')
        if request.form.get('processingService') == 'on':
            processing_service = farm_services['obrada']
            processing_service_price_per_kg = processing_service[f'{animal.animal_category_id}']
        if 'services' not in session:
            session['services'] = []
        if request.form.get('slaughterService') == 'on' or request.form.get('processingService') == 'on':
            new_service = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
            new_service['category'] = animal.animal_category.animal_category_name
            new_service['subcategory'] = animal.animal_categorization.subcategory
            new_service['race'] = animal.animal_race.animal_race_name
            new_service['farm'] = animal.farm_animal.farm_name
            new_service['location'] = animal.farm_animal.farm_city
            if request.form.get('slaughterService') == 'on':
                new_service['slaughterService'] = True
                new_service['slaughterPrice'] = float(animal.current_weight) * float(slaughter_service_price_per_kg)
            else:
                new_service['slaughterPrice'] = 0
            if request.form.get('processingService') == 'on':
                new_service['processingService'] = True
                new_service['processingPrice'] = float(animal.current_weight) * float(processing_service_price_per_kg)
            else:
                new_service['processingPrice'] = 0
            session['services'].append(new_service)
        flash('Uspesno ste dodali uslugu u korpu!', 'success')
    
    return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))


@main.route('/add_animal_to_cart/<int:animal_id>')
def add_animal_to_cart(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if 'animals' not in session:
        session['animals'] = []
    if animal.id in [a['id'] for a in session['animals']]:
        flash('Ova zivotinja se vec nalazi u korpi!', 'danger')
        return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
    
    new_animal = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
    new_animal['category'] = animal.animal_category.animal_category_name
    new_animal['subcategory'] = animal.animal_categorization.subcategory
    new_animal['race'] = animal.animal_race.animal_race_name
    new_animal['farm'] = animal.farm_animal.farm_name
    new_animal['location'] = animal.farm_animal.farm_city

    session['animals'].append(new_animal)
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste dodali ovu zivotinju u korpu!', 'success')
    return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))


@main.route('/add_product_to_cart/<int:product_id>', methods=['POST'])
def add_product_to_cart(product_id):
    print(f'{request.form=}')
    product = Product.query.get_or_404(product_id)
    if 'products' not in session:
        session['products'] = []
    if product.id in [p['id'] for p in session['products']]:
        flash('Proizvod se vec nalazi u korpi!', 'danger')
        return redirect(url_for('marketplace.product_detail', product_id=product.id))
    
    new_product = {column.name: getattr(product, column.name) for column in product.__table__.columns}
    new_product['category'] = product.product_category.product_category_name
    new_product['subcategory'] = product.product_subcategory.product_subcategory_name
    new_product['section'] = product.product_section.product_section_name
    new_product['farm'] = product.farm_product.farm_name
    new_product['location'] = product.farm_product.municipality_farm.municipality_name
    new_product['quantity'] = request.form['quantity']
    new_product['total_price'] = float(request.form['quantity']) * float(product.product_price_per_unit)

    session['products'].append(new_product)
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste dodali ovaj proizvod u korpu!', 'success')
    return redirect(url_for('marketplace.product_detail', product_id=product.id))


# @main.route('/add_delevery_to_cart', methods=['POST'])
# def add_delevery_to_cart():
    # pass


@main.route('/view_cart', methods=['GET', 'POST'])
def view_cart():
    route_name = request.endpoint
    # print(f'debug session pre: {session=}')
    
    # Prvo proveravamo da li ima stavki u korpi
    has_items = any([
        session.get('animals', []),
        session.get('products', []),
        session.get('fattening', []),
        session.get('services', [])
    ])
    
    # Ako nema stavki, brišemo delivery iz sesije
    if not has_items and 'delivery' in session:
        del session['delivery']
        session.modified = True
    
    # print(f'debug session posle: {session=}')
    # Dohvatamo sve podatke iz korpe
    cart_contents = {
        'animals': session.get('animals', []),
        'products': session.get('products', []),
        'fattening': session.get('fattening', []),
        'services': session.get('services', []),
        'delivery': session.get('delivery', {'delivery_total': 0, 'delivery_status': False})
    }
    
    app.logger.debug(f'View cart sadržaj: {cart_contents}')
    
    # Provera da li je korpa stvarno prazna (isto kao u clear_cart_session)
    has_items = any(
        len(items) > 0 if isinstance(items, list) else bool(items)
        for items in cart_contents.values()
    )
    
    if not has_items:
        flash('Korpa je prazna!', 'info')
        return render_template('view_cart.html', 
                            title='Korpa', 
                            route_name=route_name, 
                            animals=[],
                            products=[],
                            services=[],
                            fattening=[])
                            
    # Izvlačimo pojedinačne liste iz cart_contents
    animals = cart_contents['animals']
    products = cart_contents['products']
    fattening = cart_contents['fattening']
    services = cart_contents['services']
    delivery = cart_contents['delivery']
    
    print(f'debug delivery: {delivery=}')
    
    submit_button = 'nije_na_rate'
    if fattening:  # Koristimo već izvučenu listu
        for f in fattening:
            if int(f.get('installment_options', 0)) > 1:
                submit_button = 'na_rate'
                break

    merchant_order_amount, installment_total, delivery_total = get_cart_total()
    app.logger.debug(f'Cart totals: merchant_order_amount={merchant_order_amount}, installment_total={installment_total}, delivery_total={delivery_total}')
    
    if request.method == 'POST':
        app.logger.debug(f'POST DELIVERY: {request.form}')
        delivery_status = request.form.get('delivery_total') == 'on'
        session['delivery'] = {
            "delivery_total": delivery_total,
            "delivery_status": delivery_status
        }
        cart_contents['delivery'] = session['delivery']  # Ažuriramo i lokalni cart_contents
        return redirect(url_for('main.view_cart'))
        
    # Računamo cenu dostave
    if 'delivery' not in session:
        session['delivery'] = {
            "delivery_total": delivery_total,
            "delivery_status": False  # Uvek postavljamo na False kada se prvi put kreira
        }
        cart_contents['delivery'] = session['delivery']  # Ažuriramo i lokalni cart_contents
    delivery_status = cart_contents['delivery']['delivery_status']
    app.logger.debug(f'Delivery status: {delivery_status}')
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('view_cart.html',
                            route_name=route_name,
                            animals=animals, 
                            products=products, 
                            submit_button=submit_button, 
                            fattening=fattening,
                            services=services, 
                            delivery=delivery,
                            merchant_order_amount=merchant_order_amount,
                            installment_total=installment_total,
                            delivery_total=delivery_total,
                            delivery_status=delivery_status,
                            current_date=current_date)


@main.route('/remove_animal_from_cart/<int:animal_id>')
def remove_animal_from_cart(animal_id):
    try:
        # Provera da li je sesija inicijalizovana
        if 'animals' not in session or not isinstance(session.get('animals'), list):
            flash('Korpa je prazna ili je došlo do greške!', 'info')
            return redirect(url_for('main.view_cart'))

        # Uklanjanje životinje iz sesije 'animals'
        session['animals'] = [animal for animal in session['animals'] if animal.get('id') != animal_id]

        # Provera i uklanjanje životinje iz sesije 'fattening'
        if 'fattening' in session and isinstance(session.get('fattening'), list):
            session['fattening'] = [animal for animal in session['fattening'] if animal.get('id') != animal_id]

        # Provera i uklanjanje životinje iz sesije 'services'
        if 'services' in session and isinstance(session.get('services'), list):
            session['services'] = [animal for animal in session['services'] if animal.get('id') != animal_id]

        # Obezbeđivanje da Flask zna da je sesija promenjena
        session.modified = True

        flash('Uspešno ste obrisali ovu životinju iz korpe!', 'success')
    
    except Exception as e:
        flash(f'Došlo je do greške: {str(e)}', 'danger')

    return redirect(url_for('main.view_cart'))



@main.route('/remove_product_from_cart/<int:product_id>')
def remove_product_from_cart(product_id):
    try:
        # Provera da li 'products' postoji u sesiji i da li je lista
        if 'products' not in session or not isinstance(session.get('products'), list):
            flash('Korpa je prazna ili je došlo do greške!', 'info')
            return redirect(url_for('main.view_cart'))

        # Uklanjanje proizvoda iz sesije 'products'
        session['products'] = [product for product in session['products'] if product.get('id') != product_id]

        # Obezbeđivanje da Flask zna da je sesija promenjena
        session.modified = True

        flash('Uspešno ste obrisali ovaj proizvod iz korpe!', 'success')
    
    except Exception as e:
        flash(f'Došlo je do greške: {str(e)}', 'danger')

    return redirect(url_for('main.view_cart'))



@main.route('/remove_fattening_from_cart/<int:animal_id>')
def remove_fattening_from_cart(animal_id):
    try:
        # Provera da li 'fattening' postoji u sesiji i da li je lista
        if 'fattening' not in session or not isinstance(session.get('fattening'), list):
            flash('Korpa je prazna ili je došlo do greške!', 'info')
            return redirect(url_for('main.view_cart'))

        # Uklanjanje životinje iz sesije 'fattening'
        session['fattening'] = [animal for animal in session['fattening'] if animal.get('id') != animal_id]
        animal = Animal.query.get(animal_id)
        animal.wanted_weight = None
        db.session.commit()

        # Obezbeđivanje da Flask zna da je sesija promenjena
        session.modified = True

        flash('Uspešno ste obrisali ovaj proizvod iz korpe!', 'success')
    
    except Exception as e:
        flash(f'Došlo je do greške: {str(e)}', 'danger')

    return redirect(url_for('main.view_cart'))



@main.route('/remove_service_from_cart/<int:service_id>')
def remove_service_from_cart(service_id):
    try:
        # Provera da li 'services' postoji u sesiji i da li je lista
        if 'services' not in session or not isinstance(session.get('services'), list):
            flash('Korpa je prazna ili je došlo do greške!', 'info')
            return redirect(url_for('main.view_cart'))

        # Uklanjanje usluge iz sesije 'services'
        session['services'] = [service for service in session['services'] if service.get('id') != service_id]

        # Obezbeđivanje da Flask zna da je sesija promenjena
        session.modified = True

        flash('Uspešno ste obrisali ovu uslugu iz korpe!', 'success')
    
    except Exception as e:
        flash(f'Došlo je do greške: {str(e)}', 'danger')

    return redirect(url_for('main.view_cart'))



@main.route('/clear_cart')
def clear_cart():
    clear_cart_session()
    flash('Korpa je obrisana!', 'info')
    return redirect(url_for('main.view_cart'))

@main.route('/terms_and_conditions')
def terms_and_conditions():
    return render_template('terms_and_conditions.html')


@main.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')
