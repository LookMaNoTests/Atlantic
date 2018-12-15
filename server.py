"""A simple Flask web server."""

from contextlib import contextmanager
from flask import Flask
from mysql.connector import connect

@contextmanager
def subscriptions():
    db = None
    try:
        db = connect(
            host='localhost',
            user='atlantic',
            password='atlantic',
            database='subscriptions')
        yield db
    finally:
        if db:
            db.close()

app = Flask(__name__)

@app.route('/purchases', methods=['POST'])
def update_subscriptions():
    pass

