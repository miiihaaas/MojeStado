import datetime
import json
import os
from flask import Blueprint, app, current_app, jsonify
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db
from mojestado.animals.functions import get_animal_categorization
from mojestado.users.forms import AddAnimalForm, AddProductForm, EditProfileForm, LoginForm, RequestResetForm, ResetPasswordForm, RegistrationUserForm, RegistrationFarmForm
from mojestado.users.functions import farm_profile_completed_check, send_contract, send_conformation_email
from mojestado.models import Animal, AnimalCategorization, AnimalCategory, AnimalRace, Product, ProductCategory, ProductSection, ProductSubcategory, User, Farm, Municipality, InvoiceItems
from flask_login import login_user, login_required, logout_user, current_user


users = Blueprint('users', __name__)


@users.route("/register_farm", methods=['GET', 'POST'])
def register_farm(): #! Registracija poljoprivrednog gazdinstva
    form = RegistrationFarmForm()
    form.municipality.choices = [(municipality.id, f'{municipality.municipality_name} ({municipality.municipality_zip_code})') for municipality in db.session.query(Municipality).all()]
    if form.validate_on_submit():
        municipality = Municipality.query.get(form.municipality.data)
        user = User(email=form.email.data, 
                    password=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
                    name=form.name.data,
                    surname=form.surname.data,
                    address=form.address.data,
                    city=form.city.data,
                    zip_code=municipality.municipality_zip_code,
                    phone=form.phone.data,
                    PBG=form.pbg.data,
                    JMBG=form.jmbg.data,
                    MB=form.mb.data,
                    user_type='farm_inactive', #! definisati tipove korisnika (farm, user, admin), razraditi za farm neaktivan dok ne potpiše ugovor, pa posle toga ga admin premesti u aktivan
                    registration_date=datetime.date.today()
                    )
        db.session.add(user)
        db.session.commit()
        farm = Farm(farm_name="Definisati naziv farme",
                    farm_address=form.address.data,
                    farm_city=form.city.data,
                    farm_zip_code=municipality.municipality_zip_code,
                    farm_municipality_id=municipality.id,
                    farm_phone=form.phone.data,
                    farm_description="Definisati opis farme",
                    registration_date=datetime.date.today(),
                    user_id=user.id,
                    farm_image_collection=[],
                    services={"klanje": {"1": "0", "2": "0", "3": "0", "4": "0", "5": "0", "6": "0", "7": "0", "8": "0"}, "obrada": {"1": "0", "2": "0", "3": "0"}})
        db.session.add(farm)
        db.session.commit()
        flash(f'Uspesno ste poslali zahtev za registraciju. Na Vaš mejl je poslat ugovor pomoću koga se završava registracija.', 'success')
        #! napisati kod za generisanje ugovora i slanje ugovora na mejl
        # send_contract(user) #! aktivirati ovaj kod kada se postavi funkcionalnost slanja mejla
        return redirect(url_for('main.home'))
    elif request.method == 'GET':
        return render_template('register_farm.html', 
                                title='Registracija poljoprivrednog gazdinstva',
                                form=form)
    else:
        flash(f'Doslo je do greske: {form.errors}. Molimo pokusajte ponovo.', 'danger')
        return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva',form=form)


@users.route("/register_user", methods=['GET', 'POST'])
def register_user(): #! Registracija korisnika
    form = RegistrationUserForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, 
                    password=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
                    name=form.name.data,
                    surname=form.surname.data,
                    address=form.address.data,
                    city=form.city.data,
                    zip_code=form.zip_code.data,
                    JMBG=form.jmbg.data,
                    user_type='user', #! definisati tipove korisnika (farm, user, admin), razraditi za farm neaktivan dok ne potpiše ugovor, pa posle toga ga admin premesti u aktivan
                    registration_date = datetime.date.today()
                    )
        db.session.add(user)
        db.session.commit()
        flash(f'Uspesno ste se poslali zahtev za registraciju. Na Vašu mejl adresu je poslat link za potvrdu registracije.', 'success')
        #! nastaviti kod za slanje mejla korisniku
        # send_conformation_email(user) #! aktiviraj ovaj kod kada se postavi funkcionalnost slanja mejla
        return redirect(url_for('main.home'))
    return render_template('register_user.html', title='Registracija korisnika',
                            form=form)

