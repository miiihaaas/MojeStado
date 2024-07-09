import json
from flask import Blueprint, request
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app
from mojestado.models import Animal, AnimalCategorization, AnimalCategory, Farm, Municipality, Product, ProductCategory, ProductSection, ProductSubcategory, User


marketplace = Blueprint('marketplace', __name__)


@marketplace.route('/livestock_market/<int:animal_category_id>', methods=['GET', 'POST'])
def livestock_market(animal_category_id):
    municipality_filter_list = Municipality.query.all()
    if animal_category_id == 0:
        animal_categories = AnimalCategory.query.all()
        return render_template('livestock_market.html', animal_categories=animal_categories)

    animal_categories = None
    animal_category = AnimalCategory.query.get(animal_category_id)
    animal_subcategories = AnimalCategorization.query.filter_by(animal_category_id=animal_category_id).all()
    animals = Animal.query.filter_by(animal_category_id=animal_category_id).filter_by(active=True).all()
    weight_filter = True
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
    product_categories = None
    product_category = ProductCategory.query.get(product_category_id)
    product_subcategories = ProductSubcategory.query.filter_by(product_category_id=product_category_id).all()
    print(f'{product_subcategories=}')
    product_sections = ProductSection.query.filter_by(product_category_id=product_category_id).all()
    # product_sections = ProductSection.query.filter_by(product_subcategory_id=product_subcategory_id).all()
    section_filter = False
    if request.method == 'POST':
        selected_municipality = request.form.getlist('municipality')
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


@marketplace.route('/product_detail')
def product_detail():
    render_template('product_detail.html')