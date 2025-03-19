import datetime
import json
from operator import itemgetter
import os
from flask import Blueprint, current_app, jsonify
from flask import  render_template, url_for, flash, redirect, request, abort
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from mojestado import bcrypt, db, app, mail
from mojestado.animals.functions import get_animal_categorization
from mojestado.users.forms import AddAnimalForm, AddProductForm, EditFarmForm, EditProfileForm, LoginForm, RequestResetForm, ResetPasswordForm, RegistrationUserForm, RegistrationFarmForm
from mojestado.users.functions import farm_profile_completed_check, confirm_token, send_confirmation_email, send_contract_to_farmer
from mojestado.models import Animal, AnimalCategorization, AnimalCategory, AnimalRace, Debt, Invoice, Payment, PaymentStatement, Product, ProductCategory, ProductSection, ProductSubcategory, User, Farm, Municipality, InvoiceItems

users = Blueprint('users', __name__)

@users.route("/register_farm", methods=['GET', 'POST'])
def register_farm():
    """
    Registracija novog poljoprivrednog gazdinstva.
    
    Returns:
        GET: Renderovan template sa formom za registraciju
        POST: Redirect na home page nakon uspešne registracije
        
    Note:
        - Kreira novog korisnika sa tipom 'farm_unverified'
        - Kreira novu farmu povezanu sa korisnikom
        - Ako email već postoji:
            - Dozvoljava ažuriranje ako je tip 'farm_unverified'
            - Odbija ako je bilo koji drugi tip
        - Šalje email za potvrdu registracije
    """
    try:
        form = RegistrationFarmForm()
        form.municipality.choices = [
            (municipality.id, f'{municipality.municipality_name} ({municipality.municipality_zip_code})')
            for municipality in db.session.query(Municipality).all()
        ]
    except Exception as e:
        current_app.logger.error(f'Greška pri inicijalizaciji forme: {str(e)}')
        flash('Došlo je do greške pri učitavanju forme. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))
    
    if form.validate_on_submit():
        try:
            user_email_list = [user.email for user in User.query.all()]
            municipality = Municipality.query.get(form.municipality.data)
            if not municipality:
                raise ValueError(f'Opština sa ID {form.municipality.data} nije pronađena')
            
            if form.email.data not in user_email_list:
                try:
                    # Kreiranje novog korisnika
                    user = User(
                        email=form.email.data, 
                        password=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
                        name=form.name.data,
                        surname=form.surname.data,
                        address=form.address.data,
                        city=form.city.data,
                        zip_code=municipality.municipality_zip_code,
                        phone=form.phone.data,
                        BPG=form.bpg.data,
                        JMBG=form.jmbg.data,
                        MB=form.mb.data,
                        user_type='farm_unverified',
                        registration_date=datetime.date.today()
                    )
                    db.session.add(user)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f'Greška pri kreiranju korisnika: {str(e)}')
                    flash('Došlo je do greške pri kreiranju korisnika. Molimo pokušajte ponovo.', 'danger')
                    return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva', form=form)
                
                try:
                    # Kreiranje farme
                    farm = Farm(
                        farm_name="Definisati naziv farme",
                        farm_address=form.address.data,
                        farm_city=form.city.data,
                        farm_zip_code=municipality.municipality_zip_code,
                        farm_municipality_id=municipality.id,
                        farm_phone=form.phone.data,
                        farm_account_number=form.account_number.data,
                        farm_description="Definisati opis farme",
                        registration_date=datetime.date.today(),
                        user_id=user.id,
                        farm_image_collection=[],
                        services={
                            "klanje": {
                                "1": "0", "2": "0", "3": "0", "4": "0",
                                "5": "0", "6": "0", "7": "0", "8": "0"
                            },
                            "obrada": {
                                "1": "0", "2": "0", "3": "0"
                            }
                        }
                    )
                    db.session.add(farm)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    # Brisanje prethodno kreiranog korisnika
                    try:
                        db.session.delete(user)
                        db.session.commit()
                    except:
                        pass
                    current_app.logger.error(f'Greška pri kreiranju farme: {str(e)}')
                    flash('Došlo je do greške pri kreiranju farme. Molimo pokušajte ponovo.', 'danger')
                    return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva', form=form)
            else:
                try:
                    # Ažuriranje postojećeg korisnika ako je farm_unverified
                    user = User.query.filter_by(email=form.email.data).first()
                    if user.user_type == 'farm_unverified':
                        user.password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
                        user.name = form.name.data
                        user.surname = form.surname.data
                        user.address = form.address.data
                        user.city = form.city.data
                        user.zip_code = municipality.municipality_zip_code
                        user.phone = form.phone.data
                        user.BPG = form.bpg.data
                        user.JMBG = form.jmbg.data
                        user.MB = form.mb.data
                        user.registration_date = datetime.date.today()
                        db.session.commit()
                    else:
                        flash(f'Već postoji korisnik sa mejlom {form.email.data}.', 'danger')
                        return redirect(url_for('main.home'))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f'Greška pri ažuriranju korisnika: {str(e)}')
                    flash('Došlo je do greške pri ažuriranju podataka. Molimo pokušajte ponovo.', 'danger')
                    return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva', form=form)
            
            try:
                # Slanje mejla za potvrdu
                send_confirmation_email(user)
                flash('Uspešno ste registrovali nalog na portalu. Na Vaš mejl poslat je link za verifikaciju Vašeg naloga.', 'success')
                return redirect(url_for('main.home'))
            except Exception as e:
                current_app.logger.error(f'Greška pri slanju email-a: {str(e)}')
                flash('Registracija je uspešna, ali došlo je do greške pri slanju verifikacijskog email-a. Molimo kontaktirajte podršku.', 'warning')
                return redirect(url_for('main.home'))
                
        except Exception as e:
            current_app.logger.error(f'Neočekivana greška u register_farm: {str(e)}')
            flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo.', 'danger')
            return render_template('register_farm.html', title='Registracija poljoprivrednog gazdinstva', form=form)
    
    if request.method == 'GET':
        return render_template('register_farm.html', 
                                title='Registracija poljoprivrednog gazdinstva',
                                form=form)

    flash(f'Došlo je do greške: {form.errors}. Molimo pokušajte ponovo.', 'danger')
    return render_template('register_farm.html', 
                            title='Registracija poljoprivrednog gazdinstva',
                            form=form)

@users.route("/register_user", methods=['GET', 'POST'])
def register_user():
    """
    Registracija novog korisnika.
    
    Returns:
        GET: Renderovan template sa formom za registraciju
        POST: Redirect na home page nakon uspešne registracije
        
    Note:
        - Kreira novog korisnika sa tipom 'user_unverified'
        - Šalje email za potvrdu registracije
    """
    try:
        form = RegistrationUserForm()
    except Exception as e:
        current_app.logger.error(f'Greška pri inicijalizaciji forme: {str(e)}')
        flash('Došlo je do greške pri učitavanju forme. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))

    if form.validate_on_submit():
        try:
            user_email_list = [user.email for user in User.query.all()]
            
            if form.email.data not in user_email_list:
                try:
                    user = User(
                        email=form.email.data,
                        password=bcrypt.generate_password_hash(form.password.data).decode('utf-8'),
                        name=form.name.data,
                        surname=form.surname.data,
                        address=form.address.data,
                        city=form.city.data,
                        zip_code=form.zip_code.data,
                        phone=form.phone.data,
                        JMBG=form.jmbg.data,
                        user_type='user_unverified',
                        registration_date=datetime.date.today()
                    )
                    db.session.add(user)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f'Greška pri kreiranju korisnika: {str(e)}')
                    flash('Došlo je do greške pri kreiranju korisnika. Molimo pokušajte ponovo.', 'danger')
                    return render_template('register_user.html', title='Registracija korisnika', form=form)
            else:
                flash(f'Već postoji korisnik sa mejlom {form.email.data}.', 'danger')
                return redirect(url_for('main.home'))

            try:
                send_confirmation_email(user)
                flash('Uspešno ste registrovali nalog na portalu. Na Vaš mejl poslat je link za verifikaciju Vašeg naloga.', 'success')
                return redirect(url_for('main.home'))
            except Exception as e:
                current_app.logger.error(f'Greška pri slanju email-a: {str(e)}')
                flash('Registracija je uspešna, ali došlo je do greške pri slanju verifikacijskog email-a. Molimo kontaktirajte podršku.', 'warning')
                return redirect(url_for('main.home'))

        except Exception as e:
            current_app.logger.error(f'Neočekivana greška u register_user: {str(e)}')
            flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo.', 'danger')
            return render_template('register_user.html', title='Registracija korisnika', form=form)

    if request.method == 'GET':
        return render_template('register_user.html',
                                title='Registracija korisnika',
                                form=form)

    flash(f'Došlo je do greške: {form.errors}. Molimo pokušajte ponovo.', 'danger')
    return render_template('register_user.html',
                            title='Registracija korisnika',
                            form=form)

