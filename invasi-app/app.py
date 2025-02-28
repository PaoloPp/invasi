import matplotlib
matplotlib.use('Agg')

from config import DevelopmentConfig, ProductionConfig
from extensions import db, login_manager
from flask import Flask
from flask_mail import Mail
from models import User
from blueprints.auth.routes import auth_bp
from blueprints.admin.routes import admin_bp
from blueprints.main.routes import main_bp


# Define user_loader outside create_app()
@login_manager.user_loader
def loader_user(user_id):
    return User.query.get(user_id)


def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = 'supersecretkey'

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(main_bp, url_prefix='/')

    mail = Mail(app)

    return app

##Debugging
#if __name__ == "__main__":
#    app = create_app()
#
#    # Only for initial setup (remove if using Flask-Migrate)
#    with app.app_context():
#        db.create_all()
#
#    app.run(debug=True)

# Production
if __name__ == "__main__":
    app = create_app()
    
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=8080, debug=True)