"""
Billing-related Celery tasks for Stripe synchronization.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_maker
from app.models import User, Subscription, UserPlan, SubscriptionStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.billing_tasks.sync_stripe_subscriptions")
async def sync_stripe_subscriptions() -> dict:
    """
    Sync local subscription state with Stripe.
    Runs daily via Celery beat.

    Fetches all users with Stripe customer IDs and updates
    local subscription records to match Stripe state.

    Returns:
        Dict with sync statistics
    """
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("sk_test_your"):
        logger.warning("Stripe not configured, skipping subscription sync")
        return {"synced": 0, "skipped": True, "reason": "Stripe not configured"}

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    async with async_session_maker() as session:
        # Get all users with Stripe customer IDs
        result = await session.execute(
            select(User).where(User.stripe_customer_id.is_not(None))
        )
        users = result.scalars().all()

        synced = 0
        errors = []

        for user in users:
            try:
                await _sync_user_subscription(session, user, stripe)
                synced += 1
            except Exception as e:
                logger.error(f"Error syncing subscription for user {user.id}: {e}")
                errors.append({"user_id": str(user.id), "error": str(e)})

        await session.commit()

        return {
            "users_synced": synced,
            "errors": errors,
        }


async def _sync_user_subscription(session, user: User, stripe) -> None:
    """Sync a single user's subscription with Stripe."""
    # Get subscriptions from Stripe for this customer
    subscriptions = stripe.Subscription.list(
        customer=user.stripe_customer_id,
        status="all",
        limit=10,
    )

    if not subscriptions.data:
        # No subscription - update user to free plan if they have an active sub locally
        local_sub_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        local_sub = local_sub_result.scalar_one_or_none()

        if local_sub and local_sub.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
            local_sub.status = SubscriptionStatus.CANCELED
            local_sub.plan = UserPlan.FREE
            user.plan = UserPlan.FREE
        return

    # Use the most recent subscription
    stripe_sub = subscriptions.data[0]

    # Map Stripe status to local enum
    status_map = {
        "active": SubscriptionStatus.ACTIVE,
        "trialing": SubscriptionStatus.TRIALING,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.UNPAID,
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
        "paused": SubscriptionStatus.PAUSED,
    }

    # Determine plan from price ID
    plan = _get_plan_from_price_id(stripe_sub.items.data[0].price.id if stripe_sub.items.data else None)

    # Get or create local subscription record
    local_sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    local_sub = local_sub_result.scalar_one_or_none()

    if not local_sub:
        local_sub = Subscription(
            user_id=user.id,
            stripe_customer_id=user.stripe_customer_id,
        )
        session.add(local_sub)

    # Update fields
    local_sub.stripe_subscription_id = stripe_sub.id
    local_sub.plan = plan
    local_sub.status = status_map.get(stripe_sub.status, SubscriptionStatus.INCOMPLETE)
    local_sub.current_period_start = datetime.fromtimestamp(stripe_sub.current_period_start, tz=timezone.utc)
    local_sub.current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
    local_sub.cancel_at_period_end = stripe_sub.cancel_at_period_end
    local_sub.canceled_at = (
        datetime.fromtimestamp(stripe_sub.canceled_at, tz=timezone.utc)
        if stripe_sub.canceled_at
        else None
    )
    local_sub.trial_start = (
        datetime.fromtimestamp(stripe_sub.trial_start, tz=timezone.utc)
        if stripe_sub.trial_start
        else None
    )
    local_sub.trial_end = (
        datetime.fromtimestamp(stripe_sub.trial_end, tz=timezone.utc)
        if stripe_sub.trial_end
        else None
    )

    # Update user plan
    user.plan = plan


def _get_plan_from_price_id(price_id: Optional[str]) -> UserPlan:
    """Map Stripe price ID to local plan tier."""
    if not price_id:
        return UserPlan.FREE

    price_map = {
        settings.STRIPE_PRICE_ID_STARTER: UserPlan.STARTER,
        settings.STRIPE_PRICE_ID_PRO: UserPlan.PRO,
        settings.STRIPE_PRICE_ID_ENTERPRISE: UserPlan.ENTERPRISE,
    }

    return price_map.get(price_id, UserPlan.FREE)


