import os

from flask import session
from flask_mail import Message

from mojestado import mail, app




def clear_cart_session():
    """Čisti sve podatke o korpi iz sesije."""
    try:
        # Lista svih ključeva koje treba očistiti
        cart_keys = ['animals', 'products', 'fattening', 'services', 'delivery']
        
        # Čuvamo informaciju o tome šta je bilo u korpi pre čišćenja
        cart_contents = {
            'animals': session.get('animals', []),
            'products': session.get('products', []),
            'fattening': session.get('fattening', []),
            'services': session.get('services', []),
            'delivery': session.get('delivery', {})
        }
        
        # Provera da li je korpa stvarno prazna
        has_items = any(
            len(items) > 0 if isinstance(items, list) else bool(items)
            for items in cart_contents.values()
        )
        
        if not has_items:
            app.logger.info('Korpa je već bila prazna')
            return True
            
        # Čišćenje specifičnih ključeva iz sesije
        for key in cart_keys:
            if key in session:
                del session[key]
        
        # Označavamo da je sesija modifikovana
        session.modified = True
        
        app.logger.info(f'Uspešno očišćena korpa. Prethodni sadržaj: {cart_contents}')
        return True
        
    except Exception as e:
        app.logger.error(f'Greška prilikom čišćenja korpe: {str(e)}', exc_info=True)
        return False


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
    if 'products' in session and isinstance(session.get('products'), list) and cart_total < 5000: #! dodati logiku da nema životinja u korpi
        delivery_total += 500
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


def send_faq_email(email, question):
    sender = email
    subject = 'Novo pitanje na portalu "Moje stado"'
    body = f'''
Pitanje: {question}
Odgovor slati na mejl: {sender}'''
    
    message = Message(subject=subject, sender=sender, recipients=[os.environ.get('MAIL_ADMIN'), sender], body=body)
    
    try:
        mail.send(message)
        print('wip: email sa pitanjem korisnika poslat adminu portala')
    except Exception as e:
        print(f'Greška slajna mejla: {e}')