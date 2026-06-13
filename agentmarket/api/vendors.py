"""
Vendor Management API Routes
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from agentmarket.models import get_db_dependency
from agentmarket.models.database import User, Vendor, Product
from agentmarket.services.auth import get_current_user, get_vendor_user
from agentmarket.services import payments


router = APIRouter()


# Pydantic models
class VendorCreate(BaseModel):
    business_name: str
    description: Optional[str] = None
    website_url: Optional[str] = None
    api_endpoint: Optional[str] = None


class VendorResponse(BaseModel):
    id: int
    business_name: str
    description: Optional[str]
    website_url: Optional[str]
    is_verified: bool
    commission_rate: float
    
    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    external_id: str
    name: str
    description: str
    price: float
    category: str
    tags: Optional[List[str]] = []
    stock_count: Optional[int] = None
    is_unlimited_stock: bool = False
    max_quantity_per_transaction: Optional[int] = None


class ProductResponse(BaseModel):
    id: int
    external_id: str
    name: str
    description: str
    price: float
    currency: str
    category: str
    tags: Optional[List[str]]
    stock_count: Optional[int]
    is_unlimited_stock: bool
    is_active: bool
    
    class Config:
        from_attributes = True


@router.post("/register", response_model=VendorResponse)
async def register_vendor(
    vendor_data: VendorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Register as a vendor"""
    
    # Check if user already has a vendor profile
    existing_vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if existing_vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a vendor profile"
        )
    
    # Create vendor profile
    vendor = Vendor(
        user_id=current_user.id,
        business_name=vendor_data.business_name,
        description=vendor_data.description,
        website_url=vendor_data.website_url,
        api_endpoint=vendor_data.api_endpoint
    )
    
    db.add(vendor)
    
    # Update user role to vendor
    current_user.role = "vendor"
    
    db.commit()
    db.refresh(vendor)
    
    return vendor


@router.get("/profile", response_model=VendorResponse)
async def get_vendor_profile(
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """Get vendor profile"""
    
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found"
        )
    
    return vendor


@router.post("/connect/onboard")
async def start_connect_onboarding(
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """
    Start Stripe Connect onboarding so purchases of this vendor's products
    pay out to their own bank account automatically. Returns a Stripe-hosted
    URL where the vendor enters their details (we never see them).
    """

    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found"
        )

    try:
        onboarding_url = payments.create_connect_onboarding(vendor, current_user.email)
    except payments.PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()

    return {"onboarding_url": onboarding_url}


@router.get("/connect/status")
async def get_connect_status(
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """Check whether this vendor's Stripe Connect account is ready for payouts"""

    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not found"
        )

    try:
        return payments.connect_status(vendor)
    except payments.PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """Create a new product"""
    
    # Get vendor profile
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No vendor profile found"
        )
    
    # Check if external_id already exists for this vendor
    existing_product = db.query(Product).filter(
        Product.vendor_id == vendor.id,
        Product.external_id == product_data.external_id
    ).first()
    
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this external_id already exists"
        )
    
    # Create product
    product = Product(
        vendor_id=vendor.id,
        external_id=product_data.external_id,
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        category=product_data.category,
        tags=product_data.tags,
        stock_count=product_data.stock_count,
        is_unlimited_stock=product_data.is_unlimited_stock,
        max_quantity_per_transaction=product_data.max_quantity_per_transaction
    )
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return product


@router.get("/products", response_model=List[ProductResponse])
async def list_vendor_products(
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """List all products for the current vendor"""
    
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No vendor profile found"
        )
    
    products = db.query(Product).filter(Product.vendor_id == vendor.id).all()
    return products


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductCreate,
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """Update a product"""
    
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No vendor profile found"
        )
    
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.vendor_id == vendor.id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Update product fields
    for field, value in product_data.dict(exclude_unset=True).items():
        setattr(product, field, value)
    
    db.commit()
    db.refresh(product)
    
    return product


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    current_user: User = Depends(get_vendor_user),
    db: Session = Depends(get_db_dependency)
):
    """Delete (deactivate) a product"""
    
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No vendor profile found"
        )
    
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.vendor_id == vendor.id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Deactivate instead of deleting
    product.is_active = False
    db.commit()
    
    return {"message": "Product deactivated successfully"}