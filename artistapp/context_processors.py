from django.db.models import Sum
from .models import Cart


def cart_summary(request):
    """Expose live pending cart item count to all templates."""
    if request.user.is_authenticated:
        customer_key = str(request.user.id)
    elif request.session.session_key:
        customer_key = f"guest:{request.session.session_key}"
    else:
        return {"cart_count": 0}

    total_qty = (
        Cart.objects.filter(customer_id=customer_key, status="pending")
        .aggregate(total=Sum("quantity"))
        .get("total")
        or 0
    )
    return {"cart_count": total_qty}
