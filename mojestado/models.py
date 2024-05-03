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
    password = db.Column(db.String(60), nullable=False)
    name = db.Column(db.String(20), unique=False, nullable=False)
    surname = db.Column(db.String(20), unique=False, nullable=False)
    address = db.Column(db.String(20), unique=False, nullable=False)
    city = db.Column(db.String(20), unique=False, nullable=False)
    zip_code = db.Column(db.String(5), unique=False, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False) #! samo za farm
    PBG = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    JMBG = db.Column(db.String(13), unique=True, nullable=True)
    MB = db.Column(db.String(20), unique=True, nullable=True) #! samo za farm
    user_type = db.Column(db.String(20), nullable=False) #! postoje tipovi: admin, farm, user, guest(onaj koji je kupio a da nije napravio nalog: bitni su nam email, telefon, ime i prezime + ostalo)
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
    farm_name = db.Column(db.String(20), nullable=False)
    farm_address = db.Column(db.String(20), nullable=False)
    farm_city = db.Column(db.String(20), nullable=False)
    farm_zip_code = db.Column(db.String(5), nullable=False)
    farm_municipality_id = db.Column(db.Integer, db.ForeignKey('municipality.id'), nullable=False) #!
    farm_phone = db.Column(db.String(20), nullable=False)
    farm_description = db.Column(db.String(2000), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #!
    animals = db.relationship('Animal', backref='farm_animal', lazy=True) #!
    products = db.relationship('Product', backref='farm_product', lazy=True) #!


class Animal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.String(12), nullable=False) #! Svako grlo stoke odnosno živine ima minđušu odnosno nanogicu. Na minđuši je ispisan jedinstveni broj koji se sastoji od dva bloka cifara. Prvi petocifreni blok označava PG, a drugi petocifreni ili šestocifreni broj označava redni broj grla.
    animal_category_id = db.Column(db.Integer, db.ForeignKey('animal_category.id'), nullable=False) #!
    animal_gender = db.Column(db.String(20), nullable=False) #! pol
    measured_weight = db.Column(db.String(20), nullable=False) #! izmerena težina
    measured_date = db.Column(db.String(20), nullable=False) #! datum merenja
    current_weight = db.Column(db.String(20), nullable=False) #! trenutna težina = preračunava se u odnosu na izmerenu težinu i datum merenja
    price_per_kg = db.Column(db.String(20), nullable=False) #! cena po kg
    total_price = db.Column(db.String(20), nullable=False) #! ukupna cena
    insured = db.Column(db.Boolean, nullable=False) #! osigurano
    organic_animal = db.Column(db.Boolean, nullable=False) #! organska proizvodnja
    cardboard = db.Column(db.String(50), nullable=False) #! karton grla/životinje
    fattening = db.Column(db.Boolean, nullable=False) #! tov: true/false
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False) #!


class AnimalCategory (db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_category_name = db.Column(db.String(20), nullable=False)
    animal_subcategory_id = db.Column(db.Integer, db.ForeignKey('animal_subcategory.id'), nullable=False) #!
    animal_race_id = db.Column(db.Integer, db.ForeignKey('animal_race.id'), nullable=False) #!
    animals = db.relationship('Animal', backref='animal_category', lazy=True) #!
    pass


class AnimalSubcategory (db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_subcategory_name = db.Column(db.String(20), nullable=False)
    animal_categories = db.relationship('AnimalCategory', backref='animal_subcategory_animal_category', lazy=True) 
    #! ovde treba dodati kolone za priraštaj mase za tov (min/max) i težina (od-do)
    pass


class AnimalRace (db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_race_name = db.Column(db.String(20), nullable=False)
    animals = db.relationship('AnimalCategory', backref='animal_race_animal_category', lazy=True) #!
    pass


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_image = db.Column(db.String(20), nullable=False) #! slika proizvoda
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'), nullable=False) #!
    product_name = db.Column(db.String(20), nullable=False)
    product_price_per_kg = db.Column(db.String(20), nullable=False) #! da li da se ovo polje preračuna u odnosu na input vrednosti kom, konverzija?
    #! razraditi konverziju pakovanje (npr kajmak 1kom = 400g)
    unite_of_measurement = db.Column(db.String(20), nullable=False) #! jedinica mere može da bude kom ili kg
    #! ako je kom onda mora da se definiše koliko 1kom ima kg
    #! ako je kg onda je polje konverzije prazno
    organic_product = db.Column(db.Boolean, nullable=False) #! organska proizvodnja
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'), nullable=False) #!


class ProductCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_subcategory_id = db.Column(db.Integer, db.ForeignKey('product_subcategory.id'), nullable=False) #!
    products = db.relationship('Product', backref='product_category_product', lazy=True) #!
    pass


class ProductSubcategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_categories = db.relationship('ProductCategory', backref='product_subcategory_product_category', lazy=True) #!
    pass


class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transactions = db.relationship('Transaction', backref='transaction_debt', lazy=True) #!
    pass


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transactions = db.relationship('Transaction', backref='transaction_payment', lazy=True) #!
    pass


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    debt_id = db.Column(db.Integer, db.ForeignKey('debt.id'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    pass


class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    answer = db.Column(db.String(200), nullable=False)


with app.app_context():
    print('models: checkopint -> posle ovog koda treba da se inicira db!!')
    db.create_all()