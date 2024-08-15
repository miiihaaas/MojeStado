from mojestado import app, db, login_manager
from flask_login import UserMixin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer


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
    PBG = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    JMBG = db.Column(db.String(13), unique=True, nullable=True)
    MB = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    user_type = db.Column(db.String(20), nullable=False) #! postoje tipovi: admin, farm_active, farm_inactive, user, user_removed, guest(onaj koji je kupio a da nije napravio nalog: bitni su nam email, telefon, ime i prezime + ostalo)
    registration_date = db.Column(db.DateTime, nullable=False)
    farms = db.relationship('Farm', backref='user_farm', lazy=True) #! 
    

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
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
    farm_description = db.Column(db.String(2000), nullable=False)
    services = db.Column(db.JSON, nullable=True) #! usluga klanja, usluga obrade - tu treba da se definišu cene usluga za kategorije
    registration_date = db.Column(db.Date, nullable=True) #! kada admin potvrdi da je registrovan, tada se dodeli trenutni datum
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #!
    animals = db.relationship('Animal', backref='farm_animal', lazy=True) #!
    products = db.relationship('Product', backref='farm_product', lazy=True) #!


class Animal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.String(15), nullable=False)  # Svako grlo stoke odnosno živine ima minđušu odnosno nanogicu. Na minđuši je ispisan jedinstveni broj koji se sastoji od dva bloka cifara. Prvi petocifreni blok označava PG, a drugi petocifreni ili šestocifreni broj označava redni broj grla.
    animal_category_id = db.Column(db.Integer, db.ForeignKey('animal_category.id'), nullable=False)
    animal_categorization_id = db.Column(db.Integer, db.ForeignKey('animal_categorization.id'), nullable=False)
    animal_race_id = db.Column(db.Integer, db.ForeignKey('animal_race.id'), nullable=False)

    animal_gender = db.Column(db.String(20), nullable=False)  # pol
    measured_weight = db.Column(db.String(20), nullable=False)  # izmerena težina
    measured_date = db.Column(db.String(20), nullable=False)  # datum merenja
    current_weight = db.Column(db.String(20), nullable=False)  # trenutna težina = preračunava se u odnosu na izmerenu težinu i datum merenja
    wanted_weight = db.Column(db.String(20), nullable=True)  # zeljena težina
    price_per_kg = db.Column(db.String(20), nullable=False)  # cena po kg
    total_price = db.Column(db.String(20), nullable=False)  # ukupna cena
    insured = db.Column(db.Boolean, nullable=False)  # osigurano
    organic_animal = db.Column(db.Boolean, nullable=False)  # organska proizvodnja
    cardboard = db.Column(db.String(50), nullable=True)  # karton grla/životinje
    intended_for = db.Column(db.String(20), nullable=False)  # tov/priplod
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False)
    
    fattening = db.Column(db.Boolean, nullable=False) #! podrazumevana vrednost je False, a kada kupac naruči da se tovi neka životnja onda prelazi u True
    active = db.Column(db.Boolean, nullable=False)

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


class AnimalCategorization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_category_id = db.Column(db.Integer, db.ForeignKey('animal_category.id'), nullable=False)
    subcategory = db.Column(db.String(500), nullable=False)
    intended_for = db.Column(db.String(20), nullable=False)  # tov/priplod
    min_weight = db.Column(db.Float, nullable=True)  # min tezina za podklasu tova
    max_weight = db.Column(db.Float, nullable=True)  # max tezina za podklasu tova
    min_weight_gain = db.Column(db.Float, nullable=True)  # min tezina za podklasu priplodova
    max_weight_gain = db.Column(db.Float, nullable=True)  # max tezina za podklasu priplodova
    fattening_price = db.Column(db.Float, nullable=False)  # cena za podklasu tova
    animals = db.relationship('Animal', back_populates='animal_categorization', lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False) #!
    product_subcategory_id = db.Column(db.Integer, db.ForeignKey('product_subcategory.id'), nullable=False) #!
    product_section_id = db.Column(db.Integer, db.ForeignKey('product_section.id'), nullable=False) #!
    product_name = db.Column(db.String(50), nullable=False)
    product_description = db.Column(db.String(500), nullable=False)
    product_image = db.Column(db.String(20), nullable=False, default='default.jpg') #! prilagoditi da može da se stavi do 10 slika
    product_image_collection = db.Column(db.JSON, nullable=True)
    #! razraditi konverziju pakovanje (npr kajmak 1kom = 400g)
    unit_of_measurement = db.Column(db.String(20), nullable=False) #! jedinica mere može da bude KOM ili KG
    weight_conversion = db.Column(db.String(20), nullable=True) #! ako je kom onda mora da se definiše koliko 1kom ima kg
    #! ako je kg onda je polje konverzije prazno ili je =1
    product_price_per_unit = db.Column(db.String(20), nullable=False) #! da li da se ovo polje preračuna u odnosu na input vrednosti kom, konverzija?
    product_price_per_kg = db.Column(db.String(20), nullable=True) #! ako je jedinica mere kg, onda se prepisuje taj podatak, a ako je jedinica mere kom onda se uz pomoć podatka weight_conversion izracunava te vrednosti
    organic_product = db.Column(db.Boolean, nullable=False) #! organska proizvodnja
    #! dodati količinu/masu
    quantity = db.Column(db.String(20), nullable=False) #! količina/masa
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False) #!
    
    product_category = db.relationship('ProductCategory', back_populates='products')
    product_subcategories = db.relationship('ProductSubcategory', back_populates='products')
    product_section = db.relationship('ProductSection', back_populates='products')


class ProductCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_category_name = db.Column(db.String(50), nullable=False)
    products = db.relationship('Product', back_populates='product_category', lazy=True) #!


class ProductSubcategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_subcategory_name = db.Column(db.String(50), nullable=False)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    product_categories = db.relationship('ProductCategory', backref='product_subcategory_product_category', lazy=True) #!
    products = db.relationship('Product', backref='product_subcategory_product', lazy=True) #!
    product_sections = db.relationship('ProductSection', back_populates='product_subcategory', lazy=True)


class ProductSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_section_name = db.Column(db.String(20), nullable=False)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False)
    product_subcategory_id = db.Column(db.Integer, db.ForeignKey('product_subcategory.id'), nullable=False)
    products = db.relationship('Product', back_populates='product_section', lazy=True)
    product_categories = db.relationship('ProductCategory', backref='product_section_product_category', lazy=True)
    product_subcategory = db.relationship('ProductSubcategory', back_populates='product_sections') # Ovde dodajemo relaciju sa ProductSubcategory



class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    datetime = db.Column(db.DateTime, nullable=False)
    invoice_number = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #! kupac
    status = db.Column(db.String(20), nullable=False) #! unconfirmed, confirmed
    
    invoice_items = db.relationship('InvoiceItems', backref='invoice_items_invoice', lazy=True) #!
    pass


# class Payment(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     transactions = db.relationship('Transaction', backref='transaction_payment', lazy=True) #!
#     pass


class InvoiceItems(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    invoice_item_details = db.Column(db.String(200), nullable=False)
    invoice_item_type = db.Column(db.Integer, nullable=False) #! 1 = product, 2 = animal, 3 = service, 4 = fattening
    # payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    pass


class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    answer = db.Column(db.String(200), nullable=False)


class PaySpotCallback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    recived_at = db.Column(db.DateTime, nullable=False)
    callback_data = db.Column(db.JSON, nullable=False)


with app.app_context():
    print('models: checkopint -> posle ovog koda treba da se inicira db!!')
    db.create_all()