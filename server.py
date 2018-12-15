"""A simple Flask web server."""

from contextlib import contextmanager
from dateutil.parser import parse
from flask import Flask, request, Response
from json import dumps
from mysql.connector import connect
from sys import exc_info

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

class UnknownSubscription(Exception):
    """We cancelled a nonexistent subscription!"""
    pass

class UnrecognizedPurchase(Exception):
    """Purchase status not one of: (canceled, new)!"""
    pass

def update_subscribers(db, row):
    status, cust, prod = row[6], row[0], row[7]
    if status == 'new':
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
    elif status == 'canceled':
        sub_update = '''
            DELETE FROM subscribers
            WHERE
                customer_id = %s AND product_id = %s;'''
        delete = db.cursor()
        delete.execute(sub_update, (cust, prod))
        if not delete.rowcount:
            raise UnknownSubscription()
    else:
        raise UnrecognizedPurchase(status)

class MissingOrderFields(Exception):
    """We received an ambiguous input!"""
    pass

@app.route('/purchases', methods=['POST'])
def update_subscriptions():
    with subscriptions() as db:
        errors = []
        body = request.get_data(as_text=True)
        i = 0
        for line in body.split('\n'):
            i += 1
            if line:  # Trailing newline...
                row = line.replace('\r', '').split('\t')
                row = [col if col else None for col in row]  # No ''!
                try:
                    if len(row) != 11:
                        raise MissingOrderFields()
                    update_customer(db, row)
                    update_product(db, row)
                    update_subscribers(db, row)
                    db.commit()
                except:
                    db.rollback()
                    e_type, _, __ = exc_info()
                    errors.append({
                        'line': i,
                        'row': row,
                        'err': e_type.__name__
                        })
        if not errors:
            return ('', 200)
        else:
            return Response(
                status=400,
                content_type='application/json',
                response=dumps(errors))

if __name__ == '__main__':
    app.run(port=8080)

