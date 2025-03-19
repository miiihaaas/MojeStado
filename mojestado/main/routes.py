import datetime
import os
import random
from flask import Blueprint, jsonify, session
from flask import  render_template, flash, redirect, url_for, request
from flask_login import current_user
from flask_mail import Message
from mojestado import app, db, mail
from mojestado.main.functions import clear_cart_session, get_cart_total, send_faq_email
from mojestado.models import FAQ, Animal, AnimalCategory, Farm, Product
from mojestado.transactions.functions import calculate_hash, generate_random_string
from sqlalchemy.exc import SQLAlchemyError


main = Blueprint('main', __name__)


@main.route('/')
@main.route('/home')
def home():
    random.seed(datetime.datetime.now().timestamp())
    route_name = request.endpoint
    try:
        faq = FAQ.query.all()
        faq = [question for question in faq if question.id < 4]
        animal_categories = AnimalCategory.query.all()
        
        # Nasumično izaberi tačno 6 farmi
        all_farms = Farm.query.all()
        active_farms = [farm for farm in all_farms if farm.user_farm.user_type == 'farm_active']
        farm_list = random.sample(active_farms, min(6, len(active_farms)))
        
        # Nasumično izaberi tačno 6 proizvoda
        all_products = Product.query.all()
        active_products = [product for product in all_products if product.farm_product.user_farm.user_type == 'farm_active']
        product_list = random.sample(active_products, min(6, len(active_products)))
        
        # Dodaj anti-cache parametar za sprečavanje keširanja
        anti_cache = int(datetime.datetime.now().timestamp())
        
        
        return render_template('home.html', title='Početna strana',
                                route_name=route_name,
                                faq=faq,
                                animal_categories=animal_categories,
                                farm_list=farm_list,
                                product_list=product_list,
                                anti_cache=anti_cache)
    except SQLAlchemyError as e:
        app.logger.error(f'Greška pri pristupu bazi podataka na početnoj strani: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/about')
def about():
    route_name = request.endpoint
    return render_template('about.html', 
                            route_name=route_name,
                            title='O portalu')


@main.route('/faq', methods=['GET', 'POST'])
def faq():
    route_name = request.endpoint
    try:
        faq = FAQ.query.all()
        
        if request.method == 'POST':
            email = request.form.get('email')
            question = request.form.get('question')
            
            if not email or not question:
                flash('Molimo popunite sva polja.', 'danger')
                return render_template('faq.html', 
                                    route_name=route_name,
                                    title='Najčešće postavljena pitanja',
                                    faq=faq)
            
            try:
                if send_faq_email(email, question):
                    flash('Uspešno ste poslali pitanje timu portala "Moje stado".', 'success')
                else:
                    flash('Došlo je do greške pri slanju pitanja. Molimo pokušajte kasnije.', 'danger')
                    app.logger.error(f'Neuspelo slanje FAQ pitanja od korisnika {email}')
            except Exception as e:
                app.logger.error(f'Greška pri slanju FAQ email-a: {str(e)}')
                flash('Došlo je do greške pri slanju pitanja. Molimo pokušajte kasnije.', 'danger')
            
            return redirect(url_for('main.faq'))
        
        return render_template('faq.html', 
                                route_name=route_name, 
                                title='Najčešće postavljena pitanja',
                                faq=faq)
    except SQLAlchemyError as e:
        app.logger.error(f'Greška pri pristupu FAQ bazi: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/contact', methods=['GET', 'POST'])
