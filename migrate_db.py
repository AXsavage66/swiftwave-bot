import sqlite3

conn = sqlite3.connect("swiftwave.db")
cursor = conn.cursor()

# Columns to add to the existing users table
columns = [
    ("bank_name", "TEXT"),
    ("account_number", "TEXT"),
    ("account_name", "TEXT"),
    ("tracking_reference", "TEXT"),
]

for col_name, col_type in columns:
    try:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
        print(f"✅ Added column: {col_name}")
    except sqlite3.OperationalError:
        print(f"ℹ️ Column {col_name} already exists.")

conn.commit()
conn.close()
print("Database schema updated successfully!")