from flask import Flask, redirect, url_for, session
from config import Config
from db import init_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_db()

    from auth import auth_bp
    from survey import survey_bp
    from fill import fill_bp
    from stats import stats_bp
    from question_library import question_library_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(survey_bp)
    app.register_blueprint(fill_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(question_library_bp)

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('survey.dashboard'))
        return redirect(url_for('auth.login'))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
