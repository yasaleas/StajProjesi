import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from chat import routing 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mesajlasma_projesi.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # WebSocket bağlantıları için:
    "websocket": AllowedHostsOriginValidator( 
        AuthMiddlewareStack( 
            URLRouter(
                routing.websocket_urlpatterns # Bu satırda 'core' kullanılıyor
            )
        )
    ),
})