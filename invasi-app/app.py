import matplotlib
matplotlib.use('Agg')
import os


from config import DevelopmentConfig, ProductionConfig
from extensions import db, login_manager
from flask import Flask
from flask_mail import Mail
from flask_migrate import Migrate
from models import User, PastExchange, JsonFile
from blueprints.auth.routes import auth_bp
from blueprints.admin.routes import admin_bp
from blueprints.main.routes import main_bp


# Define user_loader outside create_app()
@login_manager.user_loader
def loader_user(user_id):
    return User.query.get(user_id)


def create_app(config_class=DevelopmentConfig):
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)

    app.config.from_object(config_class)
    

    db_path = os.path.join(app.instance_path, 'invasi.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.secret_key = 'supersecretkey'

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(main_bp, url_prefix='/')

    mail = Mail(app)
    # Initialize Flask-Migrate with a custom migrations directory if needed
    migrate = Migrate(app, db, directory=os.path.join(app.instance_path, 'migrations'))


    return app

#Debugging
if __name__ == "__main__":
    app = create_app()

    app.run(debug=True)

# Production
#if __name__ == "__main__":
#    app = create_app()
#
#    app.run(host="0.0.0.0", port=8080, debug=True)