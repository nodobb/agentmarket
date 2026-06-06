import uuid
import time
import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, status, Request
from pydantic import BaseModel, Field

app = FastAPI(
    title="AgentMarket API",
    description="The world's first B2A (Business-to-Agent) marketplace built from the ground up for autonomous AI agents.",
    version="1.0.0",
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log the incoming visit details to visits.log
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    method = request.method
    url_path = request.url.path
    
    # Exclude internal health checks or loopback queries if we want, but let's log everything
    log_line = f"[{timestamp}] IP: {client_host} | {method} {url_path} | UA: {user_agent}\n"
    
    with open("/Users/noeldobbin/Downloads/agent-market/visits.log", "a") as f:
        f.write(log_line)
        
    response = await call_next(request)
    return response

# --- In-Memory Database ---
PRODUCTS = [
    {
        "id": "gpu-h100-hour",
        "name": "NVIDIA H100 GPU Hour",
        "description": "On-demand high-performance cloud compute for training and inference. Located in us-east-5.",
        "price": 2.85,
        "category": "compute",
        "stock": 120,
        "tags": ["fast", "ai", "ml", "gpu", "training", "compute", "premium"]
    },
    {
        "id": "api-tokens-deepseek",
        "name": "DeepSeek API 10M Tokens",
        "description": "Prepaid credits for DeepSeek-V3 and DeepSeek-R1 API usage. Fast response times, low latency.",
        "price": 1.50,
        "category": "api-credits",
        "stock": 500,
        "tags": ["api", "llm", "tokens", "cheap", "credits", "deepseek", "chat"]
    },
    {
        "id": "dev-sticker-pack",
        "name": "Ultimate Developer Sticker Pack",
        "description": "High-quality vinyl stickers featuring popular tech logos (Python, Rust, Docker, Hermes, etc.). Free global shipping.",
        "price": 12.00,
        "category": "merch",
        "stock": 45,
        "tags": ["stickers", "merch", "swag", "dev", "cheap", "decor"]
    },
    {
        "id": "premium-api-gateway-key",
        "name": "Agentic API Gateway Premium Monthly Subscription",
        "description": "Unlimited enterprise rate limits for standard SaaS integrations and translation hubs.",
        "price": 49.00,
        "category": "subscriptions",
        "stock": 1000,
        "tags": ["api", "gateway", "subscription", "premium", "developer", "enterprise"]
    }
]

# Active handshakes: handshake_token -> CheckoutDetails
ACTIVE_HANDSHAKES: Dict[str, Dict[str, Any]] = {}
COMPLETED_ORDERS: Dict[str, Dict[str, Any]] = {}

# --- Pydantic Schemas ---
class ProductSchema(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    stock: int
    tags: List[str]

class DryRunRequest(BaseModel):
    product_id: str = Field(..., description="The exact ID of the product to purchase.")
    quantity: int = Field(1, ge=1, description="Number of items to purchase.")
    agent_budget_limit: Optional[float] = Field(None, description="The maximum total cost (including taxes/fees) the agent is authorized to spend.")
    shipping_address: Optional[str] = Field(None, description="Required for physical goods (e.g. stickers). Ignore for digital ones.")

class DryRunResponse(BaseModel):
    handshake_token: str = Field(..., description="A unique token representing this validated checkout state. Expires in 5 minutes.")
    product_id: str
    quantity: int
    price_per_unit: float
    subtotal: float
    tax: float
    shipping: float
    total_cost: float
    requires_human_approval: bool = Field(..., description="If true, the agent MUST escalate to the human operator for approval before committing.")
    approval_reason: Optional[str] = Field(None, description="The explanation for why human approval is required.")
    expires_at: float = Field(..., description="Unix epoch timestamp when this handshake token expires.")
    instructions: str = Field(..., description="Clear, natural language guide on how the agent should proceed next.")

class CommitRequest(BaseModel):
    handshake_token: str = Field(..., description="The active token returned by the dry-run handshake.")
    payment_auth_code: str = Field(..., description="A mock payment voucher or token authorizing the release of funds. Try 'MOCK-GOLD-AUTH'.")

class CommitResponse(BaseModel):
    receipt_id: str = Field(..., description="A unique transaction ID for auditing.")
    product_id: str
    quantity: int
    total_charged: float
    status: str = Field(..., description="Final status, typically 'completed'.")
    estimated_delivery: str = Field(..., description="Natural language delivery estimate.")
    audit_log: str = Field(..., description="Factual confirmation of the transaction suitable for the agent's memory or logs.")

# --- Endpoints ---

@app.get("/")
@app.get("/.well-known/agent-manifest.json")
def get_manifest():
    """
    The Agent Manifest. AI Agents should hit this first to understand the service.
    """
    return {
        "manifest_version": "1.0.0",
        "service_name": "AgentMarket",
        "description": "An autonomous-first marketplace serving digital resources and developer physical merch. Tailored to be searched, parsed, and executed by LLM-driven agents.",
        "developer_contact": "noel@agentmarket.ai",
        "rules_of_engagement": {
            "currency": "USD",
            "dry_run_first": "You must ALWAYS perform a /checkout/dry-run before committing a purchase to ensure prices, stock, and shipping are valid.",
            "budget_safety": "If the total_cost exceeds your agent_budget_limit, the server will return requires_human_approval=True. Respect this flag and escalate to your user.",
            "idempotency": "Handshake tokens are single-use. If a commit succeeds, that token is invalidated immediately.",
            "error_handling": "We return descriptive JSON error messages. If you receive a 400 or 422, parse the detail block and adjust your input autonomously."
        },
        "endpoints": {
            "GET /.well-known/agent-manifest.json": {
                "description": "Retrieve this manifest.",
                "parameters": {}
            },
            "GET /products": {
                "description": "Search and list available items. Supports fuzzy search over names, descriptions, and tags.",
                "parameters": {
                    "query": "Optional natural language query string (e.g. 'cheap computation' or 'stickers').",
                    "category": "Optional filter by category (compute, api-credits, merch, subscriptions)."
                }
            },
            "POST /checkout/dry-run": {
                "description": "Dry-run checkout to generate a payment handshake token, calculate taxes/fees, and check budget compliance.",
                "request_body": "DryRunRequest"
            },
            "POST /checkout/commit": {
                "description": "Execute and finalize the purchase using a valid handshake token and authorization code.",
                "request_body": "CommitRequest"
            }
        }
    }

@app.get("/products", response_model=List[ProductSchema])
def list_products(
    query: Optional[str] = Query(None, description="Fuzzy natural language query searching name, description, and tags."),
    category: Optional[str] = Query(None, description="Filter products by exact category.")
):
    """
    Search and filter products. Natural language matching is simulated via keyword matching.
    """
    results = PRODUCTS
    
    if category:
        results = [p for p in results if p["category"].lower() == category.lower()]
        
    if query:
        query_words = query.lower().split()
        matched = []
        for p in results:
            score = 0
            # Check name
            if any(w in p["name"].lower() for w in query_words):
                score += 5
            # Check description
            if any(w in p["description"].lower() for w in query_words):
                score += 2
            # Check tags
            if any(w in p["tags"] for w in query_words):
                score += 3
            
            if score > 0:
                matched.append((p, score))
        # Sort by match score descending
        matched.sort(key=lambda x: x[1], reverse=True)
        results = [m[0] for m in matched]
        
    return results

@app.post("/checkout/dry-run", response_model=DryRunResponse)
def checkout_dry_run(req: DryRunRequest):
    """
    Compiles fees, taxes, stock, and checks agent budget limits. Returns a handshake token.
    """
    # 1. Find product
    product = next((p for p in PRODUCTS if p["id"] == req.product_id), None)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{req.product_id}' was not found in our database."
        )
        
    # 2. Check stock
    if product["stock"] < req.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock. Requested {req.quantity}, but only {product['stock']} units are left."
        )
        
    # 3. Compute costs
    price_per_unit = product["price"]
    subtotal = price_per_unit * req.quantity
    
    # Calculate tax (8%)
    tax = round(subtotal * 0.08, 2)
    
    # Calculate shipping (merch gets $3.99 shipping; digital goods are free)
    shipping = 3.99 if product["category"] == "merch" else 0.00
    
    # Required shipping address check for physical goods
    if product["category"] == "merch" and not req.shipping_address:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shipping address is required for checkout of physical merchandise (Ultimate Developer Sticker Pack)."
        )
        
    total_cost = round(subtotal + tax + shipping, 2)
    
    # 4. Budget compliance check
    requires_human_approval = False
    approval_reason = None
    
    if req.agent_budget_limit is not None:
        if total_cost > req.agent_budget_limit:
            requires_human_approval = True
            approval_reason = f"Total cost ${total_cost:.2f} exceeds the agent's authorized budget limit of ${req.agent_budget_limit:.2f}."
            
    # 5. Generate unique handshake token (valid for 300 seconds)
    token = "hs_" + uuid.uuid4().hex[:12]
    expires_at = time.time() + 300.0
    
    ACTIVE_HANDSHAKES[token] = {
        "token": token,
        "product_id": req.product_id,
        "quantity": req.quantity,
        "total_cost": total_cost,
        "expires_at": expires_at,
        "completed": False
    }
    
    # Create clear guidelines for the agent inside the JSON response
    instructions = (
        f"Handshake validated. To complete this purchase of {req.quantity}x '{product['name']}' "
        f"for a total of ${total_cost:.2f}, send a POST to `/checkout/commit` with "
        f"{{'handshake_token': '{token}', 'payment_auth_code': 'MOCK-GOLD-AUTH'}}. "
        f"Token expires in 5 minutes."
    )
    if requires_human_approval:
        instructions = (
            f"WARNING: Human approval required! {approval_reason} "
            f"Do NOT execute `/checkout/commit` until you present this total to your human user "
            f"and get confirmation."
        )
        
    return DryRunResponse(
        handshake_token=token,
        product_id=req.product_id,
        quantity=req.quantity,
        price_per_unit=price_per_unit,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        total_cost=total_cost,
        requires_human_approval=requires_human_approval,
        approval_reason=approval_reason,
        expires_at=expires_at,
        instructions=instructions
    )

