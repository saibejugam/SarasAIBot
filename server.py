from fastapi import FastAPI, Request, HTTPException, Query
from dotenv import load_dotenv
import os
import logging
from datetime import datetime
import uvicorn
from typing import Optional
import httpx

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(title="Webhook Receiver")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PORT = int(os.getenv("PORT", "3000"))
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

@app.get("/")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[int] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Endpoint for webhook verification (GET)

    Expects query params: hub.mode, hub.challenge, hub.verify_token
    Returns the challenge when verified, otherwise 403.
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logging.info("WEBHOOK VERIFIED")
        # Respond with the challenge string
        return hub_challenge

    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/")
async def receive_webhook(request: Request):
    """Endpoint for receiving webhook events (POST)

    Logs the timestamp and request body, then returns 200 OK.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        body = await request.json()
    except Exception:
        body = await request.body()

    logging.info("\n\nWebhook received %s\n", timestamp)
    logging.info("%s", body)

    # Extract nested value from WhatsApp webhook structure
    try:
        entry = body.get("entry", []) if isinstance(body, dict) else []
        changes = entry[0].get("changes", []) if entry else []
        value = changes[0].get("value", {}) if changes else {}
    except Exception:
        value = {}

    logging.info("entry: %s", entry)
    logging.info("changes: %s", changes)
    logging.info("value: %s", value)

    # Extract phone_number_id
    phone_number_id = None
    try:
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")
    except Exception:
        phone_number_id = None

    logging.info("phone_number_id: %s", phone_number_id)

    # Extract sender 'from' or wa_id
    from_number = None
    content = "No content"
    timestamp = None
    ignore_message = False
    try:
        messages = value.get("messages", {})
        if messages and isinstance(messages, list):
            from_number = messages[0].get("from")
            content = messages[0].get("text", {}).get("body", "No text content")
            timestamp = messages[0].get("timestamp")
    except Exception:
        from_number = None

    logging.info("from_number: %s", from_number)
    logging.info("content: %s", content)
    logging.info("timestamp: %s", timestamp)

    if timestamp:
        try:
            message_time = datetime.utcfromtimestamp(int(timestamp))
            now = datetime.utcnow()
            if (now - message_time).total_seconds() > 120:
                logging.error("Received message is older than 2 minutes (timestamp: %s)", timestamp)
                ignore_message = True
        except Exception as e:
            logging.error("Error parsing timestamp: %s", str(e))


    # If we have necessary fields, call the external analysis API and then send its reply via Graph API
    if phone_number_id and from_number and not ignore_message:
        # Call the external POST endpoint with the incoming message as `body`
        reply_text = None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                external_resp = await client.post(
                    "https://stockanalyzer-wk3v.onrender.com/whatsapp/webhook",
                    json={"body": content},
                )
                external_resp.raise_for_status()
                try:
                    external_json = external_resp.json()
                except Exception:
                    external_json = {"status_code": external_resp.status_code, "text": external_resp.text}

                logging.info("External API response: %s", external_json)
                reply_text = external_json.get("reply")
        except httpx.HTTPStatusError as e:
            logging.error("External API returned error: %s %s", e.response.status_code, e.response.text)
        except Exception as e:
            logging.exception("Unexpected error calling external API: %s", str(e))

        if not reply_text:
            logging.error("No reply returned from external API; not sending a message")
            return {"status": "received", "note": "no reply from external API"}

        endpoint = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": f"{from_number}",
            "type": "text",
            "text": {"body": reply_text},
        }

        if not AUTH_TOKEN:
            logging.error("AUTH_TOKEN not configured")
            raise HTTPException(status_code=500, detail="Server not configured for outbound messages")

        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"status_code": resp.status_code, "text": resp.text}

                logging.info("Sent template message, response: %s", resp_json)
                return {"status": "sent", "provider_response": resp_json}

        except httpx.HTTPStatusError as e:
            logging.error("Graph API returned error: %s %s", e.response.status_code, e.response.text)
            raise HTTPException(status_code=502, detail="Failed to send message to provider")
        except Exception as e:
            logging.exception("Unexpected error sending message: %s", str(e))
            raise HTTPException(status_code=500, detail="Unexpected error while sending message")

    # Acknowledge receipt if we couldn't send an outbound message
    return {"status": "received", "note": "no outbound message sent"}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8005,
        log_level="info"
    )