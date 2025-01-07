from flask import Flask
from weather.routers import weather_bp


def create_app():
    """App factory."""

    app = Flask(__name__)
    app.register_blueprint(weather_bp)

    return app