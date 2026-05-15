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

Streaming endpoint (chatbot_message_stream)
-------------------------------------------
Emits Server-Sent Events so the browser can show live progress while the
chatbot service builds context and calls the AI provider.  Event format:

    data: {"type":"status","step":"Querying the database…"}
    data: {"type":"reply","reply":"…","source":"google","diagnostics":{…}}
    data: {"type":"error","error":"…"}

The session / DB persistence logic is identical to the non-streaming endpoint.
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass

from asgiref.sync import sync_to_async
from django.http import JsonResponse, StreamingHttpResponse
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
    return hashlib.sha256(raw.encode()).hexdigest()


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


def _load_sync_session(request) -> tuple:
    """Ensure a session key exists and return (ChatSession, history list)."""
    if not request.session.session_key:
        request.session.create()
    chat_session, _ = ChatSession.objects.get_or_create(
        session_key=request.session.session_key,
        defaults={"user": request.user},
    )
    raw = chat_session.messages.order_by("-created_at")[:HISTORY_WINDOW]
    history = [{"role": m.role, "content": m.content} for m in reversed(list(raw))]
    return chat_session, history


def _call_service(message, filters, history, session_id=None) -> tuple:
    """Call get_chatbot_reply and return (payload, error_response).

    On success: (dict, None). On error: (None, JsonResponse).
    """
    try:
        return get_chatbot_reply(message, filters=filters, history=history, session_id=session_id), None
    except ValueError as exc:
        return None, JsonResponse({"error": str(exc)}, status=400)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error from chatbot service")
        return None, JsonResponse({"error": "An internal error occurred."}, status=500)


def _persist_sync_reply(chat_session, message: str, reply: str, source: str, cache_key: str) -> None:
    """Save the conversation turn to the DB and update the response cache if applicable."""
    ChatMessage.objects.bulk_create([
        ChatMessage(session=chat_session, role=ChatMessage.ROLE_USER, content=message),
        ChatMessage(session=chat_session, role=ChatMessage.ROLE_ASSISTANT, content=reply),
    ])
    chat_session.save(update_fields=["last_active"])
    if source == "rules":
        _cache_set(cache_key, reply)


@require_POST
@ajax_login_required
def chatbot_message(request):
    """Non-streaming JSON endpoint — returns the full reply in one response."""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    message = str(payload.get("message") or "").strip()
    filters = payload.get("filters") or {}
    if not message:
        return JsonResponse({"error": "A message is required."}, status=400)

    chat_session, history = _load_sync_session(request)
    cache_key = _make_cache_key(message, filters)
    cached = _cache_get(cache_key)
    if cached:
        return JsonResponse({
            "reply": cached, "source": "cache", "source_label": "Cache",
            "diagnostics": {"returned_source": "cache", "cache_hit": True},
        })

    response_payload, err = _call_service(message, filters, history, session_id=request.session.session_key)
    if err:
        return err

    _persist_sync_reply(
        chat_session, message,
        response_payload.get("reply", ""),
        response_payload.get("source", "rules"),
        cache_key,
    )
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


# ---------------------------------------------------------------------------
# Streaming endpoint — Server-Sent Events
# ---------------------------------------------------------------------------

def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


@dataclass
class _StreamCtx:
    """Bundles per-request data passed between the streaming view and its helpers."""
    message: str
    filters: dict
    history: list
    chat_session: object  # ChatSession instance
    cache_key: str


async def _load_session(request) -> tuple:
    """Ensure a session key exists and return (ChatSession, history list)."""
    if not request.session.session_key:
        await sync_to_async(request.session.create)()
    chat_session, _ = await ChatSession.objects.aget_or_create(
        session_key=request.session.session_key,
        defaults={"user": request.user},
    )
    raw = await sync_to_async(list)(
        chat_session.messages.order_by("-created_at")[:HISTORY_WINDOW]
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(raw)]
    return chat_session, history


