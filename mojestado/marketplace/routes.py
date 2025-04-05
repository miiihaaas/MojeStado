import json
import os
from flask import Blueprint, request
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user, login_required
from mojestado import app, db
from mojestado.models import Animal, AnimalCategorization, AnimalCategory, Farm, Municipality, Product, ProductCategory, ProductSection, ProductSubcategory, User
from sqlalchemy import func


marketplace = Blueprint('marketplace', __name__)


@marketplace.route('/livestock_market/<int:animal_category_id>', methods=['GET', 'POST'])
def livestock_market(animal_category_id):
    """
    Prikazuje pijacu stoke sa filterima za pretragu.
    
    Args:
        animal_category_id (int): ID kategorije životinja (0 za sve kategorije)
        
    Returns:
        str: Renderovan HTML template sa podacima o životinjama
        
    Note:
        Funkcija podržava filtriranje po:
        - Opštinama
        - Organskoj proizvodnji
        - Osiguranju
        - Potkategorijama životinja
        - Masama
    """
    try:
        app.logger.debug(f'Pristup pijaci stoke za kategoriju: {animal_category_id}')
        
        # Učitavanje osnovnih podataka
        route_name = request.endpoint
        municipality_filter_list = Municipality.query.all()
        animal_categories = AnimalCategory.query.all()
        
        # Ako je kategorija 0, prikaži samo osnovni template
        if animal_category_id == 0:
            app.logger.info('Prikazujem osnovni template za pijacu stoke')
            return render_template('marketplace/livestock_market.html', 
                                title='Živa vaga',
                                route_name=route_name, 
                                animal_categories=animal_categories, 
                                municipality_filter_list=municipality_filter_list,
                                animal_category_id=animal_category_id,
                                selected_municipality=[])
        
        # Učitavanje podataka za specifičnu kategoriju
        try:
            animal_category = AnimalCategory.query.get_or_404(animal_category_id)
            app.logger.debug(f'Učitana kategorija: {animal_category.animal_category_name}')
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kategorije {animal_category_id}: {str(e)}')
            flash('Kategorija nije pronađena.', 'danger')
            return redirect(url_for('marketplace.livestock_market', animal_category_id=0))
            
        # Učitavanje potkategorija i životinja
        animal_subcategories = AnimalCategorization.query.filter_by(animal_category_id=animal_category_id).all()
        animals = Animal.query.filter_by(animal_category_id=animal_category_id, active=True).all()
        
        # Podešavanje filtera za masu
        weight_filter = False
        mass_filters = None
        if animal_category.mass_filters:
            weight_filter = True
            mass_filters = list(animal_category.mass_filters.keys())
            app.logger.debug(f'Postavljeni filteri za masu: {mass_filters}')
            
        # Inicijalizacija osnovnih vrednosti
        selected_municipality = []
        organic_filter = None
        insure_filter = None
        active_subcategories = []
            
        if request.method == 'POST':
            app.logger.debug('Obrada POST zahteva za filtere')
            
            # Obrada filtera za opštine
            selected_municipality = request.form.getlist('municipality')
            if '0' in selected_municipality:
                selected_municipality.remove('0')
                
            # Obrada ostalih filtera
            organic_filter = request.form.get('organic_filter')
            insure_filter = request.form.get('insure_filter')
            
            # Obrada filtera za potkategorije
            active_subcategories = [int(key.split('_')[1]) 
                                    for key, value in request.form.items() 
                                    if key.startswith('subcategory_') and value == 'on' and key.split('_')[1].isdigit()]
            
            # Primena filtera na životinje
            if organic_filter == 'on':
                animals = [animal for animal in animals if animal.organic_animal]
            if insure_filter == 'on':
                animals = [animal for animal in animals if animal.insured]
            if active_subcategories:
                animals = [animal for animal in animals if animal.animal_categorization_id in active_subcategories]
                
            # Obrada filtera za masu
            active_mass_filters = [key.split('_')[1] 
                                  for key, value in request.form.items() 
                                  if key.startswith('subcategory_') and value == 'on' and key.split('_')[1] in mass_filters]
            
            # Primena filtera za masu
            if active_mass_filters and mass_filters:
                filtered_animals = []
                for animal in animals:
                    for mass_range in active_mass_filters:
                        # Parsiranje stringa opsega mase
                        if mass_range == '0-15kg':
                            min_mass = 0
                            max_mass = 15
                        elif mass_range == '15kg-30kg':
                            min_mass = 15
                            max_mass = 30
                        elif mass_range == '30kg-80kg':
                            min_mass = 30
                            max_mass = 80
                        elif mass_range == '80kg-120kg':
                            min_mass = 80
                            max_mass = 120
                        elif mass_range == '120kg-200kg':
                            min_mass = 120
                            max_mass = 200
                        elif mass_range == '200kg+':
                            min_mass = 200
                            max_mass = float('inf')
                        else:
                            # Pokušaj da parsira string u formatu 'min-max' ili 'min+'
                            try:
                                if '-' in mass_range:
                                    # Format: 'min-max'
                                    parts = mass_range.replace('kg', '').split('-')
                                    min_mass = float(parts[0])
                                    max_mass = float(parts[1])
                                elif '+' in mass_range:
                                    # Format: 'min+'
                                    min_mass = float(mass_range.replace('kg+', ''))
                                    max_mass = float('inf')
                                else:
                                    # Nepoznat format, preskači
                                    continue
                            except (ValueError, IndexError):
                                # Ako ne možemo da parsiramo, preskači ovaj filter
                                app.logger.warning(f'Nije moguće parsirati opseg mase: {mass_range}')
                                continue
                        
                        # Provera da li je masa životinje u izabranom opsegu
                        if min_mass <= animal.current_weight <= max_mass:
                            filtered_animals.append(animal)
                            break  # Dodajemo životinju samo jednom ako odgovara bilo kom filteru
                
                animals = filtered_animals
                app.logger.debug(f'Filtrirano po masi: {len(animals)} životinja')
            
            # Filtriranje po opštinama
            if selected_municipality:
                farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
                animals = [animal for animal in animals if animal.farm_id in [farm.id for farm in farm_list]]
                app.logger.debug(f'Filtrirano po opštinama: {len(animals)} životinja')
            else:
                farm_list = Farm.query.join(User).filter(User.user_type == 'farm_active').all()
            
            app.logger.info(f'Prikazujem {len(animals)} životinja za kategoriju {animal_category.animal_category_name}')
            
            return render_template('marketplace/livestock_market.html',
                                title=animal_category.animal_category_name,
                                route_name=route_name,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality),
                                organic_filter=json.dumps(organic_filter),
                                insure_filter=json.dumps(insure_filter),
                                animal_category_id=animal_category_id,
                                animal_categories=animal_categories,
                                animal_category=animal_category,
                                animal_subcategories=animal_subcategories,
                                mass_filters=mass_filters,
                                animals=animals,
                                active_subcategories=active_subcategories,
                                active_mass_filters=active_mass_filters,
                                weight_filter=weight_filter)
                            
        # GET zahtev
        return render_template('marketplace/livestock_market.html',
                                title=animal_category.animal_category_name,
                                route_name=route_name,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality),
                                animal_category_id=animal_category_id,
                                animal_categories=animal_categories,
                                animal_category=animal_category,
                                animal_subcategories=animal_subcategories,
                                mass_filters=mass_filters,
                                animals=animals,
                                active_subcategories=[],
                                active_mass_filters=[],
                                weight_filter=weight_filter)
                                
    except Exception as e:
        app.logger.error(f'Neočekivana greška u pijaci stoke: {str(e)}', exc_info=True)
        flash('Došlo je do greške pri učitavanju pijace.', 'danger')
        return redirect(url_for('main.home'))


