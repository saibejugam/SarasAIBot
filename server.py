# listen for request(post) from whatsapp
# query the database for user's data
# send the user query and user data to the agent
# wait for the agent to respond
# send the agent's response back to whatsapp

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer
from starlette.authentication import AuthCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import httpx
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# MongoDB Atlas connection string from environment variable
MONGODB_URL = os.getenv("MONGODB_URL")
# Agent service URL from environment variable
AGENT_URL = os.getenv("AGENT_URL")  # e.g., https://agrigpt-backend-agent.onrender.com/chat
# Authentication token from environment variable
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

# Security setup
security = HTTPBearer()

async def verify_token(credentials = Depends(security)):
    """
    Verify the authentication token from request headers
    
    Args:
        credentials: HTTP Bearer credentials from Authorization header
        
    Raises:
        HTTPException: If token is invalid or missing
        
    Returns:
        str: The authenticated token
    """
    token = credentials.credentials
    if not AUTH_TOKEN:
        raise HTTPException(status_code=500, detail="Authentication not configured")
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return token


# Initialize FastAPI app with lifespan handler
app = FastAPI(
    title="WhatsApp Bot Service",
    description="Service to handle WhatsApp messages and interact with AI agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WHATSAPP_ORIGIN")] if os.getenv("WHATSAPP_ORIGIN") else ["*"],  # Allow specific origin or all if not set
    allow_methods=["GET", "POST"],
)

class WhatsAppRequest(BaseModel):
    """
    Request model for incoming WhatsApp messages
    """
    phoneNumber: str
    message: str

@app.get("/")
async def root():
    """
    Root endpoint - Returns service information and available endpoints
    
    Returns:
        dict: Service status and endpoint information
    """
    return {
        "status": "healthy",
        "service": "WhatsApp Bot Service",
        "version": "1.0.0",
        "endpoints": {
            "root": "GET / (Service info)",
            "health": "GET /health",
            "whatsapp": "POST /whatsapp (Main endpoint)",
            "docs": "GET /docs (Swagger UI)",
            "redoc": "GET /redoc (ReDoc UI)"
        }
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint - Returns service health status and database connection
    
    Returns:
        dict: Health status of the service and its dependencies
    """
    
    # Check agent service availability (optional quick check)
    agent_status = "unknown"
    if AGENT_URL:
        agent_status = "configured"
    else:
        agent_status = "not configured"
    
    return {
        "status": "healthy",
        "service": "WhatsApp Bot Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "agent_service": agent_status
        }
    }


@app.post("/whatsapp")
async def handle_whatsapp_request(req: WhatsAppRequest, token: str = Depends(verify_token)):
    """
    Main endpoint to handle incoming WhatsApp messages
    Requires valid authentication token in Authorization header
    
    Flow:
    1. Verify authentication token
    2. Receive request from WhatsApp
    3. Return agent response to WhatsApp
    
    Args:
        req: WhatsAppRequest containing phoneNumber and message
        token: Authentication token from Authorization header (verified by verify_token dependency)
        
    Returns:
        dict: Agent's response (phoneNumber and message)
    """
    # Step 1: Query the database for user's data (creates user if not exists)
    #user_data = await query_database(req.phoneNumber)

    # Step 2: Send the user query and user data to the agent
    #agent_response = await send_to_agent(req.message, user_data)

    # Step 3: Send the agent's response back to WhatsApp
    # Return the agent's response as-is
    return {"phoneNumber": req.phoneNumber, "message": req.message}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8005,
        log_level="info"
    )