from datetime import datetime
from mojestado import db, app
from mojestado.models import Animal, AnimalCategorization


def get_animal_categorization(category: str, intended_for: str, weight: float, subcategory: str = None) -> dict:
    categories = AnimalCategorization.query.filter_by(
        animal_category_id=category,
        intended_for=intended_for
    ).all()
    if intended_for == 'tov':
        print(f'{weight=}; {type(weight)=}')
        print(f'treba da odredi podkategoriju tova na osnovu tezine: {weight}')
        for category in categories:
            if category.min_weight <= weight <= category.max_weight:
                return category.id
    else:
        print(f'izabrana podkategorija je { subcategory= }')
        for category in categories:
            if category.subcategory == subcategory:
                return category.id


def calculate_number_and_price_of_fattening_days(animal):
    current_weight = float(animal.current_weight)
    wanted_weight = animal.wanted_weight
    
    print(f'{current_weight=}; {wanted_weight=}')
    print(f'{animal}')
    
    calculated_weight = current_weight
    number_of_fattening_days = 0
    fattening_price = 0
    
    categorization_id = animal.animal_categorization_id
    print(f'{categorization_id=}')
    categorization = AnimalCategorization.query.get(categorization_id)
    print(f'{categorization.min_weight=}')
    
    stop_fattening = False  # Privremeni marker za prekidanje spoljašnje petlje
    
    while categorization and categorization.min_weight is not None:
        while calculated_weight < categorization.max_weight:
            average_weight_gain = (categorization.min_weight_gain + categorization.max_weight_gain) / 2
            calculated_weight += average_weight_gain
            if calculated_weight > wanted_weight:
                stop_fattening = True  # Postavite marker za prekid spoljašnje petlje
                break  # Prekid unutrašnje petlje
            number_of_fattening_days += 1
            fattening_price += categorization.fattening_price
        if stop_fattening:
            break  # Prekid spoljašnje petlje
        categorization_id += 1
        categorization = AnimalCategorization.query.get(categorization_id)

    return number_of_fattening_days, fattening_price



def daily_weight_gain():
    with app.app_context():
        try:
            animals = Animal.query.filter(
                (Animal.active == True) | (Animal.fattening == True),
                Animal.intended_for == "tov"
            ).all()
            
            for animal in animals:
                try:
                    current_weight = float(animal.current_weight)
                    
                    # Provera da li je životinja dostigla željenu težinu
                    if animal.fattening and current_weight >= float(animal.wanted_weight):
                        print(f'ID:{animal.id} - Životinja je postigla željenu masu od {animal.wanted_weight}kg!')
                        # Ovde bi trebalo dodati logiku za obaveštavanje (email, notification, itd.)
                        continue
                    
                    # Provera kategorije i računanje prirasta
                    if animal.animal_categorization and animal.animal_categorization.min_weight >= 0:
                        avg_gain = (animal.animal_categorization.min_weight_gain + animal.animal_categorization.max_weight_gain) / 2
                        new_weight = current_weight + avg_gain
                        animal.current_weight = str(new_weight)
                        
                        # Provera za prelazak u sledeću kategoriju
                        if new_weight > animal.animal_categorization.max_weight:
                            next_category = AnimalCategorization.query.get(animal.animal_categorization_id + 1)
                            if next_category:
                                animal.animal_categorization_id = next_category.id
                                if next_category.intended_for == 'priplod':
                                    animal.intended_for = 'priplod'
                
                except (ValueError, AttributeError) as e:
                    print(f"Greška pri obradi životinje ID:{animal.id} - {str(e)}")
                    continue
            
            db.session.commit()
            print(f"Weight update executed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            db.session.rollback()
            print(f"Došlo je do greške: {str(e)}")


def schedule_daily_weight_gain(scheduler):
    # @scheduler.task('interval', id='daily_weight_update', seconds=10) #! služi za testiranje, na svakih 10s je novi dan
    @scheduler.task('cron', id='daily_weight_update', hour=1) #! svakim danom u 1AM uveća masu životinja za tov
    def scheduled_daily_weight_gain():
        daily_weight_gain()