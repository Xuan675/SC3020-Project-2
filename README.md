# SC3020 Project 2

Query execution plan cost annotation tool for PostgreSQL.

## Setup Prerequisites

- Python 3.11 or newer
- PostgreSQL installed locally
- The TPC-H database from Project 1 already created and loaded with data

## Installation

```bash
cd sc3020-project-2
pip install -r requirements.txt
```

## PostgreSQL Config

Create a local `config.py` file by copying `config.example.py` and updating the connection details to match your PostgreSQL setup.

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "TPC-H",
    "user": "postgres",
    "password": "your-password-here",
}
```

## Run

```bash
python project.py --query "SELECT * FROM customer c, orders o WHERE c.c_custkey = o.o_custkey"
```

You can also pass a SQL file:

```bash
python project.py --query-file query.sql
```

Or pipe a generated query:

```bash
echo "SELECT * FROM customer c, orders o WHERE c.c_custkey = o.o_custkey" | python project.py
```

The program connects to the configured PostgreSQL database, retrieves the query execution plan and representative alternative query plans, and prints an annotated explanation for the provided query in the terminal.
