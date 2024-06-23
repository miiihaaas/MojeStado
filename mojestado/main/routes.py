from flask import Blueprint
from flask import  render_template, flash, redirect, url_for, request
from flask_login import current_user
from mojestado import app
from mojestado.models import FAQ, AnimalCategory


main = Blueprint('main', __name__)


@main.route('/')
@main.route('/home')
def home():
    faq = FAQ.query.all()
    faq = [question for question in faq if question.id < 4]
    animal_categories = AnimalCategory.query.all()
    return render_template('home.html', title='Početna strana',
                            faq=faq,
                            animal_categories=animal_categories)


@main.route('/about')
def about():
    return render_template('about.html', title='O portalu')


@main.route('/faq', methods=['GET', 'POST'])
def faq():
    faq = FAQ.query.all()
    if request.method == 'POST':
        print(f'{request.form=}')
        flash('Uspesno ste poslali pitanje!', 'success')
        #! razviti funkciju koja će da pošalje mejl sa pitanjem vlasniku portala
        return render_template('faq.html', title='Najžešće postavljena pitanja',
                                faq=faq)
    return render_template('faq.html', title='Najčešće postavljena pitanja',
                            faq=faq)


@main.route('/contact')
def contact():
    return render_template('contact.html', title='Kontakt strana')