import os
from fpdf import FPDF
from flask import render_template, url_for, current_app
from flask_mail import Message, Attachment
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from mojestado import mail, app
from mojestado.models import Animal


def generate_confirmation_token(user):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user.email, salt='email-confirm')

def confirm_token(token, expiration=1800):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='email-confirm', max_age=expiration)
        return {'success': True, 'email': email}
    except SignatureExpired as e:
        current_app.logger.warning(f'Token je istekao: {str(e)}')
        return {'success': False, 'error': 'expired'}
    except BadSignature as e:
        current_app.logger.warning(f'Neispravan token: {str(e)}')
        return {'success': False, 'error': 'invalid'}
    except Exception as e:
        current_app.logger.error(f'Neočekivana greška pri validaciji tokena: {str(e)}')
        return {'success': False, 'error': 'unknown'}


def send_confirmation_email(user):
    token = generate_confirmation_token(user)
    confirm_url = url_for('users.confirm_email', token=token, _external=True)
    html = render_template('message_html_confirm_email.html',
                            user=user,
                            confirm_url=confirm_url)
    subject = "Potvrda registracije"
    msg = Message(subject=subject, recipients=[user.email], html=html, sender=current_app.config['MAIL_DEFAULT_SENDER'])
    mail.send(msg)



def send_contract(user):
    msg = Message(subject='Ugovor o pristupu', 
                    sender='Wqo2M@example.com', 
                    recipients=[user.email], 
                    bcc=['Wqo2M@example.com'], 
                    attachments=[])
    msg.body = 'Ugovor o pristupu'
    mail.send(msg)


def send_conformation_email(user):
    msg = Message(subject='Registracija korisnika', 
                    sender='Wqo2M@example.com', 
                    recipients=[user.email], 
                    bcc=['Wqo2M@example.com'], 
                    attachments=[])
    msg.body = f'Da bi ste dovršili registraciju korisnickog naloga, kliknite na sledeći link: {url_for("users.confirm_email", token=user.get_reset_token(), _external=True)}'
    mail.send(msg)


def send_contract_to_farmer(user):
    '''
    Nakon unosa podataka generiše se ugovor koji se šalje PG na mejl koji je unelo.
    PG mora potpisati ugovor i vratiti administartoru putem pošte. 
    Nakon dobijanja ugovora od strane PG, administrator odobrava nalog PG.
    U admin panelu portala administrator manuelno aktivira nalog PG. 
    '''
    current_app.logger.info(f'wip: register farmer > confirm mail > send contract')
    subject = 'Ugovor za registraciju poljoprivrednog gazdinstva na portal "Moje stado"'
    html = render_template('message_html_contract_to_farmer.html')
    
    #! dodati kod za generisajne attachmenta
    contract_file = generate_contract(user)
    
    message = Message(subject=subject, 
                        sender=os.environ.get('MAIL_DEFAULT_SENDER'), 
                        recipients=[user.email], 
                        bcc=os.environ.get('MAIL_ADMIN'))
    message.html = html
    #! dodati kod za attachovanje ugovora
    # Prilagođavanje attachmenta prema izmenama u generate_contract funkciji
    message.attach(filename='ugovor.pdf', content_type='application/pdf', data=contract_file)
    # slanje mejla
    try:
        mail.send(message)
        current_app.logger.info(f'wip: poslat mejl | register farmer > confirm mail > send contract')
    except Exception as e:
        current_app.logger.error(f'Greška prilikom slanja mejla sa ugovorom poljoprivrednom gazdinstvu: {e}')



def generate_contract(user):
    '''
    Generisanje ugovora kojiće se attachovati u send_contract_to_farmer i poslati PG
    '''
    print('Generisanje ugovora...')
    # Definisanje putanja do fonta
    current_file_path = os.path.abspath(__file__)
    project_folder = os.path.dirname(os.path.dirname((current_file_path)))
    # Putanje za fontove
    font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
    font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')
    
    # Kreiranje direktorijuma ako ne postoji
    contract_dir = os.path.join('mojestado', 'static', 'contracts', 'farms')
    os.makedirs(contract_dir, exist_ok=True)

    # Kreiranje naziva fajla sa vodećim nulama
    filename = f'ugovor_{user.id:05d}.pdf'
    filepath = os.path.join(contract_dir, filename)
    
    # Kreiranje praznog PDF-a

    pdf = FPDF()
    pdf.add_page()
    # Dodavanje fonta
    pdf.add_font('DejaVuSansCondensed', '', font_path, uni=True)
    pdf.add_font('DejaVuSansCondensed', 'B', font_path_B, uni=True)
    
    pdf.set_font('DejaVuSansCondensed', size=12)
    
    # Čuvanje PDF-a
    pdf.output(filepath)

    # Čitanje sadržaja fajla za slanje emaila
    with open(filepath, 'rb') as f:
        pdf_content = f.read()
    
    return pdf_content



def farm_profile_completed_check(farm):
    print(f'provera kompletiranja profila farme: {len(farm.farm_description) > 100} i {farm.farm_image != "default.jpg"}')
    if len(farm.farm_description) > 100 and farm.farm_image != 'default.jpg':
        farm_profile_completed = True
    else:
        farm_profile_completed = False
    return farm_profile_completed


def process_overdued_debt(debt, customer):
    """
    Pomoćna funkcija koja obrađuje dug koji je prekoračio rok plaćanja
    i vraća formatirane podatke za prikaz.
    """
    invoice_item_type = debt.invoice_item.invoice_item_type
    invoice_details = debt.invoice_item.invoice_item_details
    
    # Podrazumevane vrednosti
    overdued_debt = {
        'animal': '',
        'service': '',
        'farm': '',
        'farm_id': None,
        'customer': customer,
        'user_id': debt.user_id
    }
    
    # Provera da li postoji ID životinje u detaljima fakture
    if 'id' not in invoice_details:
        app.logger.warning(f"Nedostaje ID životinje u detaljima fakture za debt_id={debt.id}")
        return None
        
    animal_id = invoice_details['id']
    app.logger.debug(f"Pokušaj dohvata životinje animal_id={animal_id} za debt_id={debt.id}")
    
    # Dohvatanje podataka o životinji
    animal = Animal.query.get(animal_id)
    if not animal:
        app.logger.warning(f"Životinja sa ID {animal_id} nije pronađena za debt_id={debt.id}.")
        return None
        
    # Popunjavanje osnovnih podataka o životinji i farmi
    overdued_debt['animal'] = animal.animal_category.animal_category_name
    overdued_debt['farm'] = animal.farm_animal.farm_name
    overdued_debt['farm_id'] = animal.farm_animal.user_id
    
    # Obrada prema tipu fakturne stavke
    if invoice_item_type == 2:  # Prodaja životinje
        animal.active = True
        animal.fattening = False
        overdued_debt['service'] = '-'
    
    elif invoice_item_type == 3:  # Usluga klanja/obrade
        if invoice_details.get('slaughterService', False) and invoice_details.get('processingService', False):
            overdued_debt['service'] = 'Klanje i obrada'
        elif invoice_details.get('slaughterService', False):
            overdued_debt['service'] = 'Klanje'
        else:
            overdued_debt['service'] = 'Nepoznata usluga'
    
    elif invoice_item_type == 4:  # Usluga tova
        overdued_debt['service'] = 'Tov'
    
    return overdued_debt