@require_POST
@ajax_login_required
async def chatbot_message_stream(request):
    """
    Async streaming variant of chatbot_message using Server-Sent Events.

    Emits SSE events as the chatbot service progresses through its stages:
      {"type":"status","step":"Querying the database…"}
      {"type":"reply","reply":"…","source":"…","diagnostics":{…}}
      {"type":"error","error":"…"}

    The service runs in asyncio's thread-pool executor (asyncio.to_thread) so
    it never blocks the event loop.  Client disconnects are detected via
    request.is_disconnected() and the service task is cancelled immediately,
    preventing wasted DB queries and AI API calls.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    message = str(payload.get("message", "") or "").strip()
    if not message:
        return JsonResponse({"error": "A message is required."}, status=400)

    chat_session, history = await _load_session(request)
    filters = payload.get("filters") or {}
    cache_key = _make_cache_key(message, filters)

    cached = await sync_to_async(_cache_get)(cache_key)
    if cached:
        return _stream_cached_reply(cached)

    ctx = _StreamCtx(message, filters, history, chat_session, cache_key)
    return _stream_service_reply(request, ctx)


def _stream_cached_reply(cached: str) -> StreamingHttpResponse:
    """Return a StreamingHttpResponse that immediately emits a cached reply."""
    async def _gen():
        yield _sse({"type": "status", "step": "Retrieving saved answer\u2026"})
        yield _sse({
            "type": "reply",
            "reply": cached,
            "source": "cache",
            "source_label": "Cache",
            "diagnostics": {"returned_source": "cache", "cache_hit": True},
        })

    resp = StreamingHttpResponse(_gen(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


def _stream_service_reply(request, ctx: _StreamCtx) -> StreamingHttpResponse:
    """Return a StreamingHttpResponse that runs the chatbot service asynchronously."""
    loop = None  # captured lazily inside the async generator

    async def _gen():
        nonlocal loop
        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue = asyncio.Queue()

        def _on_status(step: str) -> None:
            loop.call_soon_threadsafe(event_queue.put_nowait, {"type": "status", "step": step})

        service_task = asyncio.create_task(
            _run_service(ctx.message, ctx.filters, ctx.history, event_queue, _on_status,
                         session_id=request.session.session_key)
        )

        try:
            async for event in _drain_queue(request, event_queue, service_task):
                if event["type"] == "_done":
                    await _persist_and_cache(event, ctx.chat_session, ctx.message, ctx.cache_key)
                    payload = {k: v for k, v in event.items() if k != "type"}
                    yield _sse({"type": "reply", **payload})
                    break
                if event["type"] == "error":
                    yield _sse(event)
                    break
                yield _sse(event)
        except GeneratorExit:
            service_task.cancel()

    resp = StreamingHttpResponse(_gen(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


async def _run_service(message, filters, history, event_queue, on_status, session_id=None) -> None:
    """Run get_chatbot_reply in the thread-pool executor and push the result onto the queue."""
    try:
        result = await asyncio.to_thread(
            get_chatbot_reply,
            message,
            filters=filters,
            history=history,
            status_callback=on_status,
            session_id=session_id,
        )
        await event_queue.put({"type": "_done", **result})
    except ValueError as exc:
        await event_queue.put({"type": "error", "error": str(exc)})
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error from chatbot service (stream)")
        await event_queue.put({"type": "error", "error": "An internal error occurred."})


async def _drain_queue(request, event_queue: asyncio.Queue, service_task: asyncio.Task):
    """Async generator that yields events from the queue until done or client disconnects.

    Disconnect detection requires an ASGI request (e.g. uvicorn).  Under WSGI
    (manage.py runserver / gunicorn) the attribute is absent — we skip the
    check and let the stream finish naturally.
    """
    _can_detect_disconnect = hasattr(request, "is_disconnected")
    while True:
        if _can_detect_disconnect and await request.is_disconnected():
            service_task.cancel()
            return
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        yield event
        if event["type"] in ("_done", "error"):
            break


async def _persist_and_cache(event: dict, chat_session, message: str, cache_key: str) -> None:
    """Persist the conversation turn to DB and optionally update the response cache."""
    reply = event.get("reply", "")
    source = event.get("source", "rules")

    await ChatMessage.objects.abulk_create([
        ChatMessage(session=chat_session, role=ChatMessage.ROLE_USER, content=message),
        ChatMessage(session=chat_session, role=ChatMessage.ROLE_ASSISTANT, content=reply),
    ])
    await chat_session.asave(update_fields=["last_active"])

    if source == "rules":
        await sync_to_async(_cache_set)(cache_key, reply)
