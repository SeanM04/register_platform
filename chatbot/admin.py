from django.contrib import admin
from django.utils import timezone

from .models import ChatMessage, ChatResponseCache, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = ("role", "content", "created_at")
    readonly_fields = ("role", "content", "created_at")
    extra = 0
    max_num = 0
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("session_key_short", "user", "started_at", "last_active", "message_count")
    list_filter = ("user",)
    search_fields = ("session_key", "user__username", "user__email")
    readonly_fields = ("session_key", "user", "started_at", "last_active")
    inlines = [ChatMessageInline]

    def session_key_short(self, obj):
        return obj.session_key[:16] + "…"
    session_key_short.short_description = "Session key"

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "content_short", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "session__session_key", "session__user__username")
    readonly_fields = ("session", "role", "content", "created_at")

    def content_short(self, obj):
        return obj.content[:80]
    content_short.short_description = "Content"


@admin.register(ChatResponseCache)
class ChatResponseCacheAdmin(admin.ModelAdmin):
    list_display = ("cache_key_short", "created_at", "expires_at", "valid")
    readonly_fields = ("cache_key", "response", "created_at", "expires_at")
    actions = ["purge_expired"]

    def cache_key_short(self, obj):
        return obj.cache_key[:16] + "…"
    cache_key_short.short_description = "Cache key"

    def valid(self, obj):
        return obj.is_valid
    valid.boolean = True
    valid.short_description = "Valid"

    @admin.action(description="Purge expired cache entries")
    def purge_expired(self, request, queryset):
        deleted, _ = ChatResponseCache.objects.filter(expires_at__lt=timezone.now()).delete()
        self.message_user(request, f"Purged {deleted} expired cache entries.")
