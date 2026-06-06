"""
AgentMarket Production Application

A B2A (Business-to-Agent) marketplace platform that enables autonomous AI agents
to discover and transact with business services safely and efficiently.
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from datetime import datetime
from loguru import logger
from contextlib import asynccontextmanager

from agentmarket.api import auth, vendors, transactions, agents
from agentmarket.models.database import init_db
from agentmarket.services.analytics import AnalyticsService
from agentmarket.utils.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("Starting AgentMarket application...")
    
    # Initialize database
    await init_db()
    
    # Initialize analytics service
    analytics = AnalyticsService()
    app.state.analytics = analytics
    
    logger.info("Application startup complete")
    yield
    
    logger.info("Shutting down AgentMarket application...")


# Create FastAPI application
app = FastAPI(
    title="AgentMarket",
    description="The world's first B2A (Business-to-Agent) marketplace built from the ground up for autonomous AI agents.",
    version="2.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Security Middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=settings.ALLOWED_HOSTS.split(",") if settings.ALLOWED_HOSTS else ["*"]
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Call the endpoint
    response = await call_next(request)
    
    # Log the request
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s - "
        f"IP: {request.client.host if request.client else 'unknown'}"
    )
    
    # Track analytics
    if hasattr(app.state, 'analytics'):
        await app.state.analytics.track_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            response_time=process_time,
            user_agent=request.headers.get("user-agent", ""),
            ip_address=request.client.host if request.client else "unknown"
        )
    
    return response


# Core API Routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agent APIs"])


# Agent Discovery Endpoint (The heart of agent-first design)
@app.get("/.well-known/agent-manifest.json")
async def agent_manifest():
    """
    Agent Discovery Manifest - The entry point for autonomous AI agents
    This endpoint provides agents with everything they need to interact with our platform
    """
    return {
        "service_name": "AgentMarket",
        "service_description": "B2A Marketplace for autonomous AI agents",
        "version": "2.0.0",
        "agent_capabilities": {
            "discovery": "GET /api/agents/products for semantic product search",
            "transactions": "Two-phase commit protocol via /api/transactions/dry-run and /api/transactions/commit",
            "authentication": "API key authentication via X-Agent-API-Key header",
            "budget_controls": "Built-in budget validation and human escalation triggers"
        },
        "rules_of_engagement": {
            "currency": "USD",
            "commission_rate": float(settings.COMMISSION_RATE),
            "max_transaction": float(settings.MAX_TRANSACTION_AMOUNT),
            "handshake_ttl_minutes": int(settings.HANDSHAKE_EXPIRE_MINUTES),
            "required_headers": ["X-Agent-API-Key", "User-Agent"],
            "safety_protocol": "ALWAYS perform dry-run validation before committing transactions"
        },
        "endpoints": {
            "product_search": "/api/agents/products",
            "dry_run": "/api/transactions/dry-run",
            "commit": "/api/transactions/commit",
            "status": "/api/agents/status",
            "documentation": "/docs"
        },
        "contact": {
            "support_email": settings.SUPPORT_EMAIL,
            "api_status": "https://status.agentmarket.com",
            "developer_docs": "https://docs.agentmarket.com"
        }
    }


# Web Interface Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page for human visitors"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Vendor dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/demo", response_class=HTMLResponse)
async def live_demo(request: Request):
    """Live demo showing agents making purchases"""
    return templates.TemplateResponse("demo.html", {"request": request})


@app.get("/docs-agent", response_class=HTMLResponse) 
async def agent_documentation(request: Request):
    """Agent integration documentation"""
    return templates.TemplateResponse("agent-docs.html", {"request": request})


# Health check
@app.get("/health")
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.DEBUG,
        log_level="info"
    )