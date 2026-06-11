"""
Database Models for AgentMarket
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum


Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    VENDOR = "vendor" 
    AGENT_OWNER = "agent_owner"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    DRY_RUN = "dry_run"
    COMMITTED = "committed"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class User(Base):
    """User accounts - vendors and agent owners"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.AGENT_OWNER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vendor_profile = relationship("Vendor", back_populates="user", uselist=False)
    agents = relationship("Agent", back_populates="owner")


class Vendor(Base):
    """Vendor profiles and business information"""
    __tablename__ = "vendors"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_name = Column(String, nullable=False)
    description = Column(Text)
    website_url = Column(String)
    api_endpoint = Column(String)
    
    # Business verification
    is_verified = Column(Boolean, default=False)
    verification_documents = Column(JSON)
    
    # Payment settings
    stripe_account_id = Column(String)
    commission_rate = Column(Float, default=0.025)  # 2.5%
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="vendor_profile")
    products = relationship("Product", back_populates="vendor")


class Product(Base):
    """Products/services available in the marketplace"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    
    # Product details
    external_id = Column(String, nullable=False)  # vendor's internal ID
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    category = Column(String)
    tags = Column(JSON)  # List of search tags
    
    # Inventory & availability
    stock_count = Column(Integer)
    is_unlimited_stock = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Agent-specific configuration
    agent_manifest = Column(JSON)  # Special agent instructions
    requires_approval = Column(Boolean, default=False)
    max_quantity_per_transaction = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vendor = relationship("Vendor", back_populates="products")
    transactions = relationship("Transaction", back_populates="product")


class Agent(Base):
    """AI Agents registered on the platform"""
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Agent identification
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False, index=True)
    user_agent_string = Column(String)
    
    # Budget and safety controls
    daily_budget_limit = Column(Float, default=100.00)
    transaction_limit = Column(Float, default=50.00)
    requires_human_approval_over = Column(Float, default=10.00)

    # Payment (Stripe customer + saved payment method used to fund purchases)
    stripe_customer_id = Column(String)
    stripe_payment_method_id = Column(String)

    # Status
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="agents")
    transactions = relationship("Transaction", back_populates="agent")


class Transaction(Base):
    """Transactions between agents and vendors"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    
    # Transaction details
    handshake_token = Column(String, unique=True, index=True)
    quantity = Column(Integer, nullable=False)
    price_per_unit = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    shipping_amount = Column(Float, default=0.0)
    commission_amount = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    
    # Status and processing
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    requires_human_approval = Column(Boolean, default=False)
    approval_reason = Column(String)
    
    # Payment processing
    stripe_payment_intent_id = Column(String)
    stripe_charge_id = Column(String)
    
    # Timestamps
    dry_run_at = Column(DateTime(timezone=True))
    committed_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="transactions")
    product = relationship("Product", back_populates="transactions")
    vendor = relationship("Vendor")


class Analytics(Base):
    """Analytics and tracking data"""
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Request tracking
    method = Column(String)
    path = Column(String)
    status_code = Column(Integer)
    response_time = Column(Float)
    user_agent = Column(String)
    ip_address = Column(String)
    
    # Business metrics
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    revenue = Column(Float, default=0.0)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())