@users.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        print(f'već je ulogovan korisnik : {current_user=}')
        return redirect(url_for('main.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        print(f'user: {user}')
        print(f'password form hash: {bcrypt.generate_password_hash(form.password.data).decode("utf-8")}')
        print(f'password check: {bcrypt.check_password_hash(user.password, form.password.data)}')
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Dobro došli, {user.name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash(f'Email ili lozinka nisu odgovarajući.', 'danger')
    return render_template('login.html', title='Prijavljivanje', form=form, legend='Prijavljivanje')


@users.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))


@users.route("/my_profile/<user_id>", methods=['GET', 'POST'])
def my_profile(user_id): #! Moj nalog za korisnika
    user = User.query.get_or_404(user_id)
    if current_user.user_type == 'admin':
        flash('Admin pregleda druga PG', 'info')
        return render_template('my_profile.html', title='Moj nalog', user=user)
    elif current_user.id != user.id:
        flash('Nemate pravo pristupa ovoj stranici.', 'danger')
        return redirect(url_for('main.home'))
    print(f'current_user: {current_user}')
    if current_user.user_type == 'user':
        print(f'current_user: {current_user}')
        if request.method == 'POST':
            user.address = request.form.get('addressInput')
            db.session.commit()
            flash('Uspesno ste izmenili adresu.', 'success')
            return redirect(url_for('users.my_profile', user_id=user.id))
        return render_template('my_profile.html', title='Moj nalog', user=user)
    
    
    elif current_user.user_type == 'farm_active':
        farm = Farm.query.filter_by(user_id=user.id).first()
        farm_profile_completed = farm_profile_completed_check(farm)
        return render_template('my_profile.html', title='Moj nalog', 
                                user=user,
                                farm=farm,
                                farm_profile_completed=farm_profile_completed)
    elif current_user.user_type == 'farm_inactive':
        flash('Još uvek nije aktivirana vaše poljoprivredno gazdinstvo.', 'info')
        return render_template('my_profile.html', title='Moj nalog', user=user)


#! ispod je za farmera !#
#! ispod je za farmera !#
#! ispod je za farmera !#


@users.route("/my_farm/<int:farm_id>", methods=['GET', 'POST'])
def my_farm(farm_id):#! Moj nalog za poljoprivrednog gazdinstva
    farm = Farm.query.get_or_404(farm_id)
    # definiše listu kategorija koja se koristi za label u formi usluga
    animal_categories = {str(category.id): category.animal_category_name for category in AnimalCategory.query.all()}
    if current_user.id != farm.user_id:
        flash('Nemate pravo pristupa ovoj stranici.', 'danger')
        return redirect(url_for('main.home'))
    farm_profile_completed = farm_profile_completed_check(farm)
    return render_template('my_farm.html', title='Moj nalog', 
                            user=current_user,
                            farm=farm,
                            farm_profile_completed=farm_profile_completed,
                            animal_categories=animal_categories)


@users.route("/my_flock/<int:farm_id>", methods=['GET', 'POST'])
def my_flock(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    if current_user.id != farm.user_id:
        flash('Nemate pravo pristupa ovoj stranici.', 'danger')
        return redirect(url_for('main.home'))
    animals = Animal.query.filter_by(farm_id=farm_id).filter_by(active=True).all()
    fattening_animals = Animal.query.filter_by(farm_id=farm_id).filter_by(fattening=True).all()
    if len(farm.farm_description) < 100:
        flash('Opis poljoprivrednog gazdinstva mora biti duši od 100 znakova', 'danger')
        return redirect(url_for('users.my_farm', farm_id=farm.id))
    form = AddAnimalForm()
    categories_query = AnimalCategory.query.all()
    categories_list = list(dict.fromkeys((category.id, category.animal_category_name) for category in categories_query))
    form.category.choices = categories_list
    print(f'{categories_list=}')
    if request.method == 'POST':
        print(f'submitovana je forma {request.form=}')
        print(f'submitovana je forma {form.category.data=}')
        print(f'submitovana je forma {form.intended_for.data=}')
        print(f'submitovana je forma {form.weight.data=}')
        print(f'submitovana je forma {form.subcategory.data=}')
        if form.subcategory.data:
            subcategory = form.subcategory.data
        else:
            subcategory = None
        print(f'pre nego što se pokrene get_animal_categorization: {subcategory=}')
        category_id = get_animal_categorization(form.category.data, form.intended_for.data, form.weight.data, subcategory)
        if not category_id:
            flash('Kategorija ne postoji', 'danger')
            return redirect(url_for('users.my_flock', farm_id=farm.id))
        print(f'category_id: {category_id}')
        animals = Animal.query.all()
        if len(animals) > 0:
            animal_max_id = max([animal.id for animal in animals]) + 1
        else:
            animal_max_id = 1
            
        print(f'{form.cardboard.data=}')
        new_animal = Animal(
            animal_id=f'{farm.id:05}-{int(form.category.data):02}-{animal_max_id:06}',
            animal_category_id = form.category.data,
            animal_categorization_id=category_id,
            animal_race_id = form.race.data,
            animal_gender = form.animal_gender.data,
            measured_weight=form.weight.data,
            measured_date = datetime.datetime.now(),
            current_weight=form.weight.data,
            price_per_kg=form.price.data,
            total_price=form.price.data * form.weight.data,
            insured = form.insured.data,
            organic_animal = form.organic.data,
            cardboard = None,
            intended_for=form.intended_for.data,
            farm_id=farm.id,
            fattening = False, #! podrazumevana vrednost je False, a kad kupac želi da se tovi onda se postavlja True
            active = True
        )
        db.session.add(new_animal)
        db.session.flush()
        
        if form.cardboard.data:
            filename = f'{new_animal.id:06}.pdf'
            filepath = os.path.join(current_app.root_path, 'static', 'cardboards', filename)
            form.cardboard.data.save(filepath)
            new_animal.cardboard = filename
        
        db.session.commit()
        flash('Uspesno ste dodali životinju', 'success')
        return redirect(url_for('users.my_flock', farm_id=farm.id))
    return render_template('my_flock.html', title='Moj stado', user=current_user,
                            animals=animals,
                            fattening_animals=fattening_animals,
                            form=form,
                            farm=farm)


@users.route("/remove_animal/<int:animal_id>", methods=['POST'])
def remove_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    animal.active = False
    db.session.commit()
    flash('Uspesno ste uklonili životinju iz ponude', 'success')
    return redirect(url_for('users.my_flock', farm_id=animal.farm_id))


@users.route("/edit_animal/<int:animal_id>", methods=['GET', 'POST'])
def edit_animal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    print(f'***{animal=}')
    animal.animal_gender = request.form.get('animal_gender')
    animal.current_weight = request.form.get('weight')
    animal.price_per_kg = request.form.get('price')
    animal.total_price = float(animal.price_per_kg) * float(animal.current_weight)
    print(f'{request.form.get("insured")=}')
    print(f'{request.form.get("organic")=}')
    print(f'{request.files.get("cardboard")=}')
    if request.form.get('insured') == 'y':
        animal.insured = True
    else:
        animal.insured = False
    if request.form.get('organic') == 'y':
        animal.organic_animal = True
    else:
        animal.organic_animal = False
    if request.files.get('cardboard'):
        filename = f'{animal.id:06}.pdf'
        filepath = os.path.join(current_app.root_path, 'static', 'cardboards', filename)
        request.files.get('cardboard').save(filepath)
        animal.cardboard = filename
    
    db.session.commit()
    flash('Uspesno ste izmenili podatke životinje', 'success')
    
    return redirect(url_for('users.my_flock', farm_id=animal.farm_id))


@users.route("/save_services", methods=['POST'])
def save_services():
    farm_id = request.form.get('farm_id')
    farm = Farm.query.get(farm_id)
    print(f'request.form: {request.form.keys()=}')
    print(f'request.form: {request.form.to_dict()=}')
    for key, value in request.form.to_dict().items():
        try:
            float_value = float(value)
            print(f'{key=} {value=}')
        except ValueError:
            print(f'Cannot convert value for key {key} to float: {value}')
            flash('Neuspesno sacuvano', 'danger')
            redirect(url_for('users.my_farm', farm_id=farm_id))
            
    service_dict = {
        "klanje": {
            "1": request.form.get('klanje_1'),
            "2": request.form.get('klanje_2'),
            "3": request.form.get('klanje_3'),
            "4": request.form.get('klanje_4'),
            "5": request.form.get('klanje_5'),
            "6": request.form.get('klanje_6'),
            "7": request.form.get('klanje_7'),
            "8": request.form.get('klanje_8'),
        },
        "obrada": {
            "1": request.form.get('obrada_1'),
            "2": request.form.get('obrada_2'),
            "3": request.form.get('obrada_3'),
        }
    }
    print(f'{service_dict=}')
    # farm.services = json.dumps(service_dict)
    farm.services = service_dict
    db.session.commit()
    return redirect(url_for('users.my_farm', farm_id=farm_id))


@users.route("/get_animal_subcategories", methods=['GET'])
def get_animal_subcategories():
    category = request.args.get('category')
    subcategories = AnimalCategorization.query.filter_by(animal_category_id=category, intended_for='priplod').all()
    subcategories_options = [{'value': subcategory.subcategory, 'text': subcategory.subcategory} for subcategory in subcategories]
    print(f'subcategories_options: {subcategories_options}')
    return jsonify(subcategories_options)


@users.route("/get_races", methods=['GET'])
def get_races():
    category = request.args.get('category')
    print(f'get_races: {category=}')
    races = AnimalRace.query.filter_by(animal_category_id=category).all()
    races_options = [{'value': race.id, 'text': race.animal_race_name} for race in races]
    print(f'races_options: {races_options}')
    return jsonify(races_options)



@users.route("/my_market/<int:farm_id>", methods=['GET', 'POST'])
def my_market(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    if current_user.id != farm.user_id:
        flash('Nemate pravo pristupa ovoj stranici.', 'danger')
        return redirect(url_for('main.home'))
    products = Product.query.filter_by(farm_id=farm_id).all()
    
    invoice_items = InvoiceItems.query.filter_by(farm_id=farm_id).filter_by(invoice_item_type=1).all()
    for item in invoice_items:
        print(f'** {type(item.invoice_item_details)=} {item=}')
    
    form = AddProductForm()
    form.category.choices = [(category.id, category.product_category_name) for category in ProductCategory.query.all()]
    if request.method == 'POST':
        print(f'{form.data=}')
        new_product = Product(
            product_image = 'default.jpg',
            product_category_id = int(form.category.data),
            product_subcategory_id = int(form.subcategory.data),
            product_section_id = int(form.section.data),
            product_name = form.product_name.data,
            product_description = form.product_description.data,
            unit_of_measurement = form.unit_of_measurement.data,
            weight_conversion = float(form.weight_conversion.data) if form.unit_of_measurement.data == 'kom' else 1.0,
            product_price_per_unit = float(form.product_price_per_unit.data),
            product_price_per_kg = float(form.product_price_per_unit.data) / float(form.weight_conversion.data) if form.unit_of_measurement.data == 'kom' else float(form.product_price_per_unit.data),
            organic_product = form.organic_product.data,
            quantity = float(form.quantity.data),
            farm_id = farm.id,
            product_image_collection = []            
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Uspesno ste dodali novi proizvod', 'success')
        return redirect(url_for('users.my_market', farm_id=farm_id))
    return render_template('my_market.html', title='Moj prodavnica', 
                            user=current_user,
                            products=products,
                            invoice_items=invoice_items,
                            form=form,
                            farm=farm)


@users.route("/get_product_subcategories", methods=['GET'])
def get_product_subcategories():
    category = request.args.get('category')
    print(f'get_product_subcategories: {category=}')
    subcategories = ProductSubcategory.query.filter_by(product_category_id=category).all()
    subcategories_options = [{'value': subcategory.id, 'text': subcategory.product_subcategory_name} for subcategory in subcategories]
    print(f'subcategories_options: {subcategories_options}')
    return jsonify(subcategories_options)


@users.route("/get_product_sections", methods=['GET'])
def get_product_sections():
    subcategory = request.args.get('subcategory')
    print(f'get_product_sections: {subcategory=}')
    sections = ProductSection.query.filter_by(product_subcategory_id=subcategory).all()
    sections_options = [{'value': section.id, 'text': section.product_section_name} for section in sections]
    print(f'sections_options: {sections_options}')
    return jsonify(sections_options)


#! ispod je za user !#
#! ispod je za user !#
#! ispod je za user !#


@users.route("/my_fattening/<int:user_id>", methods=['GET', 'POST'])
def my_fattening(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('my_fattening.html', title='Moj stado', user=user)


@users.route("/my_shop/<int:user_id>", methods=['GET', 'POST'])
def my_shop(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('my_shop.html', title='Moj prodavnica', user=user)


#! ispod je za admin !#
#! ispod je za admin !#
#! ispod je za admin !#

@users.route("/settings", methods=['GET', 'POST'])
def settings():
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    return render_template('settings.html', title='Settings')


@users.route("/admin_view_farms", methods=['GET', 'POST'])
def admin_view_farms():
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    farms = Farm.query.all()
    return render_template('admin_view_farms.html', 
                            farms=farms, 
                            title='Prikaz PG')


@users.route("/admin_view_users", methods=['GET', 'POST'])
def admin_view_users():
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    from sqlalchemy import or_

    users = User.query.filter(or_(User.user_type == 'user', User.user_type == 'guest')).all()

    return render_template('admin_view_users.html', 
                            users=users, 
                            title='Prikaz korisnika')


@users.route("/admin_view_purchases", methods=['GET', 'POST'])
def admin_view_purchases():
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    # purchases = Purchase.query.all() #! dodati klasu u models.py
    return render_template('admin_view_purchases.html', 
                            purchases=[], 
                            title='Prikaz narudžbi')


@users.route("/admin_view_overview", methods=['GET', 'POST'])
def admin_view_overview():
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    users = User.query.filter_by(user_type='user').all()
    return render_template('admin_view_overview.html',
                            users=users,
                            title='Pregled stanja')


@users.route("/admin_view_overview_user/<int:user_id>", methods=['GET', 'POST'])
def admin_view_overview_user(user_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    user = User.query.get_or_404(user_id)
    return render_template('admin_view_overview_user.html',
                            user=user,
                            title='Pregled stanja korisnika')


@users.route("/admin_view_slips", methods=['GET', 'POST'])
def admin_view_slips():
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    return render_template('admin_view_slips.html',
                            title='Pregled PG')


@users.route("/admin_edit_profile/<int:user_id>", methods=['GET', 'POST'])
def admin_edit_profile(user_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    user = User.query.get_or_404(user_id)
    if user.user_type != 'user':
        flash('Nije moguće promeniti profil gosta.', 'danger')
        return redirect(url_for('main.home'))
    form = EditProfileForm()
    if form.validate_on_submit():
        print('form validated')
        user.name = form.name.data
        user.surname = form.surname.data
        user.email = form.email.data
        user.address = form.address.data
        user.zip_code = form.zip_code.data
        user.city = form.city.data
        user.jmbg = form.jmbg.data
        db.session.commit()
        flash('Uspešno ste sačuvali izmene na profilu.', 'success')
        return redirect(url_for('users.admin_edit_profile', user_id=user.id))
    print(f'form not validated')
    form.name.data = user.name
    form.surname.data = user.surname
    form.email.data = user.email
    form.address.data = user.address
    form.zip_code.data = user.zip_code
    form.city.data = user.city
    form.jmbg.data = user.JMBG
    return render_template('admin_edit_profile.html',
                            user=user,
                            title='Uredi profil',
                            form=form)


@users.route("/admin_remove_user/<int:user_id>", methods=['GET', 'POST'])
def admin_remove_user(user_id):
    if not current_user.is_authenticated:
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    user = User.query.get_or_404(user_id)
    user.user_type = 'user_removed'
    db.session.commit()
    flash('Uspesno ste obrisali korisnika', 'success')
    return redirect(url_for('users.admin_view_users'))