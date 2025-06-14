from ..celery_app import celery
from .. import db
from ..models import Animal, AnimalCategorization
from datetime import datetime
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@celery.task(name='mojestado.animals.tasks.daily_weight_gain_task')
def daily_weight_gain_task():
    try:
        logger.info(f"============ POČETAK ZADATKA - {datetime.now()} ============")

        # Procesiranje životinja u grupama od 100 za bolje performanse
        page = 0
        per_page = 100
        total_processed = 0
        
        while True:
            animals = Animal.query.filter(
                Animal.active == True
            ).limit(per_page).offset(page * per_page).all()
            
            if not animals:
                break
                
            for animal in animals:
                try:
                    animal_id = animal.id
                    current_weight = float(animal.current_weight)
                    logger.info(f"Obrađujem životinju ID:{animal_id} - Trenutna težina: {current_weight} kg.")
                    
                    # Provera da li je životinja već van opsega TRENUTNE kategorije
                    if animal.animal_categorization and current_weight > animal.animal_categorization.max_weight:
                        # Prvo prebaci u odgovarajuću kategoriju PRE računanja prirasta
                        correct_category = AnimalCategorization.query.filter(
                            AnimalCategorization.animal_category_id == animal.animal_category_id,
                            AnimalCategorization.intended_for == animal.intended_for,
                            AnimalCategorization.min_weight <= current_weight,  # Trenutna težina je u opsegu
                            AnimalCategorization.max_weight >= current_weight   # Trenutna težina je u opsegu
                        ).first()
                        
                        if correct_category:
                            prev_category_id = animal.animal_categorization_id if animal.animal_categorization_id else 'Nema'
                            animal.animal_categorization_id = correct_category.id
                            animal.animal_categorization = correct_category  # Ažuriraj i objekat
                            logger.info(f"Životinja ID:{animal_id} - Korekcija kategorije pre prirasta: {prev_category_id} -> {correct_category.id} (težina {current_weight} kg).")

                    # Sada računaj prirast sa ISPRAVNOM kategorijom
                    if animal.animal_categorization and animal.animal_categorization.min_weight >= 0:
                        avg_gain = (animal.animal_categorization.min_weight_gain + 
                                    animal.animal_categorization.max_weight_gain) / 2
                        new_weight = round(current_weight + avg_gain, 2)
                        old_price = animal.total_price
                        animal.current_weight = str(new_weight)
                        animal.total_price = round(new_weight * float(animal.price_per_kg), 2)
                        logger.info(f"Životinja ID:{animal_id} - Prirast: {current_weight} kg -> {new_weight} kg (prirast {avg_gain} kg).")
                        logger.info(f"Životinja ID:{animal_id} - Cena: {old_price} -> {animal.total_price} ({animal.price_per_kg} po kg).")
                        
                        # Provera za prelazak u SLEDEĆU kategoriju nakon prirasta
                        if new_weight > animal.animal_categorization.max_weight:
                            next_category = AnimalCategorization.query.filter(
                                AnimalCategorization.animal_category_id == animal.animal_category_id,
                                AnimalCategorization.intended_for == animal.intended_for,
                                AnimalCategorization.min_weight >= animal.animal_categorization.max_weight  # >= umesto >
                            ).order_by(AnimalCategorization.min_weight).first()
                            
                            if next_category:
                                prev_category_id = animal.animal_categorization_id
                                animal.animal_categorization_id = next_category.id
                                logger.info(f"Životinja ID:{animal_id} - Prelazak u novu kategoriju nakon prirasta: {prev_category_id} -> {next_category.id} (nova težina {new_weight} kg).")
                    
                    total_processed += 1
                
                except (ValueError, AttributeError) as e:
                    logger.error(f"Greška pri obradi životinje ID:{animal.id} - {str(e)}")
                    continue
            
            db.session.commit()  # Commit nakon svake grupe
            page += 1
            
        msg = f"Uspešno ažurirano {total_processed} životinja u {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info(msg)
        logger.info(f"============ KRAJ ZADATKA - {datetime.now()} ============")
        return msg
            
    except Exception as e:
        error_msg = f"Došlo je do greške: {str(e)}"
        logger.error(error_msg)
        logger.error(f"============ ZADATAK PREKINUT SA GREŠKOM - {datetime.now()} ============")
        db.session.rollback()
        return error_msg