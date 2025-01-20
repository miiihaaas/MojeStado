from flask import Blueprint, render_template
from mojestado import db, app


errors = Blueprint('errors', __name__)


@errors.app_errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'404 Error: Stranica nije pronađena - {error}')
    return render_template('errors/404.html'), 404

@errors.app_errorhandler(403)
def forbidden_error(error):
    app.logger.warning(f'403 Error: Zabranjen pristup - {error}')
    return render_template('errors/403.html'), 403

@errors.app_errorhandler(500)
def internal_error(error):
    app.logger.error(f'500 Error: Interna greška servera - {error}')
    db.session.rollback()
    return render_template('errors/500.html'), 500

@errors.app_errorhandler(400)
def bad_request_error(error):
    app.logger.warning(f'400 Error: Neispravan zahtev - {error}')
    return render_template('errors/400.html'), 400