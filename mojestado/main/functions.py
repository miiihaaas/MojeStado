import os
import json
import pickle
from flask import session
from flask import current_app as app
from flask_mail import Message

from mojestado import mail




def clear_cart_session(session_id=None):
    """Čisti sve podatke o korpi iz sesije.
    
    Args:
        session_id: Ako je prosleđen, čisti specifičnu sesiju. Ako nije, čisti trenutnu.
    """
    try:
        # Lista svih ključeva koje treba očistiti
        cart_keys = ['animals', 'products', 'fattening', 'services', 'delivery']
        
        if session_id:
            # Tražimo session fajl u direktorijumu
            session_files = os.listdir(app.config['SESSION_FILE_DIR'])
            session_found = False
            
            # Čitamo svaki fajl i tražimo onaj koji sadrži naš session_id
            for filename in session_files:
                if not filename.endswith('_session.txt'):  # Preskačemo naše pomoćne fajlove
                    file_path = os.path.join(app.config['SESSION_FILE_DIR'], filename)
                    try:
                        with open(file_path, 'rb') as f:  # Otvaramo u binary modu
                            session_data = pickle.load(f)  # Koristimo pickle za čitanje
                            
                            # Proveravamo da li je ovo prava sesija
                            if isinstance(session_data, dict) and session_data.get('_id') == session_id:
                                # Čistimo specifične ključeve
                                modified = False
                                for key in cart_keys:
                                    if key in session_data:
                                        del session_data[key]
                                        modified = True
                                
                                if modified:
                                    # Čuvamo izmenjenu sesiju
                                    with open(file_path, 'wb') as f:  # Čuvamo u binary modu
                                        pickle.dump(session_data, f)
                                    app.logger.info(f'Korpa je očišćena za sesiju {session_id} u fajlu {filename}')
                                    session_found = True
                                    break
                                
                    except (pickle.UnpicklingError, EOFError) as e:
                        app.logger.debug(f'Preskačem fajl {filename}: {str(e)}')
                        continue
                        
            if not session_found:
                app.logger.warning(f'Sesija {session_id} nije pronađena u fajlovima')
                return False
                
            return True
        else:
            # Čistimo trenutnu sesiju
            for key in cart_keys:
                if key in session:
                    del session[key]
            session.modified = True
            app.logger.info('Korpa je očišćena za trenutnu sesiju')
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