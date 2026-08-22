"""
Billing API routes for OminiVoice.
Handles Stripe checkout, portal, and usage statistics.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import User, Agent, Subscription, CallLog, SubscriptionStatus, UserPlan
from app.schemas.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PortalSessionResponse,
    UsageStatsResponse,
    PlanTier,
)

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    checkout_request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """
    Create a Stripe checkout session for subscription upgrade.
    Returns session_id, url (for redirect), and client_secret (for Stripe Elements).
    """
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("sk_test_your"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Get or create Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)},
            )
            current_user.stripe_customer_id = customer.id
        else:
            customer_id = current_user.stripe_customer_id

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": checkout_request.price_id, "quantity": 1}],
            mode="subscription",
            success_url=checkout_request.success_url,
            cancel_url=checkout_request.cancel_url,
            metadata={"user_id": str(current_user.id)},
        )

        return CheckoutSessionResponse(
            session_id=session.id,
            url=session.url,
            client_secret=session.client_secret
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )


@router.post("/payment-intent", response_model=CheckoutSessionResponse)
async def create_payment_intent(
    plan: PlanTier,
    current_user: User = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """
    Create a Stripe PaymentIntent for inline checkout with Stripe Elements.
    Used for embedded checkout flow (no redirect).
    """
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("sk_test_your"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    # Map plan to price ID
    price_id_map = {
        PlanTier.STARTER: settings.STRIPE_PRICE_ID_STARTER,
        PlanTier.PRO: settings.STRIPE_PRICE_ID_PRO,
        PlanTier.ENTERPRISE: settings.STRIPE_PRICE_ID_ENTERPRISE,
    }

    price_id = price_id_map.get(plan)
    if not price_id or price_id.startswith("price_"):
        # Allow test price IDs
        pass

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Get or create Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)},
            )
            current_user.stripe_customer_id = customer.id

        # Create PaymentIntent for subscription
        payment_intent = stripe.PaymentIntent.create(
            customer=current_user.stripe_customer_id,
            amount=2900 if plan == PlanTier.STARTER else 9900 if plan == PlanTier.PRO else 29900,  # cents
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={
                "user_id": str(current_user.id),
                "plan": plan.value,
                "price_id": price_id,
            },
        )

        return CheckoutSessionResponse(
            session_id=payment_intent.id,
            url="",
            client_secret=payment_intent.client_secret,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment intent: {str(e)}",
        )


@router.get("/prices")
async def get_prices() -> dict:
    """
    Get Stripe price IDs for each plan.
    Returns the price IDs configured in settings.
    """
    return {
        "starter": settings.STRIPE_PRICE_ID_STARTER,
        "pro": settings.STRIPE_PRICE_ID_PRO,
        "enterprise": settings.STRIPE_PRICE_ID_ENTERPRISE,
    }


@router.post("/portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    current_user: User = Depends(get_current_user),
) -> PortalSessionResponse:
    """
    Create a Stripe customer portal session for subscription management.
    """
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith("sk_test_your"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe not configured",
        )

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer associated with this account",
        )

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/account",
        )

        return PortalSessionResponse(url=session.url)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {str(e)}",
        )


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageStatsResponse:
    """
    Get current usage statistics for the user's plan.
    """
    # Get user's subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    # Determine plan limits
    plan = current_user.plan
    if subscription and subscription.status == SubscriptionStatus.ACTIVE:
        plan = subscription.plan

    # Plan limits
    PLAN_LIMITS = {
        UserPlan.FREE: {"agents": 3, "minutes": 100, "queue_rows": 0},
        UserPlan.STARTER: {"agents": 10, "minutes": 1000, "queue_rows": 1000},
        UserPlan.PRO: {"agents": None, "minutes": 10000, "queue_rows": None},
        UserPlan.ENTERPRISE: {"agents": None, "minutes": None, "queue_rows": None},
    }

    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS[UserPlan.FREE])

    # Count current usage
    # Agents count
    result = await db.execute(
        select(func.count(Agent.id)).where(Agent.owner_id == current_user.id)
    )
    agents_used = result.scalar() or 0

    # Minutes used this period (from call logs)
    period_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if subscription and subscription.current_period_start:
        period_start = subscription.current_period_start

    result = await db.execute(
        select(func.coalesce(func.sum(CallLog.duration_s), 0)).where(
            CallLog.agent_id.in_(
                select(Agent.id).where(Agent.owner_id == current_user.id)
            ),
            CallLog.started_at >= period_start,
            CallLog.status == "completed",
        )
    )
    total_seconds = result.scalar() or 0
    minutes_used = total_seconds // 60

    # Queue rows used
    result = await db.execute(
        select(func.count()).select_from(
            select(1).where(
                __import__("app.models", fromlist=["ColdCallQueueEntry"]).ColdCallQueueEntry.agent_id.in_(
                    select(Agent.id).where(Agent.owner_id == current_user.id)
                )
            ).exists()
        )
    )
    # Simpler approach: count queue entries for user's agents
    from app.models import ColdCallQueueEntry
    result = await db.execute(
        select(func.count(ColdCallQueueEntry.id)).where(
            ColdCallQueueEntry.agent_id.in_(
                select(Agent.id).where(Agent.owner_id == current_user.id)
            )
        )
    )
    queue_rows_used = result.scalar() or 0

    period_end = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_end.month == 12:
        period_end = period_end.replace(year=period_end.year + 1, month=1)
    else:
        period_end = period_end.replace(month=period_end.month + 1)

    return UsageStatsResponse(
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        agents_used=agents_used,
        agents_limit=limits["agents"],
        minutes_used=minutes_used,
        minutes_limit=limits["minutes"],
        queue_rows_used=queue_rows_used,
        queue_rows_limit=limits["queue_rows"],
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Stripe webhook events.
    """
    if not settings.STRIPE_WEBHOOK_SECRET or settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_your"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook not configured",
        )

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        if user_id:
            # Update user's subscription
            from sqlalchemy import update
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(stripe_customer_id=session.get("customer"))
            )
            # Subscription will be created by customer.subscription.created event

    elif event["type"] == "customer.subscription.created":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        # Find user by stripe_customer_id
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            await _sync_subscription(db, user, subscription)

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            await _sync_subscription(db, user, subscription)

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            await _sync_subscription(db, user, subscription)

    return {"received": True}


