"""
Voice API endpoints — Phase 5.

Twilio webhook handlers for real-time voice call processing.

Endpoints
---------
POST /api/v1/voice/inbound
    Initial call from Twilio — creates session, returns TwiML greeting.

POST /api/v1/voice/gather
    Twilio posts SpeechResult after <Gather> — runs agent, returns TwiML reply.

POST /api/v1/voice/status
    Twilio call status callback — keeps session status in sync.

GET  /api/v1/voice/sessions
    List active (or all) call sessions for monitoring dashboards.

GET  /api/v1/voice/sessions/{call_sid}
    Retrieve a single call session by CallSid.

WS   /api/v1/voice/stream/{call_sid}
    Twilio Media Stream WebSocket.  Receives mulaw audio, forwards to Deepgram
    live STT, and broadcasts real-time transcripts back to the WebSocket client.
    Configure in TwiML via <Start><Stream url="wss://{domain}/api/v1/voice/stream/{call_sid}"/></Start>

Webhook signature validation
-----------------------------
Set TWILIO_VALIDATE_WEBHOOKS=true and supply TWILIO_AUTH_TOKEN to enable
HMAC-SHA1 request validation in production.  Disabled by default for
local development.

Form data note
--------------
Twilio sends webhook payloads as application/x-www-form-urlencoded.
``request.form()`` is used directly to avoid the Python reserved-word
conflict with the ``From`` field.
"""

from __future__ import annotations

import base64
import json
from typing import Optional

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import Response

from app.config import Settings, get_settings
from app.dependencies import get_voice_service
from app.schemas.voice import CallSessionResponse, VoiceSessionsResponse
from app.services.voice_service import VoiceService

router = APIRouter()
log = structlog.get_logger(__name__)

_TWIML_CONTENT_TYPE = "application/xml"


# ---------------------------------------------------------------------------
# Security helper
# ---------------------------------------------------------------------------

async def _verify_twilio_signature(
    request: Request,
    settings: Settings,
) -> None:
    """
    Validate the X-Twilio-Signature header if webhook validation is enabled.

    Raises HTTP 403 on invalid signature.
    Silently passes when validation is disabled (local dev) or twilio package
    is not installed.
    """
    if not settings.twilio_validate_webhooks or not settings.twilio_auth_token:
        return

    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        log.warning("twilio_not_installed_skipping_signature_validation")
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    # request.form() is cached by Starlette after first access
    form_data = dict(await request.form())

    validator = RequestValidator(settings.twilio_auth_token)
    if not validator.validate(url, form_data, signature):
        log.warning("twilio_invalid_signature", url=url)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio webhook signature.",
        )


# ---------------------------------------------------------------------------
# Twilio webhook endpoints
# ---------------------------------------------------------------------------

@router.post("/inbound", response_class=Response)
async def voice_inbound(
    request: Request,
    voice_service: VoiceService = Depends(get_voice_service),
    settings: Settings = Depends(get_settings),
) -> Response:
    """
    Twilio inbound call webhook.

    Creates a call session backed by a ConversalQ conversation and returns
    TwiML that greets the caller and opens the first Gather.

    Twilio configuration: set this as the Voice webhook URL for your phone number.
    """
    await _verify_twilio_signature(request, settings)

    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    from_number = str(form.get("From", ""))
    to_number = str(form.get("To", ""))

    log.info("voice_inbound_webhook", call_sid=call_sid, from_number=from_number)

    if not call_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing CallSid in webhook payload.",
        )

    twiml = await voice_service.handle_inbound_call(
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
    )
    return Response(content=twiml, media_type=_TWIML_CONTENT_TYPE)


@router.post("/gather", response_class=Response)
async def voice_gather(
    request: Request,
    voice_service: VoiceService = Depends(get_voice_service),
    settings: Settings = Depends(get_settings),
) -> Response:
    """
    Twilio Gather result webhook.

    Receives the caller's transcribed speech, runs it through the multi-agent
    graph, and returns TwiML with the agent's spoken response plus the next Gather.

    Twilio configuration: set as the ``action`` URL on all <Gather> verbs.
    """
    await _verify_twilio_signature(request, settings)

    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech_result: Optional[str] = form.get("SpeechResult")  # type: ignore[assignment]
    confidence_raw = form.get("Confidence")
    confidence: Optional[float] = float(confidence_raw) if confidence_raw else None

    log.info(
        "voice_gather_webhook",
        call_sid=call_sid,
        has_speech=speech_result is not None,
        confidence=confidence,
    )

    if not call_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing CallSid in webhook payload.",
        )

    twiml = await voice_service.handle_gather(
        call_sid=call_sid,
        speech_result=speech_result,
        confidence=confidence,
    )
    return Response(content=twiml, media_type=_TWIML_CONTENT_TYPE)


