"""
Transaction Management API Routes
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from agentmarket.models import get_db_dependency
from agentmarket.models.database import Transaction, TransactionStatus, User, UserRole, Agent, Vendor, Product
from agentmarket.services.auth import get_current_user, get_admin_user
from agentmarket.services import payments


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
    
    query = (
        db.query(Transaction)
        .join(Agent, Transaction.agent_id == Agent.id)
        .join(Product, Transaction.product_id == Product.id)
        .join(Vendor, Transaction.vendor_id == Vendor.id)
    )
    
    # Non-admins see transactions for their vendor profile and/or their agents.
    # Ownership is checked directly (not via role) because a user can be both
    # a vendor and an agent owner.
    if current_user.role != UserRole.ADMIN:
        conditions = []
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if vendor:
            conditions.append(Transaction.vendor_id == vendor.id)
        agent_ids = [agent.id for agent in current_user.agents]
        if agent_ids:
            conditions.append(Transaction.agent_id.in_(agent_ids))
        if not conditions:
            return []  # No vendor profile and no agents
        query = query.filter(or_(*conditions))
    
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
    
    # Admins can access any transaction; others must own the vendor or the agent side
    if current_user.role != UserRole.ADMIN:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        owns_vendor_side = vendor is not None and transaction.vendor_id == vendor.id
        owns_agent_side = transaction.agent_id in [agent.id for agent in current_user.agents]
        if not (owns_vendor_side or owns_agent_side):
            raise HTTPException(status_code=403, detail="Access denied")
    
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
    
    # Only the agent's owner or an admin can approve, regardless of the
    # owner's current role (e.g. a user who also registered as a vendor)
    if current_user.role != UserRole.ADMIN:
        agent_ids = [agent.id for agent in current_user.agents]
        if transaction.agent_id not in agent_ids:
            raise HTTPException(status_code=403, detail="Access denied")
    
    if approval_request.approved:
        # Reserve inventory before charging: the conditional atomic update
        # can neither lose concurrent updates nor drive stock negative.
        # The reservation only persists at db.commit() below, so a failed
        # charge rolls it back and the transaction stays retryable.
        if not transaction.product.is_unlimited_stock:
            reserved = db.query(Product).filter(
                Product.id == transaction.product_id,
                Product.stock_count >= transaction.quantity
            ).update(
                {Product.stock_count: Product.stock_count - transaction.quantity},
                synchronize_session=False
            )
            if not reserved:
                db.rollback()
                raise HTTPException(status_code=400, detail="Insufficient inventory")

        try:
            payment = payments.charge_transaction(transaction.agent, transaction)
        except payments.PaymentError as e:
            db.rollback()
            raise HTTPException(status_code=402, detail=str(e))

        transaction.requires_human_approval = False
        transaction.approval_reason = f"Approved by {current_user.full_name}: {approval_request.reason or 'No reason provided'}"
        transaction.status = TransactionStatus.COMMITTED
        transaction.committed_at = datetime.utcnow()
        transaction.stripe_payment_intent_id = payment["payment_intent_id"]
        transaction.stripe_charge_id = payment["charge_id"]

        message = "Transaction approved and processed"
    else:
        # Deny the transaction
        transaction.status = TransactionStatus.FAILED
        transaction.approval_reason = f"Denied by {current_user.full_name}: {approval_request.reason or 'No reason provided'}"
        
        message = "Transaction denied"
    
    db.commit()

    return {"message": message, "status": transaction.status.value}


@router.post("/{transaction_id}/refund")
async def refund_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Refund a committed transaction in full (agent owner or admin only)"""

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if current_user.role != UserRole.ADMIN:
        agent_ids = [agent.id for agent in current_user.agents]
        if transaction.agent_id not in agent_ids:
            raise HTTPException(status_code=403, detail="Access denied")

    if transaction.status not in (TransactionStatus.COMMITTED, TransactionStatus.COMPLETED):
        raise HTTPException(
            status_code=400,
            detail=f"Only completed transactions can be refunded (status is '{transaction.status.value}')"
        )

    try:
        refund = payments.refund_transaction(transaction)
    except payments.PaymentError as e:
        raise HTTPException(status_code=402, detail=str(e))

    transaction.status = TransactionStatus.REFUNDED
    transaction.approval_reason = f"Refunded by {current_user.full_name}"

    # Return the items to inventory (atomic, and via a query update so no
    # SQL expression object lingers on the in-memory product instance)
    if not transaction.product.is_unlimited_stock:
        db.query(Product).filter(Product.id == transaction.product_id).update(
            {Product.stock_count: Product.stock_count + transaction.quantity},
            synchronize_session=False
        )

    db.commit()

    return {
        "message": "Transaction refunded",
        "status": transaction.status.value,
        "payment_mode": refund["payment_mode"],
        "refund_id": refund["refund_id"],
    }