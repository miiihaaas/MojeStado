from mojestado import app, db, login_manager
from flask_login import UserMixin
# from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous.url_safe import URLSafeTimedSerializer
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    print('ušao sam u funkciju load_user')
    return User.query.get(int(user_id))



class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=True)
    name = db.Column(db.String(20), unique=False, nullable=False)
    surname = db.Column(db.String(20), unique=False, nullable=False)
    address = db.Column(db.String(20), unique=False, nullable=False)
    city = db.Column(db.String(20), unique=False, nullable=False)
    zip_code = db.Column(db.String(5), unique=False, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    BPG = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    #JMBG = db.Column(db.String(13), unique=True, nullable=True, default=None)
    MB = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    user_type = db.Column(db.String(20), nullable=False) #! postoje tipovi: admin, farm_active, farm_inactive, user, user_removed, guest(onaj koji je kupio a da nije napravio nalog: bitni su nam email, telefon, ime i prezime + ostalo)
    registration_date = db.Column(db.DateTime, nullable=False)
    farms = db.relationship('Farm', backref='user_farm', lazy=True) #! 
    invoices = db.relationship('Invoice', backref='user_invoice', lazy=True)
    

    def get_reset_token(self, expires_sec=1800):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})  # ne treba više decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=1800)['user_id']  # dodajemo max_age parametar
        except:
            return None
        return User.query.get(user_id)
    

    def __repr__(self):
        return f"User('{self.name}', '{self.email}')"


class Municipality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    municipality_name = db.Column(db.String(50), nullable=False)
    municipality_zip_code = db.Column(db.String(5), nullable=False)
    farms = db.relationship('Farm', backref='municipality_farm', lazy=True) #! razradi ovo bolje
    pass


class Farm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farm_image = db.Column(db.String(20), nullable=False, default='default.jpg') #! prilagoditi da može da se stavi do 10 slika
    farm_image_collection = db.Column(db.JSON, nullable=True)
    farm_name = db.Column(db.String(20), nullable=False)
    farm_address = db.Column(db.String(20), nullable=False)
    farm_city = db.Column(db.String(20), nullable=False)
    farm_zip_code = db.Column(db.String(5), nullable=False)
    farm_municipality_id = db.Column(db.Integer, db.ForeignKey('municipality.id'), nullable=False) #!
    farm_phone = db.Column(db.String(20), nullable=False)
    farm_account_number = db.Column(db.String(20), nullable=False)
    farm_description = db.Column(db.Text, nullable=False)
    services = db.Column(db.JSON, nullable=True) #! usluga klanja, usluga obrade - tu treba da se definišu cene usluga za kategorije
    registration_date = db.Column(db.Date, nullable=True) #! kada admin potvrdi da je registrovan, tada se dodeli trenutni datum
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #!
    animals = db.relationship('Animal', backref='farm_animal', lazy=True) #!
    products = db.relationship('Product', backref='farm_product', lazy=True) #!
    payspot_transactions = db.relationship('PaySpotTransaction', backref='farm_payspot_transaction', lazy=True)


class Animal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.String(10), nullable=True)  # Svako grlo stoke odnosno živine ima minđušu odnosno nanogicu. Na minđuši je ispisan jedinstveni broj koji se sastoji od dva bloka cifara. Prvi petocifreni blok označava PG, a drugi petocifreni ili šestocifreni broj označava redni broj grla.
    animal_category_id = db.Column(db.Integer, db.ForeignKey('animal_category.id'), nullable=False)
    animal_categorization_id = db.Column(db.Integer, db.ForeignKey('animal_categorization.id'), nullable=False)
    animal_race_id = db.Column(db.Integer, db.ForeignKey('animal_race.id'), nullable=False)

    animal_gender = db.Column(db.String(20), nullable=False)  # pol
    measured_weight = db.Column(db.String(20), nullable=False)  # izmerena težina
    measured_date = db.Column(db.String(20), nullable=False)  # datum merenja
    current_weight = db.Column(db.Float, nullable=False)  # trenutna težina = preračunava se u odnosu na izmerenu težinu i datum merenja
    wanted_weight = db.Column(db.Float, nullable=True)  # zeljena težina
    price_per_kg_farmer = db.Column(db.Float, nullable=False)  # cena po kg
    price_per_kg = db.Column(db.Float, nullable=False)  # cena po kg
    total_price = db.Column(db.Float, nullable=False)  # ukupna cena
    insured = db.Column(db.Boolean, nullable=False)  # osigurano
    organic_animal = db.Column(db.Boolean, nullable=False)  # organska proizvodnja
    cardboard = db.Column(db.String(50), nullable=True)  # karton grla/životinje
    intended_for = db.Column(db.String(20), nullable=False)  # tov/priplod
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False)
    
    fattening = db.Column(db.Boolean, nullable=False) #! podrazumevana vrednost je False, a kada kupac naruči da se tovi neka životnja onda prelazi u True
    active = db.Column(db.Boolean, nullable=False)
    
    #! projektovani datum završetka tova (ako se životinja izabere za tov)
    #! invoice_id - iz koga može da se izvuče user_id, cena tova, datum početka tova
    
    fattening_finish_date = db.Column(db.Date, nullable=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)

    animal_category = db.relationship('AnimalCategory', back_populates='animals')
    animal_race = db.relationship('AnimalRace', back_populates='animals')
    animal_categorization = db.relationship('AnimalCategorization', back_populates='animals')


