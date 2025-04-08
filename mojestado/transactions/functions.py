import base64, hashlib
import io
import datetime, os
import random, string

import requests

from PIL import Image

from mojestado import db, mail
from mojestado.models import Animal, Debt, Farm, Invoice, InvoiceItems, Product, User

from flask import flash, json, redirect, render_template, session, url_for
from flask import current_app as app
from flask_login import current_user
from flask_mail import Message, Attachment

from fpdf import FPDF

current_file_path = os.path.abspath(__file__)
project_folder = os.path.dirname(os.path.dirname((current_file_path)))
print(f'{current_file_path=}')
print(f'{project_folder=}')

font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')


def add_fonts(pdf):
    pdf.add_font('DejaVuSansCondensed', '', font_path, uni=True)
    pdf.add_font('DejaVuSansCondensed', 'B', font_path_B, uni=True)


def generate_payment_slips_attach(invoice_item):
    '''
    generiše 2+ uplatnice na jednom dokumentu (A4) u fpdf, qr kod/api iz nbs
    '''
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
        poziv_na_broj = f'{invoice_item.invoice.user_id:05d}-{invoice_item.id:06d}'
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
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    invoice = Invoice.query.get(invoice_id)
    
    file_name = f'{invoice.invoice_number}.pdf'
    
    products = [invoice_item.invoice_item_details for invoice_item in invoice_items if invoice_item.invoice_item_type == 1]
    animals = [invoice_item.invoice_item_details for invoice_item in invoice_items if invoice_item.invoice_item_type == 2]
    services = [invoice_item.invoice_item_details for invoice_item in invoice_items if invoice_item.invoice_item_type == 3]
    # fattening = [invoice_item.invoice_item_details for invoice_item in invoice_items if (invoice_item.invoice_item_type == 4 and json.loads(invoice_item.invoice_item_details)['installment_options'] > 1)]
    fattening = [invoice_item.invoice_item_details for invoice_item in invoice_items if (invoice_item.invoice_item_type == 4 and invoice_item.invoice_item_details['installment_options'] > 1)]
    print(f'{fattening=}')
    
    #! generisi fakturu uz pomoć fpdf
    current_file_path = os.path.abspath(__file__)
    project_folder = os.path.dirname(os.path.dirname((current_file_path)))
    font_path = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed.ttf')
    font_path_B = os.path.join(project_folder, 'static', 'fonts', 'DejaVuSansCondensed-Bold.ttf')
    class PDF(FPDF):
        def __init__(self, **kwargs):
            super(PDF, self).__init__(**kwargs)
            self.add_font('DejaVuSansCondensed', '', font_path, uni=True)
            self.add_font('DejaVuSansCondensed', 'B', font_path_B, uni=True)
        def header(self):
            self.set_font('DejaVuSansCondensed', 'B', 16)
            self.cell(0, 10, f'Faktura {invoice.invoice_number}', new_x='LMARGIN', new_y='NEXT', align='C')
    
    pdf = PDF()
    pdf.add_page(orientation='L')
    pdf.set_fill_color(200, 200, 200)  # Svetlo siva boja
    #! proizvodi
    if products:
        pdf.set_font('DejaVuSansCondensed', 'B', 10)
        pdf.cell(0, 10, f'Proizvodi', new_y='NEXT', new_x='LMARGIN', align='L', border=0, fill=False)
        pdf.set_font('DejaVuSansCondensed', 'B', 7)
        pdf.cell(30, 10, f'Kategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Potkategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Sektor', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Naziv', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(15, 10, f'Količina', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(20, 10, f'Jedinica mere', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Cena po jedinici mere', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(20, 10, f'Cena po kg', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(20, 10, f'Ukupna cena', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'PG', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Lokacija', new_y='NEXT', new_x='LMARGIN', align='L', border=1, fill=True)
        # pdf.set_fill_color(255, 255, 255)  # Svetlo siva boja
        pdf.set_font('DejaVuSansCondensed', '', 7)
        for product in products:
            pdf.cell(30, 10, f'{product["category"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{product["subcategory"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{product["section"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{product["product_name"]}', new_y='LAST', align='L', border=1)
            pdf.cell(15, 10, f'{product["quantity"]}', new_y='LAST', align='L', border=1)
            pdf.cell(20, 10, f'{product["unit_of_measurement"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{float(product["product_price_per_unit"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(20, 10, f'{float(product["product_price_per_kg"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(20, 10, f'{float(product["total_price"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{product["farm"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{product["location"]}', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(0, 10, '', new_y='NEXT', new_x='LMARGIN')
    #! živa vaga
    if animals:
        pdf.set_font('DejaVuSansCondensed', 'B', 10)
        pdf.cell(0, 10, f'Živa vaga', new_y='NEXT', new_x='LMARGIN', align='L', border=0, fill=False)
        # pdf.set_fill_color(200, 200, 200)  # Svetlo siva boja
        pdf.set_font('DejaVuSansCondensed', 'B', 7)
        pdf.cell(30, 10, f'Kategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Potkategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Rasa', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(10, 10, f'Pol', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(15, 10, f'Masa', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(20, 10, f'Cena po kg', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(20, 10, f'Ukupna cena', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Osigurano', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Organsko', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'PG', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Lokacija', new_y='NEXT', new_x='LMARGIN', align='L', border=1, fill=True)
        # pdf.set_fill_color(255, 255, 255)  # Svetlo siva boja
        pdf.set_font('DejaVuSansCondensed', '', 7)
        for animal in animals:
            pdf.cell(30, 10, f'{animal["category"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{animal["subcategory"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{animal["race"]}', new_y='LAST', align='L', border=1)
            pdf.cell(10, 10, f'{animal["animal_gender"]}', new_y='LAST', align='L', border=1)
            pdf.cell(15, 10, f'{float(animal["current_weight"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(20, 10, f'{float(animal["price_per_kg"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(20, 10, f'{float(animal["total_price"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{animal["insured"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{animal["organic_animal"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{animal["farm"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{animal["location"]}', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(0, 10, '', new_y='NEXT', new_x='LMARGIN')
    #! usluge
    if services:
        pdf.set_font('DejaVuSansCondensed', 'B', 10)
        pdf.cell(0, 10, f'Usluge', new_y='NEXT', new_x='LMARGIN', align='L', border=0, fill=False)
        pdf.set_font('DejaVuSansCondensed', 'B', 7)
        pdf.cell(30, 10, f'Kategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Potkategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Rasa', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(10, 10, f'Pol', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(15, 10, f'Masa', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Usluga', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Cena', new_y='NEXT', new_x='LMARGIN', align='L', border=1, fill=True)
        pdf.set_font('DejaVuSansCondensed', '', 7)
        for service in services:
            pdf.cell(30, 10, f'{service["category"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{service["subcategory"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{service["race"]}', new_y='LAST', align='L', border=1)
            pdf.cell(10, 10, f'{service["animal_gender"]}', new_y='LAST', align='L', border=1)
            pdf.cell(15, 10, f'{float(service["current_weight"]):.2f}', new_y='LAST', align='L', border=1)
            if service['slaughterService'] == True and service['processingPrice'] > 0:
                pdf.cell(30, 10, f'Klanje i obrada', new_y='LAST', align='L', border=1)
                pdf.cell(30, 10, f'{float(service["slaughterPrice"]):.2f}', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
            elif service['slaughterService']:
                pdf.cell(30, 10, f'Klanje', new_y='LAST', align='L', border=1)
                pdf.cell(30, 10, f'{float(service["slaughterPrice"] + service["processingPrice"]):.2f}', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
        pdf.cell(0, 10, '', new_y='NEXT', new_x='LMARGIN')
    
    #! tov (samo koji NIJE na rate?)
    if fattening:
        pdf.set_font('DejaVuSansCondensed', 'B', 10)
        pdf.cell(0, 10, f'Tov', new_y='NEXT', new_x='LMARGIN', align='L', border=0, fill=False)
        pdf.set_font('DejaVuSansCondensed', 'B', 7)
        pdf.cell(30, 10, f'Kategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Potkategorija', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Rasa', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(10, 10, f'Pol', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(15, 10, f'Željena masa', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(15, 10, f'Cena tova', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(15, 10, f'Br hranidbenih dana', new_y='LAST', align='L', border=1, fill=True)
        pdf.cell(30, 10, f'Br rata', new_y='NEXT', new_x='LMARGIN', align='L', border=1, fill=True)
        pdf.set_font('DejaVuSansCondensed', '', 7)
        for fattening_item in fattening:
            pdf.cell(30, 10, f'{fattening_item["category"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{fattening_item["subcategory"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{fattening_item["race"]}', new_y='LAST', align='L', border=1)
            pdf.cell(10, 10, f'{fattening_item["animal_gender"]}', new_y='LAST', align='L', border=1)
            pdf.cell(15, 10, f'{float(fattening_item["desired_weight"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(15, 10, f'{float(fattening_item["fattening_price"]):.2f}', new_y='LAST', align='L', border=1)
            pdf.cell(15, 10, f'{fattening_item["feeding_days"]}', new_y='LAST', align='L', border=1)
            pdf.cell(30, 10, f'{fattening_item["installment_options"]}', new_y='NEXT', new_x='LMARGIN', align='L', border=1)
    
    
    path = os.path.join(project_folder, 'static', 'invoices')
    if not os.path.exists(path):
        os.mkdir(path)
    pdf.output(os.path.join(path, file_name))
    return os.path.join(path, file_name)


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


def create_invoice():
    '''
    čuva podaatke u db (faktura i stavke)
    -faktura treba da sadrži:
    -- datum i vreme transakcije
    -- broj fakture (2024-000001, 2024-000002, ...)
    -- customer_id (user, guest)
    
    - stavka treba da sadrži:
    -- farm_id
    -- animal_id + usluge(tov, klanje, obrada, dostava ako je izabrano)
    -- product_id + količina
    -- tov?
    -- usluga? (klanje, obrada, dostava)
    '''
    print('wip: Faktura kreirana')
    # Generisanje broja fakture (primer: 2024-000001)
    last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
    if last_invoice:
        last_invoice_number = int(last_invoice.invoice_number.split('-')[1])
        new_invoice_number = f'{datetime.datetime.now().year}-{last_invoice_number + 1:06d}'
    else:
        new_invoice_number = f'{datetime.datetime.now().year}-000001'
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        print(f'{session=}')
        print(f'wip: Guest user: {session.get("guest_email")=}')
        guest_user = User.query.filter_by(email=session['guest_email']).first()
        user_id = guest_user.id
        
    new_invoice = Invoice(
        datetime=datetime.datetime.now(),
        invoice_number=new_invoice_number,
        user_id=user_id,
        status='unconfirmed'
    )
    db.session.add(new_invoice)
    db.session.commit()
    

    #! Nastavi kod koji će iz session kopre da doda svaku stavku u fakturu
    #! Nastavi kod koji će iz session kopre da doda svaku stavku u fakturu
    #! Nastavi kod koji će iz session kopre da doda svaku stavku u fakturu
    
    for product in session.get('products', []):
        new_invoice_item = InvoiceItems(
            farm_id=product['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=product,
            # invoice_item_details=json.dumps(product),
            invoice_item_type=1
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    
    for animal in session.get('animals', []):
        new_invoice_item = InvoiceItems(
            farm_id=animal['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=animal,
            # invoice_item_details=json.dumps(animal),
            invoice_item_type=2
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    
    for service in session.get('services', []):
        new_invoice_item = InvoiceItems(
            farm_id=service['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=service,
            # invoice_item_details=json.dumps(service),
            invoice_item_type=3
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    
    for fattening in session.get('fattening', []):
        new_invoice_item = InvoiceItems(
            farm_id=fattening['farm_id'],
            invoice_id=new_invoice.id,
            invoice_item_details=fattening,
            # invoice_item_details=json.dumps(fattening),
            invoice_item_type=4
        )
        db.session.add(new_invoice_item)
        db.session.commit()
    return new_invoice


def deactivate_animals(invoice_id):
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 2:
            animal_id = invoice_item.invoice_item_details['id']
            # animal_id = json.loads(invoice_item.invoice_item_details)['id']
            animal_to_edit = Animal.query.get(animal_id)
            animal_to_edit.active = False
            db.session.commit()


def deactivate_products(invoice_id):
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 1:
            product_id = invoice_item.invoice_item_details['id']
            # product_id = json.loads(invoice_item.invoice_item_details)['id']
            product_to_edit = Product.query.get(product_id)
            product_to_edit.quantity = float(product_to_edit.quantity) - float(invoice_item.invoice_item_details['quantity'])
            # product_to_edit.quantity = float(product_to_edit.quantity) - float(json.loads(invoice_item.invoice_item_details)['quantity'])
            db.session.commit()


def send_email(user, invoice_id):
    '''
    - ako je na rate šalje fiskalni račun (dobija od firme Fiscomm) i sve uplatnice (generiše portal)
    -- fiskalni račnu obugvata ukupnu sumu novca za plaćanje, stim što se odmah sa računa skida suma koja nije za tov (preko PaySpot firma), a ostatak se plaća preko uplatnica (koje generiše portal)
    - ako nije na rate šalje samo fiskalni račun (dobija od firme Fiscomm)
    '''
    
    #! proveravam da li je na rate
    #! invoice_items čiji je type = 4 (fattening)
    
    payment_slips = [] #! ako je prazna lista onda NIJE na rate
    invoice_items = InvoiceItems.query.filter_by(invoice_id=invoice_id).all()
    for invoice_item in invoice_items:
        if invoice_item.invoice_item_type == 4: #! razmatra samo usluge tova (4)
            # fattening = json.loads(invoice_item.invoice_item_details)
            fattening = invoice_item.invoice_item_details
            if int(fattening['installment_options']) > 1: #! Ako je na rate, generišu se uplatnice i zaduži
                create_debt(user, invoice_item)
                print('wip: ova usluga je na rate')
                new_payment_slip = generate_payment_slips_attach(invoice_item)
                payment_slips.append(new_payment_slip) #! ako lista NIJE prazna onda je na rate
        elif invoice_item.invoice_item_type == 1: #! ako je gotov proizvod treba da pošalje mejl farmeru:
            '''
            Prilikom svake kupovine stiže mejl sa informacijama o prodatoj količini i o trenutnom stanju količine proizvoda na portalu, 
            sa molbom da se količine ažuriraju po potrebi. U mejlu se nalazi i link za ažuriranje stanja gotovih proizvoda.
            '''
            send_email_to_update_product_quantity(invoice_item) #! definisati funkciju
    print(f'{payment_slips=}')
    
    invoice_attach = generate_invoice_attach(invoice_id)

    to = [user.email]
    bcc = [os.environ.get('MAIL_ADMIN')]
    subject = 'Potvrda kupovine na portalu "Moje stado"'

    if payment_slips: #! ako lista NIJE prazna onda je na rate
        # body = f"Poštovani/a {user.name},\n\nVaša kupovina je uspešno izvršena.\n\nDetalji kupovine i uplatnice možete da vidite u prilogu.\n\nHvala na poverenju!"
        attachments = [invoice_attach] + [new_payment_slip]
        na_rate = True
        # message = Message(subject=subject, sender=os.environ.get('MAIL_DEFAULT_SENDER'), recipients=to, bcc=bcc, attachments=[invoice_attach] + payment_slips)
    else:
        # body = f"Poštovani/a {user.name},\n\nVaša kupovina je uspešno izvršena.\n\nDetalje kupovine možete da vidite u prilogu.\n\nHvala na poverenju!"
        attachments = [invoice_attach]
        na_rate = False
        # message = Message(subject=subject, sender=os.environ.get('MAIL_DEFAULT_SENDER'), recipients=to, bcc=bcc, attachments=[invoice_attach])
        
    message = Message(subject=subject, sender=os.environ.get('MAIL_DEFAULT_SENDER'), recipients=to, bcc=bcc)
    # message.body = body
    message.html = render_template('message_html_confirm_invoice.html', na_rate=na_rate)
    print(f'{attachments=}')
    for attachment in attachments:
        try:
            with open(attachment, 'rb') as f:
                message.attach(os.path.basename(attachment), "application/pdf", f.read())
        except Exception as e:
            print(f"Greška prilikom dodavanja priloga: {attachment}. Greška: {e}")
    
    print(f"To: {to}")
    print(f"Subject: {subject}")
    # print(f"Body: {body}")
    
    # TODO: Implement actual email sending logic here
    # For now, we'll just print the email details
    
    try:
        mail.send(message)
        print('wip: Email poslat')
    except Exception as e:
        print(f'Error sending email: {e}')


def send_email_to_update_product_quantity(invoice_item):
    '''
    Prilikom svake kupovine stiže mejl sa informacijama o prodatoj količini i o trenutnom stanju količine proizvoda na portalu, 
    sa molbom da se količine ažuriraju po potrebi. U mejlu se nalazi i link za ažuriranje stanja gotovih proizvoda.
    '''
    print(f'send_email > proizvod > slanje mejla PG ako je proizvod da ažurira količine proizvoda na portalu')
    farm = Farm.query.filter_by(id=invoice_item.farm_id).first()
    farmer = User.query.filter_by(id=farm.user_id).first()
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
        print('wip: poslat mejl PG o prodaji proizvod')
    except Exception as e:
        print(f'Greška slana mejla PG; {e}')

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


def send_payment_order_insert(merchant_order_id, merchant_order_amount, user):
    """
    Šalje PaymentOrderInsert (MsgType=101) zahtev ka PaySpot-u pre plaćanja
    """
    try:
        import requests
        import os
        import datetime
        import json
        from mojestado import app
        
        app.logger.info(f'Započinjem slanje PaymentOrderInsert za narudžbinu {merchant_order_id}')
        app.logger.debug(f'Parametri: merchant_order_id={merchant_order_id}, merchant_order_amount={merchant_order_amount}')
        app.logger.debug(f'Korisnik: id={user.id}, name={user.name}, surname={user.surname}')
        
        # Generisanje random stringa za hash
        rnd = generate_random_string()
        app.logger.debug(f'Generisan random string: {rnd}')
        
        # Trenutno vreme u formatu koji očekuje PaySpot
        request_date_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        app.logger.debug(f'Vreme zahteva: {request_date_time}')
        
        # Priprema podataka za nalog
        orders_data = []
        
        # Provera da li korisnik ima adresu i grad
        user_address = user.address if hasattr(user, 'address') and user.address else "Nepoznata adresa"
        user_city = user.city if hasattr(user, 'city') and user.city else "Nepoznat grad"
        app.logger.debug(f'Adresa korisnika: {user_address}, Grad: {user_city}')
        
        # Ovde treba pripremiti podatke za svaki nalog (za svakog prodavca)
        # Primer za jedan nalog:
        order = {
            "sequenceNo": 1,
            "merchantOrderReference": f"REF-{merchant_order_id}",
            "debtorName": f"{user.name} {user.surname}",
            "debtorAddress": user_address,
            "debtorCity": user_city,
            "beneficiaryAccount": "265178031000308698",  # Račun primaoca
            "beneficiaryName": "Naša imperija doo",
            "beneficiaryAddress": "Kneza Grbovića 10",
            "beneficiaryCity": "Mionica",
            "amountTrans": float(merchant_order_amount),
            "senderFeeAmount": 0.00,  # Provizija
            "beneficiaryAmount": float(merchant_order_amount),
            "beneficiaryCurrency": 941,  # RSD
            "purposeCode": 289,  # Kod plaćanja
            "paymentPurpose": "Plaćanje za proizvode",
            "isUrgent": 0,  # Nije hitno
            "valueDate": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")  # Datum valute
        }
        
        orders_data.append(order)
        app.logger.debug(f'Pripremljeni podaci za nalog: {json.dumps(order)}')
        
        # Priprema podataka za zahtev
        request_data = {
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
                        "sumOfOrders": float(merchant_order_amount),  # Ukupan iznos svih naloga
                        "numberOfOrders": len(orders_data),  # Broj naloga
                        "terminalID": os.environ.get('PAYSPOT_TERMINAL_ID', 'XXXXX'),
                        "transtype": "Auth",
                        "orders": orders_data
                    }
                }
            }
        }
        
        # Provera konfiguracije
        app.logger.debug(f'PAYSPOT_COMPANY_ID: {os.environ.get("PAYSPOT_COMPANY_ID")}')
        app.logger.debug(f'PAYSPOT_TERMINAL_ID: {os.environ.get("PAYSPOT_TERMINAL_ID")}')
        
        # Izračunavanje hash-a
        secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
        if not secret_key:
            app.logger.error('Nedostaje PAYSPOT_SECRET_KEY u konfiguraciji')
            return False, "Nedostaje PAYSPOT_SECRET_KEY u konfiguraciji"
            
        # Formiranje plaintext stringa za hash
        plaintext = f"{rnd}|{request_date_time}|{merchant_order_id}|{merchant_order_amount:.2f}|{secret_key}"
        app.logger.debug(f'Plaintext za hash (bez secret_key): {rnd}|{request_date_time}|{merchant_order_id}|{merchant_order_amount:.2f}|******')
        
        hash_value = calculate_hash(plaintext)
        app.logger.debug(f'Izračunati hash: {hash_value}')
        
        # Dodavanje hash-a u zahtev
        request_data["data"]["header"]["hash"] = hash_value
        
        # Logovanje zahteva za dijagnostiku (bez osetljivih podataka)
        request_data_log = json.loads(json.dumps(request_data))
        request_data_log["data"]["header"]["hash"] = "*****"
        app.logger.info(f'PaymentOrderInsert zahtev: {json.dumps(request_data_log)}')
        
        # Slanje zahteva ka PaySpot-u
        url = "https://test.nsgway.rs:50009/api/paymentorderinsert"
        headers = {"Content-Type": "application/json"}
        app.logger.debug(f'Šaljem zahtev na URL: {url}')
        
        try:
            response = requests.post(url, json=request_data, headers=headers, timeout=30)
            app.logger.debug(f'Status kod odgovora: {response.status_code}')
            app.logger.debug(f'Zaglavlja odgovora: {response.headers}')
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    app.logger.info(f'PaymentOrderInsert odgovor: {json.dumps(response_data)}')
                    error_code = response_data.get("data", {}).get("status", {}).get("errorCode")
                    
                    if error_code == 0:
                        app.logger.info(f'Uspešno poslat PaymentOrderInsert za narudžbinu {merchant_order_id}')
                        return True, None
                    else:
                        error_message = response_data.get("data", {}).get("status", {}).get("errorMessage", "Nepoznata greška")
                        app.logger.error(f'Greška pri slanju PaymentOrderInsert: {error_message}')
                        return False, error_message
                except ValueError as e:
                    app.logger.error(f'Greška pri parsiranju JSON odgovora: {str(e)}')
                    app.logger.debug(f'Sadržaj odgovora: {response.text}')
                    return False, f"Greška pri parsiranju odgovora: {str(e)}"
            else:
                # Logovanje detalja greške
                try:
                    error_content = response.text
                    app.logger.error(f'HTTP greška pri slanju PaymentOrderInsert: {response.status_code}')
                    app.logger.error(f'Detalji greške: {error_content}')
                    return False, f"HTTP greška: {response.status_code}"
                except Exception as e:
                    app.logger.error(f'HTTP greška pri slanju PaymentOrderInsert: {response.status_code}, Nije moguće parsirati odgovor: {str(e)}')
                    return False, f"HTTP greška: {response.status_code}"
        except requests.exceptions.Timeout:
            app.logger.error(f'Timeout pri slanju PaymentOrderInsert zahteva')
            return False, "Isteklo je vreme za odgovor servera. Molimo pokušajte ponovo kasnije."
        except requests.exceptions.ConnectionError as e:
            app.logger.error(f'Greška pri povezivanju sa PaySpot servisom: {str(e)}')
            return False, "Nije moguće povezati se sa servisom za plaćanje. Molimo proverite internet konekciju."
        except Exception as e:
            app.logger.error(f'Neočekivana greška pri slanju zahteva: {str(e)}')
            return False, f"Neočekivana greška: {str(e)}"
            
    except Exception as e:
        app.logger.error(f'Izuzetak pri slanju PaymentOrderInsert: {str(e)}')
        return False, str(e)


def send_payment_order_confirm(merchant_order_id, payspot_order_id, invoice_id):
    """
    Šalje PaymentOrderConfirm (MsgType=110) zahtev ka PaySpot-u nakon uspešnog plaćanja
    """
    try:
        import requests
        import os
        import datetime
        from mojestado import app, db
        from mojestado.models import Invoice
        
        # Generisanje random stringa za hash
        rnd = generate_random_string()
        
        # Trenutno vreme u formatu koji očekuje PaySpot
        request_date_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Pronalazenje fakture i podataka o narudžbini
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return False, "Faktura nije pronađena."
        
        # Priprema podataka za zahtev
        request_data = {
            "data": {
                "header": {
                    "companyID": os.environ.get('PAYSPOT_COMPANY_ID'),
                    "requestDateTime": request_date_time,
                    "msgType": 110,
                    "rnd": rnd,
                    "hash": "",  # Biće izračunat kasnije
                    "language": 1  # Srpski jezik
                },
                "body": {
                    "orderConfirm": [
                        {
                            "merchantOrderID": merchant_order_id,
                            "merchantReference": f"REF-{merchant_order_id}",
                            "payspotGroupID": payspot_order_id,
                            "payspotTransactionID": payspot_order_id,
                            "beneficiaryAccount": "265178031000308698",  # Račun primaoca
                            "beneficiaryAmount": float(invoice.total_amount),
                            "valueDate": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")  # Datum valute
                        }
                    ]
                }
            }
        }
        
        # Izračunavanje hash-a
        secret_key = os.environ.get('PAYSPOT_SECRET_KEY')
        plaintext = f"{rnd}|{request_date_time}|{merchant_order_id}|{secret_key}"
        hash_value = calculate_hash(plaintext)
        
        # Dodavanje hash-a u zahtev
        request_data["data"]["header"]["hash"] = hash_value
        
        # Slanje zahteva ka PaySpot-u
        url = "https://test.nsgway.rs:50009/api/paymentorderconfirm"
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=request_data, headers=headers)
        
        if response.status_code == 200:
            response_data = response.json()
            error_code = response_data.get("data", {}).get("body", {}).get("errorCode")
            
            if error_code == 0:
                app.logger.info(f'Uspešno poslat PaymentOrderConfirm za narudžbinu {merchant_order_id}')
                return True, None
            else:
                error_message = response_data.get("data", {}).get("body", {}).get("errorMsg", "Nepoznata greška")
                app.logger.error(f'Greška pri slanju PaymentOrderConfirm: {error_message}')
                return False, error_message
        else:
            app.logger.error(f'HTTP greška pri slanju PaymentOrderConfirm: {response.status_code}')
            return False, f"HTTP greška: {response.status_code}"
            
    except Exception as e:
        app.logger.error(f'Izuzetak pri slanju PaymentOrderConfirm: {str(e)}')
        return False, str(e)