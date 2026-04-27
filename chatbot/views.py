"""
AJAX endpoints for the UniStudio platform chatbot.

Session lifecycle
-----------------
1. The browser's Django session key is used as the chatbot session identifier.
2. On every POST we get-or-create a ChatSession row tied to that key and the
   logged-in user.
3. Full conversation history is loaded from ChatMessage rows (DB), so the
   frontend does NOT need to manage or replay history in its payload.
4. After a successful AI reply, both the user message and the assistant reply
   are persisted as ChatMessage rows.
"""

import hashlib
import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import ajax_login_required
from services.chatbot_service import get_chatbot_reply

from .models import ChatMessage, ChatResponseCache, ChatSession

logger = logging.getLogger(__name__)

# How many recent turns to feed into the AI context (matches prototype)
HISTORY_WINDOW = 16

# Cache TTL seconds — mirrors CACHE_TTL_SECS from the standalone prototype
CACHE_TTL_SECONDS = 3600


def _make_cache_key(message: str, filters: dict) -> str:
    scope = "|".join([
        str(filters.get("year", "") or ""),
        str(filters.get("period", "") or ""),
        str(filters.get("faculty", "") or ""),
    ])
    raw = f"{message.lower().strip()}|{scope}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    entry = ChatResponseCache.objects.filter(cache_key=key).first()
    if entry and entry.is_valid:
        return entry.response
    if entry:
        entry.delete()
    return None


def _cache_set(key: str, response: str) -> None:
    expiry = timezone.now() + timezone.timedelta(seconds=CACHE_TTL_SECONDS)
    ChatResponseCache.objects.update_or_create(
        cache_key=key,
        defaults={"response": response, "expires_at": expiry},
    )


@require_POST
@ajax_login_required
def chatbot_message(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    message = str(payload.get("message", "") or "").strip()
    filters = payload.get("filters") or {}

    if not message:
        return JsonResponse({"error": "A message is required."}, status=400)

    # Ensure the Django session has a key so we can link the chatbot session to it
    if not request.session.session_key:
        request.session.create()

    # Retrieve or create the chatbot session for this browser session + user
    chat_session, _ = ChatSession.objects.get_or_create(
        session_key=request.session.session_key,
        defaults={"user": request.user},
    )

    # Build history from the DB — no client-supplied history needed
    db_messages = (
        chat_session.messages.order_by("-created_at")[:HISTORY_WINDOW]
    )
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(list(db_messages))
    ]

    # Check the response cache for cacheable, tool-free queries
    cache_key = _make_cache_key(message, filters)
    cached = _cache_get(cache_key)
    if cached:
        return JsonResponse(
            {
                "reply": cached,
                "source": "cache",
                "source_label": "Cache",
                "diagnostics": {"returned_source": "cache", "cache_hit": True},
            }
        )

    try:
        response_payload = get_chatbot_reply(message, filters=filters, history=history)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except Exception:
        logger.exception("Unexpected error from chatbot service")
        return JsonResponse({"error": "An internal error occurred."}, status=500)

    reply = response_payload.get("reply", "")
    source = response_payload.get("source", "rules")

    # Persist this turn to the DB
    ChatMessage.objects.bulk_create(
        [
            ChatMessage(session=chat_session, role=ChatMessage.ROLE_USER, content=message),
            ChatMessage(session=chat_session, role=ChatMessage.ROLE_ASSISTANT, content=reply),
        ]
    )
    # Refresh last_active via auto_now
    chat_session.save(update_fields=["last_active"])

    # Cache rule-based / static replies so identical questions skip the AI call
    if source == "rules":
        _cache_set(cache_key, reply)

    return JsonResponse(response_payload)


@require_POST
@ajax_login_required
def chatbot_clear(request):
    """
    Clear the conversation history for the current session.
    Useful for a 'New conversation' button in the UI.
    """
    if not request.session.session_key:
        return JsonResponse({"cleared": False})

    deleted, _ = ChatMessage.objects.filter(
        session__session_key=request.session.session_key,
        session__user=request.user,
    ).delete()

    return JsonResponse({"cleared": True, "messages_deleted": deleted})
