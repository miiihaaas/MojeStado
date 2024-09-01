import json
import os
from flask import Blueprint, request
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app, db
from mojestado.models import Animal, AnimalCategorization, AnimalCategory, Farm, Municipality, Product, ProductCategory, ProductSection, ProductSubcategory, User


marketplace = Blueprint('marketplace', __name__)


@marketplace.route('/livestock_market/<int:animal_category_id>', methods=['GET', 'POST'])
def livestock_market(animal_category_id):
    
    municipality_filter_list = Municipality.query.all()
    animal_categories = AnimalCategory.query.all()
    if animal_category_id == 0:
        return render_template('livestock_market.html', animal_categories=animal_categories, animal_category_id=animal_category_id)

    # animal_categories = None
    animal_category = AnimalCategory.query.get(animal_category_id)
    animal_subcategories = AnimalCategorization.query.filter_by(animal_category_id=animal_category_id).all()
    animals = Animal.query.filter_by(animal_category_id=animal_category_id).filter_by(active=True).all()
    if animal_category.mass_filters:
        weight_filter = True
        mass_filters = list(animal_category.mass_filters.keys())
    else:
        weight_filter = False
        mass_filters = None
    print(f'{weight_filter=}, {mass_filters=}')
    if request.method == 'POST':
        selected_municipality = request.form.getlist('municipality')
        if '0' in selected_municipality:
            selected_municipality.remove('0')
        organic_filter = request.form.get('organic_filter')
        insure_filter = request.form.get('insure_filter')
        
        # Get the list of active subcategory filters
        active_subcategories = [int(key.split('_')[1]) for key, value in request.form.items() if key.startswith('subcategory_') and value == 'on']
        
        if organic_filter == 'on':
            animals = [animal for animal in animals if animal.organic_animal == True]
        if insure_filter == 'on':
            animals = [animal for animal in animals if animal.insured == True]
        if active_subcategories:
            animals = [animal for animal in animals if animal.animal_categorization_id in active_subcategories]
            weight_filter = False
            mass_filters = None

        
        print(f'post: {selected_municipality=}, {organic_filter=}')
        print(f'post: {active_subcategories=}')
        if selected_municipality:
            farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
            print(f'farm_list: {farm_list}')
            print(f'dodati kod da filtrira životineje iz farmi koje su izabranim opštinama')
            animals = [animal for animal in animals if animal.farm_id in [farm_list.id for farm_list in farm_list]]
        else:
            farm_list = Farm.query.all()
            farm_list_active = [farm for farm in farm_list if User.query.get(farm.user_id).user_type == 'farm_active']
            farm_list = farm_list_active
        return render_template('livestock_market.html',
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
                            weight_filter=weight_filter)
    elif request.method == 'GET':
        selected_municipality = [] #[3, 5, 7] # request.form.getlist('municipality')
        print(f'GET: {selected_municipality=}')
        farm_list = Farm.query.all()
        farm_list_active = [farm for farm in farm_list if User.query.get(farm.user_id).user_type == 'farm_active']
        farm_list = farm_list_active
        
    return render_template('livestock_market.html',
                            municipality_filter_list=municipality_filter_list,
                            selected_municipality=json.dumps(selected_municipality),
                            animal_category_id=animal_category_id,
                            animal_categories=animal_categories,
                            animal_category=animal_category,
                            animal_subcategories=animal_subcategories,
                            mass_filters=mass_filters,
                            animals=animals,
                            active_subcategories=[],
                            weight_filter=weight_filter)


@marketplace.route('/livestock_detail')
def livestock_detail():
    return render_template('livestock_detail.html')


