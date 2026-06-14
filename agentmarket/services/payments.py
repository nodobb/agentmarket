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

    # Vendors who completed Stripe Connect onboarding get their share
    # routed automatically (destination charge); the platform keeps the
    # commission as the application fee. Unconnected vendors fall back to
    # the beta behavior: full amount to the platform, manual payout.
    # We read the cached stripe_charges_enabled flag (refreshed during
    # onboarding/status checks) so the checkout path never blocks on a
    # synchronous Stripe API call.
    split = {}
    vendor = transaction.vendor
    if vendor is not None and vendor.stripe_account_id and vendor.stripe_charges_enabled:
        split = {
            "transfer_data": {"destination": vendor.stripe_account_id},
            "application_fee_amount": int(round(transaction.commission_amount * 100)),
        }

    # A clear, human-readable description reduces "I don't recognize this
    # charge" disputes (the top chargeback cause) and helps Stripe reviewers
    # understand our automated transactions at a glance. (The brand shown on
    # buyers' card statements is set once at the account level in the Stripe
    # dashboard, not per-charge.)
    # Truncate vendor-controlled names so a very long product/business name
    # can never push past Stripe's limits (description 1000 chars, metadata
    # value 500 chars) and make the charge fail.
    product_name = (transaction.product.name if transaction.product
                    else f"product {transaction.product_id}")[:200]
    vendor_name = (transaction.vendor.business_name if transaction.vendor
                   else "a vendor")[:200]
    description = (
        f"AgentMarket: {transaction.quantity}x {product_name} from {vendor_name} "
        f"(agent purchase, txn {transaction.id})"
    )

    try:
        intent = stripe.PaymentIntent.create(
            amount=int(round(transaction.total_amount * 100)),  # cents
            currency="usd",
            customer=agent.stripe_customer_id,
            payment_method=agent.stripe_payment_method_id,
            off_session=True,
            confirm=True,
            description=description,
            metadata={
                "transaction_id": str(transaction.id),
                "agent_id": str(agent.id),
                "vendor_id": str(transaction.vendor_id),
                "product": product_name,
                "vendor": vendor_name,
            },
            **split,
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


def reverse_charge(payment: dict, transaction_id) -> None:
    """
    Best-effort compensating refund for a charge whose transaction could not
    be finalized (e.g. the database commit failed after the card was charged).
    Never raises: a refund failure here needs a human, so it is logged as
    critical instead.
    """
    if payment.get("payment_mode") == "simulated" or not payment.get("payment_intent_id"):
        return

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        stripe.Refund.create(
            payment_intent=payment["payment_intent_id"],
            metadata={"transaction_id": str(transaction_id), "reason": "finalization_failed"},
        )
        logger.error(
            f"Reversed charge {payment['payment_intent_id']} for transaction "
            f"{transaction_id} after a finalization failure"
        )
    except stripe.StripeError as e:
        logger.critical(
            f"MANUAL INTERVENTION REQUIRED: charge {payment['payment_intent_id']} for "
            f"transaction {transaction_id} succeeded but finalization failed AND the "
            f"automatic refund failed: {e}"
        )


def refund_transaction(transaction: Transaction) -> dict:
    """
    Refund a committed transaction in full.
    Returns {"payment_mode", "refund_id"}.
    """
    mode = _payment_mode()

    # Nothing was charged if Stripe is off now, or was off when this
    # transaction was committed - so there is nothing to refund at Stripe.
    if mode == "simulated" or not transaction.stripe_payment_intent_id:
        return {"payment_mode": "simulated", "refund_id": None}

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # If the charge was split to a vendor's Connect account, the refund
        # must pull the vendor's share and the commission back too
        intent = stripe.PaymentIntent.retrieve(transaction.stripe_payment_intent_id)
        reverse = {}
        if getattr(intent, "transfer_data", None):
            reverse = {"reverse_transfer": True, "refund_application_fee": True}

        refund = stripe.Refund.create(
            payment_intent=transaction.stripe_payment_intent_id,
            metadata={"transaction_id": str(transaction.id)},
            **reverse,
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe error refunding transaction {transaction.id}: {e}")
        raise PaymentError("Refund failed; the charge was not reversed") from e

    return {"payment_mode": mode, "refund_id": refund.id}


def create_connect_onboarding(vendor, email: str, db) -> str:
    """
    Create (or reuse) a Stripe Connect Express account for the vendor and
    return a Stripe-hosted onboarding URL where they enter their own
    business and bank details.
    """
    if not stripe_enabled():
        raise PaymentError(
            "Stripe is not configured on this server (STRIPE_SECRET_KEY is not set)"
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        if not vendor.stripe_account_id:
            account = stripe.Account.create(
                type="express",
                email=email,
                metadata={"vendor_id": str(vendor.id)},
                capabilities={"transfers": {"requested": True}},
                business_profile={"name": vendor.business_name},
            )
            # Persist immediately: if the link step below fails, a retry
            # must reuse this account instead of orphaning it at Stripe
            vendor.stripe_account_id = account.id
            db.commit()

        link = stripe.AccountLink.create(
            account=vendor.stripe_account_id,
            refresh_url=f"{settings.SITE_URL}/dashboard?connect=retry",
            return_url=f"{settings.SITE_URL}/dashboard?connect=done",
            type="account_onboarding",
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe error during Connect onboarding for vendor {vendor.id}: {e}")
        raise PaymentError(e.user_message or "Could not start Stripe onboarding") from e

    return link.url


def connect_status(vendor, db=None) -> dict:
    """
    Report whether the vendor's Connect account can receive payouts, and
    refresh the cached stripe_charges_enabled flag the checkout path relies
    on. Pass db to persist the refreshed flag.
    """
    if not vendor.stripe_account_id:
        return {"connected": False, "charges_enabled": False, "payouts_enabled": False}

    if not stripe_enabled():
        raise PaymentError(
            "Stripe is not configured on this server (STRIPE_SECRET_KEY is not set)"
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        account = stripe.Account.retrieve(vendor.stripe_account_id)
    except stripe.StripeError as e:
        logger.error(f"Stripe error checking Connect status for vendor {vendor.id}: {e}")
        raise PaymentError("Could not check Stripe onboarding status") from e

    charges_enabled = bool(getattr(account, "charges_enabled", False))
    if vendor.stripe_charges_enabled != charges_enabled:
        vendor.stripe_charges_enabled = charges_enabled
        if db is not None:
            db.commit()

    return {
        "connected": True,
        "charges_enabled": bool(getattr(account, "charges_enabled", False)),
        "payouts_enabled": bool(getattr(account, "payouts_enabled", False)),
    }
