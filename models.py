from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="Valued Customer")
    wallet_balance = Column(Float, default=0.0)
    
    # Virtual Dedicated Bank Account Details
    bank_name = Column(String, nullable=True)          # e.g., "9PSB / Wema Bank"
    account_number = Column(String, nullable=True)     # 10-digit NUBAN
    account_name = Column(String, nullable=True)       # e.g., "SWIFTWAVE / MUKHTAR"
    tracking_reference = Column(String, nullable=True) # Unique Payvessel customer ref

    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    network = Column(String, nullable=False)
    recipient_phone = Column(String, nullable=False)
    plan_id = Column(String, nullable=False)
    cost_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    profit = Column(Float, nullable=False)
    status = Column(String, default="PENDING")
    external_ref = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)  # "CREDIT" or "DEBIT"
    description = Column(String, nullable=False)
    reference = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")