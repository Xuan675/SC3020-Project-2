# SC3020 Project 2

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create a local `config.py` file by copying `config.example.py` and filling in your own PostgreSQL credentials.
4. Make sure your local PostgreSQL instance contains the `TPC-H` database.

## Notes

- `config.py` is intentionally ignored so personal database credentials are not committed.
- Generated data files under `tpch-tools/dbgen/*.csv` and `tpch-tools/dbgen/*.tbl` are intentionally ignored because several exceed GitHub's file size limits.
