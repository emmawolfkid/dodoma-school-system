from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def division_css(division):
    """'Division I' -> 'division-i', 'Division 0' -> 'division-0',
    'Incomplete' -> 'division-incomplete' -- for the result-sheet pill styling."""
    if not division:
        return ''
    if str(division).strip().lower() == 'incomplete':
        return 'division-incomplete'
    return str(division).strip().lower().replace(' ', '-')


@register.filter
def grade_css(grade):
    """'A' -> 'grade-a', 'ABS' -> 'grade-abs' -- for the result-sheet pill styling."""
    if not grade or grade == '-':
        return ''
    return f'grade-{str(grade).strip().lower()}'