import json
from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail
from mojestado.users.forms import LoginForm, RequestResetForm, ResetPasswordForm
from mojestado.models import User, Farm, Municipality
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message


farms = Blueprint('farms', __name__)


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
            print('nije slektovano noša, prikaži sve farme sa svih mesta')
        return render_template('farm_list.html', title='Farms',
                                farm_list=farm_list,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality))
    elif request.method == 'GET':
        selected_municipality = [] #[3, 5, 7] # request.form.getlist('municipality')
        print(f'GET: {selected_municipality=}')
        farm_list = Farm.query.all()
        return render_template('farm_list.html', title='Farms',
                                farm_list=farm_list,
                                municipality_filter_list=municipality_filter_list,
                                selected_municipality=json.dumps(selected_municipality))


@farms.route("/farm_detail/<int:farm_id>")
def farm_detail(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    return render_template('farm_detail.html', title=farm.farm_name, farm=farm)