@marketplace.route('/livestock_detail')
def livestock_detail():
    return render_template('livestock_detail.html')


@marketplace.route('/products_market/<int:product_category_id>', methods=['GET', 'POST'])
def products_market(product_category_id):
    """
    Prikazuje pijacu gotovih proizvoda sa filterima za pretragu.
    
    Args:
        product_category_id (int): ID kategorije proizvoda (0 za sve kategorije)
        
    Returns:
        str: Renderovan HTML template sa podacima o proizvodima
        
    Note:
        Funkcija podržava filtriranje po:
        - Opštinama
        - Organskoj proizvodnji
        - Potkategorijama proizvoda
        - Sekcijama proizvoda
    """
    try:
        app.logger.debug(f'Pristup pijaci proizvoda za kategoriju: {product_category_id}')
        
        # Učitavanje osnovnih podataka
        route_name = request.endpoint
        municipality_filter_list = Municipality.query.all()
        
        # Ako je kategorija 0, prikaži samo osnovni template
        if product_category_id == 0:
            product_categories = ProductCategory.query.all()
            app.logger.info('Prikazujem osnovni template za pijacu proizvoda')
            return render_template('marketplace/products_market.html', 
                                route_name=route_name,
                                title='Gotovi proizvodi',
                                product_categories=product_categories)
        
        # Učitavanje podataka za specifičnu kategoriju
        try:
            product_category = ProductCategory.query.get_or_404(product_category_id)
            app.logger.debug(f'Učitana kategorija: {product_category.product_category_name}')
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kategorije {product_category_id}: {str(e)}')
            flash('Kategorija nije pronađena.', 'danger')
            return redirect(url_for('marketplace.products_market', product_category_id=0))
            
        # Učitavanje proizvoda i njihovih kategorija
        products = Product.query.filter_by(product_category_id=product_category_id).all()
        products = [product for product in products if float(product.quantity) > 0]
        product_categories = None
        product_subcategories = ProductSubcategory.query.filter_by(product_category_id=product_category_id).all()
        product_sections = ProductSection.query.filter_by(product_category_id=product_category_id).all()
        
        app.logger.debug(f'Učitano {len(products)} proizvoda, {len(product_subcategories)} potkategorija, {len(product_sections)} sekcija')
        
        # Inicijalizacija filtera
        section_filter = False
        selected_municipality = []
        organic_filter = None
        active_subcategories = []
        active_sections = []
            
        if request.method == 'POST':
            app.logger.debug('Obrada POST zahteva za filtere')
            
            # Obrada filtera za opštine
            selected_municipality = request.form.getlist('municipality')
            if '0' in selected_municipality:
                selected_municipality.remove('0')
                
            # Obrada ostalih filtera
            organic_filter = request.form.get('organic_filter')
            active_subcategories = [int(key.split('_')[1]) 
                                    for key, value in request.form.items() 
                                    if key.startswith('subcategory_') and value == 'on']
            active_sections = [int(key.split('_')[1]) 
                                for key, value in request.form.items() 
                                if key.startswith('section_') and value == 'on']
            
            # Primena filtera na proizvode
            if organic_filter == 'on':
                products = [product for product in products if product.organic_product]
                
            if active_subcategories:
                products = [product for product in products if product.product_subcategory_id in active_subcategories]
                section_filter = True
                product_sections = [product_section for product_section in product_sections 
                                    if product_section.product_subcategory_id in active_subcategories]
                
            if active_sections:
                products = [product for product in products if product.product_section_id in active_sections]
            
            # Filtriranje po opštinama
            if selected_municipality:
                farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
                products = [product for product in products if product.farm_id in [farm.id for farm in farm_list]]
                app.logger.debug(f'Filtrirano po opštinama: {len(products)} proizvoda')
            else:
                farm_list = Farm.query.join(User).filter(User.user_type == 'farm_active').all()
            
            app.logger.info(f'Prikazujem {len(products)} proizvoda za kategoriju {product_category.product_category_name}')
            
            return render_template('marketplace/products_market.html',
                                route_name=route_name,
                                title=product_category.product_category_name,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality),
                                organic_filter=json.dumps(organic_filter),
                                product_category_id=product_category_id,
                                product_categories=product_categories,
                                product_category=product_category,
                                product_subcategories=product_subcategories,
                                product_sections=product_sections,
                                products=products,
                                active_subcategories=active_subcategories,
                                active_sections=active_sections,
                                section_filter=section_filter)
                                
        # GET zahtev
        return render_template('marketplace/products_market.html',
                                route_name=route_name,
                                title=product_category.product_category_name,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality),
                                product_category_id=product_category_id,
                                product_categories=product_categories,
                                product_category=product_category,
                                product_subcategories=product_subcategories,
                                product_sections=product_sections,
                                products=products,
                                active_subcategories=[],
                                active_sections=[],
                                section_filter=section_filter)
                                
    except Exception as e:
        app.logger.error(f'Neočekivana greška u pijaci proizvoda: {str(e)}', exc_info=True)
        flash('Došlo je do greške pri učitavanju pijace.', 'danger')
        return redirect(url_for('main.home'))


