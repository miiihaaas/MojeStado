import json, os
from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail, app
from mojestado.users.forms import LoginForm, RequestResetForm, ResetPasswordForm
from mojestado.models import User, Farm, Municipality
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
        return 'Broj slika prekoračio ograničenje, pokušajte ponovo'
    
    picture = request.files['picture']
    f_name = f'farm_{farm.id:05}_{(counter + 1):03}'
    _, f_ext = os.path.splitext(picture.filename)
    farm_image_fn = f_name + f_ext
    farm_image_path = os.path.join(app.root_path, 'static', 'farm_image', farm_image_fn)
    picture.save(farm_image_path)
    #! dodati kod koji će da proširi listu u objektu farm tako što će dodati generisani fajl
    # farm.farm_image_colection = farm.farm_image_colection + [farm_image_fn] #! dodati kolonu farm_image_colection
    # db.session.commit()
    return redirect(url_for('users.my_user', user_id=farm.user_id))


@farms.route("/farm_list", methods=['GET', 'POST'])
def farm_list():
    municipality_filter_list = Municipality.query.all()
    if request.method == 'POST':
        print(f'{request.form=}')
        selected_municipality = request.form.getlist('municipality')
        print(f'post: {selected_municipality=}')
        if selected_municipality:
            farm_list = Farm.query.filter(Farm.farm_municipality_id.in_(selected_municipality)).all()
        else:
            farm_list = Farm.query.all()
            farm_list_active = [farm for farm in farm_list if User.query.get(farm.user_id).user_type == 'farm_active']
            farm_list = farm_list_active
        return render_template('farm_list.html', title='Farms',
                                farm_list=farm_list,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality))
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


@farms.route("/farm_detail/<int:farm_id>")
def farm_detail(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    return render_template('farm_detail.html', title=farm.farm_name, farm=farm)


