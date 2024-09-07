import os
from flask import render_template, url_for
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
    print(f'wip: register farmer > confirm mail > send contract')
    subject = 'Ugovor za registraciju poljoprivrednog gazdinstva na portal "Moje stado"'
    html = render_template('message_html_contract_to_farmer.html')
    
    message = Message(subject=subject, 
                        sender=os.environ.get('MAIL_DEFAULT_SENDER'), 
                        recipients=[user], 
                        bcc=os.environ.get('MAIL_ADMIN'))
    message.html = html
    #! dodati kod za generisajne attachmenta
    contract_file = generate_contract(user)
    # slanje mejla
    try:
        mail.send(message)
        print(f'wip: poslat mejl | register farmer > confirm mail > send contract')
    except Exception as e:
        print(f'Greška prilikom slanja mejla sa ugovorom poljoprivrednom gazdinstvu: {e}')



def generate_contract(user):
    '''
    Generisanje ugovora koji će se attachovati u send_contract_to_farmer i poslati PG
    '''
    print('Generisanje ugovora...')
    pass


def farm_profile_completed_check(farm):
    print(f'provera kopetiranja profila farme: {len(farm.farm_description) > 100} i {farm.farm_image != "default.jpg"}')
    if len(farm.farm_description) > 100 and farm.farm_image != 'default.jpg':
        farm_profile_completed = True
    else:
        farm_profile_completed = False
    return farm_profile_completed