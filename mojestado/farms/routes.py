import json, os
from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail, app
from mojestado.users.forms import LoginForm, RequestResetForm, ResetPasswordForm
from mojestado.models import Animal, Product, User, Farm, Municipality
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message


farms = Blueprint('farms', __name__)


@farms.route("/upload_image", methods=['POST'])
def upload_image():
    farm = Farm.query.get(request.form.get('farm_id'))
    if not farm:
        return 'Farm not found', 404
    farm_prefix = f'farm_{farm.id:05}_'
    farm_image_folder = os.path.join(app.root_path, 'static', 'farm_image')
    farm_image_list = os.listdir(farm_image_folder)
    farm_image_list = [f for f in farm_image_list if os.path.isfile(os.path.join(farm_image_folder, f))]
    farm_image_list = [f for f in farm_image_list if f.startswith(farm_prefix)]
    image_sufix_list = [int(f.split('_')[-1].split('.')[0]) for f in farm_image_list]
    print(f'{image_sufix_list=}')
    if len(image_sufix_list) == 0:
        counter = 0
    else:
        counter = max(image_sufix_list)
    print(f'{farm_image_list=}')
    print(f'{len(farm_image_list)=}')
    if len(farm_image_list) > 9:
        flash('Nije dodata slika. Maksimalan broj slika je 10.', 'danger')
        return redirect(url_for('users.my_farm', farm_id=farm.id))
    
    picture = request.files['picture']
    f_name = f'farm_{farm.id:05}_{(counter + 1):03}'
    _, f_ext = os.path.splitext(picture.filename)
    farm_image_fn = f_name + f_ext
    farm_image_path = os.path.join(app.root_path, 'static', 'farm_image', farm_image_fn)
    picture.save(farm_image_path)
    #! dodati kod koji će da proširi listu u objektu farm tako što će dodati generisani fajl
    farm.farm_image_collection = farm.farm_image_collection + [farm_image_fn] #! dodati kolonu farm_image_colection
    db.session.commit()
    flash('Slika je uspješno dodata', 'success')
    return redirect(url_for('users.my_farm', farm_id=farm.id))


@farms.route("/delete_image", methods=['POST'])
def delete_image():
    farm_id = request.form.get('farm_id')
    farm = Farm.query.get(farm_id)
    if not farm:
        return 'Farm not found', 404

    farm_image_fn = request.form.get('farm_image')
    # Uklonite farm_image_fn iz farm.farm_image_collection
    farm_images = farm.farm_image_collection
    if farm_image_fn in farm_images:
        print(f'pre remove: {farm_images=}')
        farm_images = [image for image in farm_images if image != farm_image_fn]
        print(f'posle remove: {farm_images=}')
        # Ažurirajte farm.farm_image_collection u bazi podataka
        farm.farm_image_collection = farm_images
        print(f'{farm.farm_image_collection=}')
        db.session.commit()
        #! dodati kod koji će da iz foldera obriše fajl sa nazivom farm_image_fn
        image_path = os.path.join(app.root_path, 'static', 'farm_image', farm_image_fn)
        if os.path.exists(image_path):
            os.remove(image_path)
        if farm_image_fn == farm.farm_image:
            farm.farm_image = 'default.jpg'
            db.session.commit()
            flash('Obrisana je naslovna slika, definišite novu naslovnu sliku', "warning")
        flash('Slika obrisana', "success")
    else:
        flash('Slika nije pronađena u kolekciji', "danger")
    return redirect(url_for('users.my_farm', farm_id=farm.id))


@farms.route("/default_image", methods=['GET', 'POST'])
def default_image():
    farm_id = request.form.get('farm_id')
    farm = Farm.query.get(farm_id)
    if not farm:
        return 'Farm not found', 404
    farm_image_fn = request.form.get('farm_image')
    farm.farm_image = farm_image_fn
    db.session.commit()
    return redirect(url_for('users.my_farm', farm_id=farm.id))

@farms.route("/edit_farm_description", methods=['POST'])
def edit_farm_description():
    farm_id = request.form.get('farm_id')
    farm = Farm.query.get(farm_id)
    if not farm:
        return 'Farm not found', 404
    farm.farm_description = request.form.get('farm_description')
    db.session.commit()
    return redirect(url_for('users.my_farm', farm_id=farm.id))


@farms.route("/farm_list", methods=['GET', 'POST'])
def farm_list():
    municipality_filter_list = Municipality.query.all()
    if request.method == 'POST':
        print(f'{request.form=}')
        organic_filter = request.form.get('organic_filter')
        selected_municipality = request.form.getlist('municipality')
        if '0' in selected_municipality:
            selected_municipality.remove('0')
        print(f'post: {selected_municipality=}')
        if selected_municipality:
            farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
        else:
            farm_list = Farm.query.all()
            farm_list_active = [farm for farm in farm_list if User.query.get(farm.user_id).user_type == 'farm_active']
            farm_list = farm_list_active
        if organic_filter == 'on':
            animals = Animal.query.filter(Animal.organic_animal == True).all()
            products = Product.query.filter(Product.organic_product == True).all()
            farm_list = [farm for farm in farm_list if farm.id in [animal.farm_id for animal in animals] or farm.id in [product.farm_id for product in products]]
        return render_template('farm_list.html', title='Farms',
                                farm_list=farm_list,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality),
                                organic_filter=json.dumps(organic_filter))
    elif request.method == 'GET':
        selected_municipality = [] #[3, 5, 7] # request.form.getlist('municipality')
        print(f'GET: {selected_municipality=}')
        farm_list = Farm.query.all()
        farm_list_active = [farm for farm in farm_list if User.query.get(farm.user_id).user_type == 'farm_active']
        farm_list = farm_list_active
        return render_template('farm_list.html', title='Farms',
                                farm_list=farm_list,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality))


@farms.route("/farm_detail/<int:farm_id>", methods=['GET', 'POST'])
def farm_detail(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    animals = Animal.query.filter_by(farm_id=farm_id).all()
    #! samo životinje koje nisu u tovu
    animals = [animal for animal in animals if animal.fattening == False]
    products = Product.query.filter_by(farm_id=farm_id).all()
    organic_filter = request.form.get('organic_filter')
    if request.method == 'POST':
        if organic_filter == 'on':
            animals = [animal for animal in animals if animal.organic_animal == 1]
            products = [product for product in products if product.organic_product == 1]
    return render_template('farm_detail.html', 
                            title=farm.farm_name,
                            organic_filter=json.dumps(organic_filter),
                            animals=animals,
                            products=products,
                            farm=farm)


