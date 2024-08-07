from flask import Blueprint, jsonify, session
from flask import  render_template, flash, redirect, url_for, request
from flask_login import current_user
from mojestado import app
from mojestado.main.functions import clear_cart_session
from mojestado.models import FAQ, Animal, AnimalCategory, Product


main = Blueprint('main', __name__)


@main.route('/')
@main.route('/home')
def home():
    faq = FAQ.query.all()
    faq = [question for question in faq if question.id < 4]
    animal_categories = AnimalCategory.query.all()
    return render_template('home.html', title='Početna strana',
                            faq=faq,
                            animal_categories=animal_categories)


@main.route('/about')
def about():
    return render_template('about.html', title='O portalu')


@main.route('/faq', methods=['GET', 'POST'])
def faq():
    faq = FAQ.query.all()
    if request.method == 'POST':
        print(f'{request.form=}')
        flash('Uspesno ste poslali pitanje!', 'success')
        #! razviti funkciju koja će da pošalje mejl sa pitanjem vlasniku portala
        return render_template('faq.html', title='Najžešće postavljena pitanja',
                                faq=faq)
    return render_template('faq.html', title='Najčešće postavljena pitanja',
                            faq=faq)


@main.route('/contact')
def contact():
    return render_template('contact.html', title='Kontakt strana')


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
    animal_id = request.form.get('animalId')
    animal = Animal.query.get_or_404(animal_id)
    add_animal_to_cart(animal_id)
    
    if 'fattening' not in session:
        session['fattening'] = []
    
    new_fattening = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
    new_fattening['category'] = animal.animal_category.animal_category_name
    new_fattening['subcategory'] = animal.animal_categorization.subcategory
    new_fattening['race'] = animal.animal_race.animal_race_name
    new_fattening['farm'] = animal.farm_animal.farm_name
    new_fattening['location'] = animal.farm_animal.farm_city
    new_fattening['current_weight'] = request.form.get('currentWeight')
    new_fattening['desired_weight'] = request.form.get('desiredWeight')
    new_fattening['fattening_price'] = request.form.get('calculatedPrice')
    new_fattening['feeding_days'] = request.form.get('feedingDays')
    print(f'**** {request.form.get("installmentPayment")=}')
    if request.form.get('installmentPayment') == 'on':
        new_fattening['installment_options'] = request.form.get('installmentOptions')
    else:
        new_fattening['installment_options'] = 1
    new_fattening['installment_price'] = request.form.get('installmentPrice')
    
    session['fattening'].append(new_fattening)
    session.modified = True
    
    flash('Uspesno ste dodali ovu zivotinju u korpu za tov!', 'success')
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
    new_product['subcategory'] = product.product_subcategory_product.product_subcategory_name
    new_product['section'] = product.product_section.product_section_name
    new_product['farm'] = product.farm_product.farm_name
    new_product['location'] = product.farm_product.municipality_farm.municipality_name
    new_product['quantity'] = request.form['quantity']
    new_product['total_price'] = float(request.form['quantity']) * float(product.product_price_per_unit)

    session['products'].append(new_product)
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste dodali ovaj proizvod u korpu!', 'success')
    return redirect(url_for('marketplace.product_detail', product_id=product.id))


@main.route('/view_cart')
def view_cart():
    animals = session.get('animals', [])
    products = session.get('products', [])
    fattening = session.get('fattening', [])
    services = session.get('services', [])
    
    if not animals and not products:
        flash('Korpa je prazna!', 'info')
        return render_template('view_cart.html', animals=[], products=[])
    #! ovo treba prilogoditi, ukoliko se u korpi nalazi tov koji se prodaje na rate - možda sutra ne bude fattening već neki drugi naziv
    #! ovo treba prilogoditi, ukoliko se u korpi nalazi tov koji se prodaje na rate - možda sutra ne bude fattening već neki drugi naziv
    #! ovo treba prilogoditi, ukoliko se u korpi nalazi tov koji se prodaje na rate - možda sutra ne bude fattening već neki drugi naziv
    #! ovo treba prilogoditi, ukoliko se u korpi nalazi tov koji se prodaje na rate - možda sutra ne bude fattening već neki drugi naziv
    if not 'fattening' in session:
        print(f'*** debug fattening nije u sessiji')
        submit_button = 'nije_na_rate'
    else:
        print(f'{session["fattening"]=}')
        for f in session['fattening']:
            if int(f['installment_options']) > 1:
                submit_button = 'na_rate'
                break
            else:
                submit_button = 'nije_na_rate'

    return render_template('view_cart.html', 
                            animals=animals, 
                            products=products, 
                            submit_button=submit_button, 
                            fattening=fattening,
                            services=services)


@main.route('/remove_animal_from_cart/<int:animal_id>')
def remove_animal_from_cart(animal_id):
    if 'animals' not in session:
        flash('Korpa je prazna!', 'info')
        return redirect(url_for('main.view_cart'))
    
    session['animals'] = [animal for animal in session['animals'] if animal['id'] != animal_id]
    session['fattening'] = [animal for animal in session['fattening'] if animal['id'] != animal_id]
    session['services'] = [animal for animal in session['services'] if animal['id'] != animal_id]
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste obrisali ovu zivotinju iz korpe!', 'success')
    return redirect(url_for('main.view_cart'))


@main.route('/remove_product_from_cart/<int:product_id>')
def remove_product_from_cart(product_id):
    if 'products' not in session:
        flash('Korpa je prazna!', 'info')
        return redirect(url_for('main.view_cart'))
    
    session['products'] = [product for product in session['products'] if product['id'] != product_id]
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste obrisali ovaj proizvod iz korpe!', 'success')
    return redirect(url_for('main.view_cart'))


@main.route('/remove_fattening_from_cart/<int:animal_id>')
def remove_fattening_from_cart(animal_id):
    if 'fattening' not in session:
        flash('Korpa je prazna!', 'info')
        return redirect(url_for('main.view_cart'))
    
    session['fattening'] = [animal for animal in session['fattening'] if animal['id'] != animal_id]
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste obrisali ovaj proizvod iz korpe!', 'success')
    return redirect(url_for('main.view_cart'))


@main.route('/remove_service_from_cart/<int:service_id>')
def remove_service_from_cart(service_id):
    if 'services' not in session:
        flash('Korpa je prazna!', 'info')
        return redirect(url_for('main.view_cart'))
    
    session['services'] = [service for service in session['services'] if service['id'] != service_id]
    session.modified = True  # Obezbeđuje da Flask zna da je sesija promenjena

    flash('Uspesno ste obrisali ovaj proizvod iz korpe!', 'success')
    return redirect(url_for('main.view_cart'))


@main.route('/clear_cart')
def clear_cart():
    clear_cart_session()
    flash('Korpa je obrisana!', 'info')
    return redirect(url_for('main.view_cart'))
