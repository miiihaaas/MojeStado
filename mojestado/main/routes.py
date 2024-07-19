from flask import Blueprint, jsonify, session
from flask import  render_template, flash, redirect, url_for, request
from flask_login import current_user
from mojestado import app
from mojestado.models import FAQ, Animal, AnimalCategory


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


@main.route('/set/<value>')
def set(value):
    session['value'] = value
    return f'vrednost koja je postavljena je: {value}'

@main.route('/get')
def get():
    if 'value' not in session:
        return 'nije postavljena ni jedna vrednost...'
    return f'vrednost koja je postavljena je: {session["value"]}. ovo je get vrednost.'


@main.route('/add_animal_to_cart/<int:animal_id>')
def add_animal_to_cart(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if 'animals' not in session:
        session['animals'] = []
    if animal.id in [animal['id'] for animal in session['animals']]:
        flash('Ova zivotinja se vec nalazi u korpi!', 'danger')
        return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))
    new_animal = {column.name: getattr(animal, column.name) for column in animal.__table__.columns}
    print(f'* * * new_animal: {new_animal}')
    session['animals'].append(new_animal)
    print(f'* * * session["animals"]: {session["animals"]}')
    flash('Uspesno ste dodali ovu zivotinju u korpu!', 'success')
    return redirect(url_for('marketplace.livestock_market', animal_category_id=animal.animal_category_id))


@main.route('/view_cart')
def view_cart():
    if 'animals' not in session:
        flash('Korpa je prazna!', 'info')
        return render_template('view_cart.html', cart={})
    else:
        animals=session['animals']
        print(f'view_cart: {animals}')
        return render_template('view_cart.html', animals=animals)


@main.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return 'korpa je obrisana...'