@app.post("/checkout/commit", response_model=CommitResponse)
def checkout_commit(req: CommitRequest):
    """
    Finalizes the transaction using a validated handshake token.
    """
    # 1. Fetch handshake
    handshake = ACTIVE_HANDSHAKES.get(req.handshake_token)
    if not handshake:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid handshake token. Please execute a fresh dry-run check."
        )
        
    # 2. Check expiration
    if time.time() > handshake["expires_at"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handshake token has expired. Tokens are valid for 5 minutes."
        )
        
    # 3. Check single-use
    if handshake["completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handshake token has already been spent. Create a new checkout dry-run."
        )
        
    # 4. Validate payment authority code
    if req.payment_auth_code != "MOCK-GOLD-AUTH":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Payment authorization code '{req.payment_auth_code}' is invalid or has insufficient funds. Try using 'MOCK-GOLD-AUTH'."
        )
        
    # 5. Deduct stock and finalize
    product_id = handshake["product_id"]
    quantity = handshake["quantity"]
    
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Underlying product has disappeared from catalog."
        )
        
    if product["stock"] < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Underlying stock was depleted during the handshake period."
        )
        
    product["stock"] -= quantity
    handshake["completed"] = True
    
    receipt_id = "rec_" + uuid.uuid4().hex[:12]
    delivery_est = "Instant delivery to cloud account" if product["category"] != "merch" else "Shipped within 24 hours via FedEx Agent-Priority"
    
    audit_log = (
        f"SUCCESSFUL PURCHASE: Charged ${handshake['total_cost']:.2f} to authorization code '{req.payment_auth_code}'. "
        f"Item: {quantity}x '{product['name']}' (ID: {product_id}). Receipt ID: {receipt_id}."
    )
    
    COMPLETED_ORDERS[receipt_id] = {
        "receipt_id": receipt_id,
        "product_id": product_id,
        "quantity": quantity,
        "total_charged": handshake["total_cost"],
        "timestamp": time.time(),
        "delivery_est": delivery_est
    }
    
    return CommitResponse(
        receipt_id=receipt_id,
        product_id=product_id,
        quantity=quantity,
        total_charged=handshake["total_cost"],
        status="completed",
        estimated_delivery=delivery_est,
        audit_log=audit_log
    )