@marketplace.route('/product_detail/<int:product_id>')
def product_detail(product_id):
    """
    Prikazuje detaljne informacije o specifičnom proizvodu.
    
    Args:
        product_id (int): ID proizvoda koji se prikazuje
        
    Returns:
        str: Renderovan HTML template sa detaljima proizvoda
        
    Note:
        Ako proizvod nije pronađen, korisnik se preusmerava na pijacu proizvoda
        uz odgovarajuću poruku o grešci.
    """
    try:
        app.logger.debug(f'Pristup detaljima proizvoda: {product_id}')
        
        # Učitavanje proizvoda
        product = Product.query.get_or_404(product_id)
        farm = Farm.query.get_or_404(product.farm_id)
        
        # Učitavanje kategorija proizvoda za formular za izmenu
        product_categories = ProductCategory.query.all()
        
        # Provera da li je korisnik ulogovan
        if current_user.is_authenticated:
            user = current_user
            farm_profile_completed = True if user.user_type == 'farm_active' else False
        else:
            user = None
            farm_profile_completed = False
        
        # Dobijanje 6 nasumično izabranih proizvoda iste kategorije
        similar_products = Product.query.filter(
            Product.product_category_id == product.product_category_id,
            Product.id != product.id
        ).order_by(func.random()).limit(6).all()
        
        app.logger.info(f'Prikazujem detalje za proizvod: {product.product_name}')
        
        return render_template('marketplace/product_detail.html',
                                product=product,
                                user=user,
                                farm=farm,
                                farm_profile_completed=farm_profile_completed,
                                similar_products=similar_products,
                                product_categories=product_categories)
                                
    except Exception as e:
        app.logger.error(f'Greška pri učitavanju proizvoda {product_id}: {str(e)}')
        flash('Proizvod nije pronađen.', 'danger')
        return redirect(url_for('marketplace.products_market', product_category_id=0))


