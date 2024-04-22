from flask import Blueprint
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app


products = Blueprint('products', __name__)


@products.route('/products_list')
def products_list():
    return render_template('products_list.html')


@products.route('/product_detail')
def product_detail():
    pass