@users.route('/confirm/<token>')
def confirm_email(token):
    """
    Potvrda email adrese korisnika i aktivacija naloga.
    
    Args:
        token (str): Token za potvrdu email adrese
        
    Returns:
        redirect: Preusmeravanje na početnu stranicu ili login stranicu
        
    Flow:
        1. Validacija tokena
        2. Pronalaženje korisnika po email-u
        3. Ažuriranje tipa korisnika na osnovu trenutnog stanja
        4. Za farmere: slanje ugovora
        5. Čuvanje promena u bazi
    """
    app.logger.info(f'Pokušaj potvrde email-a sa tokenom: {token}')
    
    # Validacija tokena
    result = confirm_token(token)
    if not result['success']:
        error_messages = {
            'expired': ('Link za potvrdu je istekao. Molimo zatražite novi link.', 'warning'),
            'invalid': ('Link za potvrdu je neispravan.', 'danger'),
            'default': ('Došlo je do greške pri potvrdi email-a. Molimo pokušajte ponovo.', 'danger')
        }
        message, category = error_messages.get(result.get('error'), error_messages['default'])
        flash(message, category)
        app.logger.warning(f"Neuspešna validacija tokena: {result.get('error', 'unknown error')}")
        return redirect(url_for('users.login'))
    
    email = result['email']
    app.logger.info(f'Token uspešno dekodiran za email: {email}')
    
    try:
        # Pronalaženje i validacija korisnika
        user = User.query.filter_by(email=email).first_or_404()
        app.logger.info(f'Pronađen korisnik: {user.email} (tip: {user.user_type})')
        
        # Provera da li je email već potvrđen
        if user.user_type == 'user':
            app.logger.info('Korisnik je već potvrđen')
            flash('Vaš email je već potvrđen', 'info')
            return redirect(url_for('main.home'))
        
        # Ažuriranje tipa korisnika
        if user.user_type == 'user_unverified':
            user.user_type = 'user'
            app.logger.info('Promena tipa korisnika iz user_unverified u user')
        elif user.user_type == 'farm_unverified':
            # Slanje ugovora farmeru
            try:
                send_contract_to_farmer(user)
                app.logger.info(f'Poslat ugovor farmeru: {user.email}')
            except Exception as e:
                app.logger.error(f'Greška pri slanju ugovora: {str(e)}')
                flash('Došlo je do greške pri slanju ugovora. Molimo kontaktirajte podršku.', 'warning')
            
            user.user_type = 'farm_inactive'
            app.logger.info('Promena tipa korisnika iz farm_unverified u farm_inactive')
        
        # Čuvanje promena
        try:
            db.session.commit()
            app.logger.info('Uspešno sačuvane promene u bazi')
            flash('Vaš nalog je uspešno verifikovan.', 'success')
        except Exception as e:
            app.logger.error(f'Greška pri čuvanju promena u bazi: {str(e)}')
            db.session.rollback()
            flash('Došlo je do greške pri potvrdi naloga. Molimo pokušajte ponovo.', 'danger')
            return redirect(url_for('users.login'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri potvrdi email-a: {str(e)}')
        flash('Došlo je do greške pri potvrdi naloga. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('users.login'))
    
    return redirect(url_for('main.home'))

@users.route("/login", methods=['GET', 'POST'])
def login():
    """
    Prijava korisnika na sistem.
    
    Methods:
        GET: Prikazuje formu za prijavu
        POST: Obrađuje podatke iz forme i prijavljuje korisnika
        
    Returns:
        GET: Renderovan login template
        POST: Redirect na home page ili sledeću stranicu nakon uspešne prijave
              Redirect nazad na login u slučaju greške
    
    Flow:
        1. Provera da li je korisnik već prijavljen
        2. Validacija forme
        3. Provera kredencijala
        4. Provera verifikacije naloga
        5. Prijava korisnika
    """
    # Provera da li je korisnik već prijavljen
    if current_user.is_authenticated:
        app.logger.info(f'Pokušaj prijave već prijavljenog korisnika: {current_user.email}')
        return redirect(url_for('main.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        app.logger.info(f'Pokušaj prijave za korisnika: {email}')
        
        # Pronalaženje korisnika i provera kredencijala
        user = User.query.filter_by(email=email).first()
        
        if not user:
            app.logger.warning(f'Pokušaj prijave sa nepostojećim email-om: {email}')
            flash('Mejl ili lozinka nisu odgovarajući.', 'danger')
            return render_template('login.html', title='Prijavljivanje', form=form, legend='Prijavljivanje')
        
        if not bcrypt.check_password_hash(user.password, form.password.data):
            app.logger.warning(f'Pogrešna lozinka za korisnika: {email}')
            flash('Mejl ili lozinka nisu odgovarajući.', 'danger')
            return render_template('login.html', title='Prijavljivanje', form=form, legend='Prijavljivanje')
        
        # Provera verifikacije naloga
        unverified_types = {
            'user_unverified': 'Vaš nalog nije verifikovan. Poslali smo Vam novi link za verifikaciju na email adresu. Molimo Vas da potvrdite svoj identitet u narednih 30 minuta.',
            'farm_unverified': 'Vaše poljoprivredno gazdinstvo nije verifikovano. Poslali smo Vam novi link za verifikaciju na email adresu. Molimo Vas da potvrdite registraciju u narednih 30 minuta.'
        }
        
        if user.user_type in unverified_types:
            try:
                send_confirmation_email(user)
                app.logger.info(f'Poslat novi verifikacioni email za: {email}')
                flash(unverified_types[user.user_type], 'warning')
            except Exception as e:
                app.logger.error(f'Greška pri slanju verifikacionog email-a: {str(e)}')
                flash('Došlo je do greške pri slanju verifikacionog email-a. Molimo pokušajte ponovo ili kontaktirajte podršku.', 'danger')
            return redirect(url_for('users.login'))
        
        # Prijava korisnika
        try:
            login_user(user, remember=form.remember.data)
            app.logger.info(f'Uspešna prijava korisnika: {email}')
            
            next_page = request.args.get('next')
            flash(f'Dobro došli, {user.name}!', 'success')
            
            if next_page:
                app.logger.info(f'Preusmeravanje korisnika {email} na: {next_page}')
                return redirect(next_page)
            return redirect(url_for('main.home'))
            
        except Exception as e:
            app.logger.error(f'Greška pri prijavi korisnika {email}: {str(e)}')
            flash('Došlo je do greške pri prijavi. Molimo pokušajte ponovo.', 'danger')
    
    return render_template('login.html', title='Prijavljivanje', form=form, legend='Prijavljivanje')


@users.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))


def send_reset_email(user):
    """
    Slanje email-a za resetovanje lozinke.
    
    Args:
        user (User): Korisnik kome se šalje email
        
    Returns:
        bool: True ako je email uspešno poslat, False inače
        
    Raises:
        ValueError: Ako korisnik nema validnu email adresu
    """
    if not user or not user.email:
        app.logger.error("Pokušaj slanja reset email-a korisniku bez email adrese")
        raise ValueError("Korisnik mora imati validnu email adresu")
    
    try:
        # Generisanje tokena za reset
        token = user.get_reset_token()
        app.logger.info(f"Generisan token za reset lozinke za korisnika: {user.email}")
        
        # Kreiranje email poruke
        msg = Message(
            'Zahtev za resetovanje lozinke',
            sender='noreply@uplatnice.online',
            recipients=[user.email]
        )
        msg.body = f'''Da biste resetovali lozinku, kliknite na sledeći link:
{url_for('users.reset_token', token=token, _external=True)}

Ako Vi niste napavili ovaj zahtev, molim Vas ignorišite ovaj mejl i neće biti napravljene nikakve izmene na Vašem nalogu.

Link za resetovanje lozinke je validan 30 minuta.
'''
        # Slanje email-a
        mail.send(msg)
        app.logger.info(f"Uspešno poslat email za reset lozinke na: {user.email}")
        return True
        
    except Exception as e:
        app.logger.error(f"Greška pri slanju reset email-a za {user.email}: {str(e)}")
        return False


@users.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    """
    Ruta za zahtev resetovanja lozinke.
    
    Methods:
        GET: Prikazuje formu za unos email adrese
        POST: Obrađuje zahtev i šalje email sa instrukcijama
        
    Returns:
        GET: Renderovan template sa formom
        POST: Redirect na login stranicu nakon slanja email-a
    """
    route_name = request.endpoint
    
    # Provera da li je korisnik već prijavljen
    if current_user.is_authenticated:
        app.logger.info(f'Već prijavljen korisnik pokušava reset lozinke: {current_user.email}')
        return redirect(url_for('main.home'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        email = form.email.data
        app.logger.info(f'Primljen zahtev za reset lozinke za email: {email}')
        
        # Provera da li korisnik postoji
        user = User.query.filter_by(email=email).first()
        if not user:
            app.logger.warning(f'Pokušaj reseta lozinke za nepostojeći email: {email}')
            # Iz sigurnosnih razloga, prikazujemo istu poruku kao da je email poslat
            flash('Mejl je poslat na Vašu adresu sa instrukcijama za resetovanje lozinke.', 'info')
            return redirect(url_for('users.login'))
        
        # Slanje email-a za reset
        try:
            if send_reset_email(user):
                app.logger.info(f'Uspešno poslat email za reset lozinke na: {email}')
                flash('Mejl je poslat na Vašu adresu sa instrukcijama za resetovanje lozinke.', 'info')
            else:
                app.logger.error(f'Neuspešno slanje email-a za reset lozinke na: {email}')
                flash('Došlo je do greške pri slanju email-a. Molimo pokušajte ponovo kasnije.', 'danger')
        except ValueError as e:
            app.logger.error(f'Validaciona greška pri slanju reset email-a: {str(e)}')
            flash('Došlo je do greške pri obradi zahteva. Molimo kontaktirajte podršku.', 'danger')
        except Exception as e:
            app.logger.error(f'Neočekivana greška pri slanju reset email-a: {str(e)}')
            flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo kasnije.', 'danger')
        
        return redirect(url_for('users.login'))
    
    return render_template('reset_request.html', 
                            title='Resetovanje lozinke', 
                            form=form, 
                            legend='Resetovanje lozinke',
                            route_name=route_name)


@users.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    """
    Ruta za resetovanje lozinke pomoću tokena.
    
    Args:
        token (str): Token za verifikaciju zahteva za reset
        
    Methods:
        GET: Prikazuje formu za unos nove lozinke
        POST: Obrađuje novu lozinku i ažurira je u bazi
        
    Returns:
        GET: Renderovan template sa formom
        POST: Redirect na login stranicu nakon uspešne promene
    """
    route_name = request.endpoint
    
    # Provera da li je korisnik već prijavljen
    if current_user.is_authenticated:
        app.logger.info(f'Već prijavljen korisnik pokušava reset lozinke: {current_user.email}')
        return redirect(url_for('main.home'))
    
    # Verifikacija tokena
    try:
        user = User.verify_reset_token(token)
        if user is None:
            app.logger.warning(f'Pokušaj resetovanja lozinke sa nevalidnim tokenom')
            flash('Ovo je nevažeći ili istekli token.', 'warning')
            return redirect(url_for('users.reset_request'))
        
        app.logger.info(f'Validan token za reset lozinke za korisnika: {user.email}')
        
    except Exception as e:
        app.logger.error(f'Greška pri verifikaciji reset tokena: {str(e)}')
        flash('Došlo je do greške pri verifikaciji tokena. Molimo zatražite novi link.', 'danger')
        return redirect(url_for('users.reset_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            # Heširanje i čuvanje nove lozinke
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            user.password = hashed_password
            
            # Čuvanje promena u bazi
            db.session.commit()
            app.logger.info(f'Uspešno resetovana lozinka za korisnika: {user.email}')
            
            flash('Vaša lozinka je uspešno ažurirana! Možete se prijaviti sa novom lozinkom.', 'success')
            return redirect(url_for('users.login'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Greška pri ažuriranju lozinke za {user.email}: {str(e)}')
            flash('Došlo je do greške pri ažuriranju lozinke. Molimo pokušajte ponovo.', 'danger')
    
    return render_template('reset_token.html', 
                            title='Resetovanje lozinke', 
                            form=form, 
                            legend='Resetovanje lozinke', 
                            route_name=route_name)




@users.route("/my_profile/<user_id>", methods=['GET', 'POST'])
def my_profile(user_id):
    """
    Prikaz i izmena profila korisnika.
    
    Args:
        user_id (str): ID korisnika čiji se profil prikazuje/menja
        
    Methods:
        GET: Prikazuje profil korisnika
        POST: Ažurira podatke profila
        
    Returns:
        GET: Renderovan profil template
        POST: Redirect na profil nakon izmena
    """
    try:
        user = User.query.get_or_404(user_id)
        farm = Farm.query.filter_by(user_id=user.id).first()
        app.logger.info(f'Pristup profilu za korisnika {user.email} (tip: {user.user_type})')
        
        # Provera pristupa
        if current_user.id != user.id and current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup profilu: {current_user.email} pokušava pristupiti {user.email}')
            flash('Nemate pravo pristupa ovoj stranici.', 'danger')
            return redirect(url_for('main.home'))
        
        # Admin pristup
        if current_user.user_type == 'admin':
            return handle_admin_profile(user, farm)
            
        # Običan korisnik
        if current_user.user_type == 'user':
            return handle_user_profile(user)
            
        # Aktivna farma
        if current_user.user_type == 'farm_active':
            return handle_active_farm_profile(user, farm)
            
        # Neaktivna farma
        if current_user.user_type == 'farm_inactive':
            app.logger.info(f'Pristup profilu neaktivne farme: {user.email}')
            flash('Vaše poljoprivredno gazdinstvo nije aktivno. Ukoliko ste potpisali ugovor, kontaktirajte administratora.', 'info')
            return render_template('my_profile.html', title='Moj nalog', user=user)
            
        # Neverifikovan korisnik
        if current_user.user_type == 'user_unverified':
            app.logger.info(f'Pristup profilu neverifikovanog korisnika: {user.email}')
            flash('Vas email nije potvrđen. Molimo potvrdite email.', 'info')
            return render_template('my_profile.html', title='Moj nalog', user=user)
            
        # Neverifikovana farma
        if current_user.user_type == 'farm_unverified':
            app.logger.info(f'Pristup profilu neverifikovane farme: {user.email}')
            flash('Vaše poljoprivredno gazdinstvo nije potvrđeno. Molimo potvrdite poljoprivredno gazdinstvo.', 'info')
            return render_template('my_profile.html', title='Moj nalog', user=user)
            
    except Exception as e:
        app.logger.error(f'Greška pri pristupu profilu {user_id}: {str(e)}')
        flash('Došlo je do greške pri pristupu profilu. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))

def handle_admin_profile(user, farm):
    """Helper funkcija za obradu admin profila"""
    try:
        form = EditFarmForm(obj=user)
        form.municipality.choices = [(m.id, f'{m.municipality_name} ({m.municipality_zip_code})')
                                    for m in db.session.query(Municipality).all()]

        if form.validate_on_submit():
            app.logger.info(f'Admin ažurira profil za: {user.email}')
            try:
                user.name = request.form.get('name')
                user.surname = request.form.get('surname')
                user.address = request.form.get('address')
                user.city = request.form.get('city')
                user.JMBG = request.form.get('jmbg')
                user.BPG = request.form.get('bpg')
                user.MB = request.form.get('mb')
                user.phone = request.form.get('phone')
                user.email = request.form.get('email')
                if farm:
                    farm.farm_account_number = request.form.get('account_number')
                    farm.farm_municipality_id = request.form.get('municipality')
                
                db.session.commit()
                app.logger.info(f'Uspešno ažuriran profil za: {user.email}')
                flash('Uspešno ste izmenili podatke.', 'success')
                return redirect(url_for('users.admin_view_farms', user_id=user.id))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri ažuriranju profila: {str(e)}')
                flash('Došlo je do greške pri čuvanju podataka. Molimo pokušajte ponovo.', 'danger')
        
        elif form.errors:
            app.logger.warning(f'Greške u formi za {user.email}: {form.errors}')
            flash(f'{form.errors}', 'danger')
        
        # Popunjavanje forme postojećim podacima
        form.jmbg.data = user.JMBG
        form.bpg.data = user.BPG
        form.mb.data = user.MB
        form.account_number.data = farm.farm_account_number if farm else ''
        form.municipality.data = str(farm.farm_municipality_id) if farm else ''
        
        return render_template('my_profile.html', title='Moj nalog', user=user, form=form)
        
    except Exception as e:
        app.logger.error(f'Greška pri obradi admin profila za {user.email}: {str(e)}')
        flash('Došlo je do greške pri učitavanju profila. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))

def handle_user_profile(user):
    """Helper funkcija za obradu korisničkog profila"""
    try:
        if request.method == 'POST':
            app.logger.info(f'Korisnik ažurira adresu: {user.email}')
            try:
                user.address = request.form.get('address')
                db.session.commit()
                app.logger.info(f'Uspešno ažurirana adresa za: {user.email}')
                flash('Uspešno ste izmenili adresu.', 'success')
                return redirect(url_for('users.my_profile', user_id=user.id))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri ažuriranju adrese: {str(e)}')
                flash('Došlo je do greške pri čuvanju adrese. Molimo pokušajte ponovo.', 'danger')
        
        return render_template('my_profile.html', title='Moj nalog', user=user)
        
    except Exception as e:
        app.logger.error(f'Greška pri obradi korisničkog profila za {user.email}: {str(e)}')
        flash('Došlo je do greške pri učitavanju profila. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))

def handle_active_farm_profile(user, farm):
    """Helper funkcija za obradu profila aktivne farme"""
    try:
        farm_profile_completed = farm_profile_completed_check(farm)
        form = EditFarmForm()
        
        try:
            form.municipality.choices = [(m.id, f'{m.municipality_name} ({m.municipality_zip_code})')
                                        for m in Municipality.query.filter_by(id=farm.farm_municipality_id).all()]
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju opština: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka o opštinama.', 'warning')
            form.municipality.choices = []

        # Popunjavanje forme postojećim podacima
        form.email.data = user.email
        form.name.data = user.name
        form.surname.data = user.surname
        form.address.data = user.address
        form.city.data = user.city
        form.phone.data = user.phone
        form.municipality.data = str(farm.farm_municipality_id)
        form.jmbg.data = user.JMBG
        form.bpg.data = user.BPG
        form.mb.data = user.MB
        form.account_number.data = farm.farm_account_number

        return render_template('my_profile.html', 
                            title='Moj nalog',
                            user=user,
                            farm=farm,
                            form=form,
                            farm_profile_completed=farm_profile_completed)
                            
    except Exception as e:
        app.logger.error(f'Greška pri obradi profila farme za {user.email}: {str(e)}')
        flash('Došlo je do greške pri učitavanju profila. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


#! ispod je za farmera !#
#! ispod je za farmera !#
#! ispod je za farmera !#

@users.route("/my_farm/<int:farm_id>", methods=['GET', 'POST'])
def my_farm(farm_id):
    """
    Prikaz detalja farme i upravljanje uslugama.
    
    Args:
        farm_id (int): ID farme koja se prikazuje
        
    Returns:
        GET: Renderovan template sa detaljima farme
        POST: Trenutno nije implementirano
        
    Raises:
        404: Ako farma nije pronađena
        403: Ako korisnik nema pristup farmi
    """
    try:
        # Pronalaženje farme
        farm = Farm.query.get_or_404(farm_id)
        app.logger.info(f'Pristup farmi ID {farm_id} od strane korisnika {current_user.email}')
        
        # Provera pristupa
        if current_user.id != farm.user_id:
            app.logger.warning(f'Nedozvoljen pristup farmi {farm_id} od strane {current_user.email}')
            flash('Nemate pravo pristupa ovoj stranici.', 'danger')
            return redirect(url_for('main.home'))
        
        # Učitavanje kategorija životinja
        try:
            animal_categories = {
                str(category.id): category.animal_category_name 
                for category in AnimalCategory.query.all()
            }
            app.logger.debug(f'Učitano {len(animal_categories)} kategorija životinja')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kategorija životinja: {str(e)}')
            animal_categories = {}
            flash('Došlo je do greške pri učitavanju kategorija životinja.', 'warning')
        
        # Provera kompletnosti profila
        try:
            farm_profile_completed = farm_profile_completed_check(farm)
            if not farm_profile_completed:
                app.logger.info(f'Profil farme {farm_id} nije kompletan')
                flash('Molimo vas da kompletirate profil farme da bi ste mogli upravljati uslugama. Potrebno je da opis poljoprivrednog gazdinstva bude duži od 100 znakova i da izaberete podrazumevanu sliku poljoprivrednog gazdinstva.', 'info')
        except Exception as e:
            app.logger.error(f'Greška pri proveri kompletnosti profila: {str(e)}')
            farm_profile_completed = False
            flash('Došlo je do greške pri proveri statusa profila.', 'warning')
        
        return render_template('my_farm.html', 
                            title='Moj nalog',
                            user=current_user,
                            farm=farm,
                            farm_profile_completed=farm_profile_completed,
                            animal_categories=animal_categories)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri pristupu farmi {farm_id}: {str(e)}')
        flash('Došlo je do greške pri učitavanju podataka o farmi. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/my_flock/<int:farm_id>", methods=['GET', 'POST'])
def my_flock(farm_id):
    """
    Prikaz i upravljanje stadom na farmi.
    
    Args:
        farm_id (int): ID farme čije se stado prikazuje
        
    Methods:
        GET: Prikazuje listu životinja i formu za dodavanje nove
        POST: Dodaje novu životinju u stado
        
    Returns:
        GET: Renderovan template sa životinjama i formom
        POST: Redirect na istu stranicu nakon dodavanja
    """
    try:
        # Provera farme i pristupa
        farm = Farm.query.get_or_404(farm_id)
        app.logger.info(f'Pristup stadu farme {farm_id} od strane korisnika {current_user.email}')
        
        if current_user.id != farm.user_id:
            app.logger.warning(f'Nedozvoljen pristup stadu farme {farm_id} od strane {current_user.email}')
            flash('Nemate pravo pristupa ovoj stranici.', 'danger')
            return redirect(url_for('main.home'))
        
        # Provera opisa farme
        if len(farm.farm_description) < 100:
            app.logger.info(f'Nedovoljan opis farme {farm_id}')
            flash('Opis poljoprivrednog gazdinstva mora biti duži od 100 znakova', 'danger')
            return redirect(url_for('users.my_farm', farm_id=farm.id))
        
        # Učitavanje životinja
        try:
            animals = Animal.query.filter_by(farm_id=farm_id, active=True).all()
            fattening_animals = Animal.query.filter_by(farm_id=farm_id, fattening=True).all()
            app.logger.debug(f'Učitano {len(animals)} aktivnih i {len(fattening_animals)} tovnih životinja')
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju životinja: {str(e)}')
            flash('Došlo je do greške pri učitavanju životinja.', 'warning')
            animals = []
            fattening_animals = []
        
        # Inicijalizacija forme i kategorija
        form = AddAnimalForm()
        try:
            categories_query = AnimalCategory.query.all()
            categories_list = list(dict.fromkeys((category.id, category.animal_category_name) 
                                                for category in categories_query))
            form.category.choices = categories_list
            app.logger.debug(f'Učitano {len(categories_list)} kategorija')
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kategorija: {str(e)}')
            flash('Došlo je do greške pri učitavanju kategorija životinja.', 'warning')
            form.category.choices = []
        
        # Obrada POST zahteva
        if request.method == 'POST':
            app.logger.info(f'Pokušaj dodavanja nove životinje na farmu {farm_id}')
            
            try:
                # Određivanje kategorije
                subcategory = form.subcategory.data if form.subcategory.data else None
                category_id = get_animal_categorization(
                    form.category.data,
                    form.intended_for.data,
                    form.weight.data,
                    subcategory
                )
                
                if not category_id:
                    app.logger.warning('Pokušaj dodavanja životinje sa nepostojećom kategorijom')
                    flash('Kategorija ne postoji', 'danger')
                    return redirect(url_for('users.my_flock', farm_id=farm.id))
                
                # Kreiranje nove životinje
                new_animal = Animal(
                    animal_id=form.animal_id.data,
                    animal_category_id=form.category.data,
                    animal_categorization_id=category_id,
                    animal_race_id=form.race.data,
                    animal_gender=form.animal_gender.data,
                    measured_weight=form.weight.data,
                    measured_date=datetime.datetime.now(),
                    current_weight=form.weight.data,
                    price_per_kg_farmer=form.price.data,
                    price_per_kg=form.price.data * 1.38,  # 1.2 * 1.15 = 1.38
                    total_price=form.price.data * form.weight.data,
                    insured=form.insured.data,
                    organic_animal=form.organic.data,
                    cardboard=None,
                    intended_for=form.intended_for.data,
                    farm_id=farm.id,
                    fattening=False,
                    active=True
                )
                
                db.session.add(new_animal)
                db.session.flush()
                
                # Obrada kartona ako postoji
                if form.cardboard.data:
                    try:
                        filename = f'{new_animal.id:06}.pdf'
                        filepath = os.path.join(current_app.root_path, 'static', 'cardboards', filename)
                        form.cardboard.data.save(filepath)
                        new_animal.cardboard = filename
                        app.logger.info(f'Sačuvan karton za životinju ID {new_animal.id}')
                    except Exception as e:
                        app.logger.error(f'Greška pri čuvanju kartona: {str(e)}')
                        flash('Došlo je do greške pri čuvanju kartona životinje.', 'warning')
                
                db.session.commit()
                app.logger.info(f'Uspešno dodata nova životinja ID {new_animal.id} na farmu {farm_id}')
                flash('Uspešno ste dodali životinju', 'success')
                return redirect(url_for('users.my_flock', farm_id=farm.id))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri dodavanju životinje: {str(e)}')
                flash('Došlo je do greške pri dodavanju životinje. Molimo pokušajte ponovo.', 'danger')
        
        return render_template('my_flock.html',
                            title='Moje stado',
                            user=current_user,
                            animals=animals,
                            fattening_animals=fattening_animals,
                            form=form,
                            farm=farm)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri pristupu stadu {farm_id}: {str(e)}')
        flash('Došlo je do greške pri učitavanju stada. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/remove_animal/<int:animal_id>", methods=['POST'])
def remove_animal(animal_id):
    """
    Uklanja životinju iz ponude (postavlja active=False).
    
    Args:
        animal_id (int): ID životinje koja se uklanja
        
    Returns:
        Redirect na my_flock stranicu nakon uklanjanja
    """
    try:
        # Pronalaženje životinje
        animal = Animal.query.get_or_404(animal_id)
        app.logger.info(f'Pokušaj uklanjanja životinje ID {animal_id} sa farme {animal.farm_id}')
        
        # Provera pristupa
        if current_user.id != animal.farm_animal.user_id:
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava ukloniti životinju {animal_id}')
            flash('Nemate pravo pristupa ovoj životinji.', 'danger')
            return redirect(url_for('main.home'))
        
        try:
            # Deaktivacija životinje
            animal.active = False
            db.session.commit()
            app.logger.info(f'Uspešno uklonjena životinja ID {animal_id}')
            flash('Uspešno ste uklonili životinju iz ponude', 'success')
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Greška pri uklanjanju životinje {animal_id}: {str(e)}')
            flash('Došlo je do greške pri uklanjanju životinje. Molimo pokušajte ponovo.', 'danger')
            
        return redirect(url_for('users.my_flock', farm_id=animal.farm_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri pristupu životinji {animal_id}: {str(e)}')
        flash('Došlo je do greške pri pristupu životinji. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/edit_animal/<int:animal_id>", methods=['GET', 'POST'])
def edit_animal(animal_id):
    """
    Izmena podataka o životinji.
    
    Args:
        animal_id (int): ID životinje koja se menja
        
    Methods:
        GET: Prikazuje formu za izmenu
        POST: Čuva izmenjene podatke
        
    Returns:
        Redirect na my_flock stranicu nakon izmene
    """
    try:
        # Pronalaženje životinje
        animal = Animal.query.get_or_404(animal_id)
        app.logger.info(f'Pristup izmeni životinje ID {animal_id} od strane {current_user.email}')
        
        # Provera pristupa
        if current_user.id != animal.farm_animal.user_id:
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava izmeniti životinju {animal_id}')
            flash('Nemate pravo pristupa ovoj životinji.', 'danger')
            return redirect(url_for('main.home'))
            
        if request.method == 'POST':
            try:
                # Ažuriranje osnovnih podataka
                animal.animal_id = request.form.get('mindjusha')
                animal.animal_gender = request.form.get('animal_gender')
                animal.current_weight = request.form.get('weight')
                
                # Ažuriranje cena
                try:
                    price = float(request.form.get('price', 0))
                    animal.price_per_kg_farmer = price
                    animal.price_per_kg = price * 1.38  # 1.2 * 1.15 = 1.38
                    animal.total_price = animal.price_per_kg * float(animal.current_weight)
                    app.logger.debug(f'Ažurirane cene: farmer={price}, prodajna={animal.price_per_kg}, ukupno={animal.total_price}')
                except ValueError as e:
                    app.logger.error(f'Greška pri konverziji cene: {str(e)}')
                    flash('Cena mora biti broj.', 'danger')
                    return redirect(url_for('users.my_flock', farm_id=animal.farm_id))
                
                # Ažuriranje boolean polja
                animal.insured = request.form.get('insured') == 'y'
                animal.organic_animal = request.form.get('organic') == 'y'
                
                # Obrada kartona ako je uploadovan
                if request.files.get('cardboard'):
                    try:
                        filename = f'{animal.id:06}.pdf'
                        filepath = os.path.join(current_app.root_path, 'static', 'cardboards', filename)
                        request.files.get('cardboard').save(filepath)
                        animal.cardboard = filename
                        app.logger.info(f'Ažuriran karton za životinju ID {animal_id}')
                    except Exception as e:
                        app.logger.error(f'Greška pri čuvanju kartona: {str(e)}')
                        flash('Došlo je do greške pri čuvanju kartona životinje.', 'warning')
                
                db.session.commit()
                app.logger.info(f'Uspešno izmenjena životinja ID {animal_id}')
                flash('Uspešno ste izmenili podatke životinje', 'success')
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri izmeni životinje {animal_id}: {str(e)}')
                flash('Došlo je do greške pri izmeni podataka. Molimo pokušajte ponovo.', 'danger')
        
        return redirect(url_for('users.my_flock', farm_id=animal.farm_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri pristupu životinji {animal_id}: {str(e)}')
        flash('Došlo je do greške pri pristupu životinji. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/save_services", methods=['POST'])
def save_services():
    """
    Čuva cene usluga za farmu.
    
    Methods:
        POST: Prima podatke o cenama usluga i čuva ih u bazi
        
    Returns:
        Redirect na my_farm stranicu nakon čuvanja
    """
    try:
        # Provera i učitavanje farme
        farm_id = request.form.get('farm_id')
        if not farm_id:
            app.logger.error('Nije prosleđen farm_id')
            flash('Nedostaje ID farme.', 'danger')
            return redirect(url_for('main.home'))
            
        farm = Farm.query.get_or_404(farm_id)
        app.logger.info(f'Pokušaj čuvanja usluga za farmu {farm_id} od strane {current_user.email}')
        
        # Provera pristupa
        if current_user.id != farm.user_id:
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava izmeniti usluge farme {farm_id}')
            flash('Nemate pravo pristupa ovoj farmi.', 'danger')
            return redirect(url_for('main.home'))
        
        # Validacija cena
        invalid_values = []
        for key, value in request.form.to_dict().items():
            if key != 'farm_id':  # Preskačemo farm_id
                try:
                    float_value = float(value)
                    if float_value < 0:
                        invalid_values.append(key)
                        app.logger.warning(f'Negativna vrednost za {key}: {value}')
                except ValueError:
                    invalid_values.append(key)
                    app.logger.warning(f'Nevažeća vrednost za {key}: {value}')
        
        if invalid_values:
            app.logger.error(f'Nevažeće vrednosti za polja: {", ".join(invalid_values)}')
            flash('Sve cene moraju biti pozitivni brojevi.', 'danger')
            return redirect(url_for('users.my_farm', farm_id=farm_id))
        
        try:
            # Kreiranje rečnika usluga
            service_dict = {
                "klanje": {
                    str(i): request.form.get(f'klanje_{i}')
                    for i in range(1, 9)
                },
                "obrada": {
                    str(i): request.form.get(f'obrada_{i}')
                    for i in range(1, 4)
                }
            }
            
            # Čuvanje u bazi
            farm.services = service_dict
            db.session.commit()
            app.logger.info(f'Uspešno sačuvane usluge za farmu {farm_id}')
            flash('Uspešno ste sačuvali cene usluga.', 'success')
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Greška pri čuvanju usluga: {str(e)}')
            flash('Došlo je do greške pri čuvanju usluga. Molimo pokušajte ponovo.', 'danger')
            
        return redirect(url_for('users.my_farm', farm_id=farm_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri čuvanju usluga: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/get_animal_subcategories", methods=['GET'])
def get_animal_subcategories():
    category = request.args.get('category')
    subcategories = AnimalCategorization.query.filter_by(animal_category_id=category, intended_for='priplod').all()
    subcategories_options = [{'value': subcategory.subcategory, 'text': subcategory.subcategory} for subcategory in subcategories]
    print(f'subcategories_options: {subcategories_options}')
    return jsonify(subcategories_options)


@users.route("/get_races", methods=['GET'])
def get_races():
    category = request.args.get('category')
    print(f'get_races: {category=}')
    races = AnimalRace.query.filter_by(animal_category_id=category).all()
    races_options = [{'value': race.id, 'text': race.animal_race_name} for race in races]
    print(f'races_options: {races_options}')
    return jsonify(races_options)



@users.route("/my_market/<int:farm_id>", methods=['GET', 'POST'])
def my_market(farm_id):
    """
    Prikaz i upravljanje proizvodima na farmi.
    
    Args:
        farm_id (int): ID farme čiji se proizvodi prikazuju
        
    Methods:
        GET: Prikazuje listu proizvoda i formu za dodavanje novog
        POST: Dodaje novi proizvod
        
    Returns:
        GET: Renderovan template sa proizvodima i formom
        POST: Redirect na istu stranicu nakon dodavanja
    """
    try:
        # Provera i učitavanje farme
        farm = Farm.query.get_or_404(farm_id)
        app.logger.info(f'Pristup proizvodima farme {farm_id} od strane {current_user.email}')
        
        # Provera pristupa
        if current_user.id != farm.user_id:
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti proizvodima farme {farm_id}')
            flash('Nemate pravo pristupa ovoj stranici.', 'danger')
            return redirect(url_for('main.home'))
            
        try:
            # Učitavanje proizvoda
            products = Product.query.filter_by(farm_id=farm_id).all()
            app.logger.debug(f'Učitano {len(products)} proizvoda')
            
            # Učitavanje i filtriranje faktura
            invoice_items = InvoiceItems.query.filter_by(
                farm_id=farm_id,
                invoice_item_type=1
            ).all()
            invoice_items = [
                item for item in invoice_items 
                if item.invoice.status in ['confirmed', 'paid']
            ]
            app.logger.debug(f'Učitano {len(invoice_items)} faktura')
            
            # Računanje ukupne prodaje
            total_sales = 0.0
            for item in invoice_items:
                try:
                    total_sales += float(item.invoice_item_details['total_price'])
                except (KeyError, ValueError, TypeError) as e:
                    app.logger.error(f'Greška pri računanju prodaje za fakturu {item.id}: {str(e)}')
                    
            app.logger.info(f'Ukupna prodaja za farmu {farm_id}: {total_sales}')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju podataka: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            products = []
            invoice_items = []
            total_sales = 0.0
            
        # Inicijalizacija forme
        form = AddProductForm()
        try:
            form.category.choices = [
                (category.id, category.product_category_name) 
                for category in ProductCategory.query.all()
            ]
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kategorija: {str(e)}')
            form.category.choices = []
            flash('Došlo je do greške pri učitavanju kategorija.', 'warning')
            
        # Obrada POST zahteva
        if request.method == 'POST':
            app.logger.info(f'Pokušaj dodavanja novog proizvoda na farmu {farm_id}')
            
            try:
                # Validacija konverzije težine
                weight_conversion = 1.0
                if form.unit_of_measurement.data == 'kom':
                    try:
                        weight_conversion = float(form.weight_conversion.data)
                        if weight_conversion <= 0:
                            raise ValueError('Konverzija težine mora biti pozitivan broj')
                    except ValueError as e:
                        app.logger.error(f'Nevažeća konverzija težine: {str(e)}')
                        flash('Konverzija težine mora biti pozitivan broj.', 'danger')
                        return redirect(url_for('users.my_market', farm_id=farm_id))
                
                # Kreiranje novog proizvoda
                new_product = Product(
                    product_image='default.jpg',
                    product_category_id=int(form.category.data),
                    product_subcategory_id=int(form.subcategory.data),
                    product_section_id=int(form.section.data),
                    product_name=form.product_name.data,
                    product_description=form.product_description.data,
                    unit_of_measurement=form.unit_of_measurement.data,
                    weight_conversion=weight_conversion,
                    product_price_per_unit_farmer=float(form.product_price_per_unit.data),
                    product_price_per_unit=float(form.product_price_per_unit.data) * 1.38,
                    product_price_per_kg=(
                        (float(form.product_price_per_unit.data) / weight_conversion) * 1.38 
                        if form.unit_of_measurement.data == 'kom' 
                        else float(form.product_price_per_unit.data) * 1.38
                    ),
                    organic_product=form.organic_product.data,
                    quantity=float(form.quantity.data),
                    farm_id=farm.id,
                    product_image_collection=[]
                )
                
                db.session.add(new_product)
                db.session.commit()
                app.logger.info(f'Uspešno dodat novi proizvod ID {new_product.id}')
                flash('Uspešno ste dodali novi proizvod', 'success')
                
            except ValueError as e:
                app.logger.error(f'Greška pri validaciji podataka: {str(e)}')
                flash('Molimo proverite unete vrednosti.', 'danger')
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri dodavanju proizvoda: {str(e)}')
                flash('Došlo je do greške pri dodavanju proizvoda. Molimo pokušajte ponovo.', 'danger')
                
            return redirect(url_for('users.my_market', farm_id=farm_id))
            
        return render_template('my_market.html',
                            title='Moja prodavnica',
                            user=current_user,
                            products=products,
                            invoice_items=invoice_items,
                            total_sales=total_sales,
                            form=form,
                            farm=farm)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/get_product_subcategories", methods=['GET'])
def get_product_subcategories():
    category = request.args.get('category')
    print(f'get_product_subcategories: {category=}')
    subcategories = ProductSubcategory.query.filter_by(product_category_id=category).all()
    subcategories_options = [{'value': subcategory.id, 'text': subcategory.product_subcategory_name} for subcategory in subcategories]
    print(f'subcategories_options: {subcategories_options}')
    return jsonify(subcategories_options)


@users.route("/get_product_sections", methods=['GET'])
def get_product_sections():
    subcategory = request.args.get('subcategory')
    print(f'get_product_sections: {subcategory=}')
    sections = ProductSection.query.filter_by(product_subcategory_id=subcategory).all()
    sections_options = [{'value': section.id, 'text': section.product_section_name} for section in sections]
    print(f'sections_options: {sections_options}')
    return jsonify(sections_options)


#! ispod je za user !#
#! ispod je za user !#
#! ispod je za user !#

@users.route("/my_fattening/<int:user_id>", methods=['GET', 'POST'])
def my_fattening(user_id):
    """
    Prikaz životinja u tovu za ulogovanog kupca.
    
    Args:
        user_id (int): ID korisnika čije se životinje prikazuju
        
    Methods:
        GET: Prikazuje listu životinja u tovu
        
    Returns:
        Renderovan template sa životinjama u tovu
    """
    try:
        # Provera i učitavanje korisnika
        user = User.query.get_or_404(user_id)
        app.logger.info(f'Pristup životinjama u tovu za korisnika {user_id} od strane {current_user.email}')
        
        # Provera pristupa
        if current_user.id != user_id:
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti životinjama korisnika {user_id}')
            flash('Nemate pravo pristupa ovim podacima.', 'danger')
            return redirect(url_for('main.home'))
            
        try:
            # Učitavanje plaćenih faktura
            my_invoices = Invoice.query.filter_by(
                user_id=user_id,
                status="paid"
            ).all()
            invoice_ids = [invoice.id for invoice in my_invoices]
            app.logger.debug(f'Učitano {len(invoice_ids)} plaćenih faktura')
            
            # Učitavanje životinja u tovu
            animals = Animal.query.filter(
                Animal.fattening == True,
                Animal.intended_for == "tov"
            ).all()
            
            # Filtriranje životinja po fakturama
            my_fattening_animals = [
                animal for animal in animals 
                if animal.invoice_id in invoice_ids
            ]
            app.logger.info(f'Pronađeno {len(my_fattening_animals)} životinja u tovu za korisnika {user_id}')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju podataka: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            my_fattening_animals = []
            
        return render_template('my_fattening.html',
                            title='Moje stado',
                            my_fattening_animals=my_fattening_animals,
                            user=user)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/my_shop/<int:user_id>", methods=['GET', 'POST'])
def my_shop(user_id):
    """
    Prikaz kupljenih proizvoda i usluga za korisnika.
    
    Args:
        user_id (int): ID korisnika čije se kupovine prikazuju
        
    Methods:
        GET: Prikazuje listu kupljenih proizvoda i usluga
        
    Returns:
        Renderovan template sa kupljenim proizvodima i uslugama
    """
    try:
        # Provera i učitavanje korisnika
        user = User.query.get_or_404(user_id)
        app.logger.info(f'Pristup kupovinama za korisnika {user_id} od strane {current_user.email}')
        
        # Provera pristupa
        if current_user.id != user_id:
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti kupovinama korisnika {user_id}')
            flash('Nemate pravo pristupa ovim podacima.', 'danger')
            return redirect(url_for('main.home'))
            
        try:
            # Učitavanje plaćenih faktura
            my_invoices = Invoice.query.filter_by(
                user_id=user_id,
                status="paid"
            ).all()
            invoice_ids = [invoice.id for invoice in my_invoices]
            app.logger.debug(f'Učitano {len(invoice_ids)} plaćenih faktura')
            
            # Učitavanje i filtriranje stavki faktura
            # invoice_item_type: 1 = proizvod, 2 = usluga
            my_invoice_items = InvoiceItems.query.filter(
                InvoiceItems.invoice_id.in_(invoice_ids),
                InvoiceItems.invoice_item_type.in_([1, 2])
            ).all()
            
            app.logger.info(f'Pronađeno {len(my_invoice_items)} kupljenih proizvoda i usluga za korisnika {user_id}')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju podataka: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            my_invoice_items = []
            
        return render_template('my_shop.html',
                            title='Moja prodavnica',
                            my_invoice_items=my_invoice_items,
                            user=user)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


#! ispod je za admin !#
#! ispod je za admin !#
#! ispod je za admin !#

@users.route("/settings", methods=['GET', 'POST'])
def settings():
    """
    Podešavanja sistema - samo za administratore.
    
    Methods:
        GET: Prikazuje formu za podešavanje cena kategorija životinja
        POST: Čuva izmenjene cene kategorija
        
    Returns:
        GET: Renderovan template sa formom za podešavanja
        POST: Redirect na istu stranicu nakon čuvanja
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning(f'Pokušaj pristupa podešavanjima od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti admin podešavanjima')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup admin podešavanjima od strane {current_user.email}')
        
        # Obrada POST zahteva
        if request.method == 'POST':
            try:
                # Validacija i čuvanje cena
                invalid_prices = []
                for key, value in request.form.items():
                    try:
                        # Provera da li je cena validan broj
                        price = float(value)
                        if price < 0:
                            invalid_prices.append(key)
                            continue
                            
                        # Ažuriranje cene kategorije
                        category = AnimalCategorization.query.filter_by(id=key).first()
                        if category:
                            category.fattening_price = price
                            app.logger.debug(f'Ažurirana cena za kategoriju {category.id}: {price}')
                        else:
                            app.logger.warning(f'Kategorija {key} nije pronađena')
                            
                    except ValueError:
                        invalid_prices.append(key)
                        app.logger.warning(f'Nevažeća cena za kategoriju {key}: {value}')
                        
                if invalid_prices:
                    app.logger.error(f'Nevažeće cene za kategorije: {", ".join(invalid_prices)}')
                    flash('Sve cene moraju biti pozitivni brojevi.', 'danger')
                    return redirect(url_for('users.settings'))
                    
                # Čuvanje promena
                db.session.commit()
                app.logger.info('Uspešno sačuvane izmenjene cene kategorija')
                flash('Uspešno ste sačuvali izmenjene cene.', 'success')
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri čuvanju cena: {str(e)}')
                flash('Došlo je do greške pri čuvanju cena. Molimo pokušajte ponovo.', 'danger')
                
            return redirect(url_for('users.settings'))
            
        try:
            # Učitavanje kategorija za tov
            categorization = AnimalCategorization.query.filter_by(
                intended_for="tov"
            ).all()
            app.logger.debug(f'Učitano {len(categorization)} kategorija za tov')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kategorija: {str(e)}')
            flash('Došlo je do greške pri učitavanju kategorija. Molimo pokušajte ponovo.', 'warning')
            categorization = []
            
        return render_template('settings.html',
                            title='Podešavanja',
                            categorization=categorization)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route('/deactivate_farm_user/<int:user_id>')
def deactivate_farm_user(user_id):
    """
    Deaktivacija poljoprivrednog gazdinstva - samo za administratore.
    
    Args:
        user_id (int): ID korisnika čije se PG deaktivira
        
    Returns:
        Redirect na admin pregled farmi nakon deaktivacije
    """
    try:
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava deaktivirati PG')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pokušaj deaktivacije PG za korisnika {user_id} od strane {current_user.email}')
        
        try:
            # Učitavanje korisnika
            user = User.query.get_or_404(user_id)
            app.logger.debug(f'Učitan korisnik {user_id} sa tipom {user.user_type}')
            
            # Provera tipa korisnika
            if user.user_type in ['user', 'user_removed', 'guest', 'admin']:
                app.logger.warning(f'Pokušaj deaktivacije nepoljoprivrednog korisnika {user_id}')
                flash('Nije moguće menjati status korisnika jer nemaju poljoprivredno gazdinstvo.', 'danger')
                return redirect(url_for('users.admin_view_farms'))
                
            # Provera da li je PG već aktivno
            if user.user_type != 'farm_active':
                app.logger.warning(f'Pokušaj deaktivacije neaktivnog PG {user_id}')
                flash('Poljoprivredno gazdinstvo nije aktivno.', 'danger')
                return redirect(url_for('users.admin_view_farms'))
                
            try:
                # Deaktivacija PG
                user.user_type = 'farm_inactive'
                db.session.commit()
                app.logger.info(f'Uspešno deaktivirano PG za korisnika {user_id}')
                flash('Poljoprivredno gazdinstvo je deaktivirano.', 'success')
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri deaktivaciji PG: {str(e)}')
                flash('Došlo je do greške pri deaktivaciji. Molimo pokušajte ponovo.', 'danger')
                
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju korisnika {user_id}: {str(e)}')
            flash('Korisnik nije pronađen.', 'danger')
            
        return redirect(url_for('users.admin_view_farms'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route('/activate_farm_user/<int:user_id>')
def activate_farm_user(user_id):
    """
    Aktivacija poljoprivrednog gazdinstva - samo za administratore.
    
    Args:
        user_id (int): ID korisnika čije se PG aktivira
        
    Returns:
        Redirect na admin pregled farmi nakon aktivacije
        
    Note:
        TODO: Dodati mogućnost povezivanja ugovora kroz modal i formu za upload fajla prilikom aktivacije
    """
    try:
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava aktivirati PG')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pokušaj aktivacije PG za korisnika {user_id} od strane {current_user.email}')
        
        try:
            # Učitavanje korisnika
            user = User.query.get_or_404(user_id)
            app.logger.debug(f'Učitan korisnik {user_id} sa tipom {user.user_type}')
            
            # Provera tipa korisnika
            if user.user_type in ['user', 'user_removed', 'guest', 'admin']:
                app.logger.warning(f'Pokušaj aktivacije nepoljoprivrednog korisnika {user_id}')
                flash('Nije moguće aktivirati korisnika jer nema poljoprivredno gazdinstvo.', 'danger')
                return redirect(url_for('users.admin_view_farms'))
                
            # Provera da li je PG već aktivno
            if user.user_type != 'farm_inactive':
                app.logger.warning(f'Pokušaj aktivacije već aktivnog PG {user_id}')
                flash('Poljoprivredno gazdinstvo je već aktivno.', 'danger')
                return redirect(url_for('users.admin_view_farms'))
                
            try:
                # Aktivacija PG
                user.user_type = 'farm_active'
                db.session.commit()
                app.logger.info(f'Uspešno aktivirano PG za korisnika {user_id}')
                flash('Poljoprivredno gazdinstvo je aktivirano.', 'success')
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri aktivaciji PG: {str(e)}')
                flash('Došlo je do greške pri aktivaciji. Molimo pokušajte ponovo.', 'danger')
                
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju korisnika {user_id}: {str(e)}')
            flash('Korisnik nije pronađen.', 'danger')
            
        return redirect(url_for('users.admin_view_farms'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route('/remove_farm_user/<int:user_id>')
def remove_farm_user(user_id):
    """
    Brisanje poljoprivrednog gazdinstva i korisnika - samo za administratore.
    
    Args:
        user_id (int): ID korisnika čije se PG brise
        
    Returns:
        Redirect na admin pregled farmi nakon brisanja
        
    Note:
        TODO: Dodati mogućnost povezivanja ugovora kroz modal i formu za upload fajla prilikom brisanja
    """
    try:
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava obrisati PG')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pokušaj brisanja PG za korisnika {user_id} od strane {current_user.email}')
        
        try:
            user = User.query.get_or_404(user_id)
            # Pronalazimo farmu koja pripada korisniku
            farm = Farm.query.filter_by(user_id=user.id).first_or_404()
            if user.user_type in ['farm_unverified', 'farm_inactive']:
                db.session.delete(farm)
                db.session.delete(user)
                db.session.commit()
                app.logger.info(f'Uspešno obrisano PG za korisnika {user_id} od strane {current_user.email}')
                flash('Poljoprivredno gazdinstvo je obrisano.', 'success')
            else:
                app.logger.warning(f'Pokušaj obrisivanja već aktivnog PG {user_id}')
                flash('Poljoprivredno gazdinstvo je već aktivno.', 'danger')
            return redirect(url_for('users.admin_view_farms'))
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.error(f'Greška pri brisanju PG za korisnika {user_id}: {str(e)}')
            flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
            return redirect(url_for('users.admin_view_farms'))
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))



@users.route("/admin_view_farms", methods=['GET', 'POST'])
def admin_view_farms():
    """
    Admin pregled svih poljoprivrednih gazdinstava.
    
    Methods:
        GET: Prikazuje listu svih PG-ova
        
    Returns:
        Renderovan template sa listom PG-ova
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj pristupa admin pregledu PG od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti admin pregledu PG')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup admin pregledu PG od strane {current_user.email}')
        
        try:
            # Učitavanje svih farmi
            farms = Farm.query.all()
            app.logger.debug(f'Učitano {len(farms)} poljoprivrednih gazdinstava')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju PG: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            farms = []
            
        return render_template('admin_view_farms.html',
                            title='Pregled poljoprivrednih gazdinstava',
                            farms=farms)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/admin_view_users", methods=['GET', 'POST'])
def admin_view_users():
    """
    Admin pregled svih korisnika sistema (ne uključuje PG).
    
    Methods:
        GET: Prikazuje listu svih korisnika
        
    Returns:
        Renderovan template sa listom korisnika
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj pristupa admin pregledu korisnika od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti admin pregledu korisnika')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup admin pregledu korisnika od strane {current_user.email}')
        
        try:
            # Import potrebnog modula
            from sqlalchemy import or_
            
            # Učitavanje korisnika (samo user i guest tipovi)
            users = User.query.filter(
                or_(
                    User.user_type == 'user',
                    User.user_type == 'guest'
                )
            ).all()
            
            app.logger.debug(f'Učitano {len(users)} korisnika')
            
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju korisnika: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            users = []
            
        return render_template('admin_view_users.html',
                            title='Pregled korisnika',
                            users=users)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/admin_view_purchases", methods=['GET', 'POST'])
def admin_view_purchases():
    """
    Admin pregled svih kupovina u sistemu.
    
    Methods:
        GET: Prikazuje listu svih potvrđenih i plaćenih kupovina
        
    Returns:
        Renderovan template sa listom kupovina
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj pristupa admin pregledu kupovina od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti admin pregledu kupovina')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup admin pregledu kupovina od strane {current_user.email}')
        
        try:
            # Učitavanje svih stavki faktura
            invoice_items = InvoiceItems.query.all()
            
            # Filtriranje po statusu
            valid_statuses = ['confirmed', 'paid']  # TODO: Dodati ostale statuse kad budu definisani
            invoice_items = [
                item for item in invoice_items 
                if item.invoice.status in valid_statuses
            ]
            app.logger.debug(f'Učitano {len(invoice_items)} stavki faktura')
            
            # Parsiranje detalja stavki
            for item in invoice_items:
                try:
                    if isinstance(item.invoice_item_details, str):
                        item.invoice_item_details = json.loads(item.invoice_item_details)
                        app.logger.debug(f'Uspešno parsirani detalji za stavku {item.id}')
                except json.JSONDecodeError as e:
                    app.logger.error(f'Greška pri parsiranju detalja za stavku {item.id}: {str(e)}')
                    item.invoice_item_details = {}
                except Exception as e:
                    app.logger.error(f'Neočekivana greška pri parsiranju detalja za stavku {item.id}: {str(e)}')
                    item.invoice_item_details = {}
                    
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju kupovina: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            invoice_items = []
            
        return render_template('admin_view_purchases.html',
                            title='Pregled kupovina',
                            invoice_items=invoice_items,
                            purchases=[])  # TODO: Ukloniti purchases ako se ne koristi
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/admin_view_overview", methods=['GET', 'POST'])
def admin_view_overview():
    """
    Admin pregled finansijskog stanja korisnika.
    
    Methods:
        GET: Prikazuje pregled dugovanja i uplata za sve korisnike
        
    Returns:
        Renderovan template sa finansijskim pregledom
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj pristupa admin pregledu stanja od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti admin pregledu stanja')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup admin pregledu stanja od strane {current_user.email}')
        
        try:
            # Učitavanje korisnika
            users = User.query.filter_by(user_type='user').all()
            app.logger.debug(f'Učitano {len(users)} korisnika')
            
            # Računanje finansijskog stanja za svakog korisnika
            for user in users:
                try:
                    # Računanje ukupnih dugovanja
                    user_debts_total = db.session.query(
                        func.sum(Debt.amount)
                    ).filter_by(user_id=user.id).scalar() or 0
                    
                    # Računanje ukupnih uplata
                    user_payments_total = db.session.query(
                        func.sum(Payment.amount)
                    ).filter_by(user_id=user.id).scalar() or 0
                    
                    # Postavljanje vrednosti
                    user.debts_total = user_debts_total
                    user.payments_total = user_payments_total
                    user.saldo = user_debts_total - user_payments_total
                    
                    app.logger.debug(
                        f'Izračunato stanje za korisnika {user.id}: '
                        f'dugovanja={user_debts_total}, '
                        f'uplate={user_payments_total}, '
                        f'saldo={user.saldo}'
                    )
                    
                except Exception as e:
                    app.logger.error(f'Greška pri računanju stanja za korisnika {user.id}: {str(e)}')
                    user.debts_total = 0
                    user.payments_total = 0
                    user.saldo = 0
                    
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju podataka: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            users = []
            
        return render_template('admin_view_overview.html',
                            title='Pregled finansijskog stanja',
                            users=users)
                            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/admin_view_overview_user/<int:user_id>", methods=['GET', 'POST'])
def admin_view_overview_user(user_id):
    """
    Admin pregled finansijskog stanja pojedinačnog korisnika.
    
    Args:
        user_id (int): ID korisnika čije se stanje pregleda
        
    Methods:
        GET: Prikazuje detaljan pregled dugovanja i uplata za korisnika
        
    Returns:
        Renderovan template sa detaljnim finansijskim pregledom
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj pristupa detaljnom pregledu od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti detaljnom pregledu korisnika {user_id}')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup detaljnom pregledu korisnika {user_id} od strane {current_user.email}')
        
        try:
            # Učitavanje korisnika i transakcija
            user = User.query.get_or_404(user_id)
            debts = Debt.query.filter_by(user_id=user.id).all()
            payments = Payment.query.filter_by(user_id=user.id).all()
            
            app.logger.debug(f'Učitano {len(debts)} dugovanja i {len(payments)} uplata za korisnika {user_id}')
            
            # Inicijalizacija rečnika za tovove
            tovovi = {}
            
            # Obrada dugovanja
            for debt in debts:
                try:
                    if debt.invoice_item.invoice_item_type == 4:
                        tov_id = debt.invoice_item_id
                        if tov_id not in tovovi:
                            tovovi[tov_id] = []
                        
                        tovovi[tov_id].append({
                            'date': debt.invoice_item.invoice.datetime,
                            'description': "Zaduženje: " + debt.invoice_item.invoice_item_details['category'],
                            'debt': debt.amount,
                            'debt_id': debt.id,
                            'payment': 0,
                            'payment_statement_id': None,
                            'type': 'debt'
                        })
                        app.logger.debug(f'Obrađeno dugovanje {debt.id} za tov {tov_id}')
                except Exception as e:
                    app.logger.error(f'Greška pri obradi dugovanja {debt.id}: {str(e)}')
                    continue
            
            # Obrada uplata
            for payment in payments:
                try:
                    tov_id = payment.invoice_item_id
                    if payment.invoice_item.invoice_item_type == 4:
                        if tov_id not in tovovi:
                            tovovi[tov_id] = []
                        
                        tovovi[tov_id].append({
                            'date': payment.payment_statement_payment.payment_date,
                            'description': "Uplata za: " + payment.invoice_item.invoice_item_details['category'],
                            'debt': 0,
                            'debt_id': None,
                            'payment': payment.amount,
                            'payment_statement_id': payment.payment_statement_id,
                            'type': 'payment'
                        })
                        app.logger.debug(f'Obrađena uplata {payment.id} za tov {tov_id}')
                except Exception as e:
                    app.logger.error(f'Greška pri obradi uplate {payment.id}: {str(e)}')
                    continue

            # Sortiranje transakcija i računanje salda
            try:
                for tov_id, transactions in tovovi.items():
                    transactions.sort(key=itemgetter('date'))
                    saldo = 0
                    for transaction in transactions:
                        saldo = saldo - transaction['debt'] + transaction['payment']
                        transaction['saldo'] = saldo
                    app.logger.debug(f'Izračunat saldo za tov {tov_id}: {saldo}')

                total_saldo = sum(transactions[-1]['saldo'] for transactions in tovovi.values() if transactions)
                app.logger.info(f'Ukupan saldo za korisnika {user_id}: {total_saldo}')
                
            except Exception as e:
                app.logger.error(f'Greška pri računanju salda: {str(e)}')
                total_saldo = 0
                
            return render_template('admin_view_overview_user.html',
                                user=user,
                                tovovi=tovovi,
                                total_saldo=total_saldo,
                                title='Detaljan pregled stanja korisnika')
                                
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju podataka za korisnika {user_id}: {str(e)}')
            flash('Došlo je do greške pri učitavanju podataka. Molimo pokušajte ponovo.', 'warning')
            return redirect(url_for('users.admin_view_overview'))
            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/cancel_fattening/<int:invoice_item_id>", methods=['POST', 'GET'])
def cancel_fattening(invoice_item_id):
    """
    Otkazivanje tova za određenu stavku fakture.
    
    Args:
        invoice_item_id (int): ID stavke fakture za koju se otkazuje tov
        
    Returns:
        Redirect na pregled stanja korisnika nakon otkazivanja tova
    Note:
        TODO: napraviti logiku da ako je za životinju već prekinut tov da se u html ne vidi dugme "Prekini tov"
        TODO: implementirati slanje informacionog mejla (adminu, farmeru, korisniku?) o prekinutom tovu i daljim koracima
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj otkazivanja tova od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava otkazati tov')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        try:
            # Učitavanje stavke fakture
            invoice_item = InvoiceItems.query.get_or_404(invoice_item_id)
            user_id = invoice_item.invoice.user_id  # Dobavljanje user_id preko invoice relacije
            
            app.logger.info(f'Pokušaj otkazivanja tova za stavku {invoice_item_id} od strane {current_user.email}')
            
            try:
                # Učitavanje ID-a životinje iz detalja stavke
                invoice_details = invoice_item.invoice_item_details
                app.logger.debug(f'Detalji stavke fakture: {invoice_details}')
                
                if 'animal_id' not in invoice_details:
                    app.logger.error(f'Nedostaje animal_id u detaljima stavke: {invoice_details}')
                    flash('Greška: Nedostaje ID životinje u stavci fakture.', 'danger')
                    return redirect(url_for('users.admin_view_overview_user', user_id=user_id))
                
                animal_id = invoice_details['id']
                app.logger.debug(f'Pronađen animal_id: {animal_id}')
                
                # Provera da li životinja postoji
                animal = Animal.query.get(animal_id)
                if not animal:
                    app.logger.error(f'Životinja sa ID {animal_id} nije pronađena')
                    flash('Životinja nije pronađena u bazi.', 'danger')
                    return redirect(url_for('users.admin_view_overview_user', user_id=user_id))
                
                # Otkazivanje tova
                animal.fattening = False
                db.session.commit()
                
                app.logger.info(f'Uspešno otkazan tov za životinju {animal_id} (stavka {invoice_item_id})')
                flash('Tov je uspešno otkazan.', 'success')
                
            except KeyError as e:
                app.logger.error(f'Greška pri pristupu ID-u životinje: {str(e)}')
                flash('Greška u podacima stavke fakture.', 'danger')
                db.session.rollback()
            except Exception as e:
                app.logger.error(f'Greška pri otkazivanju tova: {str(e)}')
                flash('Došlo je do greške pri otkazivanju tova.', 'danger')
                db.session.rollback()
                
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju stavke fakture {invoice_item_id}: {str(e)}')
            flash('Stavka fakture nije pronađena.', 'danger')
            return redirect(url_for('users.admin_view_overview'))
            
        return redirect(url_for('users.admin_view_overview_user', user_id=user_id))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))



@users.route("/admin_view_slips", methods=['GET', 'POST'])
def admin_view_slips():
    """
    Prikazuje pregled svih izvoda za administratora.
    
    Returns:
        Template sa pregledom izvoda ili redirect na početnu stranu ako korisnik nema prava pristupa
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj pristupa pregledu izvoda od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava pristupiti pregledu izvoda')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        app.logger.info(f'Pristup pregledu izvoda od strane {current_user.email}')
        
        try:
            # Učitavanje svih izvoda
            payment_statements = PaymentStatement.query.order_by(PaymentStatement.payment_date.desc()).all()
            app.logger.debug(f'Učitano {len(payment_statements)} izvoda')
            
            # Računanje ukupnih iznosa
            total_amount = sum(stmt.total_payment_amount for stmt in payment_statements)
            total_errors = sum(stmt.number_of_errors for stmt in payment_statements)
            app.logger.debug(f'Ukupan iznos svih uplata: {total_amount}, ukupno grešaka: {total_errors}')
            
            return render_template('admin_view_slips.html',
                                title='Pregled izvoda',
                                payment_statements=payment_statements,
                                total_amount=total_amount,
                                total_errors=total_errors)
                                
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju izvoda: {str(e)}')
            flash('Došlo je do greške pri učitavanju izvoda.', 'danger')
            return redirect(url_for('users.admin_view_overview'))
            
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


@users.route("/admin_edit_profile/<int:user_id>", methods=['GET', 'POST'])
def admin_edit_profile(user_id):
    if not current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if current_user.user_type != 'admin':
        flash('Nemate pravo pristupa', 'danger')
        return redirect(url_for('main.home'))
    user = User.query.get_or_404(user_id)
    if user.user_type not in ['user', 'user_unverified']:
        flash('Nije moguće promeniti profil gosta.', 'danger')
        return redirect(url_for('main.home'))
    form = EditProfileForm()
    if form.validate_on_submit():
        print('form validated')
        user.name = form.name.data
        user.surname = form.surname.data
        user.email = form.email.data
        user.address = form.address.data
        user.zip_code = form.zip_code.data
        user.city = form.city.data
        user.jmbg = form.jmbg.data
        db.session.commit()
        flash('Uspešno ste sačuvali izmene na profilu.', 'success')
        return redirect(url_for('users.admin_view_users', user_id=user.id))
    print(f'form not validated')
    form.name.data = user.name
    form.surname.data = user.surname
    form.email.data = user.email
    form.address.data = user.address
    form.zip_code.data = user.zip_code
    form.city.data = user.city
    form.jmbg.data = user.JMBG
    return render_template('admin_edit_profile.html',
                            user=user,
                            title='Uredi profil',
                            form=form)


@users.route("/admin_remove_user/<int:user_id>", methods=['POST'])
def admin_remove_user(user_id):
    """
    Briše korisnika iz sistema. Ova operacija je nepovratna.
    
    Args:
        user_id (int): ID korisnika koji se briše
        
    Returns:
        Redirect na pregled korisnika nakon brisanja ili na početnu stranu u slučaju greške
        
    Note:
        - Samo POST metoda je dozvoljena za ovu operaciju
        - Proverava se da li korisnik ima aktivne transakcije pre brisanja
        - Implementiran je soft delete ako postoje povezani podaci
    """
    try:
        # Provera autentikacije
        if not current_user.is_authenticated:
            app.logger.warning('Pokušaj brisanja korisnika od strane neautentifikovanog korisnika')
            flash('Morate biti prijavljeni.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera admin prava
        if current_user.user_type != 'admin':
            app.logger.warning(f'Nedozvoljen pristup: {current_user.email} pokušava obrisati korisnika {user_id}')
            flash('Nemate administratorska prava.', 'danger')
            return redirect(url_for('main.home'))
            
        # Provera da li se admin pokušava sam obrisati
        if current_user.id == user_id:
            app.logger.warning(f'Admin {current_user.email} pokušava obrisati svoj nalog')
            flash('Ne možete obrisati svoj administratorski nalog.', 'danger')
            return redirect(url_for('users.admin_view_users'))
            
        try:
            # Učitavanje korisnika
            user = User.query.get_or_404(user_id)
            app.logger.info(f'Pokušaj brisanja korisnika {user.email} od strane {current_user.email}')
            
            # Provera da li korisnik ima aktivne transakcije
            debts = Debt.query.filter_by(user_id=user_id, status='pending').first()
            if debts:
                app.logger.warning(f'Pokušaj brisanja korisnika {user.email} sa aktivnim dugovanjima')
                flash('Nije moguće obrisati korisnika sa aktivnim dugovanjima.', 'danger')
                return redirect(url_for('users.admin_view_users'))
                
            try:
                # Brisanje povezanih podataka
                Payment.query.filter_by(user_id=user_id).delete()
                Debt.query.filter_by(user_id=user_id).delete()
                
                # Brisanje korisnika
                db.session.delete(user)
                db.session.commit()
                
                app.logger.info(f'Uspešno obrisan korisnik {user.email}')
                flash('Korisnik je uspešno obrisan.', 'success')
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Greška pri brisanju korisnika {user.email}: {str(e)}')
                flash('Došlo je do greške pri brisanju korisnika.', 'danger')
                
        except Exception as e:
            app.logger.error(f'Greška pri učitavanju korisnika {user_id}: {str(e)}')
            flash('Korisnik nije pronađen.', 'danger')
            
        return redirect(url_for('users.admin_view_users'))
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška: {str(e)}')
        flash('Došlo je do greške. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))