@marketplace.route('/deactivate_product/<int:product_id>', methods=['POST'])
@login_required
def deactivate_product(product_id):
    """
    Deaktivira proizvod postavljanjem njegove količine na 0.
    Samo vlasnik proizvoda može da izvrši ovu akciju.
    
    Args:
        product_id (int): ID proizvoda koji se deaktivira
        
    Returns:
        redirect: Preusmerava na my_market stranicu vlasnika
        
    Note:
        Zahteva da korisnik bude ulogovan i da bude vlasnik proizvoda.
        Ako proizvod nije pronađen ili korisnik nije vlasnik, prikazuje se
        odgovarajuća poruka o grešci.
    """
    try:
        app.logger.debug(f'Pokušaj deaktivacije proizvoda: {product_id}')
        
        # Učitavanje proizvoda
        product = Product.query.get_or_404(product_id)
        
        # Provera da li je trenutni korisnik vlasnik
        if product.farm_product.user_id != current_user.id:
            app.logger.warning(f'Korisnik {current_user.id} pokušao da deaktivira tuđ proizvod {product_id}')
            flash('Nemate dozvolu za ovu akciju.', 'danger')
            return redirect(url_for('main.home'))
        
        # Deaktivacija proizvoda
        product.quantity = "0"
        db.session.commit()
        
        app.logger.info(f'Proizvod {product_id} uspešno deaktiviran')
        flash('Proizvod je uspešno deaktiviran.', 'success')
        
        return redirect(url_for('users.my_market', farm_id=product.farm_id))
        
    except Exception as e:
        app.logger.error(f'Greška pri deaktivaciji proizvoda {product_id}: {str(e)}')
        db.session.rollback()
        flash('Došlo je do greške pri deaktivaciji proizvoda.', 'danger')
        return redirect(url_for('main.home'))


