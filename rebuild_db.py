import os
import shutil
import sqlite3
from database import engine, Base, SessionLocal
import models

DB_FILE = "swiftwave.db"
BAK_FILE = "swiftwave.db.bak"

print("=" * 50)
print("   🔄 SWIFTWAVE DATABASE REBUILD & SYNC")
print("=" * 50)

# 1. Create a safe backup of the database
if os.path.exists(DB_FILE):
    shutil.copyfile(DB_FILE, BAK_FILE)
    print(f"📦 Backup created: {BAK_FILE}")

# 2. Extract existing user records from disk to preserve balances
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

existing_users = []
try:
    cursor.execute("SELECT * FROM users")
    cols = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        existing_users.append(dict(zip(cols, row)))
    print(f"👤 Found {len(existing_users)} existing user(s) to preserve.")
except Exception as e:
    print(f"Notice on existing data: {e}")
finally:
    conn.close()

# 3. Drop legacy tables and reconstruct fresh schema matching models.py
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✅ Reconstructed clean schema matching models.py perfectly.")

# 4. Re-insert preserved users with their exact balances
db = SessionLocal()
for u in existing_users:
    phone = u.get("phone_number")
    if phone:
        new_user = models.User(
            phone_number=phone,
            name=u.get("name", "Valued Customer"),
            wallet_balance=float(u.get("wallet_balance", 0.0)),
            bank_name=u.get("bank_name"),
            account_number=u.get("account_number"),
            account_name=u.get("account_name"),
            tracking_reference=u.get("tracking_reference"),
        )
        db.add(new_user)

db.commit()

# 5. Verify the restored accounts
print("\n📋 Restored Users:")
for user in db.query(models.User).all():
    print(f"   • ID: {user.id} | Phone: {user.phone_number} | Balance: ₦{user.wallet_balance:,.2f}")

db.close()
print("\n🚀 Database sync complete! You can now run tests.")