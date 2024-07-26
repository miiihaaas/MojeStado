from flask import Blueprint
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app
from mojestado.models import AnimalCategorization


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


def calculate_number_of_fattening_days(animal):
    current_weight = animal.current_weight
    wanted_weight = animal.wanted_weight
    
    calculated_weight = current_weight
    number_of_fattening_days = 0
    
    categorization_id = animal.animal_categorization_id
    categorization = AnimalCategorization.query.get(categorization_id)
    while categorization.min_weight is not None:
        while calculated_weight < categorization.max_weight:
            average_weight_gain = (categorization.min_weight + categorization.max_weight) / 2
            calculated_weight += average_weight_gain
            if calculated_weight > wanted_weight:
                categorization.min_weight = None    #! da bi postavio uslov da se prekine i spoljna petlja
                break                               #! prekida se unutrašnja petlja
            number_of_fattening_days += 1
        else:
            categorization_id += 1
            categorization = AnimalCategorization.query.get(categorization_id)

    return number_of_fattening_days


@animals.route('/animal_categorization/<string:category>/<string:intended_for>/<float:weight>')
def animal_categorization(category, intended_for, weight):
    subcategory = get_animal_categorization(category, intended_for, weight)
    return f'preračunata podkategorija je: {subcategory}'

@animals.route('/animals_list')
def animals_list():
    return render_template('animals_list.html', title='Animals')