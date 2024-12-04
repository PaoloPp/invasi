from config import DevelopmentConfig, ProductionConfig
from extensions import db, login_manager
from flask import Flask
from flask_mail import Mail, Message
from models import User
from blueprints.auth.routes import auth_bp
from blueprints.admin.routes import admin_bp
from blueprints.main.routes import main_bp
import matplotlib


def create_app(config_class=DevelopmentConfig):

    matplotlib.use('Agg')

    @login_manager.user_loader
    def loader_user(user_id):
        return User.query.get(user_id)
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = 'supersecretkey'

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(main_bp)
    
    mail = Mail(app)
    
    with app.app_context():
        db.create_all()
    
    return app


if __name__ == "__main__":
    ##db.init_app(app)
    ##with app.app_context():
    ##    db.create_all()
    ###app.run(host="0.0.0.0", debug=False)
    ##app.run(debug=True)
    app = create_app()
    app.run(debug=True)
