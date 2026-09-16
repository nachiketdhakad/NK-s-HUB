from django import template

register = template.Library()

@register.filter
def format_views(value):
    """20002 -> 20k, 2001 -> 2k, 5008 -> 5k, 900 -> 900"""
    try:
        value = int(value)
    except (ValueError, TypeError):
        return value

    if value >= 1_000_000:
        num = value / 1_000_000
        return f"{num:.1f}".rstrip('0').rstrip('.') + "M"
    elif value >= 1000:
        num = value / 1000
        return f"{num:.1f}".rstrip('0').rstrip('.') + "k"
    return str(value)