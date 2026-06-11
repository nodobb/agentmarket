"""
Payment processing.

Two modes, chosen automatically:

- Stripe mode (STRIPE_SECRET_KEY configured): purchases charge the agent's
  saved payment method via a Stripe PaymentIntent. Test keys (sk_test_...)
  charge Stripe's test environment, live keys charge real money.
- Simulated mode (no key): transactions are recorded but nothing is charged,
  and responses carry payment_mode="simulated".
"""

from typing import Optional

import stripe
from loguru import logger

from agentmarket.models.database import Agent, Transaction
from agentmarket.utils.config import settings


class PaymentError(Exception):
    """Raised when a charge cannot be made; message is safe to show the caller."""


def stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _payment_mode() -> str:
    if not stripe_enabled():
        return "simulated"
    return "live" if settings.STRIPE_SECRET_KEY.startswith("sk_live") else "test"


def attach_payment_method(agent: Agent, payment_method_id: str, owner_email: str) -> str:
    """
    Attach a Stripe payment method to the agent, creating a Stripe customer
    for it on first use. Returns a human-readable card label.
    """
    if not stripe_enabled():
        raise PaymentError(
            "Stripe is not configured on this server (STRIPE_SECRET_KEY is not set)"
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        if not agent.stripe_customer_id:
            customer = stripe.Customer.create(
                email=owner_email,
                description=f"AgentMarket agent {agent.id}: {agent.name}",
                metadata={"agent_id": str(agent.id)},
            )
            agent.stripe_customer_id = customer.id

        payment_method = stripe.PaymentMethod.attach(
            payment_method_id, customer=agent.stripe_customer_id
        )
        stripe.Customer.modify(
            agent.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method.id},
        )
        agent.stripe_payment_method_id = payment_method.id
    except stripe.StripeError as e:
        logger.warning(f"Stripe error attaching payment method for agent {agent.id}: {e}")
        raise PaymentError(e.user_message or "Could not attach payment method") from e

    card = getattr(payment_method, "card", None)
    if card:
        return f"{card.brand} ending in {card.last4}"
    return payment_method.type


def charge_transaction(agent: Agent, transaction: Transaction) -> dict:
    """
    Charge the agent's saved payment method for the transaction total.
    Returns {"payment_mode", "payment_intent_id", "charge_id"}.
    """
    mode = _payment_mode()

    if mode == "simulated":
        return {"payment_mode": mode, "payment_intent_id": None, "charge_id": None}

    if not agent.stripe_payment_method_id:
        raise PaymentError(
            "This agent has no payment method on file. The agent's owner must add one "
            "via POST /api/agents/{agent_id}/payment-method before purchases can be charged."
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(round(transaction.total_amount * 100)),  # cents
            currency="usd",
            customer=agent.stripe_customer_id,
            payment_method=agent.stripe_payment_method_id,
            off_session=True,
            confirm=True,
            description=f"AgentMarket purchase: {transaction.quantity}x product {transaction.product_id}",
            metadata={
                "transaction_id": str(transaction.id),
                "agent_id": str(agent.id),
                "vendor_id": str(transaction.vendor_id),
            },
        )
    except stripe.CardError as e:
        logger.warning(f"Card declined for transaction {transaction.id}: {e}")
        raise PaymentError(e.user_message or "Card was declined") from e
    except stripe.StripeError as e:
        logger.error(f"Stripe error charging transaction {transaction.id}: {e}")
        raise PaymentError("Payment processing failed; nothing was charged") from e

    return {
        "payment_mode": mode,
        "payment_intent_id": intent.id,
        "charge_id": getattr(intent, "latest_charge", None),
    }
