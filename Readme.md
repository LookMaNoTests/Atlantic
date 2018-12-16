## Introduction

This code was written and tested on a t2.micro EC2 instance, running Ubuntu
Server 18.04 LTS. It is implemented in Python 3.6.7, with a small but ultimately
necessary list of open-source dependencies. The database is MySQL 5.7.24, and
I use features specific to that DBMS.

This is a pretty comprehensive coding exercise, involving a database, web
server, some ETL, etc. I made a conscious decision to jettison some of the
"extra point" features in order to to focus on a sane, relatively normalized
database design; I'm only somewhat satisfied with the final result and in any
case it was challenging to implement completely in the allotted time. If you're
getting candidates who, in earnest, are implementing a web server, a database,
authentication, authorization, a progress bar, and unit tests in <=2 hours, then
that's genuinely impressive and you should probably consider hiring them.

I will delete this repository after the code is adjudicated so as to maintain
the secrecy of the exercise.

## Initializing the OS

I assume you are working with a relatively unpolluted Debian derivative, like
Ubuntu. You should already have Python 3. Check with:

```bash
python3 --version
```

And, of course, there are some dependencies that you must install:

```bash
sudo apt-get install mysql-server
sudo apt-get install python3-pip
sudo pip3 install mysql-connector
sudo pip3 install python-dateutil
sudo pip3 install flask
```

I'm using raw Python (i.e. pip) here instead of, say, Anaconda, since it is not
possible to install the latter via the OS package manager. But of course, you
can get Python and the above dependencies by whatever means you like.

## Initializing the Database

It is important that you follow these instructions entirely, to the letter; I
flagrantly hardcode databases, tables, and columns in the code. (Obviously this
is not something I would do quite as liberally in production.) Launch `mysql` as
root:

```bash
sudo mysql
```

First, create the database:

```sql
CREATE DATABASE subscriptions;
USE subscriptions;
```

Then create the `customers` table:

```sql
CREATE TABLE customers (
    customer_id INT NOT NULL PRIMARY KEY,
    customer_first_name TEXT NOT NULL,
    customer_last_name TEXT NOT NULL,
    customer_address TEXT NOT NULL,
    customer_state CHAR(2) NOT NULL,
    customer_zip_code CHAR(5) NOT NULL
);
```

Then the `products` table:

```sql
CREATE TABLE products (
    product_id INT NOT NULL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL
);
```

And, lastly, the `subscribers` table:

```sql
CREATE TABLE subscribers (
    customer_id INT NOT NULL,
    product_id INT NOT NULL,
    subscription_date DATETIME NOT NULL,
    subscription_price FLOAT NOT NULL,
    PRIMARY KEY (customer_id, product_id),
    CONSTRAINT FK_Customers_CustomerId
        FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id),
    CONSTRAINT FK_Products_ProductId
        FOREIGN KEY (product_id)
        REFERENCES products (product_id)
);
```

I always find it frustrating using the default "root" account, especially
programmatically, so I create a dummy user account. And I hardcode it! So you
have to also:

```sql
CREATE USER atlantic@localhost IDENTIFIED by 'atlantic';
GRANT ALL PRIVILEGES ON subscriptions.* TO atlantic@localhost;
FLUSH PRIVILEGES; -- Not sure what this does...
quit;
```

This is a user account with bone-dumb credentials: atlantic/atlantic. Like:

```bash
mysql -u atlantic -p subscriptions
Enter password: atlantic
```

Wonderful!

## Running the code

Run the Flask server:

```bash
python3 server.py
```

