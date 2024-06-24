import json
from flask import Blueprint, request
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app
from mojestado.models import AnimalCategorization, AnimalCategory, Farm, Municipality, ProductCategory, ProductSection, ProductSubcategory, User


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
    if request.method == 'POST':
        selected_municipality = request.form.getlist('municipality')
        organic_filter = request.form.get('organic_filter')
        insure_filter = request.form.get('insure_filter')
        animal_subcategories_filter = request.form.getlist('animal_subcategories') #! nedostaje html kod
        print(f'post: {selected_municipality=}, {organic_filter=}')
        if selected_municipality:
            farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
            print(f'dodati kod da filtrira životineje iz farmi koje su izabranim opštinama')
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
                            animal_subcategories=animal_subcategories)
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
                            animal_subcategories=animal_subcategories)


@marketplace.route('/livestock_detail')
def livestock_detail():
    return render_template('livestock_detail.html')


@marketplace.route('/products_market/<int:product_category_id>', methods=['GET', 'POST'])
def products_market(product_category_id):
    municipality_filter_list = Municipality.query.all()
    if product_category_id == 0:
        product_categories = ProductCategory.query.all()
        return render_template('products_market.html', product_categories=product_categories)
    product_categories = None
    product_category = ProductCategory.query.get(product_category_id)
    product_subcategories = ProductSubcategory.query.filter_by(product_category_id=product_category_id).all()
    # product_sections = ProductSection.query.filter_by(product_subcategory_id=product_subcategory_id).all()
    if request.method == 'POST':
        selected_municipality = request.form.getlist('municipality')
        organic_filter = request.form.get('organic_filter')
        if selected_municipality:
            print('post: dodati kod da filtrira proizvode iz farmi koje su izabranim opštinama')
        else:
            pass
        return render_template('products_market.html',
                            municipality_filter_list=municipality_filter_list,
                            selected_municipality=json.dumps(selected_municipality),
                            organic_filter=json.dumps(organic_filter),
                            product_category_id=product_category_id,
                            product_categories=product_categories,
                            product_category=product_category,
                            product_subcategories=product_subcategories)
    elif request.method == 'GET':
        selected_municipality = []
        
    return render_template('products_market.html',
                            municipality_filter_list=municipality_filter_list,
                            selected_municipality=json.dumps(selected_municipality),
                            product_category_id=product_category_id,
                            product_categories=product_categories,
                            product_category=product_category,
                            product_subcategories=product_subcategories)


@marketplace.route('/product_detail')
def product_detail():
    render_template('product_detail.html')