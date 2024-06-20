from flask import Blueprint
from flask import  render_template, flash, redirect, url_for
from flask_login import current_user
from mojestado import app
from mojestado.models import AnimalCategorization


animals = Blueprint('animals', __name__)





def get_animal_categorization(category: str, intended_for: str, weight: float, subcategory: str = None) -> dict:
    categories = AnimalCategorization.query.filter_by(
        category=category,
        intended_for=intended_for
    ).all()
    if intended_for == 'tov':
        print(f'{weight=}; {type(weight)=}')
        print(f'treba da odredi podkategoriju tova na osnovu tezine: {weight}')
        for category in categories:
            if category.min_weight <= weight <= category.max_weight:
                return category.subcategory
    else:
        print(f'treba da odredi podkategoriju ručno iz liste za priplod')
        subcategory_list = [category.subcategory for category in categories]
        return subcategory_list


@animals.route('/animal_categorization/<string:category>/<string:intended_for>/<float:weight>')
def animal_categorization(category, intended_for, weight):
    subcategory = get_animal_categorization(category, intended_for, weight)
    return f'preračunata podkategorija je: {subcategory}'

@animals.route('/animals_list')
def animals_list():
    return render_template('animals_list.html', title='Animals')