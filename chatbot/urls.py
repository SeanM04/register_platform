from django.urls import path

from .views import chatbot_clear, chatbot_message

app_name = "chatbot"

urlpatterns = [
    path("api/chatbot/message/", chatbot_message, name="message"),
    path("api/chatbot/clear/", chatbot_clear, name="clear"),
]
