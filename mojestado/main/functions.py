from flask import session

from mojestado.models import Invoice


def define_next_invoice_number():
    try:
        invoices = Invoice.query.all()
        if not invoices:
            next_invoice_number = 1
        else:
            invoice_number_list = [invoice.id for invoice in invoices if isinstance(invoice.id, int)]
            if not invoice_number_list:
                next_invoice_number = 1
            else:
                max_invoice_number = max(invoice_number_list)
                next_invoice_number = max_invoice_number + 1
        
        # Formatiranje broja fakture kao string sa vodećim nulama
        formatted_invoice_number = f"{next_invoice_number:09d}"
        
        return formatted_invoice_number
    except Exception as e:
        # Logovanje greške
        print(f"Došlo je do greške pri određivanju sledećeg broja fakture: {str(e)}")
        # Vraćanje podrazumevanog broja u slučaju greške
        return "000000000"


def clear_cart_session():
    session.pop('animals', None)
    session.pop('products', None)
    session.pop('fattening', None)
    session.pop('services', None)


def get_cart_total():
    '''
    treba ragranati sa if blokom: 
    - ako je na rate tov onda sabirati samo products, animals, services
    - ako NIJE na rate, onda sabrati sve (products, animals, services, fattening)
    '''
    print(f'{session=}')
    cart_total = 0
    installment_total = 0
    
    if 'products' in session and isinstance(session.get('products'), list):
        for product in session['products']:
            cart_total += float(product['total_price'])
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
    return cart_total, installment_total