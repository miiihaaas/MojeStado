from ..celery_app import celery
from .. import db
from ..models import Animal, AnimalCategorization
from datetime import datetime
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@celery.task(name='mojestado.animals.tasks.daily_weight_gain_task')
def daily_weight_gain_task():
    try:
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
                    current_weight = float(animal.current_weight)
                    
                    # Provera željene težine samo za životinje u tovu
                    if animal.intended_for == "tov" and animal.fattening and animal.wanted_weight and current_weight >= float(animal.wanted_weight):
                        logger.info(f'ID:{animal.id} - Životinja je postigla željenu masu od {animal.wanted_weight}kg!')
                        continue
                    
                    # Provera kategorije i računanje prirasta za sve životinje
                    if animal.animal_categorization and animal.animal_categorization.min_weight >= 0:
                        avg_gain = (animal.animal_categorization.min_weight_gain + animal.animal_categorization.max_weight_gain) / 2
                        new_weight = round(current_weight + avg_gain, 2)  # zaokružujemo na 2 decimale
                        animal.current_weight = str(new_weight)
                        # Računamo total_price i zaokružujemo na 2 decimale jer je reč o novcu
                        animal.total_price = round(new_weight * float(animal.price_per_kg), 2)
                        
                        # Provera za prelazak u sledeću kategoriju
                        if new_weight > animal.animal_categorization.max_weight:
                            # Tražimo sledeću kategoriju koja pripada istom tipu životinje
                            next_category = AnimalCategorization.query.filter(
                                AnimalCategorization.animal_category_id == animal.animal_category_id,
                                AnimalCategorization.intended_for == animal.intended_for,
                                AnimalCategorization.min_weight > animal.animal_categorization.max_weight
                            ).order_by(AnimalCategorization.min_weight).first()
                            
                            if next_category:
                                animal.animal_categorization_id = next_category.id
                    
                    total_processed += 1
                
                except (ValueError, AttributeError) as e:
                    logger.error(f"Greška pri obradi životinje ID:{animal.id} - {str(e)}")
                    continue
            
            db.session.commit()  # Commit nakon svake grupe
            page += 1
            
        msg = f"Uspešno ažurirano {total_processed} životinja u {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info(msg)
        return msg
            
    except Exception as e:
        error_msg = f"Došlo je do greške: {str(e)}"
        logger.error(error_msg)
        db.session.rollback()
        return error_msg