@marketplace.route('/products_market/<int:product_category_id>', methods=['GET', 'POST'])
def products_market(product_category_id):
    municipality_filter_list = Municipality.query.all()
    if product_category_id == 0:
        product_categories = ProductCategory.query.all()
        return render_template('products_market.html', product_categories=product_categories)
    products = Product.query.filter_by(product_category_id=product_category_id).all()
    products = [product for product in products if float(product.quantity) > 0]
    product_categories = None
    product_category = ProductCategory.query.get(product_category_id)
    product_subcategories = ProductSubcategory.query.filter_by(product_category_id=product_category_id).all()
    print(f'{product_subcategories=}')
    product_sections = ProductSection.query.filter_by(product_category_id=product_category_id).all()
    # product_sections = ProductSection.query.filter_by(product_subcategory_id=product_subcategory_id).all()
    section_filter = False
    if request.method == 'POST':
        selected_municipality = request.form.getlist('municipality')
        if '0' in selected_municipality:
            selected_municipality.remove('0')
        organic_filter = request.form.get('organic_filter')
        active_subcategories = [int(key.split('_')[1]) for key, value in request.form.items() if key.startswith('subcategory_') and value == 'on']
        active_sections = [int(key.split('_')[1]) for key, value in request.form.items() if key.startswith('section_') and value == 'on']
        print(f'{active_subcategories=}')
        if organic_filter == 'on':
            products = [product for product in products if product.organic_product == True]
        if active_subcategories:
            products = [product for product in products if product.product_subcategory_id in active_subcategories]
            section_filter = True
            product_sections = [product_section for product_section in product_sections if product_section.product_subcategory_id in active_subcategories]
        if active_sections:
            products = [product for product in products if product.product_section_id in active_sections]
        
        if selected_municipality:
            farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
            products = [product for product in products if product.farm_id in [farm_list.id for farm_list in farm_list]]
            print(f'dodati kod da filtrira proizvode iz farmi koje su izabranim opštinama')
        else:
            farm_list = Farm.query.all()
            farm_list_active = [farm for farm in farm_list if User.query.get(farm.user_id).user_type == 'farm_active']
            farm_list = farm_list_active
        #todo sortiraj po ceni: products = 
        return render_template('products_market.html',
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
    elif request.method == 'GET':
        selected_municipality = []
        
    return render_template('products_market.html',
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


@marketplace.route('/product_detail/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get(product_id)
    return render_template('product_detail.html',
                            product=product)


@marketplace.route('/deactivate_product/<int:product_id>', methods=['POST'])
def deactivate_product(product_id):
    product = Product.query.get(product_id)
    product.quantity = "0"
    db.session.commit()
    return redirect(url_for('users.my_market', farm_id=product.farm_id))



@marketplace.route('/upload_product_image/<int:product_id>', methods=['GET', 'POST'])
def upload_product_image(product_id):
    product = Product.query.get(product_id)
    if not product:
        return redirect(url_for('marketplace.products_market', product_category_id=0))
    product_prefix = f'product_{product_id}_'
    product_image_folder = os.path.join(app.root_path, 'static', 'product_image')
    product_image_list = os.listdir(product_image_folder)
    product_image_list = [p for p in product_image_list if os.path.isfile(os.path.join(product_image_folder, p))]
    product_image_list = [p for p in product_image_list if p.startswith(product_prefix)]
    image_sufix_list = [int(p.split('_')[-1].split('.')[0]) for p in product_image_list]
    print(f'{image_sufix_list=}')
    if len(image_sufix_list) == 0:
        counter = 0
    else:
        counter = max(image_sufix_list)
    if len(image_sufix_list) > 4:
        flash('Nije dodata slika. Maksimalan broj slika je 4.')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))
    picture = request.files['picture']
    f_name = f'product_{product_id}_{(counter + 1):03}'
    _, f_ext = os.path.splitext(picture.filename)
    product_image_fn = f_name + f_ext
    product_image_path = os.path.join(app.root_path, 'static', 'product_image', product_image_fn)
    picture.save(product_image_path)
    
    product.product_image_collection = product.product_image_collection + [product_image_fn]
    db.session.commit()
    flash('Slika je uspešno dodata', 'success')
    return redirect(url_for('marketplace.product_detail', product_id=product_id))


@marketplace.route('/delete_product_image', methods=['POST'])
def delete_product_image():
    product_id = request.form['product_id']
    product = Product.query.get(product_id)
    if not product:
        return 'Proizvod nije nađen', 404

    product_image_fn = request.form.get('product_image')
    # uklonite product_image_fn iz product.product_image_collection
    product_images = product.product_image_collection
    if product_image_fn in product_images:
        product_images = [product_image for product_image in product_images if product_image != product_image_fn]
        # ažurirajte product.product_image_collection u bazi podataka
        product.product_image_collection = product_images
        db.session.commit()
        #! kod koji će iz foldera da obriše fajl sa nazivom product_image_fn
        image_path = os.path.join(app.root_path, 'static', 'product_image', product_image_fn)
        if os.path.exists(image_path):
            os.remove(image_path)
        if product_image_fn == product.product_image:
            product.product_image = 'default.jpg'
            db.session.commit()
            flash('Obrisana je naslovna slika, definišite novu naslovnu sliku', "warning")
        flash('Slika obrisana', "success")
    else:
        flash('Slika nije pronađena u kolekciji', "danger")
    return redirect(url_for('marketplace.product_detail', product_id=product_id))


@marketplace.route('/default_product_image', methods=['POST'])
def default_product_image():
    product_id = request.form['product_id']
    product = Product.query.get(product_id)
    if not product:
        return 'Proizvod nije nađen', 404
    product_image_fn = request.form.get('product_image')
    product.product_image = product_image_fn
    db.session.commit()
    flash('Naslovna slika je uspešno promenjena', 'success')
    return redirect(url_for('marketplace.product_detail', product_id=product_id))


@marketplace.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.query.get(product_id)
    print(f'**** {request.form["weight_conversion"]=}')
    product.product_name = request.form['product_name']
    product.product_description = request.form['product_description']
    product.unit_of_measurement = request.form['unit_of_measurement']
    product.product_price_per_unit = request.form['product_price_per_unit']
    product.weight_conversion = request.form['weight_conversion']
    if request.form['unit_of_measurement'] == 'kg':
        product.product_price_per_kg = product.product_price_per_unit
    elif request.form['unit_of_measurement'] == 'kom':
        product.product_price_per_kg = float(request.form['product_price_per_unit']) / float(request.form['weight_conversion'])
    if request.form.get('organic_product') == 'on':
        product.organic_product = True
    else:
        product.organic_product = False
    product.quantity = request.form['quantity']
    db.session.commit()
    flash('Proizvod je uspešno izmenjen', 'success')
    return redirect(url_for('marketplace.product_detail', product_id=product_id))