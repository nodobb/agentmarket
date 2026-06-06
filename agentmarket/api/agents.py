"""
Agent-Facing API Routes
The core agent interaction endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import secrets
import uuid

from agentmarket.models import get_db_dependency
from agentmarket.models.database import Product, Agent, Transaction, TransactionStatus, Vendor
from agentmarket.services.auth import get_current_agent
from agentmarket.utils.config import settings


router = APIRouter()


# Pydantic models
class ProductSearchResponse(BaseModel):
    id: int
    external_id: str
    name: str
    description: str
    price: float
    currency: str
    category: str
    tags: List[str]
    stock_available: int
    vendor_name: str
    
    class Config:
        from_attributes = True


class DryRunRequest(BaseModel):
    product_id: str = Field(..., description="The external ID of the product to purchase")
    quantity: int = Field(1, ge=1, description="Number of items to purchase")
    agent_budget_limit: Optional[float] = Field(None, description="Maximum total cost the agent is authorized to spend")
    shipping_address: Optional[str] = Field(None, description="Required for physical goods")


class DryRunResponse(BaseModel):
    handshake_token: str = Field(..., description="Unique token for this validated checkout state (expires in 5 minutes)")
    product_id: str
    quantity: int
    price_per_unit: float
    subtotal: float
    tax: float
    shipping: float
    commission: float
    total_cost: float
    requires_human_approval: bool = Field(..., description="True if transaction exceeds safety limits")
    approval_reason: Optional[str] = Field(None, description="Reason why human approval is required")
    expires_at: datetime


class CommitRequest(BaseModel):
    handshake_token: str = Field(..., description="Token from successful dry-run")


class CommitResponse(BaseModel):
    transaction_id: str
    receipt_id: str
    status: str
    total_amount: float
    completion_message: str


@router.get("/products", response_model=List[ProductSearchResponse])
async def search_products(
    query: Optional[str] = Query(None, description="Semantic search query (e.g., 'cheap API tokens')"),
    category: Optional[str] = Query(None, description="Filter by category"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    limit: int = Query(20, le=100, description="Maximum number of results"),
    x_agent_api_key: str = Header(..., alias="X-Agent-API-Key"),
    db: Session = Depends(get_db_dependency)
):
    """
    Search for products using semantic queries
    This is the primary discovery endpoint for AI agents
    """
    
    # Authenticate the agent
    agent = await get_current_agent(x_agent_api_key, db)
    
    # Build query
    query_filter = db.query(Product).join(Vendor).filter(Product.is_active == True)
    
    if category:
        query_filter = query_filter.filter(Product.category == category)
        
    if max_price:
        query_filter = query_filter.filter(Product.price <= max_price)
    
    products = query_filter.limit(limit).all()
    
    # Convert to response format
    results = []
    for product in products:
        # Simple semantic matching (in production, use vector search)
        relevance_score = 1.0
        if query:
            query_lower = query.lower()
            text_to_search = f"{product.name} {product.description} {' '.join(product.tags or [])}".lower()
            
            # Basic keyword matching
            query_words = query_lower.split()
            matches = sum(1 for word in query_words if word in text_to_search)
            relevance_score = matches / len(query_words) if query_words else 1.0
        
        if relevance_score > 0 or not query:  # Include if relevant or no query
            stock = product.stock_count if not product.is_unlimited_stock else 999999
            
            results.append(ProductSearchResponse(
                id=product.id,
                external_id=product.external_id,
                name=product.name,
                description=product.description,
                price=product.price,
                currency=product.currency,
                category=product.category,
                tags=product.tags or [],
                stock_available=stock,
                vendor_name=product.vendor.business_name
            ))
    
    # Sort by relevance (basic implementation)
    if query:
        results.sort(key=lambda x: len([tag for tag in x.tags if query.lower() in tag.lower()]), reverse=True)
    
    return results


@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run_transaction(
    request: DryRunRequest,
    x_agent_api_key: str = Header(..., alias="X-Agent-API-Key"),
    db: Session = Depends(get_db_dependency)
):
    """
    Phase 1: Validate transaction and return handshake token
    This endpoint calculates real pricing, checks inventory, and evaluates safety limits
    """
    
    # Authenticate agent
    agent = await get_current_agent(x_agent_api_key, db)
    
    # Find product
    product = db.query(Product).filter(
        Product.external_id == request.product_id,
        Product.is_active == True
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check inventory
    if not product.is_unlimited_stock and product.stock_count < request.quantity:
        raise HTTPException(status_code=400, detail="Insufficient inventory")
    
    # Calculate pricing
    subtotal = product.price * request.quantity
    tax = subtotal * 0.08  # 8% tax (simplified)
    shipping = 5.00 if product.category == "merch" else 0.00  # Simplified shipping
    commission = subtotal * settings.COMMISSION_RATE
    total_cost = subtotal + tax + shipping
    
    # Safety checks
    requires_approval = False
    approval_reason = None
    
    if request.agent_budget_limit and total_cost > request.agent_budget_limit:
        requires_approval = True
        approval_reason = f"Transaction total ${total_cost:.2f} exceeds agent budget limit of ${request.agent_budget_limit:.2f}"
    
    if total_cost > agent.requires_human_approval_over:
        requires_approval = True
        approval_reason = f"Transaction total ${total_cost:.2f} exceeds agent approval threshold of ${agent.requires_human_approval_over:.2f}"
    
    if total_cost > settings.MAX_TRANSACTION_AMOUNT:
        requires_approval = True
        approval_reason = f"Transaction total ${total_cost:.2f} exceeds platform maximum of ${settings.MAX_TRANSACTION_AMOUNT:.2f}"
    
    # Create handshake token
    handshake_token = f"hs_{secrets.token_urlsafe(32)}"
    expires_at = datetime.utcnow() + timedelta(minutes=settings.HANDSHAKE_EXPIRE_MINUTES)
    
    # Store transaction in database
    transaction = Transaction(
        agent_id=agent.id,
        product_id=product.id,
        vendor_id=product.vendor_id,
        handshake_token=handshake_token,
        quantity=request.quantity,
        price_per_unit=product.price,
        subtotal=subtotal,
        tax_amount=tax,
        shipping_amount=shipping,
        commission_amount=commission,
        total_amount=total_cost,
        status=TransactionStatus.DRY_RUN,
        requires_human_approval=requires_approval,
        approval_reason=approval_reason,
        expires_at=expires_at,
        dry_run_at=datetime.utcnow()
    )
    
    db.add(transaction)
    db.commit()
    
    return DryRunResponse(
        handshake_token=handshake_token,
        product_id=request.product_id,
        quantity=request.quantity,
        price_per_unit=product.price,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        commission=commission,
        total_cost=total_cost,
        requires_human_approval=requires_approval,
        approval_reason=approval_reason,
        expires_at=expires_at
    )


@router.post("/commit", response_model=CommitResponse)
async def commit_transaction(
    request: CommitRequest,
    x_agent_api_key: str = Header(..., alias="X-Agent-API-Key"),
    db: Session = Depends(get_db_dependency)
):
    """
    Phase 2: Commit the validated transaction
    This endpoint processes payment and completes the purchase
    """
    
    # Authenticate agent
    agent = await get_current_agent(x_agent_api_key, db)
    
    # Find the dry-run transaction
    transaction = db.query(Transaction).filter(
        Transaction.handshake_token == request.handshake_token,
        Transaction.agent_id == agent.id,
        Transaction.status == TransactionStatus.DRY_RUN
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Invalid or expired handshake token")
    
    # Check if expired
    if datetime.utcnow() > transaction.expires_at:
        raise HTTPException(status_code=400, detail="Handshake token has expired")
    
    # Check if requires human approval
    if transaction.requires_human_approval:
        raise HTTPException(
            status_code=400, 
            detail=f"Human approval required: {transaction.approval_reason}"
        )
    
    # Process payment (simplified - in production, integrate with Stripe)
    receipt_id = f"rec_{uuid.uuid4().hex[:12]}"
    
    # Update transaction
    transaction.status = TransactionStatus.COMMITTED
    transaction.committed_at = datetime.utcnow()
    transaction.completed_at = datetime.utcnow()  # Simplified
    
    # Update product inventory
    if not transaction.product.is_unlimited_stock:
        transaction.product.stock_count -= transaction.quantity
    
    db.commit()
    
    return CommitResponse(
        transaction_id=str(transaction.id),
        receipt_id=receipt_id,
        status="completed",
        total_amount=transaction.total_amount,
        completion_message=f"Successfully purchased {transaction.quantity}x {transaction.product.name}"
    )


@router.get("/status")
async def agent_status(
    x_agent_api_key: str = Header(..., alias="X-Agent-API-Key"),
    db: Session = Depends(get_db_dependency)
):
    """Get agent status and recent activity"""
    
    agent = await get_current_agent(x_agent_api_key, db)
    
    # Get recent transactions
    recent_transactions = db.query(Transaction).filter(
        Transaction.agent_id == agent.id
    ).order_by(Transaction.created_at.desc()).limit(5).all()
    
    return {
        "agent_name": agent.name,
        "daily_budget_remaining": agent.daily_budget_limit,  # Simplified
        "transaction_limit": agent.transaction_limit,
        "approval_threshold": agent.requires_human_approval_over,
        "recent_transactions": len(recent_transactions),
        "last_activity": agent.last_activity.isoformat() if agent.last_activity else None
    }