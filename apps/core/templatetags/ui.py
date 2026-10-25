from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, cls="", label=""):
    """Ikon dari sprite `static/img/icons.svg`.

    {% icon "copy" %} — dekoratif (aria-hidden).
    {% icon "x" label="Tutup" %} — diberi nama aksesibel.
    """
    href = f"{static('img/icons.svg')}#{name}"
    css = f"icon {cls}".strip()
    if label:
        return format_html(
            '<svg class="{}" role="img" aria-label="{}"><use href="{}"></use></svg>', css, label, href
        )
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="{}"></use></svg>', css, href
    )
