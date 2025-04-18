import base64, hashlib
import io
import datetime, os
import random, string

import requests

from PIL import Image

from mojestado import db, mail, app
from mojestado.models import Animal, Debt, Farm, Invoice, InvoiceItems, Product, User, PaySpotTransaction

from flask import flash, json, redirect, render_template, session, url_for
from flask_login import current_user
from flask_mail import Message, Attachment

from fpdf import FPDF

current_file_path = os.path.abspath(__file__)
project_folder = os.path.dirname(os.path.dirname((current_file_path)))
print(f'{current_file_path=}')
print(f'{project_folder=}')

font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')
font_path_I = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Oblique.ttf')


def add_fonts(pdf):
    pdf.add_font('DejaVuSansCondensed', '', font_path, uni=True)
    pdf.add_font('DejaVuSansCondensed', 'B', font_path_B, uni=True)
    pdf.add_font('DejaVuSansCondensed', 'I', font_path_I, uni=True)


def generate_payment_slips_attach(invoice_item):
    '''
    generiše 2+ uplatnice na jednom dokumentu (A4) u fpdf, qr kod/api iz nbs
    '''
    app.logger.info('Generisanje uplatnica za fakturu')
    data_list = []
    qr_code_images = []
    path = os.path.join(project_folder, 'static', 'payment_slips')
    invoice_item_details = invoice_item.invoice_item_details
    # invoice_item_details = json.loads(invoice_item.invoice_item_details)
    print(f'{invoice_item_details=}')
    broj_rata = int(invoice_item_details['installment_options'])
    print(f'** {broj_rata=}, {type(broj_rata)=}')
    for i in range(1, broj_rata+1):
        iznos_duga = float(invoice_item_details['fattening_price'])
        iznos_rate = iznos_duga/broj_rata
        print(f'{iznos_duga=}, {broj_rata=}, {iznos_rate=}')
        uplatilac = invoice_item.invoice.user_invoice.name + ' ' + invoice_item.invoice.user_invoice.surname
        sifra_placanja = f'189'
        model='00'
        poziv_na_broj = f'{invoice_item.invoice.user_id:05d}-{invoice_item.id:07d}'
        svrha_uplate = f'Uplata za uslugu tova - rata {i}'
        
        new_data = {
            'user_id': invoice_item.invoice.user_invoice.id,
            'uplatilac': invoice_item.invoice.user_invoice.name + ' ' + invoice_item.invoice.user_invoice.surname,
            'svrha_uplate': f'Uplata za uslugu tova - rata {i}',
            'primalac': 'Naša imperija doo',
            'sifra_placanja': '189',
            'valuta': 'RSD',
            'iznos': round(iznos_rate, 2),
            'racun_primaoca': '265178031000308698',
            'model': '00', #! ili 97?
            'poziv_na_broj': poziv_na_broj,
        }
        data_list.append(new_data)
        
        
        print(f'{uplatilac=}')
        print('generisane uplatnice na jednom dokumentu (A4). dokument će biti attachovan u email')
        qr_data = {
            "K": "PR",
            "V": "01",
            "C": "1",
            "R": "265178031000308698",
            "N": "Naša imperija doo", #! da li treba adresa? Kneza Grbovića 10 || 14242 Mionica
            "I": f'RSD{str(f"{round(iznos_rate, 2):.2f}").replace(".", ",")}',
            "P": uplatilac,
            "SF": sifra_placanja,
            "S": svrha_uplate if len(svrha_uplate) < 36 else svrha_uplate[:35], #! za generisanje QR koda maksimalno može da bude 35 karaktera
            "RO": f'{model}{poziv_na_broj}'
        }
        print(f'{qr_data=}')
        #! dokumentacija: https://ips.nbs.rs/PDF/Smernice_Generator_Validator_latinica_feb2023.pdf
        #! dokumentacija: https://ips.nbs.rs/PDF/pdfPreporukeNovoLat.pdf
        url = 'https://nbs.rs/QRcode/api/qr/v1/gen/250'
        headers = { 'Content-Type': 'application/json' }
        response = requests.post(url, headers=headers, json=qr_data)
        print(f'{response=}')
        if response.status_code == 500:
            print(response.content)
            print(response.headers)
            response_data = response.json()
            if 'error_message' in response_data:
                error_message = response_data['error_message']
                print(f"Error message: {error_message}")

        if response.status_code == 200:
            qr_code_image = Image.open(io.BytesIO(response.content))
            qr_code_filename = f'qr_{i}.png'
            folder_path = os.path.join(project_folder, 'static', 'payment_slips', f'qr_code')
            os.makedirs(folder_path, exist_ok=True)  # Ako folder ne postoji, kreira ga
            qr_code_filepath = os.path.join(folder_path, qr_code_filename)
            qr_code_image.save(qr_code_filepath)
            with open(qr_code_filepath, 'wb') as file:
                file.write(response.content)
            qr_code_images.append(qr_code_filename)
    
    class PDF(FPDF):
        def __init__(self, **kwargs):
            super(PDF, self).__init__(**kwargs)
    pdf = PDF()
    add_fonts(pdf)
    counter = 1
    for i, uplatnica in enumerate(data_list):
        if counter % 3 == 1:
            pdf.add_page()
            y = 0
            y_qr = 53
            pdf.line(210/3, 10, 210/3, 237/3)
            pdf.line(2*210/3, 10, 2*210/3, 237/3)
        elif counter % 3 == 2:
            print(f'druga trećina')
            y = 99
            y_qr = 152
            pdf.line(210/3, 110, 210/3, 99+237/3)
            pdf.line(2*210/3, 110, 2*210/3, 99+237/3)
        elif counter % 3 == 0:
            print(f'treća trećina')
            y = 198
            y_qr = 251
            pdf.line(210/3, 210, 210/3, 198+237/3)
            pdf.line(2*210/3, 210, 2*210/3, 198+237/3)
        pdf.set_font('DejaVuSansCondensed', 'B', 16)
        pdf.set_y(y_qr)
        pdf.set_x(2*170/3)
        # pdf.image(f'{project_folder}/static/payment_slips/qr_code/{qr_code_images[i]}' , w=25)
        if i < len(qr_code_images):
            pdf.image(f'{project_folder}/static/payment_slips/qr_code/{qr_code_images[i]}' , w=25)
        else:
            raise ValueError(f'Ne postoji QR kod slika za uplatnicu broj {counter}.')
        pdf.set_y(y+8)
        pdf.cell(2*190/3,8, f"NALOG ZA UPLATU", new_y='LAST', align='R', border=0)
        pdf.cell(190/3,8, f"IZVEŠTAJ O UPLATI", new_y='NEXT', new_x='LMARGIN', align='R', border=0)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.cell(63,4, f"Uplatilac", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.multi_cell(57, 4, f'''{uplatnica['uplatilac']}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(63,4, f"Svrha uplate", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.multi_cell(57,4, f'''{uplatnica['svrha_uplate']}\r\n{''}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(63,4, f"Primalac", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.multi_cell(57,4, f'''{uplatnica['primalac']}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(95,1, f"", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.set_y(y + 15)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(13,3, f"Šifra plaćanja", new_y='LAST', align='L', border=0)
        pdf.multi_cell(7,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Valuta", new_y='LAST', align='L', border=0)
        pdf.multi_cell(10,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Iznos", new_y='NEXT', align='L', border=0)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(13,6, f"{uplatnica['sifra_placanja']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(7,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,6, f"RSD", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(22,6, f"{uplatnica['iznos']:.2f}", new_y='NEXT', align='L', border=1)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Račun primaoca", new_y='NEXT', align='L', border=0)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(65,6, f"{uplatnica['racun_primaoca']}", new_y='NEXT', align='L', border=1)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Model i poziv na broj (odobrenje)", new_y='NEXT', align='L', border=0)
        pdf.set_x(73)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(10,6, f"{uplatnica['model']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(45,6, f"{uplatnica['poziv_na_broj']}", new_y='LAST', align='L', border=1)
        pdf.set_y(y + 15)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(13,3, f"Šifra plaćanja", new_y='LAST', align='L', border=0)
        pdf.multi_cell(7,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Valuta", new_y='LAST', align='L', border=0)
        pdf.multi_cell(10,3, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,3, f"Iznos", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(13,6, f"{uplatnica['sifra_placanja']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(7,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(13,6, f"RSD", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(22,6, f"{uplatnica['iznos']:.2f}", new_y='NEXT', align='L', border=1)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Račun primaoca", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(65,6, f"{uplatnica['racun_primaoca']}", new_y='NEXT', align='L', border=1)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 8)
        pdf.multi_cell(65,5, f"Model i poziv na broj (odobrenje)", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.multi_cell(10,6, f"{uplatnica['model']}", new_y='LAST', align='L', border=1)
        pdf.multi_cell(10,6, f"", new_y='LAST', align='L', border=0)
        pdf.multi_cell(45,6, f"{uplatnica['poziv_na_broj']}", new_y='LAST', align='L', border=1)
        pdf.set_x(141)
        pdf.set_font('DejaVuSansCondensed', '', 10)
        pdf.cell(63,4, f"Uplatilac", new_y='NEXT', align='L', border=0)
        pdf.set_x(141)
        pdf.multi_cell(57, 4, f'''{uplatnica['uplatilac']}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.set_x(141)
        pdf.cell(63,4, f"Svrha uplate", new_y='NEXT', new_x='LMARGIN', align='L', border=0)
        pdf.set_x(141)
        pdf.multi_cell(57,4, f'''{uplatnica['svrha_uplate']}\r\n{''}\r\n{''}''', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        
        pdf.line(10, 99, 200, 99)
        pdf.line(10, 198, 200, 198)
        counter += 1
        
    file_name = f'uplatnica_{invoice_item.id}.pdf'
    pdf.output(os.path.join(path, file_name))
        
    #! briše QR kodove nakon dodavanja na uplatnice
    folder_path = os.path.join(project_folder, 'static', 'payment_slips', 'qr_code')
    # Provjeri da li je putanja zaista direktorijum
    if os.path.isdir(folder_path):
        # Prolazi kroz sve fajlove u direktorijumu
        for qr_file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, qr_file)
            # Provjeri da li je trenutni element fajl
            if os.path.isfile(file_path) and os.path.exists(file_path):
                # Obriši fajl
                os.remove(file_path)
                print(f"Fajl '{file_path}' je uspješno obrisan.")
        print("Svi QR kodovi su uspešno obrisani.")
    else:
        print("Navedena putanja nije direktorijum.")
    # file_name = f'{project_folder}static/payment_slips/uplatnice.pdf' #!
    # file_name = f'uplatnice.pdf' #!

    print(f'debug na samom kraju uplatice_gen(): {file_name=}')
    return os.path.join(path, file_name)


def generate_invoice_attach(invoice_id):
    '''
    generiše fakturu. dokument će biti attachovan u emali.
    '''
    app.logger.info(f'Započeto generisanje fakture za invoice_id: {invoice_id}')
    try:
        invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
        invoice = Invoice.query.get(invoice_id)
        customer = User.query.get(invoice.user_id)
        
        if not invoice:
            app.logger.error(f'Faktura sa ID {invoice_id} nije pronađena')
            return None
        
        file_name = f'{invoice.invoice_number}.pdf'
        app.logger.info(f'Generisanje fakture: {file_name}')
        
        try:
            products = [invoice_item.invoice_item_details for invoice_item in invoice_items if invoice_item.invoice_item_type == 1]
            animals = [invoice_item.invoice_item_details for invoice_item in invoice_items if invoice_item.invoice_item_type == 2]
            services = [invoice_item.invoice_item_details for invoice_item in invoice_items if invoice_item.invoice_item_type == 3]
            # fattening = [invoice_item.invoice_item_details for invoice_item in invoice_items if (invoice_item.invoice_item_type == 4 and json.loads(invoice_item.invoice_item_details)['installment_options'] > 1)]
            fattening = [invoice_item.invoice_item_details for invoice_item in invoice_items if (invoice_item.invoice_item_type == 4 and invoice_item.invoice_item_details['installment_options'] > 1)]
            app.logger.debug(f'Pronađeno stavki: proizvoda={len(products)}, životinja={len(animals)}, usluga={len(services)}, tov={len(fattening)}')
        except Exception as e:
            app.logger.error(f'Greška pri obradi stavki fakture: {e}')
            raise
        
        #! generisi fakturu uz pomoć fpdf
        try:
            current_file_path = os.path.abspath(__file__)
            project_folder = os.path.dirname(os.path.dirname((current_file_path)))
            font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
            font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')
            font_path_I = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Oblique.ttf')
            
            # Definisanje boja za dokument
            HEADER_BG_COLOR = (41, 128, 185)  # Plava boja za zaglavlje
            HEADER_TEXT_COLOR = (255, 255, 255)  # Bela boja za tekst u zaglavlju
            TABLE_HEADER_BG_COLOR = (236, 240, 241)  # Svetlo siva za zaglavlje tabele
            TABLE_HEADER_TEXT_COLOR = (44, 62, 80)  # Tamno plava za tekst zaglavlja tabele
            BORDER_COLOR = (189, 195, 199)  # Siva boja za ivice
            SECTION_TITLE_COLOR = (52, 152, 219)  # Svetlo plava za naslove sekcija
            
            class PDF(FPDF):
                def __init__(self, **kwargs):
                    super(PDF, self).__init__(**kwargs)
                    self.add_font('DejaVuSansCondensed', '', font_path, uni=True)
                    self.add_font('DejaVuSansCondensed', 'B', font_path_B, uni=True)
                    self.add_font('DejaVuSansCondensed', 'I', font_path_I, uni=True)
                    
                def header(self):
                    # Logo i naziv kompanije
                    self.set_fill_color(*HEADER_BG_COLOR)
                    self.rect(10, 10, self.w - 20, 25, 'F')
                    self.set_text_color(*HEADER_TEXT_COLOR)
                    self.set_font('DejaVuSansCondensed', 'B', 18)
                    self.set_xy(15, 15)
                    self.cell(0, 10, 'MojeStado', new_x='RIGHT', align='L')
                    
                    # Broj fakture
                    self.set_font('DejaVuSansCondensed', 'B', 14)
                    self.set_xy(self.w - 100, 15)
                    self.cell(90, 10, f'Faktura: {invoice.invoice_number}', new_x='LMARGIN', new_y='NEXT', align='R')
                    
                    # Razmak nakon zaglavlja
                    self.ln(10)
                    
                def footer(self):
                    self.set_y(-20)
                    self.set_font('DejaVuSansCondensed', 'I', 8)
                    self.set_text_color(128, 128, 128)
                    self.cell(0, 10, f'Strana {self.page_no()}/{{nb}}', new_x='LMARGIN', new_y='NEXT', align='C')
                    self.cell(0, 5, 'MojeStado - Platforma za poljoprivrednike', new_x='LMARGIN', new_y='NEXT', align='C')
                    
                def add_section_title(self, title):
                    self.set_font('DejaVuSansCondensed', 'B', 12)
                    self.set_text_color(*SECTION_TITLE_COLOR)
                    self.cell(0, 10, title, new_x='LMARGIN', new_y='NEXT', align='L', border=0)
                    self.set_text_color(0, 0, 0)  # Vraćanje na crnu boju teksta
                    
                def add_info_section(self):
                    # Informacije o fakturi
                    self.set_font('DejaVuSansCondensed', 'B', 10)
                    self.set_fill_color(245, 245, 245)  # Vrlo svetlo siva pozadina
                    
                    # Leva kolona - informacije o kupcu
                    self.set_xy(15, 45)
                    self.cell(90, 8, 'Informacije o kupcu:', new_x='LMARGIN', new_y='NEXT', align='L')
                    self.set_font('DejaVuSansCondensed', '', 9)
                    self.set_xy(15, 53)
                    self.multi_cell(90, 6, f"Ime i prezime: {customer.name} {customer.surname}\nAdresa: {customer.address}\n{customer.zip_code}, {customer.city}\n", new_x='LMARGIN', new_y='NEXT', align='L')
                    
                    # Desna kolona - informacije o fakturi
                    self.set_xy(self.w - 105, 45)
                    self.set_font('DejaVuSansCondensed', 'B', 10)
                    self.cell(90, 8, 'Detalji fakture:', new_x='LMARGIN', new_y='NEXT', align='L')
                    self.set_font('DejaVuSansCondensed', '', 9)
                    self.set_xy(self.w - 105, 53)
                    datum_izdavanja = datetime.date.today().strftime('%d.%m.%Y.')
                    self.multi_cell(90, 6, f"Datum izdavanja: {datum_izdavanja}", new_x='LMARGIN', new_y='NEXT', align='L')
                    
                    # Razmak nakon info sekcije
                    self.ln(10)
                    
                def add_table_header(self, headers, col_widths):
                    self.set_font('DejaVuSansCondensed', 'B', 8)
                    self.set_fill_color(*TABLE_HEADER_BG_COLOR)
                    self.set_text_color(*TABLE_HEADER_TEXT_COLOR)
                    self.set_draw_color(*BORDER_COLOR)
                    
                    for i, header in enumerate(headers):
                        self.cell(col_widths[i], 8, header, new_y='LAST', align='C', border=1, fill=True)
                    self.ln()
                    self.set_text_color(0, 0, 0)  # Vraćanje na crnu boju teksta
                    
                def add_table_row(self, data, col_widths):
                    self.set_font('DejaVuSansCondensed', '', 8)
                    for i, value in enumerate(data):
                        self.cell(col_widths[i], 7, str(value), new_y='LAST', align='L', border=1)
                    self.ln()
            
            # Inicijalizacija PDF dokumenta
            pdf = PDF()
            pdf.alias_nb_pages()
            pdf.add_page(orientation='L')
            pdf.add_info_section()
            
            # Dodavanje napomene o fakturi
            pdf.set_font('DejaVuSansCondensed', 'I', 9)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 5, "Ova faktura predstavlja zvanični dokument o kupovini preko MojeStado platforme. "
                              "Za sva pitanja i reklamacije, molimo kontaktirajte našu korisničku podršku.", 
                              new_x='LMARGIN', new_y='NEXT', align='L')
            pdf.ln(5)
            pdf.set_text_color(0, 0, 0)  # Vraćanje na crnu boju teksta
            
            app.logger.info('Kreiran PDF objekat i dodate osnovne informacije')
        except Exception as e:
            app.logger.error(f'Greška pri inicijalizaciji PDF dokumenta: {e}')
            raise
        
        # Proizvodi
        if products:
            try:
                app.logger.info(f'Dodavanje {len(products)} proizvoda u fakturu')
                pdf.add_section_title('Proizvodi')
                
                headers = ['Kategorija', 'Potkategorija', 'Sektor', 'Naziv', 'Količina', 'Jed. mere', 'Cena po jed.', 'Cena po kg', 'Ukupno', 'PG', 'Lokacija']
                col_widths = [30, 30, 30, 30, 15, 15, 20, 20, 20, 25, 25]
                
                pdf.add_table_header(headers, col_widths)
                
                for product in products:
                    row_data = [
                        product["category"],
                        product["subcategory"],
                        product["section"],
                        product["product_name"],
                        product["quantity"],
                        product["unit_of_measurement"],
                        f"{float(product['product_price_per_unit']):.2f}",
                        f"{float(product['product_price_per_kg']):.2f}",
                        f"{float(product['total_price']):.2f}",
                        product["farm"],
                        product["location"]
                    ]
                    pdf.add_table_row(row_data, col_widths)
                
                pdf.ln(5)
            except Exception as e:
                app.logger.error(f'Greška pri dodavanju proizvoda u fakturu: {e}')
                raise
        
        # Živa vaga
        if animals:
            try:
                app.logger.info(f'Dodavanje {len(animals)} životinja u fakturu')
                pdf.add_section_title('Živa vaga')
                
                headers = ['Kategorija', 'Potkategorija', 'Rasa', 'Pol', 'Masa', 'Cena po kg', 'Ukupno', 'Osigurano', 'Organsko', 'PG', 'Lokacija']
                col_widths = [30, 30, 30, 10, 15, 20, 20, 25, 25, 25, 25]
                
                pdf.add_table_header(headers, col_widths)
                
                for animal in animals:
                    row_data = [
                        animal["category"],
                        animal["subcategory"],
                        animal["race"],
                        animal["animal_gender"],
                        f"{float(animal['current_weight']):.2f}",
                        f"{float(animal['price_per_kg']):.2f}",
                        f"{float(animal['total_price']):.2f}",
                        animal["insured"],
                        animal["organic_animal"],
                        animal["farm"],
                        animal["location"]
                    ]
                    pdf.add_table_row(row_data, col_widths)
                
                pdf.ln(5)
            except Exception as e:
                app.logger.error(f'Greška pri dodavanju životinja u fakturu: {e}')
                raise
        
        # Usluge
        if services:
            try:
                app.logger.info(f'Dodavanje {len(services)} usluga u fakturu')
                pdf.add_section_title('Usluge')
                
                headers = ['Kategorija', 'Potkategorija', 'Rasa', 'Pol', 'Masa', 'Usluga', 'Cena']
                col_widths = [30, 30, 30, 15, 20, 50, 30]
                
                pdf.add_table_header(headers, col_widths)
                
                for service in services:
                    usluga_tekst = 'Klanje i obrada' if service.get('slaughterService') == True and service.get('processingPrice', 0) > 0 else 'Klanje'
                    cena_tekst = f"{float(service.get('slaughterPrice', 0)):.2f}" if service.get('slaughterService') == True and service.get('processingPrice', 0) > 0 else f"{float(service.get('slaughterPrice', 0) + service.get('processingPrice', 0)):.2f}"
                    
                    row_data = [
                        service["category"],
                        service["subcategory"],
                        service["race"],
                        service["animal_gender"],
                        f"{float(service['current_weight']):.2f}",
                        usluga_tekst,
                        cena_tekst
                    ]
                    pdf.add_table_row(row_data, col_widths)
                
                pdf.ln(5)
            except Exception as e:
                app.logger.error(f'Greška pri dodavanju usluga u fakturu: {e}')
                raise
        
        # Tov
        if fattening:
            try:
                app.logger.info(f'Dodavanje {len(fattening)} stavki tova u fakturu')
                pdf.add_section_title('Tov')
                
                headers = ['Kategorija', 'Potkategorija', 'Rasa', 'Pol', 'Željena masa', 'Cena tova', 'Br. hranidbenih dana', 'Br. rata']
                col_widths = [30, 30, 30, 15, 25, 25, 30, 20]
                
                pdf.add_table_header(headers, col_widths)
                
                for fattening_item in fattening:
                    row_data = [
                        fattening_item["category"],
                        fattening_item["subcategory"],
                        fattening_item["race"],
                        fattening_item["animal_gender"],
                        f"{float(fattening_item['desired_weight']):.2f}",
                        f"{float(fattening_item['fattening_price']):.2f}",
                        fattening_item["feeding_days"],
                        fattening_item["installment_options"]
                    ]
                    pdf.add_table_row(row_data, col_widths)
                
                pdf.ln(5)
            except Exception as e:
                app.logger.error(f'Greška pri dodavanju stavki tova u fakturu: {e}')
                raise
        
        # Ukupna cena
        try:
            total_price = 0
            for item in invoice_items:
                details = item.invoice_item_details
                if isinstance(details, dict) and 'total_price' in details:
                    total_price += float(details['total_price'])
            
            pdf.ln(5)
            pdf.set_font('DejaVuSansCondensed', 'B', 10)
            pdf.cell(0, 10, f"Ukupno za plaćanje: {total_price:.2f} RSD", new_x='LMARGIN', new_y='NEXT', align='R')
            app.logger.info(f'Ukupna cena fakture: {total_price:.2f} RSD')
        except Exception as e:
            app.logger.error(f'Greška pri izračunavanju ukupne cene: {e}')
            raise
        
        # Napomene i uslovi
        try:
            pdf.ln(5)
            pdf.set_font('DejaVuSansCondensed', 'B', 9)
            pdf.cell(0, 5, "Napomene i uslovi:", new_x='LMARGIN', new_y='NEXT', align='L')
            pdf.set_font('DejaVuSansCondensed', '', 8)
            pdf.multi_cell(0, 4, "1. Plaćanje se vrši preko PaySpot servisa.\n"
                            "2. Rok za reklamacije je 7 dana od datuma izdavanja fakture.\n"
                            "3. Za dodatne informacije posetite naš sajt ili kontaktirajte korisničku podršku.", 
                            new_x='LMARGIN', new_y='NEXT', align='L')
            
            # Potpisi
            pdf.ln(10)
            pdf.line(40, pdf.get_y(), 100, pdf.get_y())
            pdf.line(pdf.w - 100, pdf.get_y(), pdf.w - 40, pdf.get_y())
            pdf.set_font('DejaVuSansCondensed', '', 8)
            pdf.cell(pdf.w/2 - 10, 5, "Potpis prodavca", new_x='RIGHT', new_y='LAST', align='C')
            pdf.cell(pdf.w/2 - 10, 5, "Potpis kupca", new_x='LMARGIN', new_y='NEXT', align='C')
        except Exception as e:
            app.logger.error(f'Greška pri dodavanju napomena i potpisa: {e}')
            raise
        
        # Čuvanje PDF-a
        try:
            path = os.path.join(project_folder, 'static', 'invoices')
            if not os.path.exists(path):
                os.mkdir(path)
                app.logger.info(f'Kreiran direktorijum za fakture: {path}')
            
            pdf_path = os.path.join(path, file_name)
            pdf.output(pdf_path)
            app.logger.info(f'Faktura uspešno sačuvana na putanji: {pdf_path}')
            return pdf_path
        except Exception as e:
            app.logger.error(f'Greška pri čuvanju PDF fakture: {e}')
            raise
            
    except Exception as e:
        app.logger.error(f'Neočekivana greška pri generisanju fakture: {e}')
        return None


def register_guest_user(form_object):
    if not form_object.get('email'):
        flash ('Niste uneli email', 'danger')
        return redirect(url_for('transactions.guest_form'))
    user = User.query.filter_by(email=form_object.get('email')).first()
    if user:
        return None
    # Kada kreirate nalog za gosta, možete sačuvati email u sesiji:
    session['guest_email'] = form_object.get('email')
    
    
    user = User(email=form_object.get('email'),
                name=form_object.get('name'),
                surname=form_object.get('surname'),
                phone=form_object.get('phone'),
                address=form_object.get('address'),
                city=form_object.get('city'),
                zip_code=form_object.get('zip_code'),
                user_type='guest',
                registration_date=datetime.date.today())
    db.session.add(user)
    db.session.commit()
    return user.id


def edit_guest_user(form_object):
    """
    Ažurira podatke postojećeg gost korisnika na osnovu forme.
    """
    user = User.query.filter_by(email=form_object.get('email'), user_type='guest').first()
    if not user:
        return None
    user.name = form_object.get('name')
    user.surname = form_object.get('surname')
    user.phone = form_object.get('phone')
    user.address = form_object.get('address')
    user.city = form_object.get('city')
    user.zip_code = form_object.get('zip_code')
    db.session.commit()
    session['guest_email'] = form_object.get('email')
    return user.id


def create_invoice():
    '''
    Kreira novu fakturu i stavke fakture na osnovu podataka iz sesije.
    
    Faktura sadrži:
    - Datum i vreme transakcije
    - Jedinstveni broj fakture (format: YYYY-NNNNNN)
    - ID korisnika (može biti registrovani korisnik ili gost)
    - Status fakture (unconfirmed, confirmed, paid, cancelled)
    
    Stavke fakture sadrže:
    - ID farme
    - ID fakture
    - Detalje stavke u JSON formatu
    - Tip stavke (1: proizvod, 2: životinja, 3: usluga, 4: tov)
    
    Returns:
        Invoice: Kreirana faktura
    '''
    # Generisanje broja fakture (primer: 2024-000001)
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    if last_invoice:
        last_invoice_number = int(last_invoice.id)
        new_invoice_number = f'PMS-{last_invoice_number + 1:09d}'
    else:
        new_invoice_number = f'PMS-000000001'
    
    # Uzimanje ID korisnika iz sesije
    if current_user.is_authenticated:
        app.logger.info(f'Ulogovan korisnik {current_user.id} kreira fakturu')
        user_id = current_user.id
    else:
        app.logger.info(f'Neregistrovani korisnik {session["guest_email"]} kreira fakturu')
        guest_user = User.query.filter_by(email=session['guest_email']).first()
        user_id = guest_user.id
        
    # Kreiranje fakture
    new_invoice = Invoice(
        datetime=datetime.datetime.now(),
        invoice_number=new_invoice_number,
        user_id=user_id,
        status='unconfirmed'
    )
    db.session.add(new_invoice)
    db.session.commit()
    
    # Dodavanje proizvoda u fakturu
    try:
        for product in session.get('products', []):
            new_invoice_item = InvoiceItems(
                farm_id=product['farm_id'],
                invoice_id=new_invoice.id,
                invoice_item_details=product,
                invoice_item_type=1
            )
            db.session.add(new_invoice_item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Greška pri dodavanju proizvoda u fakturu: {str(e)}')
    
    # Dodavanje životinja u fakturu
    try:
        for animal in session.get('animals', []):
            new_invoice_item = InvoiceItems(
                farm_id=animal['farm_id'],
                invoice_id=new_invoice.id,
                invoice_item_details=animal,
                invoice_item_type=2
            )
            db.session.add(new_invoice_item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Greška pri dodavanju životinja u fakturu: {str(e)}')
    
    # Dodavanje usluga u fakturu
    try:
        for service in session.get('services', []):
            new_invoice_item = InvoiceItems(
                farm_id=service['farm_id'],
                invoice_id=new_invoice.id,
                invoice_item_details=service,
                invoice_item_type=3
            )
            db.session.add(new_invoice_item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Greška pri dodavanju usluga u fakturu: {str(e)}')
    
    # Dodavanje tova u fakturu
    try:
        for fattening in session.get('fattening', []):
            new_invoice_item = InvoiceItems(
                farm_id=fattening['farm_id'],
                invoice_id=new_invoice.id,
                invoice_item_details=fattening,
                invoice_item_type=4
            )
            db.session.add(new_invoice_item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Greška pri dodavanju tova u fakturu: {str(e)}')
    return new_invoice


def define_invoice_user():
    '''
    Učitava korisnika za fakturisanje: vraća User objekat ili redirect ako postoji problem sa sesijom ili korisnikom.
    '''
    try:
        if current_user.is_authenticated:
            user_id = current_user.id
        else:
            guest_email = session.get('guest_email')
            if not guest_email:
                app.logger.error('Nedostaje email gost korisnika')
                flash('Došlo je do greške sa vašom sesijom. Molimo prijavite se ponovo.', 'danger')
                return redirect(url_for('users.login'))

            guest_user = User.query.filter_by(email=guest_email).first()
            if not guest_user:
                app.logger.error(f'Gost korisnik nije pronađen: {guest_email}')
                flash('Došlo je do greške sa vašim nalogom. Molimo prijavite se ponovo.', 'danger')
                return redirect(url_for('users.login'))
            user_id = guest_user.id

        user = User.query.get_or_404(user_id)
        app.logger.debug(f'Učitan korisnik: {user_id}')
        return user
    except Exception as e:
        app.logger.error(f'Greška pri učitavanju korisnika: {str(e)}')
        flash('Došlo je do greške pri učitavanju vaših podataka. Molimo pokušajte ponovo.', 'danger')
        return redirect(url_for('main.home'))


def deactivate_animals(invoice_id):
    '''
    Deaktivira životinje za fakturu
    '''
    try:
        invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
        if len(invoice_items) == 0:
            app.logger.info('Nema stavki u korpi.')
        else:
            for invoice_item in invoice_items:
                if invoice_item.invoice_item_type == 2:
                    animal_id = invoice_item.invoice_item_details['id']
                    # animal_id = json.loads(invoice_item.invoice_item_details)['id']
                    animal_to_edit = Animal.query.get(animal_id)
                    animal_to_edit.active = False
                    db.session.commit()
                    app.logger.info(f'Životinja: {animal_id} deaktivirana.')
    except Exception as e:
        app.logger.error(f'Greška pri deaktiviranju životinje: {str(e)}')
        return False, str(e)
    return True, None

def deactivate_products(invoice_id):
    '''
    Oduzima količinu proizvoda iz skladišta
    '''
    app.logger.info(f'Oduzima količinu proizvoda za fakturu: {invoice_id}')
    try:
        invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
        if len(invoice_items) == 0:
            app.logger.info('Nema stavki u korpi.')
        else:
            for invoice_item in invoice_items:
                if invoice_item.invoice_item_type == 1:
                    product_id = invoice_item.invoice_item_details['id']
                    # product_id = json.loads(invoice_item.invoice_item_details)['id']
                    product_to_edit = Product.query.get(product_id)
                    product_to_edit.quantity = float(product_to_edit.quantity) - float(invoice_item.invoice_item_details['quantity'])
                    # product_to_edit.quantity = float(product_to_edit.quantity) - float(json.loads(invoice_item.invoice_item_details)['quantity'])
                    db.session.commit()
                    app.logger.info(f'Za proizvod: {product_id} umanjena količina za {float(invoice_item.invoice_item_details["quantity"])}.')
    except Exception as e:
        app.logger.error(f'Greška pri oduzimanju količine proizvoda: {str(e)}')
        return False, str(e)
    return True, None


def send_email(user, invoice_id):
    app.logger.info(f'Započinjem slanje email-a za korisnika {user.email}, faktura {invoice_id}')
    
    payment_slips = [] 
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    app.logger.debug(f'Pronađeno {len(invoice_items)} stavki fakture')
    
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 4:
            fattening = invoice_item.invoice_item_details
            app.logger.debug(f'Stavka tova: {fattening}')
            
            if int(fattening['installment_options']) > 1:
                app.logger.info(f'Usluga na rate za stavku {invoice_item.id}')
                create_debt(user, invoice_item)
                new_payment_slip = generate_payment_slips_attach(invoice_item)
                app.logger.debug(f'Generisana uplatnica: {new_payment_slip}')
                payment_slips.append(new_payment_slip)
        elif invoice_item.invoice_item_type == 1:
            app.logger.info(f'Slanje mejla za ažuriranje količine proizvoda za stavku {invoice_item.id}')
            send_email_to_update_product_quantity(invoice_item)
    
    app.logger.debug(f'Generisane uplatnice: {payment_slips}')
    
    invoice_attach = generate_invoice_attach(invoice_id)
    app.logger.debug(f'Generisan prilog fakture: {invoice_attach}')

    to = [user.email]
    bcc = [os.environ.get('MAIL_ADMIN')]
    subject = 'Potvrda kupovine na portalu "Moje stado"'

    if payment_slips:
        app.logger.info('Faktura je na rate - prilažem uplatnice')
        attachments = [invoice_attach] + payment_slips
        na_rate = True
    else:
        app.logger.info('Faktura nije na rate - prilažem samo fakturu')
        attachments = [invoice_attach]
        na_rate = False
        
    message = Message(subject=subject, sender=os.environ.get('MAIL_DEFAULT_SENDER'), recipients=to, bcc=bcc)
    message.html = render_template('message_html_confirm_invoice.html', na_rate=na_rate)
    
    app.logger.debug(f'Prilozi za slanje: {attachments}')
    
    # Provera postojanja fajlova pre pripajanja
    for attachment in attachments:
        if not os.path.exists(attachment):
            app.logger.error(f'Fajl {attachment} ne postoji!')
            continue
            
        try:
            with open(attachment, 'rb') as f:
                file_content = f.read()
                app.logger.debug(f'Uspešno pročitan fajl: {attachment}, veličina: {len(file_content)} bajtova')
                message.attach(os.path.basename(attachment), "application/pdf", file_content)
                app.logger.debug(f'Uspešno dodat prilog: {os.path.basename(attachment)}')
        except Exception as e:
            app.logger.error(f'Greška prilikom dodavanja priloga: {attachment}. Greška: {str(e)}')
    
    try:
        mail.send(message)
        app.logger.info(f'Email uspešno poslat na: {to}')
        return True
    except Exception as e:
        app.logger.error(f'Greška prilikom slanja mejla: {str(e)}')
        return False


def send_email_to_update_product_quantity(invoice_item):
    '''
    Prilikom svake kupovine stiže mejl sa informacijama o prodatoj količini i o trenutnom stanju količine proizvoda na portalu, 
    sa molbom da se količine ažuriraju po potrebi. U mejlu se nalazi i link za ažuriranje stanja gotovih proizvoda.
    '''
    print(f'send_email > proizvod > slanje mejla PG ako je proizvod da ažurira količine proizvoda na portalu')
    farm = Farm.query.filter_by(id=invoice_item.farm_id).first()
    farmer = User.query.get(farm.user_id)
    farmer_email = farmer.email
    subject = 'Obaveštenje o prodaji i stanju proizvoda - Ažuriranje potrebno'
    
    product_id = invoice_item.invoice_item_details['id'] #! potrebno za generisanje linka koji će da bude u mejl poslatom PG da edituje količinu proizvoda
    product = Product.query.get_or_404(product_id)
    product_name = product.product_name
    quantity_sold = invoice_item.invoice_item_details['quantity']
    quantity = product.quantity
    
    html = render_template('message_html_update_product_quantity.html',
                            quantity_sold=quantity_sold,
                            product_id=product_id,
                            product_name=product_name,
                            quantity=quantity)
    message = Message(subject=subject, sender=os.environ.get('MAIL_DEFAULT_SENDER'), recipients=[farmer_email])
    message.html = html
    try:
        mail.send(message)
        app.logger.info('Email poslat o prodaji proizvoda')
    except Exception as e:
        app.logger.error(f'Greška prilikom slanja mejla: {e}')

def create_debt(user, invoice_item):
    new_debt = Debt(
        invoice_item_id=invoice_item.id,
        user_id=user.id,
        # amount=json.loads(invoice_item.invoice_item_details)['fattening_price'],
        amount=invoice_item.invoice_item_details['fattening_price'],
        status='pending'
    )
    db.session.add(new_debt)
    db.session.commit()


def provera_validnosti_poziva_na_broj(podaci):
    debts = Debt.query.all()
    all_reference_numbers = [f'{record.user_id:05d}-{record.invoice_item_id:06d}' for record in debts]
    
    if len(podaci['PozivNaBrojApp']) == 11:  # Format bez crtice: '00052000138'
        # Formatira string u oblik sa crticom (5 brojeva - 6 brojeva)
        formated_poziv_odobrenja = f"{podaci['PozivNaBrojApp'][:5]}-{podaci['PozivNaBrojApp'][5:]}"
        if formated_poziv_odobrenja in all_reference_numbers:
            podaci['Validnost'] = True
        else:
            podaci['Validnost'] = False
    elif len(podaci['PozivNaBrojApp']) == 12 and '-' in podaci['PozivNaBrojApp']:  # Format: '00052-000138'
        if podaci['PozivNaBrojApp'] in all_reference_numbers:
            podaci['Validnost'] = True
        else:
            podaci['Validnost'] = False
    else:
        # Poziv na broj nije u ispravnom formatu (treba da bude 11 cifara ili format 5-6 cifara)
        podaci['Validnost'] = False
    return podaci


###########################
### PaySpot integration ###
###########################
def generate_random_string(length=20):
    letters = string.ascii_letters + string.digits
    rnd = ''.join(random.choice(letters) for i in range(length))
    print(f'* generate random string: {rnd=}')
    return rnd


def check_invalid_characters(text):
    return '\\' in str(text) or '|' in str(text)


def calculate_hash(plaintext):
    if any(check_invalid_characters(value) for value in plaintext.split('|')):
        raise ValueError("Nevažeći karakteri: (\\ or |) pronađeni u plaintext-u.")

    print(f'* calculate hash: {plaintext=}')
    sha512_hash = hashlib.sha512(plaintext.encode('utf-8')).hexdigest()
    print(f'* calculate hash: {sha512_hash=}')
    hash_ = base64.b64encode(bytes.fromhex(sha512_hash)).decode('utf-8')
    print(f'** calculate hash: {hash_=}')
    return hash_


def send_payspot_request(request_data, merchant_order_id, invoice, orders_data, user, payment_type):
    '''
    Pomoćna funkcija za slanje zahteva ka PaySpot-u i upis u bazu.
    '''
    url = "[https://test.nsgway.rs](https://test.nsgway.rs):50009/api/paymentorderinsert"
    app.logger.debug(f'PaySpot URL: {url}')
    app.logger.debug(f'PaySpot companyID: {os.environ.get("PAYSPOT_COMPANY_ID")}')
    app.logger.debug(f'PaySpot zahtev: {json.dumps(request_data, indent=2, ensure_ascii=False)}')

    json_data = json.dumps(request_data, ensure_ascii=False).encode('utf-8')
    response = requests.post(url, data=json_data, headers={"Content-Type": "application/json; charset=utf-8"})
    app.logger.debug(f'PaySpot status kod: {response.status_code}')
    try:
        response_text = response.text
        app.logger.debug(f'PaySpot odgovor: {response_text}')
        response_data = response.json()
    except Exception as e:
        app.logger.error(f'Greška pri parsiranju PaySpot odgovora: {str(e)}')
        return False, f"HTTP greška: {response.status_code}, Nije moguće parsirati odgovor."

    if response.status_code == 200:
        error_code = response_data.get("data", {}).get("body", {}).get("errorCode")
        app.logger.debug(f'Provera da li postoji greška: {error_code=}')
        if error_code == 0:
            app.logger.info(f'Uspešno poslat PaymentOrderInsert za narudžbinu {merchant_order_id} (tip {payment_type}).')
            # --- UPIS U BAZU TRANSAKCIJA ---
            try:
                body_data = response_data.get("data", {}).get("body", {})
                payment_order_group = body_data.get("paymentOrderGroup")
                payspot_group_id = payment_order_group.get("payspotGroupID")
                orders_response = payment_order_group.get("orders", [])
                if payspot_group_id and orders_response:
                    app.logger.info(f'Pronađen payspotGroupID: {payspot_group_id} i {len(orders_response)} transakcija')
                    beneficiary_amounts = {}
                    for order in orders_data:
                        if "merchantOrderReference" in order and "beneficiaryAmount" in order:
                            beneficiary_amounts[order["merchantOrderReference"]] = order["beneficiaryAmount"]
                    app.logger.debug(f'Mapirani beneficiary iznosi: {beneficiary_amounts}')
                    for order in orders_response:
                        payspot_transaction_id = order.get("payspotTransactionID")
                        sequence_no = order.get("sequenceNo")
                        merchant_order_reference = order.get("merchantOrderReference")
                        status_trans = order.get("statusTrans")
                        create_date = order.get("createDate")
                        create_time = order.get("createTime")
                        sender_fee = order.get("senderFeeAmount")
                        # Određivanje farm_id iz merchantOrderReference
                        farm_id = None
                        if merchant_order_reference and merchant_order_reference.startswith(f"REF-{merchant_order_id}-F"):
                            try:
                                farm_id = int(merchant_order_reference.split('-F')[1])
                                app.logger.debug(f'Izdvojen farm_id: {farm_id} iz reference: {merchant_order_reference}')
                            except (ValueError, IndexError):
                                app.logger.warning(f'Nije moguće izdvojiti farm_id iz reference: {merchant_order_reference}')
                        beneficiary_amount = beneficiary_amounts.get(merchant_order_reference)
                        transaction = PaySpotTransaction(
                            invoice_id=invoice.id,
                            merchant_order_id=merchant_order_id,
                            payspot_group_id=payspot_group_id,
                            sequence_no=sequence_no,
                            merchant_order_reference=merchant_order_reference,
                            payspot_transaction_id=payspot_transaction_id,
                            status_trans=status_trans,
                            create_date=create_date,
                            create_time=create_time,
                            sender_fee=sender_fee,
                            farm_id=farm_id,
                            beneficiary_amount=beneficiary_amount
                        )
                        db.session.add(transaction)
                    db.session.commit()
                    app.logger.info(f'Sačuvano {len(orders_response)} PaySpot transakcija u bazi za fakturu {invoice.id}')
                else:
                    app.logger.warning(f'Nedostaje payspotGroupID ili orders u odgovoru za narudžbinu {merchant_order_id}')
            except Exception as e:
                app.logger.error(f'Greška pri čuvanju PaySpot transakcija u bazi: {str(e)}')
                # Ne prekidamo proces jer je plaćanje već uspešno inicirano
            # --- KRAJ UPISA U BAZU ---
            return True, None
        else:
            error_message = response_data.get("data", {}).get("body", {}).get("errorMsg", "Nepoznata greška")
            app.logger.error(f'Greška pri slanju PaymentOrderInsert: {error_message}')
            return False, error_message
    else:
        app.logger.error(f'HTTP greška pri slanju PaymentOrderInsert: {response.status_code}')
        return False, f"HTTP greška: {response.status_code}"


def send_payment_order_insert(merchant_order_id, merchant_order_amount, user, invoice):
    """
    Šalje PaymentOrderInsert (MsgType=101) zahtev ka PaySpot-u pre plaćanja
    
    Parametri:
    - merchant_order_id: ID narudžbine
    - merchant_order_amount: Ukupan iznos narudžbine
    - user: Objekat korisnika koji vrši plaćanje
    - invoice: Objekat fakture sa stavkama
    
    Returns:
        Tuple[bool, str]: (True, None) ako je kreiranje naloga za plaćanje uspešno, (False, greška) ako nije
    """
    if merchant_order_amount == 0:
        app.logger.warning('Iznos narudžbine je 0, preskačem kreiranje naloga za plaćanje')
        return False, "Iznos narudžbine je 0, preskačem kreiranje naloga za plaćanje."
    
    try:
        app.logger.info(f'Započinjem slanje PaymentOrderInsert za narudžbinu {merchant_order_id}')
        app.logger.debug(f'Parametri: merchant_order_id={merchant_order_id}, merchant_order_amount={merchant_order_amount}')
        app.logger.debug(f'Korisnik: id={user.id}, name={user.name}, surname={user.surname}')
        
        # Generisanje random stringa za hash
        rnd = generate_random_string()
        app.logger.debug(f'Generisan random string: {rnd}')        
        # Trenutno vreme u formatu koji očekuje PaySpot
        request_date_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        app.logger.debug(f'Vreme zahteva: {request_date_time}')
        
        
        # Provera da li korisnik ima adresu i grad
        user_address = user.address if hasattr(user, 'address') and user.address else "Nepoznata adresa"
        user_city = user.city if hasattr(user, 'city') and user.city else "Nepoznat grad"
        app.logger.debug(f'Adresa korisnika: {user_address}, Grad: {user_city}')
        
        # Provera da li je prosleđen objekat fakture
        if not invoice:
            app.logger.warning('Nije prosleđen objekat fakture')
            return False, "Faktura nije prosleđena."
        
        # Dohvatanje stavki fakture
        invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice.id).all()
        app.logger.debug(f'Pronađeno {len(invoice_items)} stavki za fakturu {invoice.id}')
        
        
        if not invoice_items:
            app.logger.warning(f'Faktura {invoice.id} nema stavke, nije moguu0107e kreirati naloge za plau0107anje')
            return False, "Faktura nema stavke. Nije moguu0107e kreirati naloge za plau0107anje."
        
        #! Priprema podataka za nalog
        orders_data_1 = []
        orders_data_7 = []
        sequence_no_1 = 1
        sequence_no_7 = 1
        app.logger.debug(f'Počinjem kreiranje naloga za plaćanje za {len(invoice_items)} stavki')
        
        # Rečnik za grupisanje stavki po farm.id
        farm_orders_1 = {}
        farm_orders_7 = {}
        
        for item in invoice_items:
            # Dobavljanje podataka o farmi
            farm = Farm.query.get(item.farm_id)
            if not farm:
                app.logger.warning(f'Farma sa ID {item.farm_id} nije pronađena za stavku {item.id}')
                continue
            
            app.logger.debug(f'Pronađena farma: {farm.farm_name}, ID: {farm.id}')
            
            # Dobavljanje podataka o vlasniku farme
            farmer = User.query.get(farm.user_id)
            if not farmer:
                app.logger.warning(f'Vlasnik nije pronađen za farmu {farm.id}')
                continue
            
            app.logger.debug(f'Pronađen vlasnik farme: {farmer.name} {farmer.surname}, ID: {farmer.id}')
            
            # Dobavljanje detalja stavke
            item_details = item.invoice_item_details
            
            # Provera tipa stavke i dobavljanje odgovarajućih podataka
            item_name = None
            item_price = 0
            quantity = 1
            if item.invoice_item_type == 1:  # Proizvod
                item_name = item_details.get('product_name', 'Nepoznat proizvod')
                item_price = float(item_details.get('total_price', 0))
                quantity = int(item_details.get('quantity', 1))
            elif item.invoice_item_type == 2:  # Životinja
                item_name = item_details.get('animal_name', 'Nepoznata životinja')
                item_price = float(item_details.get('total_price', 0))
                quantity = 1
            elif item.invoice_item_type == 3:  # Usluga
                item_name = item_details.get('service_name', 'Nepoznata usluga')
                item_price = float(item_details.get('total_price', 0))
                quantity = int(item_details.get('quantity', 1))
            elif item.invoice_item_type == 4:  # Tov
                item_name = item_details.get('fattening_name', 'Nepoznat tov')
                item_price = float(item_details.get('total_price', 0))
                quantity = int(item_details.get('quantity', 1))
            else:
                item_name = 'Nepoznata stavka'
                item_price = 0
                quantity = 1
            
            app.logger.debug(f'Detalji stavke: {item_name}, cena: {item_price}, količina: {quantity}')
            
            # 1. Kreiranje naloga za farmera (cena/1.38)
            farmer_amount = round(item_price / 1.38, 2)  # Cena bez PDV-a
            
            app.logger.debug(f'Iznos za farmera: {farmer_amount}, broj računa: {farm.farm_account_number if hasattr(farm, "farm_account_number") else "nije definisan"}')
            
            # Provera da li je iznos veći od 0
            if farmer_amount <= 0:
                app.logger.warning(f'Iznos za farmera je 0 ili negativan: {farmer_amount}, preskačem kreiranje naloga')
                continue

            if item.invoice_item_type == 1:
                target_dict = farm_orders_1
            elif item.invoice_item_type in [2, 3, 4]:
                target_dict = farm_orders_7
            else:
                continue

            if farm.id in target_dict:
                target_dict[farm.id]['item_price'] += item_price
                target_dict[farm.id]['farmer_amount'] += farmer_amount
            else:
                target_dict[farm.id] = {
                    'farm': farm,
                    'farmer': farmer,
                    'item_price': item_price,
                    'farmer_amount': farmer_amount,
                    'user_address': user_address,
                    'user_city': user_city
                }

        # Kreiranje orders_data_1 iz farm_orders_1
        orders_data_1 = []
        for farm_id, farm_data in farm_orders_1.items():
            farm = farm_data['farm']
            farmer = farm_data['farmer']
            item_price = farm_data['item_price']
            farmer_amount = farm_data['farmer_amount']
            order = {
                "sequenceNo": sequence_no_1,
                "merchantOrderReference": f"REF-{merchant_order_id}-F{farm.id}",
                "debtorName": f"{user.name} {user.surname}",
                "debtorAddress": farm_data['user_address'],
                "debtorCity": farm_data['user_city'],
                "beneficiaryAccount": farm.farm_account_number if hasattr(farm, 'farm_account_number') and farm.farm_account_number else "0000000000000000000",
                "beneficiaryName": f"{farmer.name} {farmer.surname}",
                "beneficiaryAddress": farmer.address if hasattr(farmer, 'address') and farmer.address else "Nepoznata adresa",
                "beneficiaryCity": farmer.city if hasattr(farmer, 'city') and farmer.city else "Nepoznat grad",
                "amountTrans": round(item_price, 2),
                "senderFeeAmount": round(item_price, 2) - farmer_amount, #! Provizija (platforma + payspot)
                "beneficiaryAmount": farmer_amount,
                "beneficiaryCurrency": 941,  # RSD
                "purposeCode": 289,  # Kod plaćanja
                "paymentPurpose": f"Plaćanje za {farm.farm_name} po fakturi sa brojem {invoice.id}",
                "isUrgent": 2,  # Nije hitno
                "valueDate": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")  # Datum valute
            }
            orders_data_1.append(order)
            sequence_no_1 += 1

        # Izračunavanje ukupnog iznosa svih naloga
        total_amount_1 = sum(order["amountTrans"] for order in orders_data_1)
        app.logger.debug(f'Ukupan iznos svih naloga: {total_amount_1}')
        
        #! Provera da li je aktivirana opcija dostave, ako jeste, dodajem nalog za dostavu
        if session.get('delivery')['delivery_status']:
            delivery_total = session.get('delivery')['delivery_total']
            
            app.logger.debug(f'Dodajem nalog za dostavu u iznosu od {delivery_total} din')
            # Dodavanje naloga za dostavu
            delivery_order = {
                "sequenceNo": sequence_no_1,
                "merchantOrderReference": f"REF-{merchant_order_id}-F0", #! F0 znači da nije farma nego da je za portal
                "debtorName": f"{user.name} {user.surname}",
                "debtorAddress": farm_data['user_address'],
                "debtorCity": farm_data['user_city'],
                "beneficiaryAccount": "325950070021477547", #! broj računa portala
                "beneficiaryName": "Miodrag Mitrović/Naša Imperija DOO", #? ime i prezime ili naziv portala
                "beneficiaryAddress": "Kneza Grbovića 10", #! adresa portala
                "beneficiaryCity": "Mionica", #! grad portala
                "amountTrans": round(delivery_total, 2), #? koliko kupac plaća za dostavu
                "senderFeeAmount": 0, #? Provizija (platforma + payspot)
                "beneficiaryAmount": delivery_total, #? koliko portal dobija za dostavu
                "beneficiaryCurrency": 941,  # RSD
                "purposeCode": 289,  # Kod plaćanja
                "paymentPurpose": f"Plaćanje dostave po fakturi sa brojem {invoice.id}",
                "isUrgent": 2,  # Nije hitno
                "valueDate": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")  # Datum valute
            }
            orders_data_1.append(delivery_order)
            sequence_no_1 += 1
            
            # Ažuriranje ukupnog iznosa svih naloga
            total_amount_1 = sum(order["amountTrans"] for order in orders_data_1)
            app.logger.debug(f'Ukupan iznos svih naloga nakon dodavanja dostave: {total_amount_1}')
            
        # Kreiranje orders_data_7 iz farm_orders_7
        orders_data_7 = []
        for farm_id, farm_data in farm_orders_7.items():
            farm = farm_data['farm']
            farmer = farm_data['farmer']
            item_price = farm_data['item_price']
            farmer_amount = farm_data['farmer_amount']
            order = {
                "sequenceNo": sequence_no_7,
                "merchantOrderReference": f"REF-{merchant_order_id}-F{farm.id}",
                "debtorName": f"{user.name} {user.surname}",
                "debtorAddress": farm_data['user_address'],
                "debtorCity": farm_data['user_city'],
                "beneficiaryAccount": farm.farm_account_number if hasattr(farm, 'farm_account_number') and farm.farm_account_number else "0000000000000000000",
                "beneficiaryName": f"{farmer.name} {farmer.surname}",
                "beneficiaryAddress": farmer.address if hasattr(farmer, 'address') and farmer.address else "Nepoznata adresa",
                "beneficiaryCity": farmer.city if hasattr(farmer, 'city') and farmer.city else "Nepoznat grad",
                "amountTrans": round(item_price, 2),
                "senderFeeAmount": round(item_price, 2) - farmer_amount,
                "beneficiaryAmount": farmer_amount,
                "beneficiaryCurrency": 941,
                "purposeCode": 289,
                "paymentPurpose": f"Plaćanje za {farm.farm_name} po fakturi sa brojem {invoice.id}",
                "isUrgent": 2,
                "valueDate": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            }
            orders_data_7.append(order)
            sequence_no_7 += 1

            
            # Ažuriranje ukupnog iznosa svih naloga
            total_amount_7 = sum(order["amountTrans"] for order in orders_data_7)
            app.logger.debug(f'Ukupan iznos svih naloga nakon dodavanja dostave: {total_amount_7}')
        
        # Priprema podataka za zahtev
        request_data_1 = {
            "data": {
                "header": {
                    "companyID": os.environ.get('PAYSPOT_COMPANY_ID'),
                    "requestDateTime": request_date_time,
                    "msgType": 101,
                    "rnd": rnd,
                    "hash": "",  # Biće izračunat kasnije
                    "language": 1  # Srpski jezik
                },
                "body": {
                    "paymentOrderGroup": {
                        "merchantOrderID": merchant_order_id,
                        "merchantOrderAmount": float(merchant_order_amount),
                        "merchantCurrencyCode": 941,  # RSD
                        "paymentType": 1,  # Plaćanje karticom
                        "actionType": "I",  # Insert
                        "sumOfOrders": total_amount_1,  #! Ukupan iznos svih naloga, u našem slučaju treba da je isti kao merchantOrderAmount
                        "numberOfOrders": len(orders_data_1),  #! spajaj uplate po farmama jer će jeftinije biti u odnosu na pojedinačne proizvode/životinje
                        "terminalID": os.environ.get('PAYSPOT_TERMINAL_ID', 'IN001807'), #! ovo treba banka da da, a ako neme u .env učitava potak iz dokumentacije 'IN001807'
                        "transtype": "Auth",
                        "orders": orders_data_1
                    }
                }
            }
        }
        
        request_data_7 = {
            "data": {
                "header": {
                    "companyID": os.environ.get('PAYSPOT_COMPANY_ID'),
                    "requestDateTime": request_date_time,
                    "msgType": 101,
                    "rnd": rnd,
                    "hash": "",  # Biće izračunat kasnije
                    "language": 1  # Srpski jezik
                },
                "body": {
                    "paymentOrderGroup": {
                        "merchantOrderID": merchant_order_id,
                        "merchantOrderAmount": float(merchant_order_amount),
                        "merchantCurrencyCode": 941,  # RSD
                        "paymentType": 7,  # Plaćanje karticom
                        "actionType": "I",  # Insert
                        "sumOfOrders": total_amount_7,  #! Ukupan iznos svih naloga, u našem slučaju treba da bude isti kao merchantOrderAmount
                        "numberOfOrders": len(orders_data_7),  #! spajaj uplate po farmama jer će jeftinije biti u odnosu na pojedinačne proizvode/životinje
                        "terminalID": os.environ.get('PAYSPOT_TERMINAL_ID', 'IN001807'), #! ovo treba banka da da, a ako neme u .env učitava potak iz dokumentacije 'IN001807'
                        "transtype": "Auth",
                        "orders": orders_data_7
                    }
                }
            }
        }
        
        # Izračunavanje hash-a
        # companyID, msgType (101), rnd, secretKey
        secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
        company_id = os.environ.get('PAYSPOT_COMPANY_ID')
        plaintext = f'{company_id}|101|{rnd}|{secret_key}'
        # plaintext = f"{rnd}|{request_date_time}|{merchant_order_id}|{secret_key}"
        app.logger.debug(f'PaySpot plaintext: {company_id}|101|{rnd}|my_secret_key')
        hash_value = calculate_hash(plaintext)
        app.logger.debug(f'PaySpot hash: {hash_value=}')
        
        # Dodavanje hash-a u zahtev
        request_data_1["data"]["header"]["hash"] = hash_value
        request_data_7["data"]["header"]["hash"] = hash_value
        
        # Slanje zahteva ka PaySpot-u
        url = "https://test.nsgway.rs:50009/api/paymentorderinsert"
        
        # Logovanje zahteva pre slanja
        app.logger.debug(f'PaySpot URL: {url}')
        app.logger.debug(f'PaySpot companyID: {os.environ.get("PAYSPOT_COMPANY_ID")}')
        app.logger.debug(f'PaySpot zahtev: {json.dumps(request_data_1, indent=2, ensure_ascii=False)}')
        app.logger.debug(f'PaySpot zahtev: {json.dumps(request_data_7, indent=2, ensure_ascii=False)}')
        
        # Slanje zahteva ka PaySpot-u
        result_1, error_1 = send_payspot_request(request_data_1, merchant_order_id, invoice, orders_data_1, user, payment_type=1)
        result_7, error_7 = send_payspot_request(request_data_7, merchant_order_id, invoice, orders_data_7, user, payment_type=7)

        if result_1 and result_7:
            return True, None
        else:
            error_message = ''
            if not result_1:
                error_message += f"[Tip 1] {error_1}. "
            if not result_7:
                error_message += f"[Tip 7] {error_7}."
            return False, error_message.strip()

    except Exception as e:
        app.logger.error(f'Izuzetak pri slanju PaymentOrderInsert: {str(e)}')
        return False, str(e)


def send_payment_order_confirm(merchant_order_id, payspot_order_id, invoice_id):
    """
    Šalje PaymentOrderConfirm (MsgType=110) zahtev ka PaySpot-u nakon uspešnog plaćanja.
    Šalje poseban zahtev za svaku transakciju.
    """
    try:
        import requests
        import os
        import datetime
        import json
        from mojestado import app, db
        from mojestado.models import Invoice, PaySpotTransaction, Farm
        
        # Pronalaženje fakture
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return False, "Faktura nije pronađena."
        
        # Pronalaženje svih PaySpot transakcija za datu fakturu
        payspot_transactions = PaySpotTransaction.query.filter_by(invoice_id=invoice_id).all()
        
        app.logger.debug(f'Pronađene PaySpot transakcije: {payspot_transactions=}')
        
        # Ako nema transakcija, vrati grešku
        if not payspot_transactions:
            app.logger.error('Nema PaySpot transakcija za datu fakturu')
            return False, "Nema transakcija za slanje"
        
        success = True
        last_error = None
        
        # Slanje posebnog zahteva za svaku transakciju
        for transaction in payspot_transactions:
            # Generisanje random stringa za hash za svaki zahtev
            rnd = generate_random_string()
            
            # Trenutno vreme u formatu koji očekuje PaySpot
            request_date_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            # Izračunavanje hash-a za svaki zahtev
            company_id = os.environ.get('PAYSPOT_COMPANY_ID')
            secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
            plaintext = f"{company_id}|110|{rnd}|{secret_key}"
            hash_value = calculate_hash(plaintext)
            
            farm = Farm.query.get(transaction.farm_id)
            if not farm:
                app.logger.error(f'Farma sa ID {transaction.farm_id} nije pronađena')
                continue
            
            # Korišćenje sačuvane vrednosti beneficiary_amount
            beneficiary_amount = transaction.beneficiary_amount
            if beneficiary_amount is None:
                app.logger.warning(f'Transakcija {transaction.id} nema definisan beneficiary_amount, koristi se 0')
                beneficiary_amount = 0
            
            # Kreiranje zahteva samo za jednu transakciju
            order_confirm_item = {
                "merchantOrderID": merchant_order_id,
                "merchantReference": f"REF-{merchant_order_id}-F{transaction.farm_id}",
                "payspotGroupID": transaction.payspot_group_id,
                "payspotTransactionID": transaction.payspot_transaction_id,
                "beneficiaryAccount": farm.farm_account_number,
                "beneficiaryAmount": beneficiary_amount,
                "valueDate": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            }
            
            # Kreiranje zahteva za trenutnu transakciju
            request_data = {
                "data": {
                    "header": {
                        "companyID": company_id,
                        "requestDateTime": request_date_time,
                        "msgType": 110,
                        "rnd": rnd,
                        "hash": hash_value,
                        "language": 1  # Srpski jezik
                    },
                    "body": {
                        "orderConfirm": [order_confirm_item]  # Lista sa samo jednim elementom
                    }
                }
            }
            
            # Slanje zahteva ka PaySpot-u
            url = "https://test.nsgway.rs:50009/api/paymentorderconfirm"
            
            app.logger.debug(f'PaySpot URL: {url}')
            app.logger.debug(f'PaySpot companyID: {company_id}')
            app.logger.debug(f'PaySpot zahtev za transakciju {transaction.payspot_transaction_id}: {json.dumps(request_data, indent=2, ensure_ascii=False)}')
            
            # Konvertovanje JSON-a u string sa UTF-8 kodiranjem
            json_data = json.dumps(request_data, ensure_ascii=False).encode('utf-8')
            
            # Slanje zahteva sa eksplicitnim UTF-8 kodiranjem
            response = requests.post(url, data=json_data, headers={"Content-Type": "application/json; charset=utf-8"})
            
            # Logovanje odgovora
            app.logger.debug(f'PaySpot status kod za transakciju {transaction.payspot_transaction_id}: {response.status_code}')
            try:
                response_text = response.text
                app.logger.debug(f'PaySpot odgovor za transakciju {transaction.payspot_transaction_id}: {response_text}')
                response_data = response.json()
            except Exception as e:
                app.logger.error(f'Greška pri parsiranju PaySpot odgovora za transakciju {transaction.payspot_transaction_id}: {str(e)}')
                success = False
                last_error = f"HTTP greška: {response.status_code}, Nije moguće parsirati odgovor."
                continue  # Prelazimo na sledeću transakciju
            
            # Provera odgovora
            if response.status_code == 200:
                # Proverimo status u odgovoru
                status = response_data.get("data", {}).get("status", {})
                error_code = status.get("errorCode") if status else None
                
                # Ako status nije dostupan u glavnom delu, proverimo u body delu
                if error_code is None:
                    error_code = response_data.get("data", {}).get("body", {}).get("errorCode")
                
                if error_code == 0:
                    app.logger.info(f'Uspešno poslat PaymentOrderConfirm za transakciju {transaction.payspot_transaction_id}')
                else:
                    # Prvo pokušaj da nađeš error message u statusu
                    error_message = status.get("errorMessage") if status else None
                    # Ako nije tamo, pokušaj u body delu
                    if not error_message:
                        error_message = response_data.get("data", {}).get("body", {}).get("errorMessage")
                    
                    if not error_message:
                        error_message = "Nepoznata greška"
                        
                    app.logger.error(f'Greška pri slanju PaymentOrderConfirm za transakciju {transaction.payspot_transaction_id}: {error_message}')
                    success = False
                    last_error = error_message
            else:
                app.logger.error(f'HTTP greška pri slanju PaymentOrderConfirm za transakciju {transaction.payspot_transaction_id}: {response.status_code}')
                success = False
                last_error = f"HTTP greška: {response.status_code}"
        
        # Vraćanje konačnog rezultata
        if success:
            app.logger.info(f'Uspešno poslati svi PaymentOrderConfirm zahtevi za narudžbinu {merchant_order_id}')
            return True, None
        else:
            app.logger.error(f'Greška pri slanju PaymentOrderConfirm zahteva za narudžbinu {merchant_order_id}: {last_error}')
            return False, last_error
            
    except Exception as e:
        app.logger.error(f'Izuzetak pri slanju PaymentOrderConfirm: {str(e)}')
        return False, str(e)