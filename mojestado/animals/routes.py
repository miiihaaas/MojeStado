from flask import Blueprint
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app


animals = Blueprint('animals', __name__)


@animals.route('/animals_list')
def animals_list():
    return render_template('animals_list.html', title='Animals')