from django.conf import settings


def site(request):
    """Data brand untuk semua template. Fase 02: diambil dari SiteSetting."""
    return {
        "brand": {
            "name": settings.BRAND_NAME,
            "tagline": settings.BRAND_TAGLINE,
            "admin_whatsapp": "",
            "instagram": "",
            "contact_email": "",
        },
        "SITE_URL": settings.SITE_URL,
        "DEBUG": settings.DEBUG,
    }
