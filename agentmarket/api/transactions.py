"""
Transaction Management API Routes
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from agentmarket.models import get_db_dependency
from agentmarket.models.database import Transaction, TransactionStatus, User, Agent, Vendor, Product
from agentmarket.services.auth import get_current_user, get_admin_user


router = APIRouter()


# Pydantic models
class TransactionResponse(BaseModel):
    id: int
    agent_name: str
    product_name: str
    vendor_name: str
    quantity: int
    total_amount: float
    status: str
    requires_human_approval: bool
    approval_reason: Optional[str]
    created_at: datetime
    committed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    approved: bool
    reason: Optional[str] = None


@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    status: Optional[str] = Query(None, description="Filter by status"),
    requires_approval: Optional[bool] = Query(None, description="Filter by approval requirement"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """List transactions (admin sees all, vendors see their own)"""
    
    query = db.query(Transaction).join(Agent).join(Product).join(Vendor)
    
    # Filter based on user role
    if current_user.role == "vendor":
        # Vendors only see their own transactions
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if vendor:
            query = query.filter(Transaction.vendor_id == vendor.id)
        else:
            return []  # No vendor profile
    elif current_user.role == "agent_owner":
        # Agent owners see transactions from their agents
        agent_ids = [agent.id for agent in current_user.agents]
        if agent_ids:
            query = query.filter(Transaction.agent_id.in_(agent_ids))
        else:
            return []  # No agents
    # Admins see all transactions (no filter)
    
    # Apply filters
    if status:
        query = query.filter(Transaction.status == status)
    
    if requires_approval is not None:
        query = query.filter(Transaction.requires_human_approval == requires_approval)
    
    # Order and paginate
    transactions = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
    
    # Format response
    result = []
    for transaction in transactions:
        result.append(TransactionResponse(
            id=transaction.id,
            agent_name=transaction.agent.name,
            product_name=transaction.product.name,
            vendor_name=transaction.vendor.business_name,
            quantity=transaction.quantity,
            total_amount=transaction.total_amount,
            status=transaction.status.value,
            requires_human_approval=transaction.requires_human_approval,
            approval_reason=transaction.approval_reason,
            created_at=transaction.created_at,
            committed_at=transaction.committed_at
        ))
    
    return result


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Get a specific transaction"""
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Check permissions
    if current_user.role == "vendor":
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if not vendor or transaction.vendor_id != vendor.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == "agent_owner":
        agent_ids = [agent.id for agent in current_user.agents]
        if transaction.agent_id not in agent_ids:
            raise HTTPException(status_code=403, detail="Access denied")
    # Admins can access any transaction
    
    return TransactionResponse(
        id=transaction.id,
        agent_name=transaction.agent.name,
        product_name=transaction.product.name,
        vendor_name=transaction.vendor.business_name,
        quantity=transaction.quantity,
        total_amount=transaction.total_amount,
        status=transaction.status.value,
        requires_human_approval=transaction.requires_human_approval,
        approval_reason=transaction.approval_reason,
        created_at=transaction.created_at,
        committed_at=transaction.committed_at
    )


@router.post("/{transaction_id}/approve")
async def approve_transaction(
    transaction_id: int,
    approval_request: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Approve or deny a transaction requiring human approval"""
    
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if not transaction.requires_human_approval:
        raise HTTPException(status_code=400, detail="Transaction does not require approval")
    
    # Check permissions - only agent owner or admin can approve
    if current_user.role == "agent_owner":
        agent_ids = [agent.id for agent in current_user.agents]
        if transaction.agent_id not in agent_ids:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    if approval_request.approved:
        # Approve and process the transaction
        transaction.requires_human_approval = False
        transaction.approval_reason = f"Approved by {current_user.full_name}: {approval_request.reason or 'No reason provided'}"
        transaction.status = TransactionStatus.COMMITTED
        transaction.committed_at = datetime.utcnow()
        
        # Update product inventory if needed
        if not transaction.product.is_unlimited_stock:
            transaction.product.stock_count -= transaction.quantity
        
        message = "Transaction approved and processed"
    else:
        # Deny the transaction
        transaction.status = TransactionStatus.FAILED
        transaction.approval_reason = f"Denied by {current_user.full_name}: {approval_request.reason or 'No reason provided'}"
        
        message = "Transaction denied"
    
    db.commit()
    
    return {"message": message, "status": transaction.status.value}