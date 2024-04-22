from flask import Blueprint
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app


main = Blueprint('main', __name__)


@main.route('/')
@main.route('/home')
def home():
    return render_template('home.html', title='Početna strana')


@main.route('/about')
def about():
    return render_template('about.html', title='O portalu')


@main.route('/faq')
def faq():
    return render_template('faq.html', title='Najčešće postavljena pitanja')


@main.route('/contact')
def contact():
    pass