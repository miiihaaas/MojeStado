from mojestado.transactions.functions import calculate_hash
import os

order_id = input("Unesite orderID: ")
shop_id = input("Unesite shopID: ")
amount = input("Unesite amount: ")
result = '00'
secret_key = os.environ.get('PAYSPOT_SECRET_KEY_CALLBACK')


plaintext = f"{order_id}|{shop_id}|{amount}|{result}|{secret_key}"
hash_for_callback = calculate_hash(plaintext)
print(f'hash_for_callback: {hash_for_callback}')