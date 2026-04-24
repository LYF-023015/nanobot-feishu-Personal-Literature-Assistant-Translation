"""Feishu custom bot (webhook) channel for external groups.

Uses a lightweight HTTP server to receive Feishu callback events
and replies via the custom bot webhook URL.

Setup:
1. Create a custom bot in a Feishu group → copy the webhook URL
2. Configure the callback URL in Feishu Open Platform (must be public HTTPS)
3. Set webhook_url and verification_token in config
"""

import asyncio
import base64
import hashlib
import hmac
import json
import threading
from typing import Any

import httpx
from flask import Flask, jsonify, request
from loguru import logger
from werkzeug.serving import make_server

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import FeishuWebhookConfig


class FeishuWebhookChannel(BaseChannel):
    """
    Feishu custom bot channel using webhook callbacks.

    Receives messages via HTTP callback and sends replies via webhook URL.
    Suitable for external groups where self-built app bots cannot be added.
    """

    name = "feishu_webhook"

    def __init__(self, config: FeishuWebhookConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: FeishuWebhookConfig = config
        self._app = Flask(__name__)
        self._server: Any | None = None
        self._server_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register Flask routes."""
        path = self.config.callback_path

        @self._app.route(path, methods=["POST"])
        def callback():
            return self._handle_callback()

        @self._app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "channel": self.name})

    def _handle_callback(self):
        """Handle incoming Feishu callback."""
        try:
            data = request.get_json(force=True, silent=True) or {}
        except Exception:
            data = {}

        # URL verification (first-time setup)
        challenge = data.get("challenge")
        if challenge is not None:
            logger.info("Feishu webhook URL verification received")
            return jsonify({"challenge": challenge})

        # Event callback validation (check token)
        token = data.get("token", "")
        if self.config.verification_token and token != self.config.verification_token:
            logger.warning("Feishu webhook invalid token")
            return jsonify({"code": 403, "msg": "invalid token"})

        # Decrypt payload if encrypt_key is configured
        if self.config.encrypt_key and data.get("encrypt"):
            try:
                payload_json = self._decrypt(data["encrypt"])
                data = json.loads(payload_json)
            except Exception as e:
                logger.error(f"Feishu webhook decrypt failed: {e}")
                return jsonify({"code": 400, "msg": "decrypt failed"})

        # Process event
        event_type = data.get("type", "")
        event = data.get("event", {})

        if event_type == "event_callback" and event.get("type") == "im.message.receive_v1":
            self._process_message_event(event)

        return jsonify({"code": 0, "msg": "ok"})

    def _process_message_event(self, event: dict[str, Any]) -> None:
        """Parse and forward message to the bus."""
        message = event.get("message", {})
        sender = event.get("sender", {})

        sender_type = sender.get("sender_type", "")
        if sender_type == "bot":
            return

        sender_id = ""
        sender_id_obj = sender.get("sender_id", {})
        if isinstance(sender_id_obj, dict):
            sender_id = sender_id_obj.get("open_id", "unknown")

        chat_id = message.get("chat_id", "")
        chat_type = message.get("chat_type", "p2p")
        msg_type = message.get("message_type", "text")
        message_id = message.get("message_id", "")

        # Parse content
        content = ""
        if msg_type == "text":
            try:
                content = json.loads(message.get("content", "{}")).get("text", "")
            except (json.JSONDecodeError, TypeError):
                content = message.get("content", "")
        elif msg_type == "image":
            content = "[image]"
        elif msg_type == "file":
            content = "[file]"
        else:
            content = f"[{msg_type}]"

        # Schedule async handling in the main event loop
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._handle_message(
                    sender_id=sender_id,
                    chat_id=chat_id if chat_type == "group" else sender_id,
                    content=content,
                    metadata={
                        "message_id": message_id,
                        "chat_type": chat_type,
                        "msg_type": msg_type,
                        "channel_name": "feishu_webhook",
                    },
                ),
                self._loop,
            )

    def _decrypt(self, encrypt: str) -> str:
        """Decrypt Feishu encrypted payload."""
        key = hashlib.sha256(self.config.encrypt_key.encode("utf-8")).digest()
        # Feishu uses AES-256-CBC with SHA256 hashed key
        # Simplified: return as-is if decrypt not fully implemented
        # Full implementation requires cryptography library
        import base64

        # Feishu encrypt format: base64(AES-256-CBC(plaintext))
        # Key = SHA256(encrypt_key)
        # IV = first 16 bytes of key
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            ciphertext = base64.b64decode(encrypt)
            iv = key[:16]
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            # Remove PKCS7 padding
            pad_len = plaintext[-1]
            plaintext = plaintext[:-pad_len]
            return plaintext.decode("utf-8")
        except ImportError:
            logger.warning("cryptography library not installed, cannot decrypt Feishu payload")
            raise
        except Exception:
            raise

    async def start(self) -> None:
        """Start the HTTP callback server."""
        self._running = True
        self._loop = asyncio.get_running_loop()

        host = "0.0.0.0"
        port = self.config.callback_port

        self._server = make_server(host, port, self._app, threaded=True)

        def run_server():
            logger.info(f"Feishu webhook server started on http://{host}:{port}{self.config.callback_path}")
            self._server.serve_forever()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the HTTP callback server."""
        self._running = False
        if self._server:
            self._server.shutdown()
            logger.info("Feishu webhook server stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message via the custom bot webhook."""
        if not self.config.webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return

        payload = self._build_payload(msg)
        if not payload:
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.config.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                if result.get("code") != 0:
                    logger.warning(f"Feishu webhook send failed: {result}")
        except Exception as e:
            logger.error(f"Feishu webhook send error: {e}")

    def _build_payload(self, msg: OutboundMessage) -> dict[str, Any] | None:
        """Build Feishu custom bot payload from OutboundMessage."""
        content = msg.content or ""

        # Check for card prefix
        if content.startswith("🎴CARD:"):
            try:
                card_json = json.loads(content[7:])
                return {"msg_type": "interactive", "card": card_json}
            except json.JSONDecodeError:
                logger.warning("Invalid card JSON, falling back to text")

        # Check if content looks like markdown with formatting
        if "**" in content or "```" in content or "#" in content:
            # Render as interactive card for better formatting
            card = self._text_to_card(content)
            return {"msg_type": "interactive", "card": card}

        # Plain text
        return {"msg_type": "text", "content": {"text": content}}

    @staticmethod
    def _text_to_card(text: str) -> dict[str, Any]:
        """Convert markdown text to a simple Feishu card."""
        elements = []
        for line in text.split("\n"):
            if line.strip():
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": line},
                })

        return {
            "config": {"wide_screen_mode": True},
            "elements": elements,
        }
