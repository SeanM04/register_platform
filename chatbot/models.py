"""
Chatbot persistence models.

These three tables replace the standalone prototype's SQLite MemoryDB and
store everything in the platform's primary PostgreSQL database.

  ChatSession      → sessions table in the prototype
  ChatMessage      → conversations table in the prototype
  ChatResponseCache → response_cache table in the prototype (TTL-based)
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatSession(models.Model):
    """One logical conversation thread per browser/Django session."""

    session_key = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_active"]

    def __str__(self):
        user_label = self.user.username if self.user_id else "anonymous"
        return f"ChatSession({user_label}, {self.session_key[:12]}…)"


class ChatMessage(models.Model):
    """Single turn (user or assistant) inside a ChatSession."""

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        short = self.content[:60].replace("\n", " ")
        return f"[{self.role}] {short}"


class ChatResponseCache(models.Model):
    """
    TTL-keyed response cache — avoids repeated AI calls for identical queries.

    cache_key  : MD5 hex of the normalised message text
    expires_at : absolute timestamp after which the entry is stale
    """

    cache_key = models.CharField(max_length=64, unique=True, db_index=True)
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cache({self.cache_key[:12]}… expires {self.expires_at:%Y-%m-%d %H:%M})"

    @property
    def is_valid(self) -> bool:
        return timezone.now() < self.expires_at