class AnimalRace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_race_name = db.Column(db.String(50), nullable=False)
    animal_category_id = db.Column(db.Integer, db.ForeignKey('animal_category.id'), nullable=False)
    # category = db.Column(db.String(20), nullable=False)
    animals = db.relationship('Animal', back_populates='animal_race', lazy=True)
    animal_category = db.relationship('AnimalCategory', back_populates='animal_races')


class AnimalCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_category_name = db.Column(db.String(80), nullable=False)
    mass_filters = db.Column(db.JSON, nullable=True)
    animals = db.relationship('Animal', back_populates='animal_category', lazy=True)
    animal_races = db.relationship('AnimalRace', back_populates='animal_category', lazy=True)
    animal_categorization = db.relationship('AnimalCategorization', back_populates='animal_category')


class AnimalCategorization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_category_id = db.Column(db.Integer, db.ForeignKey('animal_category.id'), nullable=False)
    subcategory = db.Column(db.String(500), nullable=False)
    intended_for = db.Column(db.String(20), nullable=False)  # tov/priplod
    min_weight = db.Column(db.Float, nullable=True)  # min tezina za podklasu tova
    max_weight = db.Column(db.Float, nullable=True)  # max tezina za podklasu tova
    min_weight_gain = db.Column(db.Float, nullable=True)  # min tezina za podklasu priplodova
    max_weight_gain = db.Column(db.Float, nullable=True)  # max tezina za podklasu priplodova
    fattening_price = db.Column(db.Float, nullable=True)  # cena za podklasu tova
    animals = db.relationship('Animal', back_populates='animal_categorization', lazy=True)
    animal_category = db.relationship('AnimalCategory', back_populates='animal_categorization')


class ProductCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_category_name = db.Column(db.String(50), nullable=False)
    products = db.relationship('Product', back_populates='product_category', lazy=True) #!


class ProductSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_section_name = db.Column(db.String(50), nullable=False)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    product_subcategory_id = db.Column(db.Integer, db.ForeignKey('product_subcategory.id'), nullable=False)
    products = db.relationship('Product', back_populates='product_section', lazy=True)
    product_categories = db.relationship('ProductCategory', backref='product_section_product_category', lazy=True)
    product_subcategory = db.relationship('ProductSubcategory', back_populates='product_sections') # Ovde dodajemo relaciju sa ProductSubcategory



class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    product_subcategory_id = db.Column(db.Integer, db.ForeignKey('product_subcategory.id'), nullable=False)
    product_section_id = db.Column(db.Integer, db.ForeignKey('product_section.id'), nullable=False)
    product_name = db.Column(db.String(50), nullable=False)
    product_description = db.Column(db.Text, nullable=False)
    product_image = db.Column(db.String(20), nullable=False, default='default.jpg')
    product_image_collection = db.Column(db.JSON, nullable=True)
    unit_of_measurement = db.Column(db.String(20), nullable=False)
    weight_conversion = db.Column(db.String(20), nullable=True)
    product_price_per_unit_farmer = db.Column(db.String(20), nullable=False) #! implementirati ovu izmenu u kodu i sql-u
    product_price_per_unit = db.Column(db.String(20), nullable=False)
    product_price_per_kg = db.Column(db.String(20), nullable=True)
    organic_product = db.Column(db.Boolean, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False)
    
    product_category = db.relationship('ProductCategory', back_populates='products')
    product_subcategory = db.relationship('ProductSubcategory', back_populates='products')
    product_section = db.relationship('ProductSection', back_populates='products')

class ProductSubcategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_subcategory_name = db.Column(db.String(50), nullable=False)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    products = db.relationship('Product', back_populates='product_subcategory')
    product_sections = db.relationship('ProductSection', back_populates='product_subcategory')



class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False)
    invoice_number = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #! kupac
    status = db.Column(db.String(20), nullable=False) #! unconfirmed, confirmed
    
    invoice_items = db.relationship('InvoiceItems', back_populates='invoice', lazy=True) #!
    animals = db.relationship('Animal', backref='animal_invoice', lazy=True)
    payspot_transactions = db.relationship('PaySpotTransaction', backref='invoice_payspot_transaction', lazy=True)


class InvoiceItems(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    invoice_item_details = db.Column(db.JSON, nullable=False)
    invoice_item_type = db.Column(db.Integer, nullable=False) #! 1 = product, 2 = animal, 3 = service, 4 = fattening
    # payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    # payments = db.relationship('Payment', backref='payment_invoice_items', lazy=True)
    # Dodajemo relationship sa Farm modelom
    farm = db.relationship('Farm', backref='invoice_items', lazy=True)
    # Existing relationships
    invoice = db.relationship('Invoice', back_populates='invoice_items', lazy=True)
    pass


class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_item_id = db.Column(db.Integer, db.ForeignKey('invoice_items.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False) #! pending, paid, overdue, canceled
    user = db.relationship('User', backref='debts', lazy=True)
    invoice_item = db.relationship('InvoiceItems', backref='debts', lazy=True)


class PaymentStatement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_date = db.Column(db.DateTime, nullable=False) #! izvlači iz XML fajla (<DatumIzvoda>20.05.2021</DatumIzvoda>)
    statement_number = db.Column(db.String(20), nullable=False) #! izvlači iz XML fajla (<BrojIzvoda>108</BrojIzvoda>)
    total_payment_amount = db.Column(db.Float, nullable=False) #! izvlači iz XML fajla (<IznosPotrazuje>40824,00</IznosPotrazuje>)
    number_of_items = db.Column(db.Integer, nullable=False) #! izvlači iz XML fajla (for loop bi trebalo da uradi routes.py)
    number_of_errors = db.Column(db.Integer, nullable=False)
    payments = db.relationship('Payment', backref='payment_statement_payment', lazy=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invoice_item_id = db.Column(db.Integer, db.ForeignKey('invoice_items.id'), nullable=False)
    payment_statement_id = db.Column(db.Integer, db.ForeignKey('payment_statement.id'), nullable=False)
    purpose_of_payment = db.Column(db.String(100), nullable=True) #! svrha uplate
    payer = db.Column(db.String(100), nullable=True) #! onaj koji je uplatio, podatak iz XML fajla za poređenje sa user_id ako treba
    reference_number = db.Column(db.String(100), nullable=True) #! poziv na broj
    payment_error = db.Column(db.Boolean, nullable=False)
    user = db.relationship('User', backref='payments', lazy=True)
    invoice_item = db.relationship('InvoiceItems', backref='payments', lazy=True)
    # payment_statement = db.relationship('PaymentStatement', backref='payments', lazy=True)


class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    answer = db.Column(db.String(500), nullable=False)


class PaySpotCallback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    recived_at = db.Column(db.DateTime, nullable=False)
    callback_data = db.Column(db.JSON, nullable=False)


class PaySpotTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    merchant_order_id = db.Column(db.String(50), nullable=False)
    payspot_group_id = db.Column(db.String(20), nullable=False)
    
    # Podaci specifični za pojedinačni nalog
    sequence_no = db.Column(db.Integer, nullable=False)
    merchant_order_reference = db.Column(db.String(50), nullable=False)
    payspot_transaction_id = db.Column(db.String(20), nullable=False)
    status_trans = db.Column(db.String(10), nullable=True)
    create_date = db.Column(db.String(10), nullable=True)
    create_time = db.Column(db.String(10), nullable=True)
    sender_fee = db.Column(db.Float, nullable=True)
    
    # Relacija
    invoice = db.relationship('Invoice', backref=db.backref('payspot_transactions', lazy=True))
    
    # Veza sa farmom
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=True)
    farm = db.relationship('Farm', backref=db.backref('payspot_transactions', lazy=True))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"PaySpotTransaction(id={self.id}, payspot_transaction_id={self.payspot_transaction_id})"


with app.app_context():
    print('models: checkopint -> posle ovog koda treba da se inicira db!!')
    db.create_all()