def contact():
    route_name = request.endpoint
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        if not all([name, email, message]):
            flash('Molimo popunite sva polja.', 'danger')
            return render_template('contact.html', 
                                route_name=route_name,
                                title='Kontakt strana')
        
        try:
            msg = Message('Nova poruka sa kontakt forme',
                        recipients=[app.config['MAIL_ADMIN']],
                        reply_to=email)
            
            msg.body = f"""
            Nova poruka od: {name}
            Email: {email}
            
            Poruka:
            {message}
            """
            
            mail.send(msg)
            flash('Vaša poruka je uspešno poslata.', 'success')
            return redirect(url_for('main.contact'))
            
        except Exception as e:
            app.logger.error(f'Greška pri slanju kontakt mejla od {email}: {str(e)}')
            flash('Došlo je do greške pri slanju poruke. Molimo pokušajte kasnije.', 'danger')
    
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
    try:
        app.logger.info(f'Primljen zahtev za dodavanje usluga: {request.form}')
        animal_id = request.form.get('animalId')
        
        try:
            animal = Animal.query.get_or_404(animal_id)
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri pristupu bazi za životinju {animal_id}: {str(e)}')
            return render_template('errors/500.html'), 500
            
        farm_services = animal.farm_animal.services
        app.logger.info(f'Dostupne usluge farme: {farm_services}')
        
        slaughter_service_price_per_kg = 0
        processing_service_price_per_kg = 0
        
        if request.form.get('slaughterService') == 'on':
            slaughter_service = farm_services['klanje']
            app.logger.info(f'Odabrana usluga klanja: {slaughter_service}')
            slaughter_service_price_per_kg = slaughter_service[f'{animal.animal_category_id}']
            app.logger.info(f'Cena klanja po kg: {slaughter_service_price_per_kg}')
            
        if request.form.get('processingService') == 'on':
            processing_service = farm_services['obrada']
            processing_service_price_per_kg = processing_service[f'{animal.animal_category_id}']
        
        add_animal_to_cart(animal_id)
        
        if 'services' not in session:
            session['services'] = []
            
        if request.form.get('slaughterService') == 'on' or request.form.get('processingService') == 'on':
            try:
                new_service = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
                new_service['category'] = animal.animal_category.animal_category_name
                new_service['subcategory'] = animal.animal_categorization.subcategory
                new_service['race'] = animal.animal_race.animal_race_name
                new_service['farm'] = animal.farm_animal.farm_name
                new_service['location'] = animal.farm_animal.farm_city
                new_service['slaughterService'] = request.form.get('slaughterService') == 'on'
                new_service['processingService'] = request.form.get('processingService') == 'on'
                
                if request.form.get('slaughterService') == 'on':
                    new_service['slaughterPrice'] = float(animal.current_weight) * float(slaughter_service_price_per_kg)
                else:
                    new_service['slaughterPrice'] = 0
                    
                if request.form.get('processingService') == 'on':
                    new_service['processingPrice'] = float(animal.current_weight) * float(processing_service_price_per_kg)
                else:
                    new_service['processingPrice'] = 0
                    
                session['services'].append(new_service)
                
                flash('Uspešno ste dodali uslugu u korpu.', 'success')
            except (ValueError, AttributeError) as e:
                app.logger.error(f'Greška pri kreiranju nove usluge: {str(e)}')
                flash('Došlo je do greške pri dodavanju usluge. Molimo pokušajte ponovo.', 'danger')
                return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
        
        return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri dodavanju usluga: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/add_fattening_to_chart', methods=['POST'])
def add_fattening_to_chart():
    try:
        app.logger.info(f'Primljen zahtev za dodavanje tova: {request.form}')
        animal_id = request.form.get('animalId') or request.form.get('animalId_')
        
        try:
            animal = Animal.query.get_or_404(animal_id)
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri pristupu bazi za životinju {animal_id}: {str(e)}')
            return render_template('errors/500.html'), 500
            
        add_animal_to_cart(animal_id)
        
        if 'fattening' not in session:
            session['fattening'] = []
            
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
        
        if request.form.get('installmentPayment') or request.form.get('installmentPayment_') == 'on':
            new_fattening['installment_options'] = int(request.form.get('installmentOptions')) or int(request.form.get('installmentOptions_'))
        else:
            new_fattening['installment_options'] = 1
            
        new_fattening['installment_price'] = request.form.get('installmentPrice')
        
        if existing_fattening:
            existing_fattening.update(new_fattening)
            flash('Uspešno ste ažurirali ovu životinju u korpi za tov.', 'success')
        else:
            session['fattening'].append(new_fattening)
            flash('Uspešno ste dodali ovu životinju u korpu za tov.', 'success')
        
        session.modified = True
        
        if request.form.get('slaughterService') == 'on' or request.form.get('processingService') == 'on':
            farm_services = animal.farm_animal.services
            
            if request.form.get('slaughterService') == 'on':
                slaughter_service = farm_services['klanje']
                app.logger.info(f'Odabrana usluga klanja: {slaughter_service}')
                slaughter_service_price_per_kg = slaughter_service[f'{animal.animal_category_id}']
                app.logger.info(f'Cena klanja po kg: {slaughter_service_price_per_kg}')
                
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
                
            flash('Uspešno ste dodali uslugu u korpu.', 'success')
        
        return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri dodavanju tova: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/add_animal_to_cart/<int:animal_id>')