@router.post("/status", response_class=Response, responses={204: {"description": "No Content"}})
async def voice_status(
    request: Request,
    voice_service: VoiceService = Depends(get_voice_service),
    settings: Settings = Depends(get_settings),
) -> Response:
    """
    Twilio call status callback.

    Keeps the call session status in sync with Twilio's lifecycle events
    (ringing, in-progress, completed, failed, busy, no-answer, canceled).

    Twilio configuration: set as the ``statusCallback`` URL on your phone number
    and include statusCallbackEvent=completed,failed.
    """
    await _verify_twilio_signature(request, settings)

    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))

    log.info("voice_status_webhook", call_sid=call_sid, call_status=call_status)

    if call_sid and call_status:
        await voice_service.handle_call_status(call_sid, call_status)

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Monitoring / introspection endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=VoiceSessionsResponse)
async def list_voice_sessions(
    active_only: bool = True,
    voice_service: VoiceService = Depends(get_voice_service),
) -> VoiceSessionsResponse:
    """
    List voice call sessions.

    - ``active_only=true``  (default): returns in-progress calls only.
    - ``active_only=false``: returns all calls including completed/failed.
    """
    sessions = (
        voice_service.list_active_sessions()
        if active_only
        else voice_service.list_all_sessions()
    )
    return VoiceSessionsResponse(
        total=len(sessions),
        sessions=[
            CallSessionResponse(
                call_sid=s.call_sid,
                conversation_id=s.conversation_id,
                from_number=s.from_number,
                to_number=s.to_number,
                status=s.status,
                turn_count=s.turn_count,
                escalated=s.escalated,
                created_at=s.created_at,
                updated_at=s.updated_at,
                transcript_log=s.transcript_log,
            )
            for s in sessions
        ],
    )


@router.get("/sessions/{call_sid}", response_model=CallSessionResponse)
async def get_voice_session(
    call_sid: str,
    voice_service: VoiceService = Depends(get_voice_service),
) -> CallSessionResponse:
    """Retrieve a single call session by its Twilio CallSid."""
    session = voice_service.get_session(call_sid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call session '{call_sid}' not found.",
        )
    return CallSessionResponse(
        call_sid=session.call_sid,
        conversation_id=session.conversation_id,
        from_number=session.from_number,
        to_number=session.to_number,
        status=session.status,
        turn_count=session.turn_count,
        escalated=session.escalated,
        created_at=session.created_at,
        updated_at=session.updated_at,
        transcript_log=session.transcript_log,
    )


# ---------------------------------------------------------------------------
# WebSocket — Twilio Media Stream live transcription
# ---------------------------------------------------------------------------

@router.websocket("/stream/{call_sid}")
async def voice_stream_ws(
    websocket: WebSocket,
    call_sid: str,
) -> None:
    """
    Twilio Media Stream WebSocket endpoint.

    Receives base64-encoded mulaw audio from Twilio, forwards to Deepgram
    live STT, and broadcasts final transcript segments back to the client
    as JSON ``{"event": "transcript", "transcript": "...", "call_sid": "..."}``.

    Requires ``DEEPGRAM_API_KEY`` to be set; silently buffers if unavailable.

    TwiML to activate:
      <Start>
        <Stream url="wss://{your-domain}/api/v1/voice/stream/{call_sid}"/>
      </Start>
    """
    from app.voice.call_session import add_transcript
    from app.voice.stt import get_stt_service

    await websocket.accept()
    log.info("voice_stream_connected", call_sid=call_sid)

    stt = get_stt_service()
    stream_sid: Optional[str] = None
    dg_connection = None

    # Connect Deepgram live client if available
    if stt.is_available:
        try:
            from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

            dg_client = DeepgramClient(api_key=stt._api_key)
            dg_connection = dg_client.listen.asynclive.v("1")

            async def _on_transcript(self_inner, result, **kwargs) -> None:  # noqa: ANN001
                try:
                    alt = result.channel.alternatives[0]
                    transcript: str = alt.transcript
                    if transcript and result.is_final:
                        log.info("voice_stream_transcript", call_sid=call_sid, transcript=transcript)
                        add_transcript(call_sid, "user_live", transcript)
                        await websocket.send_text(
                            json.dumps({
                                "event": "transcript",
                                "transcript": transcript,
                                "call_sid": call_sid,
                            })
                        )
                except Exception as exc:  # noqa: BLE001
                    log.warning("voice_stream_transcript_handler_error", error=str(exc))

            dg_connection.on(LiveTranscriptionEvents.Transcript, _on_transcript)

            options = LiveOptions(
                model="nova-2",
                encoding="mulaw",
                sample_rate=8000,
                channels=1,
                punctuate=True,
                interim_results=False,
            )
            await dg_connection.start(options)
            log.info("voice_stream_deepgram_live_started", call_sid=call_sid)

        except Exception as exc:
            log.warning("voice_stream_deepgram_init_failed", error=str(exc))
            dg_connection = None

    # Main receive loop
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            event_type = data.get("event")

            if event_type == "connected":
                log.debug("voice_stream_twilio_connected", call_sid=call_sid)

            elif event_type == "start":
                stream_sid = data.get("streamSid")
                log.info("voice_stream_started", call_sid=call_sid, stream_sid=stream_sid)

            elif event_type == "media":
                media = data.get("media", {})
                if media.get("track") == "inbound":
                    payload = base64.b64decode(media.get("payload", ""))
                    if dg_connection:
                        await dg_connection.send(payload)

            elif event_type == "stop":
                log.info("voice_stream_twilio_stop", call_sid=call_sid)
                break

    except WebSocketDisconnect:
        log.info("voice_stream_client_disconnected", call_sid=call_sid)
    except Exception as exc:
        log.error("voice_stream_error", call_sid=call_sid, error=str(exc))
    finally:
        if dg_connection:
            try:
                await dg_connection.finish()
            except Exception:
                pass
        log.info("voice_stream_closed", call_sid=call_sid)
