from flask import Blueprint
from flask import  render_template, url_for, flash, redirect, request, abort
from mojestado import bcrypt, db, mail
from mojestado.users.forms import LoginForm, RequestResetForm, ResetPasswordForm
from mojestado.models import User
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message


farms = Blueprint('farms', __name__)


@farms.route("/farms_list")
def farms_list():
    return render_template('farms.html', title='Farms')


@farms.route("/farm_detail")
def farm_detail():
    pass


