from flask import Blueprint, jsonify, request
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app
from mojestado.models import Animal, AnimalCategorization


animals = Blueprint('animals', __name__)





def get_animal_categorization(category: str, intended_for: str, weight: float, subcategory: str = None) -> dict:
    categories = AnimalCategorization.query.filter_by(
        animal_category_id=category,
        intended_for=intended_for
    ).all()
    if intended_for == 'tov':
        print(f'{weight=}; {type(weight)=}')
        print(f'treba da odredi podkategoriju tova na osnovu tezine: {weight}')
        for category in categories:
            if category.min_weight <= weight <= category.max_weight:
                return category.id
    else:
        print(f'izabrana podkategorija je { subcategory= }')
        for category in categories:
            if category.subcategory == subcategory:
                return category.id


def calculate_number_and_price_of_fattening_days(animal):
    current_weight = float(animal.current_weight)
    wanted_weight = animal.wanted_weight
    
    print(f'{current_weight=}; {wanted_weight=}')
    print(f'{animal}')
    
    calculated_weight = current_weight
    number_of_fattening_days = 0
    fattening_price = 0
    
    categorization_id = animal.animal_categorization_id
    print(f'{categorization_id=}')
    categorization = AnimalCategorization.query.get(categorization_id)
    print(f'{categorization.min_weight=}')
    while categorization.min_weight is not None:
        while calculated_weight < categorization.max_weight:
            average_weight_gain = (categorization.min_weight_gain + categorization.max_weight_gain) / 2
            calculated_weight += average_weight_gain
            if calculated_weight > wanted_weight:
                categorization.min_weight = None    #! da bi postavio uslov da se prekine i spoljna petlja
                break                               #! prekida se unutrašnja petlja
            number_of_fattening_days += 1
            fattening_price += categorization.fattening_price
        else:
            categorization_id += 1
            categorization = AnimalCategorization.query.get(categorization_id)

    return number_of_fattening_days, fattening_price


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

