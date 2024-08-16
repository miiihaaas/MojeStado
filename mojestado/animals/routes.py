from flask import Blueprint, jsonify, request
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app
from mojestado.animals.functions import calculate_number_and_price_of_fattening_days
from mojestado.models import Animal, AnimalCategorization


animals = Blueprint('animals', __name__)



@animals.route('/calculate_fattening_details', methods=['POST'])
def calculate_fattening_details():
    print(f'{request.form=}')
    animal_id = int(request.form.get('animalId'))
    desired_weight = float(request.form.get('desiredWeight'))
    print(f'{request.form.get("animalId")=}')
    print(f'{animal_id=}')
    print(f'{desired_weight=}')
    
    animal = Animal.query.get(animal_id)
    animal.wanted_weight = desired_weight
    
    number_of_fattening_days, fattening_price = calculate_number_and_price_of_fattening_days(animal)
    print(f'{number_of_fattening_days=}; {fattening_price=}')
    return jsonify({'number_of_fattening_days': number_of_fattening_days, 'fattening_price': fattening_price})



@animals.route('/animal_categorization/<string:category>/<string:intended_for>/<float:weight>')
def animal_categorization(category, intended_for, weight):
    subcategory = get_animal_categorization(category, intended_for, weight)
    return f'preračunata podkategorija je: {subcategory}'

