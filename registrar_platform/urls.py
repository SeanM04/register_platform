from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('dashboard.urls')),
    path("", include("accounts.urls")),
    path('admin/', admin.site.urls),
    path('api/chatbot/', include('chatbot.urls', namespace='chatbot')),
]
