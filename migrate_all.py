import sqlite3

conn = sqlite3.connect("swiftwave.db")
cursor = conn.cursor()

# 1. Ensure all columns in users table
user_columns = [
    ("bank_name", "TEXT"),
    ("account_number", "TEXT"),
    ("account_name", "TEXT"),
    ("tracking_reference", "TEXT"),
]
for col, col_type in user_columns:
    try:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
        print(f"✅ Added to users: {col}")
    except sqlite3.OperationalError:
        pass

# 2. Ensure all columns in transactions table
txn_columns = [
    ("reference", "TEXT"),
    ("type", "TEXT"),
    ("description", "TEXT"),
    ("amount", "REAL"),
]
for col, col_type in txn_columns:
    try:
        cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col} {col_type};")
        print(f"✅ Added to transactions: {col}")
    except sqlite3.OperationalError:
        pass

conn.commit()
conn.close()
print("Database schema verified and up to date!")