from fastapi import FastAPI, Request, HTTPException, Query
from dotenv import load_dotenv
import os
import logging
from datetime import datetime
import uvicorn
from typing import Optional

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(title="Webhook Receiver")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PORT = int(os.getenv("PORT", "3000"))

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

    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8005,
        log_level="info"
    )