This will launch a server on port 8080, so you can't have anything occupying
that port. (No, I didn't make this configurable. Yes, I should have.) The
challenge description stipulates that we should upload a tab-delimited file via
an input form, but I was not able to implement this (admittedly simple) HTML in
the allotted time. So instead, you will have to test my code by POSTing data
directly to it:

```bash
curl -XPOST --data-binary @purchases.txt http://localhost:8080/purchases
```

Here it is assumed that `purchases.txt` contains exactly the expected input
format: a tab-delimited file separated by newlines. (Note the `--data-binary`
flag, which preserves newlines in the input!) I delete carriage returns
explicitly in my code, so it should be safe if you are mocking up purchase files
on Windows.

## Implementation

    - customers
        |- customer_id (PK) ---+
        |- customer_first_name |
        |- customer_last_name  |
        |- customer_address    |
        |- customer_state      |
        +- customer_zip_code   |
                               |
     - products                |  - subscribers
        |- product_id (PK) ----|--->  |- product_id (CK)
        +- product_name        +--->  |- customer_id (CK)
                                      |- subscription_date
                                      +- subscription_price

## Expectations

I process each line of input and, for each, modify three tables in one
transaction:

1. I insert all of the customer information into the `customers` table. I allow
an existing row in the table to be "overwritten", e.g. with a change of address.
(This would be quite a bit more difficult had I not isolated customers in their
own table. I'm still not convinced it's fully normalized, but it's good enough
for this exercise.)
2. I insert all of the product information into the `products` table. No updates
here; it's a bug if the user tries to associate an existing id with a new
product name.
3. I branch on the "purchase status":
    1. If new, I insert a new row into the `subscribers` table, associating a
    customer and a product with a purchase price and date. Interestingly, I
    don't allow an existing (customer, product) pair to be overwritten. This is
    an implementation detail; it could just have easily been implemented the
    opposite way. In fact, it may be more intuitive. Suppose, for example, that
    a user is on the receiving end of a customer loyalty discount. This would
    probably arrive at our system as a new order with a different price than the
    existing price. But my code forbids this. No matter, this is an edge case;
    the challenge description doesn't have much to say about it.
    2. If canceled, I delete the existing row for this (customer, product) pair
    from the `subscribers` table. If it doesn't exist, I raise an exception.

If there is an error processing a row, I rollback the transaction for that row,
and append an "error frame" onto the end of a Python list. If there are no
errors, I return an empty 200 response; if there are errors, I return a 400
response with the errors dumped in the JSON body. It is important to note,
however, that changes are made to the database even when a non-2xx error code is
returned.

## Considerations

I've chosen to implement the `subscribers` table such that a `SELECT *` returns
all current subscribers, only. There's a couple things in particular that I find
unfortunate about my implementation:

1. If a user unsubscribes, by canceling a purchase, his/her "history" is wiped
completely from the database. It is impossible to notice, for example, that a
user subscribes in January, unsubscribes in May, and then re-subscribes in
August; only the most recent subscription is present in the table, at all.
That's unfortunate.
2. It assumes that a user cannot make multiple new orders for the same product.
This would seem to prohibit, for example, an institutional client like a
university subscribing to 100 copies of the newspaper.

Consider implementing the `subscribers` table like a "blotter". Then, instead of
wiping canceled orders from the table, we could just record new orders as
+$N and canceled orders as -$N. I find this weirdly enticing:

1. We can query a specific customer\_id and see all of his/her subscriptions and
unsupscriptions *without* losing the ability to get his/her current "monthly
revenue" by summing the purchase\_price, since negative canceled orders will
negate positive new orders.
2. A user can have multiple new orders for a given product active at one time.

But it was an explicit "extra point" goal to notice a canceled order for a
nonexistent new order, and this is very difficult to do with the "blotter"
implementation, as described. It's challenging, in SQL, to reason about a
"chain" of data events. Imagine being given a string like "(()())()" and asked
to determine whether it contains a "closed" parenthetical structure; this is
sort of analogous to determining whether a canceled order corresponds to an
existing new order. This is easy to do in a proper programming language, but how
in SQL? Naively checking that the "balance" is 0 is not sufficient because it
will not catch an input like "))((" and, anyway, we need to match canceled
orders with _precisely_ counter-balanced new orders: (45, -45), not (45, -25,
-20), which is pathological but possible if we only consider the balance. So
this implementation is troublesome; I like it a lot but I've rejected it.


## Improvements

There's a lot here I wish I had time to implement:

1. The actual "file upload" via an HTML form + submit. This is pretty simple, I
think -- just an `<input type="file">` -- but I did not have enough time to
actually implement it.
2. Authentication and authorization is, I think, a pretty massive ask for a
2-hour exercise. I could have supplied a "Hello World" implementation in that
time -- hardcoded users, passwords, and roles -- but decided that it wasn't
productive. (I also only have genuine experience with Kerberos, which is totally
inappropriate for this use case.)
3. A progress bar implies some kind of asynchronous mechanism. For example, when
a user POSTs a large document, I could send the task to a remote worker, e.g.
Celery. I could instantly return, in the response body, a unique ID to query
this result via another endpoint, like `/purchases/<id>`, which could return the
number of completed and outstanding tasks. I could use something like Redis as
the backend storage... This is very ambitious for a 2-hour exercise! In a
language like Java, I could probably get pretty close with an `ExecutorService`
and a synchronized map. But this is pretty awkward in Python; my code would be
dusted with `multiprocessing` and various (honestly unfamiliar) mechanisms to
share memory between processes. None of this code would actually be present in a
real production system, so in pursuit of an approximation of this feature I
would have complicated the code considerably. So I've decided against pursuing
it.

## Final Thoughts

It was a pleasure implementing this coding challenge and I sincerely hope it is
up to your standards. (If not, all the same.) I can be reached at
<sandford.jeffrey@gmail.com>, or 347-437-1203.

Thank you.

~J
