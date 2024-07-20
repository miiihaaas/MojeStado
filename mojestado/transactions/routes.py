from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from mojestado import app, db
from mojestado.models import Animal

transactions = Blueprint('transactions', __name__)


@transactions.route('/make_transaction', methods=['GET', 'POST'])
def make_transaction():
    animals = session.get('animals', [])
    products = session.get('products', [])
    if not current_user.is_authenticated:
        flash('Da bi ste dovršili kupovinu potrebno je da se prijavite!', 'warning')
        return redirect(url_for('users.login'))
        
        
    
    
    for animal in animals:
        print(f'{animal["id"]=}')
        animal_to_edit = Animal.query.get(animal['id'])
        animal_to_edit.active = False
        db.session.commit()
    
    # Ispis podataka radi provere
    print(f'Animals in session: {animals}')
    print(f'Products in session: {products}')
    return redirect(url_for('main.home'))