@celery_app.task(name="app.tasks.billing_tasks.handle_stripe_webhook_event")
async def handle_stripe_webhook_event(event_type: str, event_data: dict) -> dict:
    """
    Handle a Stripe webhook event asynchronously.
    Called from the webhook endpoint to offload processing.

    Args:
        event_type: Stripe event type (e.g., "checkout.session.completed")
        event_data: Full event data from Stripe

    Returns:
        Processing result
    """
    logger.info(f"Processing Stripe webhook: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            return await _handle_checkout_completed(event_data)
        elif event_type == "customer.subscription.updated":
            return await _handle_subscription_updated(event_data)
        elif event_type == "customer.subscription.deleted":
            return await _handle_subscription_deleted(event_data)
        elif event_type == "invoice.payment_failed":
            return await _handle_payment_failed(event_data)
        else:
            return {"status": "ignored", "event_type": event_type}
    except Exception as e:
        logger.error(f"Error handling webhook {event_type}: {e}")
        return {"status": "error", "event_type": event_type, "error": str(e)}


async def _handle_checkout_completed(event_data: dict) -> dict:
    """Handle checkout.session.completed event."""
    session_data = event_data["data"]["object"]
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")

    if not customer_id or not subscription_id:
        return {"status": "error", "reason": "Missing customer or subscription ID"}

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Fetch full subscription details
    stripe_sub = stripe.Subscription.retrieve(subscription_id)

    async with async_session_maker() as session:
        # Find user by Stripe customer ID
        from sqlalchemy import select
        from app.models.models import User
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "error", "reason": "User not found for customer"}

        # Sync the subscription
        await _sync_user_subscription(session, user, stripe)
        await session.commit()

    return {"status": "success", "customer_id": customer_id}


async def _handle_subscription_updated(event_data: dict) -> dict:
    """Handle customer.subscription.updated event."""
    stripe_sub_data = event_data["data"]["object"]
    customer_id = stripe_sub_data.get("customer")

    if not customer_id:
        return {"status": "error", "reason": "Missing customer ID"}

    async with async_session_maker() as session:
        from sqlalchemy import select
        from app.models.models import User
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "error", "reason": "User not found"}

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        await _sync_user_subscription(session, user, stripe)
        await session.commit()

    return {"status": "success", "customer_id": customer_id}


async def _handle_subscription_deleted(event_data: dict) -> dict:
    """Handle customer.subscription.deleted event."""
    stripe_sub_data = event_data["data"]["object"]
    customer_id = stripe_sub_data.get("customer")

    if not customer_id:
        return {"status": "error", "reason": "Missing customer ID"}

    async with async_session_maker() as session:
        from sqlalchemy import select
        from app.models.models import User, Subscription, SubscriptionStatus, UserPlan
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "error", "reason": "User not found"}

        # Mark local subscription as canceled
        sub_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        local_sub = sub_result.scalar_one_or_none()

        if local_sub:
            local_sub.status = SubscriptionStatus.CANCELED
            local_sub.canceled_at = datetime.now(timezone.utc)
            local_sub.plan = UserPlan.FREE
            user.plan = UserPlan.FREE
            await session.commit()

    return {"status": "success", "customer_id": customer_id}


async def _handle_payment_failed(event_data: dict) -> dict:
    """Handle invoice.payment_failed event."""
    invoice_data = event_data["data"]["object"]
    customer_id = invoice_data.get("customer")

    if not customer_id:
        return {"status": "error", "reason": "Missing customer ID"}

    async with async_session_maker() as session:
        from sqlalchemy import select
        from app.models.models import User, Subscription, SubscriptionStatus
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"status": "error", "reason": "User not found"}

        sub_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        local_sub = sub_result.scalar_one_or_none()

        if local_sub:
            local_sub.status = SubscriptionStatus.PAST_DUE
            await session.commit()

    return {"status": "success", "customer_id": customer_id}