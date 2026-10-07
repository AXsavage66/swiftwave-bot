import sqlite3

conn = sqlite3.connect("swiftwave.db")
cursor = conn.cursor()

# Inspect current schema of transactions table
cursor.execute("PRAGMA table_info(transactions);")
existing_txn_cols = [row[1] for row in cursor.fetchall()]
print(f"Current columns in 'transactions': {existing_txn_cols}")

# All columns required by models.Transaction
required_txn_cols = [
    ("user_id", "INTEGER"),
    ("amount", "REAL"),
    ("type", "TEXT"),
    ("description", "TEXT"),
    ("reference", "TEXT"),
    ("created_at", "DATETIME"),
]

for col_name, col_type in required_txn_cols:
    if col_name not in existing_txn_cols:
        cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type};")
        print(f"✅ Added missing column to transactions: {col_name} ({col_type})")

# Also check users table for safety
cursor.execute("PRAGMA table_info(users);")
existing_user_cols = [row[1] for row in cursor.fetchall()]
required_user_cols = [
    ("bank_name", "TEXT"),
    ("account_number", "TEXT"),
    ("account_name", "TEXT"),
    ("tracking_reference", "TEXT"),
]
for col_name, col_type in required_user_cols:
    if col_name not in existing_user_cols:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
        print(f"✅ Added missing column to users: {col_name} ({col_type})")

conn.commit()
conn.close()
print("\n🎉 Database schema is fully aligned with models.py!")