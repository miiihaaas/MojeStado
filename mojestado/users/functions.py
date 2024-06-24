from flask import url_for
from flask_mail import Message
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


def farm_profile_completed_check(farm):
    print(f'provera kopetiranja profila farme: {len(farm.farm_description) > 100} i {farm.farm_image != "default.jpg"}')
    if len(farm.farm_description) > 100 and farm.farm_image != 'default.jpg':
        farm_profile_completed = True
    else:
        farm_profile_completed = False
    return farm_profile_completed