async def _sync_subscription(db: AsyncSession, user: User, stripe_subscription: dict):
    """Sync Stripe subscription to local database."""
    import stripe

    # Map Stripe status to our enum
    status_map = {
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.UNPAID,
        "trialing": SubscriptionStatus.TRIALING,
        "incomplete": SubscriptionStatus.INCOMPLETE,
        "incomplete_expired": SubscriptionStatus.INCOMPLETE_EXPIRED,
        "paused": SubscriptionStatus.PAUSED,
    }

    # Determine plan from price
    plan = UserPlan.FREE
    price_id = stripe_subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
    if settings.STRIPE_PRICE_ID_PRO in price_id:
        plan = UserPlan.PRO
    elif settings.STRIPE_PRICE_ID_STARTER in price_id:
        plan = UserPlan.STARTER
    elif settings.STRIPE_PRICE_ID_ENTERPRISE in price_id:
        plan = UserPlan.ENTERPRISE

    # Upsert subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()

    if sub:
        sub.stripe_subscription_id = stripe_subscription["id"]
        sub.stripe_customer_id = stripe_subscription.get("customer")
        sub.plan = plan
        sub.status = status_map.get(stripe_subscription.get("status"), SubscriptionStatus.INCOMPLETE)
        sub.current_period_start = datetime.fromtimestamp(stripe_subscription["current_period_start"], tz=timezone.utc)
        sub.current_period_end = datetime.fromtimestamp(stripe_subscription["current_period_end"], tz=timezone.utc)
        sub.cancel_at_period_end = stripe_subscription.get("cancel_at_period_end", False)
        sub.canceled_at = (
            datetime.fromtimestamp(stripe_subscription["canceled_at"], tz=timezone.utc)
            if stripe_subscription.get("canceled_at")
            else None
        )
        sub.trial_start = (
            datetime.fromtimestamp(stripe_subscription["trial_start"], tz=timezone.utc)
            if stripe_subscription.get("trial_start")
            else None
        )
        sub.trial_end = (
            datetime.fromtimestamp(stripe_subscription["trial_end"], tz=timezone.utc)
            if stripe_subscription.get("trial_end")
            else None
        )
    else:
        sub = Subscription(
            user_id=user.id,
            stripe_subscription_id=stripe_subscription["id"],
            stripe_customer_id=stripe_subscription.get("customer"),
            plan=plan,
            status=status_map.get(stripe_subscription.get("status"), SubscriptionStatus.INCOMPLETE),
            current_period_start=datetime.fromtimestamp(stripe_subscription["current_period_start"], tz=timezone.utc),
            current_period_end=datetime.fromtimestamp(stripe_subscription["current_period_end"], tz=timezone.utc),
            cancel_at_period_end=stripe_subscription.get("cancel_at_period_end", False),
            canceled_at=(
                datetime.fromtimestamp(stripe_subscription["canceled_at"], tz=timezone.utc)
                if stripe_subscription.get("canceled_at")
                else None
            ),
            trial_start=(
                datetime.fromtimestamp(stripe_subscription["trial_start"], tz=timezone.utc)
                if stripe_subscription.get("trial_start")
                else None
            ),
            trial_end=(
                datetime.fromtimestamp(stripe_subscription["trial_end"], tz=timezone.utc)
                if stripe_subscription.get("trial_end")
                else None
            ),
        )
        db.add(sub)

    # Update user plan
    user.plan = plan
    await db.commit()