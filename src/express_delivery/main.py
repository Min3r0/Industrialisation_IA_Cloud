"""Point d'entrée : uvicorn express_delivery.main:app"""
import logging

from express_delivery.api.app import create_app

logging.basicConfig(level=logging.INFO)
app = create_app()
