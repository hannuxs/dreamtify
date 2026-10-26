from django.conf import settings

from .models import SiteSetting


def site(request):
    """Data brand untuk semua template (dari SiteSetting)."""
    setting = SiteSetting.load()
    return {
        "brand": {
            "name": setting.brand_name,
            "tagline": setting.tagline,
            "admin_whatsapp": setting.admin_whatsapp,
            "instagram": setting.instagram,
            "contact_email": setting.contact_email,
        },
        "SITE_URL": settings.SITE_URL,
        "DEBUG": settings.DEBUG,
    }