@marketplace.route('/upload_product_image/<int:product_id>', methods=['GET', 'POST'])
@login_required
def upload_product_image(product_id):
    """
    Omogućava upload slike za specifični proizvod.
    Samo vlasnik proizvoda može da doda slike.
    
    Args:
        product_id (int): ID proizvoda za koji se dodaje slika
        
    Returns:
        redirect: Preusmerava na product_detail stranicu
        
    Note:
        - Maksimalan broj slika po proizvodu je 4
        - Podržani formati su jpg, jpeg, png
        - Zahteva da korisnik bude ulogovan i da bude vlasnik proizvoda
    """
    try:
        app.logger.debug(f'Pokušaj dodavanja slike za proizvod: {product_id}')
        
        # Učitavanje proizvoda
        product = Product.query.get_or_404(product_id)
        
        # Provera da li je trenutni korisnik vlasnik
        if product.farm_product.user_id != current_user.id:
            app.logger.warning(f'Korisnik {current_user.id} pokušao da doda sliku za tuđ proizvod {product_id}')
            flash('Nemate dozvolu za ovu akciju.', 'danger')
            return redirect(url_for('main.home'))
            
        # Inicijalizacija putanja i prefiksa
        product_prefix = f'product_{product_id}_'
        product_image_folder = os.path.join(app.root_path, 'static', 'product_image')
        
        # Provera postojećih slika
        product_image_list = [p for p in os.listdir(product_image_folder) 
                            if os.path.isfile(os.path.join(product_image_folder, p)) 
                            and p.startswith(product_prefix)]
        
        # Provera maksimalnog broja slika
        if len(product_image_list) >= 4:
            flash('Nije dodata slika. Maksimalan broj slika je 4.', 'warning')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))
            
        # Određivanje sledećeg broja slike
        image_sufix_list = [int(p.split('_')[-1].split('.')[0]) for p in product_image_list]
        counter = max(image_sufix_list) if image_sufix_list else 0
        
        # Validacija uploaded fajla
        if 'picture' not in request.files:
            flash('Nije izabrana slika.', 'danger')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))
            
        picture = request.files['picture']
        if not picture.filename:
            flash('Nije izabrana slika.', 'danger')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))
            
        # Provera ekstenzije
        _, f_ext = os.path.splitext(picture.filename)
        if f_ext.lower() not in ['.jpg', '.jpeg', '.png']:
            flash('Dozvoljeni formati su: jpg, jpeg, png', 'danger')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))
            
        # Čuvanje slike
        f_name = f'product_{product_id}_{(counter + 1):03}'
        product_image_fn = f_name + f_ext.lower()
        product_image_path = os.path.join(product_image_folder, product_image_fn)
        
        picture.save(product_image_path)
        app.logger.debug(f'Slika sačuvana: {product_image_fn}')
        
        # Ažuriranje kolekcije slika
        product.product_image_collection = product.product_image_collection + [product_image_fn]
        db.session.commit()
        
        app.logger.info(f'Uspešno dodata slika za proizvod {product_id}')
        flash('Slika je uspešno dodata.', 'success')
        
        return redirect(url_for('marketplace.product_detail', product_id=product_id))
        
    except Exception as e:
        app.logger.error(f'Greška pri dodavanju slike za proizvod {product_id}: {str(e)}')
        db.session.rollback()
        flash('Došlo je do greške pri dodavanju slike.', 'danger')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))


