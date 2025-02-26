from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def category_ids_as_json(categories):
    """Convert a category queryset to a JSON array of IDs"""
    return [category.id for category in categories.all()] 
