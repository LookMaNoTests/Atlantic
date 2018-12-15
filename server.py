"""A simple Flask web server."""

from contextlib import contextmanager
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

