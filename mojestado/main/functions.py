from flask import session
from mojestado.models import Invoice



def clear_cart_session():
    session.pop('animals', None)
    session.pop('products', None)
    session.pop('fattening', None)
    session.pop('services', None)
    session.pop('delivery', None)


def get_cart_total():
    '''
    treba ragranati sa if blokom: 
    - ako je na rate tov onda sabirati samo products, animals, services
    - ako NIJE na rate, onda sabrati sve (products, animals, services, fattening)
    '''
    print(f'{session=}')
    cart_total = 0
    installment_total = 0
    delivery_total = 0
    
    if 'products' in session and isinstance(session.get('products'), list):
        for product in session['products']:
            cart_total += float(product['total_price'])
    if 'animals' in session and isinstance(session.get('animals'), list):
        for animal in session['animals']:
            cart_total += float(animal['total_price'])
    if 'fattening' in session and isinstance(session.get('fattening'), list):
        for fattening in session['fattening']:
            if int(fattening['installment_options']) == 1: #! sabira samo ako NIJE na rate, na rate ide preko uplatnica koje će se generisati
                cart_total += float(fattening['fattening_price'])
            else:
                '''
                dodati logiku koja će za svaki tov (fattening) generisati uplatnice ?!
                '''
                installment_total += float(fattening['fattening_price'])
                pass
    if 'services' in session and isinstance(session.get('services'), list):
        for service in session['services']:
            cart_total += float(service['slaughterPrice']) + float(service['processingPrice'])
    
    if 'products' in session and isinstance(session.get('products'), list) and cart_total < 3000: #! dodati logiku da nema životinja u korpi
        delivery_total += 500
    if 'animals' in session and isinstance(session.get('animals'), list):
        for animal in session['animals']:
            if animal['wanted_weight']:
                print(f"{float(animal['wanted_weight'])=}")
                delivery_price = calculate_delivery_price(float(animal['wanted_weight']))
            else: 
                print(f"{float(animal['current_weight'])=}")
                delivery_price = calculate_delivery_price(float(animal['current_weight']))
            delivery_total += delivery_price
    return cart_total, installment_total, delivery_total


def calculate_delivery_price(animal_weight):
    if 1 <= animal_weight < 30:
        return 1000
    elif 30 <= animal_weight < 80:
        return 1200
    elif 80 <= animal_weight < 130:
        return 1500
    elif 130 <= animal_weight < 200:
        return 1800
    elif 200 <= animal_weight <= 800:
        return 3000