@marketplace.route('/delete_product_image', methods=['POST'])
@login_required
def delete_product_image():
    """
    Briše sliku proizvoda iz kolekcije i sa diska.
    Samo vlasnik proizvoda može da briše slike.
    
    Returns:
        redirect: Preusmerava na product_detail stranicu
        
    Note:
        - Ako je obrisana slika bila naslovna, postavlja se default.jpg
        - Zahteva da korisnik bude ulogovan i da bude vlasnik proizvoda
        - Briše se i fizički fajl sa diska
    """
    try:
        # Validacija ulaznih parametara
        product_id = request.form.get('product_id')
        product_image_fn = request.form.get('product_image')
        
        if not product_id or not product_image_fn:
            app.logger.error('Nedostaju obavezni parametri za brisanje slike')
            flash('Nedostaju potrebni podaci za brisanje slike.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.debug(f'Pokušaj brisanja slike {product_image_fn} za proizvod: {product_id}')
        
        # Učitavanje proizvoda
        product = Product.query.get_or_404(product_id)
        
        # Provera da li je trenutni korisnik vlasnik
        if product.farm_product.user_id != current_user.id:
            app.logger.warning(f'Korisnik {current_user.id} pokušao da obriše sliku za tuđ proizvod {product_id}')
            flash('Nemate dozvolu za ovu akciju.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera da li slika postoji u kolekciji
        product_images = product.product_image_collection
        if product_image_fn not in product_images:
            app.logger.warning(f'Slika {product_image_fn} nije pronađena u kolekciji proizvoda {product_id}')
            flash('Slika nije pronađena u kolekciji.', 'danger')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))
            
        # Uklanjanje slike iz kolekcije
        product_images = [img for img in product_images if img != product_image_fn]
        product.product_image_collection = product_images
        
        # Brisanje fizičkog fajla
        image_path = os.path.join(app.root_path, 'static', 'product_image', product_image_fn)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                app.logger.debug(f'Obrisan fajl: {image_path}')
            except OSError as e:
                app.logger.error(f'Greška pri brisanju fajla {image_path}: {str(e)}')
                flash('Slika je uklonjena iz kolekcije ali nije obrisana sa diska.', 'warning')
        
        # Ako je obrisana naslovna slika
        if product_image_fn == product.product_image:
            product.product_image = 'default.jpg'
            flash('Obrisana je naslovna slika, definišite novu naslovnu sliku.', 'warning')
            app.logger.info(f'Postavljena default slika za proizvod {product_id}')
        
        # Čuvanje promena
        db.session.commit()
        app.logger.info(f'Uspešno obrisana slika {product_image_fn} za proizvod {product_id}')
        flash('Slika je uspešno obrisana.', 'success')
        
        return redirect(url_for('marketplace.product_detail', product_id=product_id))
        
    except Exception as e:
        app.logger.error(f'Greška pri brisanju slike: {str(e)}')
        db.session.rollback()
        flash('Došlo je do greške pri brisanju slike.', 'danger')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))


@marketplace.route('/default_product_image', methods=['POST'])
@login_required
def default_product_image():
    """
    Postavlja određenu sliku kao naslovnu sliku proizvoda.
    Samo vlasnik proizvoda može da menja naslovnu sliku.
    
    Returns:
        redirect: Preusmerava na product_detail stranicu
        
    Note:
        - Slika mora postojati u kolekciji slika proizvoda
        - Zahteva da korisnik bude ulogovan i da bude vlasnik proizvoda
    """
    try:
        # Validacija ulaznih parametara
        product_id = request.form.get('product_id')
        product_image_fn = request.form.get('product_image')
        
        if not product_id or not product_image_fn:
            app.logger.error('Nedostaju obavezni parametri za promenu naslovne slike')
            flash('Nedostaju potrebni podaci za promenu naslovne slike.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.debug(f'Pokušaj postavljanja slike {product_image_fn} kao naslovne za proizvod: {product_id}')
        
        # Učitavanje proizvoda
        product = Product.query.get_or_404(product_id)
        
        # Provera da li je trenutni korisnik vlasnik
        if product.farm_product.user_id != current_user.id:
            app.logger.warning(f'Korisnik {current_user.id} pokušao da promeni naslovnu sliku za tuđ proizvod {product_id}')
            flash('Nemate dozvolu za ovu akciju.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera da li slika postoji u kolekciji
        if product_image_fn not in product.product_image_collection:
            app.logger.warning(f'Slika {product_image_fn} nije pronađena u kolekciji proizvoda {product_id}')
            flash('Izabrana slika nije pronađena u kolekciji proizvoda.', 'danger')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))
            
        # Postavljanje naslovne slike
        product.product_image = product_image_fn
        db.session.commit()
        
        app.logger.info(f'Uspešno postavljena naslovna slika {product_image_fn} za proizvod {product_id}')
        flash('Naslovna slika je uspešno promenjena.', 'success')
        
        return redirect(url_for('marketplace.product_detail', product_id=product_id))
        
    except Exception as e:
        app.logger.error(f'Greška pri promeni naslovne slike: {str(e)}')
        db.session.rollback()
        flash('Došlo je do greške pri promeni naslovne slike.', 'danger')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))


