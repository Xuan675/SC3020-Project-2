# SC3020 Project 2

This repository contains our SC3020 Project 2 work on query plan-based SQL comprehension for AI-generated SQL queries.

## Project Structure

- `project.py`: main entry point used to run the project
- `preprocessing.py`: database access and query plan retrieval
- `annotation.py`: query plan annotation logic
- `interface.py`: GUI entry point placeholder
- `scripts/tbl_to_csv.py`: helper script to convert TPC-H `.tbl` files into `.csv`

## Prerequisites

- Python 3.11 or newer
- PostgreSQL installed locally
- A PostgreSQL database named `TPC-H`
- TPC-H data generated locally using the official dbgen tools

## Local Setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 3. Create your local database config

Copy `config.example.py` to `config.py`, then update the PostgreSQL credentials inside `config.py`.

Example:

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "TPC-H",
    "user": "postgres",
    "password": "your-password-here",
}
```

## Preparing the TPC-H Dataset

The coursework appendix says to generate TPC-H data using the official dbgen tools, convert the generated `.tbl` files to `.csv`, then import them into PostgreSQL.

### 1. Download and generate the source `.tbl` files

Generate these files inside `tpch-tools/dbgen/`:

- `customer.tbl`
- `lineitem.tbl`
- `nation.tbl`
- `orders.tbl`
- `part.tbl`
- `partsupp.tbl`
- `region.tbl`
- `supplier.tbl`

### 2. Convert `.tbl` files to `.csv`

```powershell
python .\scripts\tbl_to_csv.py
```

This removes the trailing `|` character from each row so the files can be imported into PostgreSQL more easily.

### 3. Import the `.csv` files into PostgreSQL

Create the tables in the `TPC-H` database, then import the generated `.csv` files into the matching tables:

- `customer`
- `lineitem`
- `nation`
- `orders`
- `part`
- `partsupp`
- `region`
- `supplier`

You can use pgAdmin's import tool or SQL `COPY` commands.

## Running the Project

```powershell
python .\project.py
```

The current `project.py` runs a sample join query, retrieves the PostgreSQL query execution plan plus representative alternative plans, and prints an annotated query explanation to the terminal.

## GitHub Upload Steps

This local repository is already initialized with Git and has an initial commit on the `main` branch.

### 1. Create an empty GitHub repository

Recommended settings:

- Repository name: `sc3020-project-2`
- Visibility: private if only your team should access it
- Do not add a README, `.gitignore`, or license on GitHub because they already exist locally

### 2. Connect the local repo to GitHub

Replace `<your-username>` with your GitHub username:

```powershell
git remote add origin https://github.com/<your-username>/sc3020-project-2.git
git push -u origin main
```

If GitHub asks you to sign in, complete the browser login or use a personal access token when prompted.

### 3. Invite your teammates

On GitHub:

1. Open the repository.
2. Go to `Settings`.
3. Open `Collaborators and teams`.
4. Add your teammates by GitHub username or email.

## Important Notes

- `config.py` is intentionally ignored so personal database credentials are not committed.
- Generated data files under `tpch-tools/dbgen/*.csv` and `tpch-tools/dbgen/*.tbl` are intentionally ignored because several exceed GitHub's file size limits.
- If teammates need the dataset, they should generate or import it locally instead of pulling it from GitHub.
