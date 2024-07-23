from flask import session


def clear_cart_session():
    session.pop('animals', None)
    session.pop('products', None)