@marketplace.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """
    Omogućava izmenu postojećeg proizvoda.
    Samo vlasnik proizvoda može da vrši izmene.
    
    Args:
        product_id (int): ID proizvoda koji se menja
        
    Returns:
        GET: Renderovan template sa formom za izmenu
        POST: Redirect na product_detail nakon izmene
        
    Note:
        - Zahteva da korisnik bude ulogovan i da bude vlasnik proizvoda
        - Automatski računa cenu po kilogramu na osnovu jedinice mere
        - Cena za kupca se uvećava za 38% od cene proizvođača
    """
    try:
        app.logger.debug(f'Pristup izmeni proizvoda: {product_id}')
        
        # Učitavanje proizvoda
        product = Product.query.get_or_404(product_id)
        
        # Provera da li je trenutni korisnik vlasnik
        if product.farm_product.user_id != current_user.id:
            app.logger.warning(f'Korisnik {current_user.id} pokušao da izmeni tuđ proizvod {product_id}')
            flash('Nemate dozvolu za ovu akciju.', 'danger')
            return redirect(url_for('main.home'))
            
        if request.method == 'GET':
            return render_template('edit_product.html', product=product)
            
        # Validacija obaveznih polja
        required_fields = ['product_name', 'product_description', 'unit_of_measurement', 
                            'product_price_per_unit', 'quantity', 'category', 'subcategory', 'section']
        
        for field in required_fields:
            if not request.form.get(field):
                app.logger.warning(f'Nedostaje obavezno polje {field} pri izmeni proizvoda {product_id}')
                flash(f'Polje {field} je obavezno.', 'danger')
                return redirect(url_for('marketplace.edit_product', product_id=product_id))
                
        # Validacija numeričkih vrednosti
        try:
            price = float(request.form['product_price_per_unit'])
            if price <= 0:
                raise ValueError('Cena mora biti pozitivan broj')
                
            quantity = float(request.form['quantity'])
            if quantity < 0:
                raise ValueError('Količina ne može biti negativna')
                
            if request.form['unit_of_measurement'] == 'kom':
                weight = float(request.form['weight_conversion'])
                if weight <= 0:
                    raise ValueError('Težina po komadu mora biti pozitivan broj')
        except ValueError as e:
            app.logger.warning(f'Nevažeća numerička vrednost pri izmeni proizvoda {product_id}: {str(e)}')
            flash(str(e), 'danger')
            return redirect(url_for('marketplace.edit_product', product_id=product_id))
            
        # Ažuriranje osnovnih podataka
        product.product_name = request.form['product_name']
        product.product_description = request.form['product_description']
        product.unit_of_measurement = request.form['unit_of_measurement']
        product.product_price_per_unit_farmer = request.form['product_price_per_unit']
        product.product_price_per_unit = price * 1.38  # Uvećanje cene za kupca
        product.quantity = request.form['quantity']
        
        # Ažuriranje kategorije, potkategorije i sekcije
        product.product_category_id = request.form['category']
        product.product_subcategory_id = request.form['subcategory']
        product.product_section_id = request.form['section']
        
        # Ažuriranje cene po kilogramu
        if request.form['unit_of_measurement'] == 'kg':
            product.product_price_per_kg = product.product_price_per_unit
            product.weight_conversion = 1
        else:  # kom
            product.weight_conversion = request.form['weight_conversion']
            product.product_price_per_kg = product.product_price_per_unit / float(product.weight_conversion)
            
        # Ažuriranje organic statusa
        product.organic_product = request.form.get('organic_product') == 'on'
        
        # Čuvanje promena
        db.session.commit()
        
        app.logger.info(f'Uspešno izmenjen proizvod {product_id}')
        flash('Proizvod je uspešno izmenjen.', 'success')
        
        return redirect(url_for('marketplace.product_detail', product_id=product_id))
        
    except Exception as e:
        app.logger.error(f'Greška pri izmeni proizvoda {product_id}: {str(e)}')
        db.session.rollback()
        flash('Došlo je do greške pri izmeni proizvoda.', 'danger')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))