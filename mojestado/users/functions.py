import os
from fpdf import FPDF
from flask import render_template, url_for, current_app
from flask_mail import Message, Attachment
from mojestado import mail


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