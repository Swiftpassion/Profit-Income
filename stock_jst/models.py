from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import datetime

class Product(Base):
    __tablename__ = 'products'

    id = Column(String, primary_key=True, index=True) # Product_ID
    name = Column(String, nullable=True) # Product_Name
    image_url = Column(String, nullable=True) # Image
    current_stock = Column(Integer, default=0) # Stock/Real_Stock
    min_limit = Column(Integer, default=0) # Min_Limit
    product_type = Column(String, default="ทั่วไป") # Type
    note = Column(Text, nullable=True) # Note
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=func.now())

    sales = relationship("Sale", back_populates="product")
    pos = relationship("PurchaseOrder", back_populates="product")
    stock_logs = relationship("StockLog", back_populates="product")

class Sale(Base):
    __tablename__ = 'sales'

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, default=0)
    shop = Column(String, nullable=True)
    order_time = Column(DateTime, nullable=True)
    date_only = Column(Date, nullable=True) # Derived for faster querying
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="sales")

class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, index=True, nullable=True)
    product_id = Column(String, ForeignKey('products.id'), nullable=False)
    
    transport_type = Column(String, nullable=True)
    order_date = Column(Date, nullable=True)
    expected_date = Column(Date, nullable=True)
    received_date = Column(Date, nullable=True)
    
    qty_ordered = Column(Integer, default=0)
    qty_received = Column(Integer, default=0)
    
    # Financials
    price_unit_novat = Column(Float, default=0.0)
    total_yuan = Column(Float, default=0.0)
    yuan_rate = Column(Float, default=0.0)
    ship_rate = Column(Float, default=0.0)
    cbm = Column(Float, default=0.0)
    ship_cost = Column(Float, default=0.0)
    transport_weight = Column(Float, default=0.0)
    
    # Platform Prices
    shopee_price = Column(Float, default=0.0)
    lazada_price = Column(Float, default=0.0)
    tiktok_price = Column(Float, default=0.0)
    total_thb = Column(Float, default=0.0)
    
    link = Column(String, nullable=True)
    wechat = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    
    status = Column(String, default="Pending") # Derived or manually set
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("Product", back_populates="pos")

class StockLog(Base):
    __tablename__ = 'stock_logs'

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, ForeignKey('products.id'), nullable=False)
    change_amount = Column(Integer, nullable=False)
    reason = Column(String, nullable=True) # e.g. "Import Actual Stock", "Sale", "Manual Adjust"
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="stock_logs")
    user = relationship("User")

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True) # If using password auth later
    role = Column(String, default="user") # admin, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
