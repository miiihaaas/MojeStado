import datetime
from flask import Blueprint, jsonify
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail
from mojestado.animals.routes import get_animal_categorization
from mojestado.users.forms import AddAnimalForm, LoginForm, RequestResetForm, ResetPasswordForm, RegistrationUserForm, RegistrationFarmForm
from mojestado.models import Animal, AnimalCategorization, AnimalCategory, AnimalRace, User, Farm, Municipality
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message

from mojestado.users.functions import farm_profile_completed_check


users = Blueprint('users', __name__)


def send_contract(user):
    msg = Message(subject='Ugovor o pristupu', 
                    sender='Wqo2M@example.com', 
                    recipients=[user.email], 
                    bcc=['Wqo2M@example.com'], 
                    attachments=[])
    msg.body = 'Ugovor o pristupu'
    mail.send(msg)


def send_conformation_email(user):
    msg = Message(subject='Registracija korisnika', 
                    sender='Wqo2M@example.com', 
                    recipients=[user.email], 
                    bcc=['Wqo2M@example.com'], 
                    attachments=[])
    msg.body = f'Da bi ste dovršili registraciju korisnickog naloga, kliknite na sledeći link: {url_for("users.confirm_email", token=user.get_reset_token(), _external=True)}'
    mail.send(msg)


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
                    user_id=user.id)
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
                    user_type='user' #! definisati tipove korisnika (farm, user, admin), razraditi za farm neaktivan dok ne potpiše ugovor, pa posle toga ga admin premesti u aktivan
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
    if current_user.id != user.id:
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
    elif current_user.user_type == 'admin':
        return render_template('my_profile.html', title='Moj nalog', user=user)
    
    
    elif current_user.user_type == 'farm_active':
        farm = Farm.query.filter_by(user_id=user.id).first()
        farm_profile_completed = farm_profile_completed_check(farm)
        return render_template('my_profile.html', title='Moj nalog', 
                                user=user,
                                farm=farm,
                                farm_profile_completed=farm_profile_completed)
    elif current_user.user_type == 'farm_inactive':
        return render_template('my_profile.html', title='Moj nalog', user=user)


#! ispod je za farmera !#
#! ispod je za farmera !#
#! ispod je za farmera !#


@users.route("/my_farm/<int:farm_id>", methods=['GET', 'POST'])
def my_farm(farm_id):#! Moj nalog za poljoprivrednog gazdinstva
    farm = Farm.query.get_or_404(farm_id)
    if current_user.id != farm.user_id:
        flash('Nemate pravo pristupa ovoj stranici.', 'danger')
        return redirect(url_for('main.home'))
    farm_profile_completed = farm_profile_completed_check(farm)
    return render_template('my_farm.html', title='Moj nalog', 
                            user=current_user,
                            farm=farm,
                            farm_profile_completed=farm_profile_completed)


@users.route("/my_flock/<int:farm_id>", methods=['GET', 'POST'])
def my_flock(farm_id):
    animals = Animal.query.filter_by(farm_id=farm_id).all()
    fattening_animals = [animal for animal in animals if animal.fattening == True]
    farm = Farm.query.get_or_404(farm_id)
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
        new_animal = Animal(
            animal_id=form.animal_id.data,
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
            cardboard = 'test',
            intended_for=form.intended_for.data,
            farm_id=farm.id,
            fattening = False #! podrazumevana vrednost je False, a kad kupac želi da se tovi onda se postavlja True
        )
        db.session.add(new_animal)
        db.session.commit()
        flash('Uspesno ste dodali životinju', 'success')
        return redirect(url_for('users.my_flock', farm_id=farm.id))
    return render_template('my_flock.html', title='Moj stado', user=current_user,
                            animals=animals,
                            fattening_animals=fattening_animals,
                            form=form,
                            farm=farm)


@users.route("/get_subcategories", methods=['GET'])
def get_subcategories():
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
    return render_template('my_market.html', title='Moj prodavnica', user=current_user,
                            farm=farm)


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