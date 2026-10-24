from django import template

register = template.Library()

RISK = {"Expired": "dark", "High": "danger", "Medium": "warning text-dark", "Low": "success"}
STATUS = {"Order now": "danger", "Overstocked": "warning text-dark", "Sufficient": "success",
          "No demand": "secondary"}


@register.filter
def risk_badge(level):
    return RISK.get(level, "secondary")


@register.filter
def status_badge(status):
    return STATUS.get(status, "secondary")


@register.filter
def inr(value):
    """Format a number in Indian style: 12,34,567.89"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    neg = value < 0
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return ("-" if neg else "") + "₹" + whole + ("" if frac == "00" else "." + frac)


@register.filter
def pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return value


@register.filter
def safe_json(value):
    import json
    from django.utils.safestring import mark_safe
    return mark_safe(json.dumps(value))
