"""A simple Flask web server."""

from contextlib import contextmanager
from dateutil.parser import parse
from flask import Flask, request, Response
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

def update_subscribers(db, row):
    mode, cust, prod = row[6], row[0], row[7]
    if mode == 'new':
        sub_insert = '''
            INSERT INTO subscribers (
                customer_id,
                product_id,
                subscription_date,
                subscription_price)
            VALUES
                (%s, %s, %s, %s);'''
        price, date = row[-2], parse(row[-1])
        db.cursor().execute(sub_insert, (cust, prod, date, price))
    elif mode == 'canceled':
        sub_update = '''
            DELETE FROM subscribers
            WHERE
                customer_id = %s AND product_id = %s;'''
        db.cursor().execute(sub_update, (cust, prod))
    else:
        return Response(400)

@app.route('/purchases', methods=['POST'])
def update_subscriptions():
    with subscriptions() as db:
        body = request.get_data(as_text=True)
        for line in body.split('\n'):
            if line:  # Trailing newline...
                row = line.replace('\r', '').split('\t')
                row = [col if col else None for col in row]  # No ''!
                update_customer(db, row)
                update_product(db, row)
                update_subscribers(db, row)
                db.commit()
        return ('', 200)

if __name__ == '__main__':
    app.run(port=8080)

