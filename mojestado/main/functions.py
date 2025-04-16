import os
from flask import session
from flask import current_app as app
from flask_mail import Message
from mojestado import mail


def clear_cart_session():
    """
    Čisti sve podatke o korpi iz sesije.
    
    Returns:
        bool: True ako je čišćenje uspešno, False ako je došlo do greške
    
    Raises:
        Exception: Ako dođe do greške prilikom pristupa ili modifikacije sesije
    """
    try:
        app.logger.debug('Započeto čišćenje korpe')
        
        # Lista svih ključeva koje treba očistiti
        cart_keys = ['animals', 'products', 'fattening', 'services', 'delivery']
        
        # Beležimo šta se briše
        items_to_clear = {key: session.get(key) for key in cart_keys if key in session}
        if items_to_clear:
            app.logger.info(f'Brisanje stavki iz korpe: {list(items_to_clear.keys())}')
        else:
            app.logger.info('Korpa je već prazna')
            return True

        # Čistimo trenutnu sesiju
        for key in cart_keys:
            if key in session:
                del session[key]
                app.logger.debug(f'Obrisan ključ iz sesije: {key}')
                
        session.modified = True
        app.logger.info('Korpa je uspešno očišćena')
        return True
        
    except Exception as e:
        app.logger.error(f'Greška prilikom čišćenja korpe: {str(e)}', exc_info=True)
        return False


def get_cart_total():
    """
    Računa ukupnu cenu korpe, cenu na rate i cenu dostave.
    
    Logika:
    - Ako je samo proizvod on ide preko kartice
    - Dostava se naplaćuje 500 din za porudžbine manje od 5000 din (samo za proizvode)
    - Ako imamo životinju, uslugu ili tov, to ide preko uplatnice (jedna rata)
    - Ako imamo životinju, uslugu i tov, moguće je odabrati na rate (dve ili više rata)
    
    Returns:
        tuple: (ukupna_cena, cena_na_rate, cena_dostave)
        
    Raises:
        ValueError: Ako dođe do greške pri konverziji cena
        Exception: Za ostale neočekivane greške
    """
    try:
        app.logger.debug('Započeto računanje ukupne cene korpe')
        cart_total = 0
        installment_total = 0
        delivery_total = 0
        #! implementirati cenu dostave životinje po kg: calculate_delivery_price(animal_weight):
        
        # Računanje cene proizvoda
        if 'products' in session and isinstance(session.get('products'), list):
            products = session['products']
            app.logger.debug(f'Pronađeno {len(products)} proizvoda u korpi')
            for product in products:
                try:
                    cart_total += float(product['total_price'])
                except (ValueError, KeyError) as e:
                    app.logger.error(f'Greška pri računanju cene proizvoda: {str(e)}')
                    raise ValueError(f'Neispravna cena proizvoda: {product.get("total_price")}')
                    
        # Računanje dostave za proizvode
        if 'products' in session and cart_total < 5000 and not session.get('animals', []):
            delivery_total = 500
            app.logger.debug('Dodata cena dostave od 500 din (porudžbina manja od 5000 din)')
            
        # Računanje cene životinja
        if 'animals' in session and isinstance(session.get('animals'), list):
            animals = session['animals']
            app.logger.debug(f'Pronađeno {len(animals)} životinja u korpi')
            for animal in animals:
                try:
                    # cart_total += float(animal['total_price']) #! ne dodaje se u korpu za uplatu preko kartice jer životinje ne moug preko kartice
                    installment_total += float(animal['total_price']) #! ali se dodaje u vrednost na rate iako se životinje plaćaju u jednom koraku
                except (ValueError, KeyError) as e:
                    app.logger.error(f'Greška pri računanju cene životinje: {str(e)}')
                    raise ValueError(f'Neispravna cena životinje: {animal.get("total_price")}')
                    
        # Računanje cene tova
        if 'fattening' in session and isinstance(session.get('fattening'), list):
            fattening_items = session['fattening']
            app.logger.debug(f'Pronađeno {len(fattening_items)} stavki tova u korpi')
            for fattening in fattening_items:
                try:
                    # cart_total += float(fattening['fattening_price']) #! ne dodaje se u korpu za uplatu preko kartice jer životinje ne moug preko kartice
                    installment_total += float(fattening['fattening_price']) #! ali se dodaje u vrednost na rate iako se tova plaća u jednom koraku
                except (ValueError, KeyError) as e:
                    app.logger.error(f'Greška pri računanju cene tova: {str(e)}')
                    raise ValueError(f'Neispravna cena tova: {fattening.get("fattening_price")}')
                    
        # Računanje cene usluga
        if 'services' in session and isinstance(session.get('services'), list):
            services = session['services']
            app.logger.debug(f'Pronađeno {len(services)} usluga u korpi')
            for service in services:
                try:
                    service_total = float(service.get('slaughterPrice', 0)) + float(service.get('processingPrice', 0))
                    # cart_total += service_total #! ne dodaje se u korpu za uplatu preko kartice jer usluge ne moug preko kartice
                    installment_total += service_total #! ali se dodaje u vrednost na rate iako se usluge plaća u jednom koraku
                    app.logger.debug(f'Dodata cena usluge: {service_total}')
                except (ValueError, KeyError) as e:
                    app.logger.error(f'Greška pri računanju cene usluge: {str(e)}')
                    raise ValueError(f'Neispravna cena usluge: {service}')
                    
        app.logger.info(f'Ukupna cena korpe: {cart_total}, Na rate: {installment_total}, Dostava: {delivery_total}')
        return cart_total, installment_total, delivery_total
        
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri računanju ukupne cene: {str(e)}', exc_info=True)
        raise


