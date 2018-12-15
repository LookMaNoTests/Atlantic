"""A simple Flask web server."""

from contextlib import contextmanager
from flask import Flask, request
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

def update_customer(db, row):
    cust_insert = '''
        INSERT INTO customers (
            customer_id,
            customer_first_name,
            customer_last_name,
            customer_address,
            customer_state,
            customer_zip_code)
        VALUES
            (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            customer_address=VALUES(customer_address),
            customer_state=VALUES(customer_state),
            customer_zip_code=VALUES(customer_zip_code);'''
    cursor = db.cursor()
    cursor.execute(cust_insert, row[:6])

def update_product(db, row):
    prod_insert = '''
        INSERT IGNORE INTO products (
            product_id,
            product_name)
        VALUES
            (%s, %s);'''
    cursor = db.cursor()
    cursor.execute(prod_insert, row[7:9])

@app.route('/purchases', methods=['POST'])
def update_subscriptions():
    with subscriptions() as db:
        body = request.get_data(as_text=True)
        for line in body.split('\n'):
            if line:  # Trailing newline...
                row = line.replace('\r', '').split('\t')
                update_customer(db, row)
                update_product(db, row)
                # ...
                db.commit()
        return ('', 200)

if __name__ == '__main__':
    app.run(port=8080)