def add_animal_to_cart(animal_id):
    try:
        animal = Animal.query.get_or_404(animal_id)
        
        if 'animals' not in session:
            session['animals'] = []
            
        if animal.id in [a['id'] for a in session['animals']]:
            flash('Ova životinja se već nalazi u korpi.', 'danger')
            return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
        
        new_animal = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
        new_animal['category'] = animal.animal_category.animal_category_name
        new_animal['subcategory'] = animal.animal_categorization.subcategory
        new_animal['race'] = animal.animal_race.animal_race_name
        new_animal['farm'] = animal.farm_animal.farm_name
        new_animal['location'] = animal.farm_animal.farm_city
        
        session['animals'].append(new_animal)
        session.modified = True
        
        flash('Uspešno ste dodali ovu životinju u korpu.', 'success')
        return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri dodavanju životinje u korpu: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/add_product_to_cart/<int:product_id>', methods=['POST'])
def add_product_to_cart(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        
        if 'products' not in session:
            session['products'] = []
            
        if product.id in [p['id'] for p in session['products']]:
            flash('Proizvod se već nalazi u korpi.', 'danger')
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
        session.modified = True
        
        flash('Uspešno ste dodali ovaj proizvod u korpu.', 'success')
        return redirect(url_for('marketplace.product_detail', product_id=product.id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri dodavanju proizvoda u korpu: {str(e)}')
        return render_template('errors/500.html'), 500


# @main.route('/add_delevery_to_cart', methods=['POST'])
# def add_delevery_to_cart():
    # pass


@main.route('/view_cart', methods=['GET', 'POST'])
def view_cart():
    try:
        route_name = request.endpoint
        app.logger.debug(f'Session pre provere: {session}')
        
        has_items = any([
            session.get('animals', []),
            session.get('products', []),
            session.get('fattening', []),
            session.get('services', [])
        ])
        
        if not has_items and 'delivery' in session:
            del session['delivery']
            session.modified = True
        
        app.logger.debug(f'Session posle provere: {session}')
        
        cart_contents = {
            'animals': session.get('animals', []),
            'products': session.get('products', []),
            'fattening': session.get('fattening', []),
            'services': session.get('services', []),
            'delivery': session.get('delivery', {'delivery_total': 0, 'delivery_status': False})
        }
        
        app.logger.debug(f'View cart sadržaj: {cart_contents}')
        
        has_items = any(
            len(items) > 0 if isinstance(items, list) else bool(items)
            for items in cart_contents.values()
        )
        
        if not has_items:
            flash('Korpa je prazna.', 'info')
            return render_template('view_cart.html', 
                                title='Korpa', 
                                route_name=route_name, 
                                animals=[],
                                products=[],
                                services=[],
                                fattening=[])
                                
        animals = cart_contents['animals']
        products = cart_contents['products']
        fattening = cart_contents['fattening']
        services = cart_contents['services']
        delivery = cart_contents['delivery']
        
        app.logger.debug(f'Delivery info: {delivery}')
        
        submit_button = 'nije_na_rate'
        if fattening:
            for f in fattening:
                if int(f.get('installment_options', 0)) > 1:
                    submit_button = 'na_rate'
                    break

        try:
            merchant_order_amount, installment_total, delivery_total = get_cart_total()
            app.logger.debug(f'Cart totals: merchant_order_amount={merchant_order_amount}, installment_total={installment_total}, delivery_total={delivery_total}')
        except Exception as e:
            app.logger.error(f'Greška pri računanju ukupne cene korpe: {str(e)}')
            flash('Došlo je do greške pri računanju ukupne cene. Molimo pokušajte ponovo.', 'danger')
            return render_template('errors/500.html'), 500
        
        if request.method == 'POST':
            app.logger.debug(f'POST DELIVERY: {request.form}')
            delivery_status = request.form.get('delivery_total') == 'on'
            session['delivery'] = {
                "delivery_total": delivery_total,
                "delivery_status": delivery_status
            }
            cart_contents['delivery'] = session['delivery']
            return redirect(url_for('main.view_cart'))
            
        if 'delivery' not in session:
            session['delivery'] = {
                "delivery_total": delivery_total,
                "delivery_status": False
            }
            cart_contents['delivery'] = session['delivery']
            
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
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri pregledu korpe: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/remove_animal_from_cart/<int:animal_id>')
def remove_animal_from_cart(animal_id):
    try:
        app.logger.info(f'Pokušaj uklanjanja životinje {animal_id} iz korpe')
        
        if 'animals' not in session or not isinstance(session.get('animals'), list):
            app.logger.warning('Korpa je prazna ili je došlo do greške sa sesijom')
            flash('Korpa je prazna ili je došlo do greške.', 'info')
            return redirect(url_for('main.view_cart'))
            
        try:
            animal = Animal.query.get(animal_id)
            if animal is None:
                app.logger.error(f'Životinja sa ID {animal_id} nije pronađena u bazi')
                flash('Životinja nije pronađena.', 'danger')
                return redirect(url_for('main.view_cart'))
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri pristupu bazi za životinju {animal_id}: {str(e)}')
            return render_template('errors/500.html'), 500

        session['animals'] = [animal for animal in session['animals'] if animal.get('id') != animal_id]

        if 'fattening' in session and isinstance(session.get('fattening'), list):
            session['fattening'] = [animal for animal in session['fattening'] if animal.get('id') != animal_id]

        if 'services' in session and isinstance(session.get('services'), list):
            session['services'] = [animal for animal in session['services'] if animal.get('id') != animal_id]

        session.modified = True
        
        app.logger.info(f'Životinja {animal_id} je uspešno uklonjena iz korpe')
        flash('Uspešno ste obrisali ovu životinju iz korpe.', 'success')
        return redirect(url_for('main.view_cart'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri uklanjanju životinje {animal_id} iz korpe: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/remove_product_from_cart/<int:product_id>')
def remove_product_from_cart(product_id):
    try:
        app.logger.info(f'Pokušaj uklanjanja proizvoda {product_id} iz korpe')
        
        if 'products' not in session or not isinstance(session.get('products'), list):
            app.logger.warning('Korpa je prazna ili je došlo do greške sa sesijom')
            flash('Korpa je prazna ili je došlo do greške.', 'info')
            return redirect(url_for('main.view_cart'))
            
        try:
            product = Product.query.get(product_id)
            if product is None:
                app.logger.error(f'Proizvod sa ID {product_id} nije pronađen u bazi')
                flash('Proizvod nije pronađen.', 'danger')
                return redirect(url_for('main.view_cart'))
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri pristupu bazi za proizvod {product_id}: {str(e)}')
            return render_template('errors/500.html'), 500

        session['products'] = [product for product in session['products'] if product.get('id') != product_id]
        session.modified = True
        
        app.logger.info(f'Proizvod {product_id} je uspešno uklonjen iz korpe')
        flash('Uspešno ste obrisali ovaj proizvod iz korpe.', 'success')
        return redirect(url_for('main.view_cart'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri uklanjanju proizvoda {product_id} iz korpe: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/remove_fattening_from_cart/<int:animal_id>')
def remove_fattening_from_cart(animal_id):
    try:
        app.logger.info(f'Pokušaj uklanjanja tova za životinju {animal_id} iz korpe')
        
        if 'fattening' not in session or not isinstance(session.get('fattening'), list):
            app.logger.warning('Korpa je prazna ili je došlo do greške sa sesijom')
            flash('Korpa je prazna ili je došlo do greške.', 'info')
            return redirect(url_for('main.view_cart'))
            
        try:
            animal = Animal.query.get(animal_id)
            if animal is None:
                app.logger.error(f'Životinja sa ID {animal_id} nije pronađena u bazi')
                flash('Životinja nije pronađena.', 'danger')
                return redirect(url_for('main.view_cart'))
                
            session['fattening'] = [animal for animal in session['fattening'] if animal.get('id') != animal_id]
            
            animal.wanted_weight = None
            db.session.commit()
            app.logger.info(f'Resetovana željena težina za životinju {animal_id}')
            
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri pristupu bazi za životinju {animal_id}: {str(e)}')
            return render_template('errors/500.html'), 500

        session.modified = True
        
        app.logger.info(f'Tov za životinju {animal_id} je uspešno uklonjen iz korpe')
        flash('Uspešno ste obrisali ovaj proizvod iz korpe.', 'success')
        return redirect(url_for('main.view_cart'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri uklanjanju tova za životinju {animal_id} iz korpe: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/remove_service_from_cart/<int:service_id>')
def remove_service_from_cart(service_id):
    try:
        app.logger.info(f'Pokušaj uklanjanja usluge {service_id} iz korpe')
        
        if 'services' not in session or not isinstance(session.get('services'), list):
            app.logger.warning('Korpa je prazna ili je došlo do greške sa sesijom')
            flash('Korpa je prazna ili je došlo do greške.', 'info')
            return redirect(url_for('main.view_cart'))
            
        try:
            animal = Animal.query.get(service_id)
            if animal is None:
                app.logger.error(f'Životinja sa ID {service_id} nije pronađena u bazi')
                flash('Životinja nije pronađena.', 'danger')
                return redirect(url_for('main.view_cart'))
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri pristupu bazi za životinju {service_id}: {str(e)}')
            return render_template('errors/500.html'), 500

        session['services'] = [service for service in session['services'] if service.get('id') != service_id]
        session.modified = True
        
        app.logger.info(f'Usluga za životinju {service_id} je uspešno uklonjena iz korpe')
        flash('Uspešno ste obrisali ovu uslugu iz korpe.', 'success')
        return redirect(url_for('main.view_cart'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri uklanjanju usluge {service_id} iz korpe: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/clear_cart')
def clear_cart():
    try:
        app.logger.info('Pokušaj čišćenja korpe')
        
        cart_items = {
            'animals': session.get('animals', []),
            'products': session.get('products', []),
            'fattening': session.get('fattening', []),
            'services': session.get('services', [])
        }
        
        has_items = any(
            len(items) > 0 for items in cart_items.values()
        )
        
        if not has_items:
            app.logger.info('Korpa je već prazna')
            flash('Korpa je već prazna.', 'info')
            return redirect(url_for('main.view_cart'))
            
        try:
            # Resetovanje wanted_weight za životinje u tovu
            if cart_items['fattening']:
                animal_ids = [animal.get('id') for animal in cart_items['fattening']]
                animals = Animal.query.filter(Animal.id.in_(animal_ids)).all()
                
                for animal in animals:
                    animal.wanted_weight = None
                    
                db.session.commit()
                app.logger.info(f'Resetovana željena težina za životinje: {animal_ids}')
                
        except SQLAlchemyError as e:
            app.logger.error(f'Greška pri resetovanju željene težine životinja: {str(e)}')
            return render_template('errors/500.html'), 500
            
        clear_cart_session()
        app.logger.info('Korpa je uspešno očišćena')
        flash('Uspešno ste očistili korpu.', 'success')
        return redirect(url_for('main.view_cart'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri čišćenju korpe: {str(e)}')
        return render_template('errors/500.html'), 500


@main.route('/terms_and_conditions')
def terms_and_conditions():
    return render_template('terms_and_conditions.html')


@main.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@main.route('/cookie_policy')
def cookie_policy():
    return render_template('cookie_policy.html')