def calculate_delivery_price(animal_weight):
    """
    Računa cenu dostave na osnovu težine životinje.
    
    Args:
        animal_weight (float): Težina životinje u kilogramima
        
    Returns:
        int: Cena dostave u dinarima
        
    Raises:
        ValueError: Ako je težina manja od 1 kg ili veća od 800 kg
        TypeError: Ako težina nije broj
    """
    try:
        # Konvertujemo težinu u float ako već nije
        weight = float(animal_weight)
        
        app.logger.debug(f'Računanje cene dostave za težinu: {weight} kg')
        
        # Provera validnosti težine
        if weight < 1 or weight > 800:
            error_msg = f'Težina životinje ({weight} kg) je van dozvoljenog opsega (1-800 kg)'
            app.logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Određivanje cene dostave
        if weight < 30:
            price = 1000
        elif weight < 80:
            price = 1200
        elif weight < 130:
            price = 1500
        elif weight < 200:
            price = 1800
        else:  # 200-800 kg
            price = 3000
            
        app.logger.info(f'Cena dostave za težinu {weight} kg je {price} din')
        return price
        
    except ValueError as e:
        if str(e).startswith('Težina životinje'):
            raise  # Prosleđujemo našu ValueError grešku
        error_msg = f'Neispravna vrednost za težinu: {animal_weight}'
        app.logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f'Neočekivana greška pri računanju cene dostave: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        raise


def send_faq_email(email, question):
    """
    Šalje email sa FAQ pitanjem administratoru.
    
    Args:
        email (str): Email adresa korisnika koji postavlja pitanje
        question (str): Tekst pitanja
        
    Returns:
        bool: True ako je email uspešno poslat, False ako je došlo do greške
        
    Raises:
        ValueError: Ako je email ili pitanje prazno
    """
    try:
        # Validacija ulaznih parametara
        if not email or not isinstance(email, str):
            error_msg = f'Neispravna email adresa: {email}'
            app.logger.error(error_msg)
            raise ValueError(error_msg)
            
        if not question or not isinstance(question, str):
            error_msg = 'Pitanje ne može biti prazno'
            app.logger.error(error_msg)
            raise ValueError(error_msg)
            
        app.logger.debug(f'Priprema FAQ email-a od korisnika: {email}')
        
        # Priprema email poruke
        subject = 'Novo pitanje na portalu "Moje stado"'
        body = f'''
Pitanje: {question}

Poslato od korisnika sa email adrese: {email}'''
        
        # Kreiranje i slanje poruke
        try:
            message = Message(
                subject=subject,
                recipients=[app.config['MAIL_ADMIN']],
                body=body,
                reply_to=email
            )
            
            mail.send(message)
            app.logger.info(f'FAQ pitanje uspešno poslato od {email}')
            return True
            
        except Exception as e:
            error_msg = f'Greška pri slanju email-a: {str(e)}'
            app.logger.error(error_msg, exc_info=True)
            return False
            
    except ValueError as e:
        # Prosleđujemo ValueError dalje
        raise
    except Exception as e:
        error_msg = f'Neočekivana greška pri slanju FAQ email-a: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        return False


def optimize_image(image_file, max_size_kb=500, allowed_formats=None):
    """
    Optimizuje veličinu slike bez promene dimenzija.
    
    Parameters:
    - image_file: File-like objekat (npr. request.files['picture'])
    - max_size_kb: Maksimalna dozvoljena veličina slike u KB
    - allowed_formats: Lista dozvoljenih ekstenzija (npr. ['.jpg', '.jpeg', '.png', '.gif'])
    
    Returns:
    - tuple: (optimizovana_slika_bytes, format_slike, ekstenzija)
    - None: ako format nije dozvoljen
    """
    from PIL import Image
    import io
    
    # Provera formata ako je navedeno
    if allowed_formats:
        _, f_ext = os.path.splitext(image_file.filename.lower())
        if f_ext not in allowed_formats:
            return None, None, None
    
    # Čitanje slike u memoriju
    img = Image.open(image_file)
    
    # Detekcija formata
    img_format = img.format or 'JPEG'
    
    # Mapiranje ekstenzije na osnovu formata
    format_to_ext = {
        'JPEG': '.jpg',
        'PNG': '.png',
        'GIF': '.gif'
    }
    extension = format_to_ext.get(img_format, '.jpg')
    
    # Sačuvaj originalnu sliku u bytes buffer sa kvalitetom 100 da izmerimo veličinu
    img_io = io.BytesIO()
    img.save(img_io, format=img_format, quality=100)
    img_size_kb = len(img_io.getvalue()) / 1024
    
    # Ako je slika veća od max_size_kb, smanjujemo kvalitet
    if img_size_kb > max_size_kb:
        quality = 90  # Početni kvalitet
        while quality > 10:  # Minimalni kvalitet 10
            img_io = io.BytesIO()
            img.save(img_io, format=img_format, quality=quality)
            new_size_kb = len(img_io.getvalue()) / 1024
            
            if new_size_kb <= max_size_kb:
                break
                
            # Smanjujemo kvalitet za 10% svakim korakom
            quality -= 10
    
    img_io.seek(0)
    return img_io.getvalue(), img_format, extension