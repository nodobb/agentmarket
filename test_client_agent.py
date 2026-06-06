import requests
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def log_agent_thought(thought: str):
    print(f"\n[\033[94mAgent Thought\033[0m] {thought}")

def log_agent_action(action: str):
    print(f"[\033[92mAgent Action\033[0m] {action}")

def log_system_response(response_dict: dict):
    print(f"[\033[93mAPI Response\033[0m] {json.dumps(response_dict, indent=2)}")

def main():
    print("=" * 65)
    print("      STARTING SIMULATED AUTONOMOUS AGENT PURCHASE FLOW")
    print("=" * 65)

    # STEP 1: Discovery (Fetch the Agent Manifest)
    log_agent_thought("I need to discover the capabilities and guidelines of the marketplace API first.")
    log_agent_action(f"Fetching agent manifest from {BASE_URL}/.well-known/agent-manifest.json")
    
    try:
        r = requests.get(f"{BASE_URL}/.well-known/agent-manifest.json")
        if r.status_code != 200:
            print(f"Error: Server returned status code {r.status_code}")
            sys.exit(1)
        manifest = r.json()
        log_system_response(manifest)
    except requests.exceptions.ConnectionError:
        print("\033[91mError: Could not connect to the API server. Please make sure the FastAPI server is running on port 8000.\033[0m")
        sys.exit(1)

    log_agent_thought(
        f"API Name: {manifest['service_name']}. "
        f"Rules of engagement mandate: currency is {manifest['rules_of_engagement']['currency']}, "
        f"and I must ALWAYS do a dry-run first before committing."
    )

    # STEP 2: Natural Language Product Search
    user_request = "Get some cheap API token credits for my chat server, budget is $10.00."
    log_agent_thought(f"Human instruction: '{user_request}'. Searching the catalog for a matching item.")
    
    search_query = "cheap API token credits"
    log_agent_action(f"GET /products?query={search_query}")
    r = requests.get(f"{BASE_URL}/products", params={"query": search_query})
    products = r.json()
    log_system_response(products)

    if not products:
        log_agent_thought("No matching products found. Aborting mission.")
        sys.exit(1)

    chosen_product = products[0]
    log_agent_thought(f"Found product: '{chosen_product['name']}' (ID: {chosen_product['id']}) for ${chosen_product['price']:.2f} per unit.")

    # STEP 3: Dry-Run Checkout (First Order: 5 units of DeepSeek tokens, within budget)
    quantity = 5
    agent_budget_limit = 10.00
    log_agent_thought(f"Budget is set to exactly ${agent_budget_limit:.2f}. I must actively try to keep purchases way under this limit.")
    
    # Calculate expected price beforehand to verify it's way under $10
    expected_subtotal = chosen_product["price"] * quantity
    expected_total = expected_subtotal * 1.08  # estimate tax
    
    if expected_total >= agent_budget_limit:
        log_agent_thought(f"Estimated total of ${expected_total:.2f} is too close to or exceeds our limit. Let's adjust quantity to keep it way under $10.")
        quantity = 3  # reduce quantity to be highly conservative
        expected_total = (chosen_product["price"] * quantity) * 1.08
        
    log_agent_thought(f"Adjusted order: {quantity} units. Estimated total: ${expected_total:.2f}. This is safely way under our $10 limit!")
    
    checkout_payload = {
        "product_id": chosen_product["id"],
        "quantity": quantity,
        "agent_budget_limit": agent_budget_limit
    }
    log_agent_action(f"POST /checkout/dry-run with body: {json.dumps(checkout_payload)}")
    r = requests.post(f"{BASE_URL}/checkout/dry-run", json=checkout_payload)
    dry_run_res = r.json()
    log_system_response(dry_run_res)

    # Analyze Dry-Run
    if dry_run_res.get("requires_human_approval"):
        log_agent_thought("Safety violation! The dry-run returned requires_human_approval=True. Stopping execution.")
        print(f"\033[91m[ESCALATION] Human intervention required: {dry_run_res['approval_reason']}\033[0m")
        sys.exit(1)
    else:
        log_agent_thought("The purchase is well within our budget limit. Proceeding to finalize checkout.")

    # STEP 4: Commit Transaction
    token = dry_run_res["handshake_token"]
    commit_payload = {
        "handshake_token": token,
        "payment_auth_code": "MOCK-GOLD-AUTH"
    }
    log_agent_action(f"POST /checkout/commit with body: {json.dumps(commit_payload)}")
    r = requests.post(f"{BASE_URL}/checkout/commit", json=commit_payload)
    commit_res = r.json()
    log_system_response(commit_res)

    log_agent_thought(f"Receipt received! ID: {commit_res['receipt_id']}. Writing successful transaction details to my memory/logs.")
    print(f"\n\033[92m[SUCCESS] Final Receipt Audit Log:\033[0m {commit_res['audit_log']}\n")

    # STEP 5: Demonstration of Human-in-the-Loop Safeguard (Order way over budget)
    log_agent_thought("Now, let's simulate a scenario that violates our budget constraints to show the safety mechanism.")
    large_quantity = 40
    log_agent_thought(f"User instruction: 'Get me stickers for the whole team'. I'll search for stickers.")
    
    log_agent_action("GET /products?query=stickers")
    r = requests.get(f"{BASE_URL}/products", params={"query": "stickers"})
    sticker_products = r.json()
    
    if not sticker_products:
        print("No sticker products found for demo.")
        sys.exit(0)
        
    sticker_product = sticker_products[0]
    log_agent_thought(f"Fuzzy search returned: '{sticker_product['name']}' (ID: {sticker_product['id']}) for ${sticker_product['price']:.2f}/ea.")
    
    log_agent_thought(f"Dry-running sticker purchase of {large_quantity} packs. Budget limit: ${agent_budget_limit:.2f}.")
    large_checkout_payload = {
        "product_id": sticker_product["id"],
        "quantity": large_quantity,
        "agent_budget_limit": agent_budget_limit,
        "shipping_address": "123 Agent Way, Silicon Valley, CA 94025"
    }
    log_agent_action(f"POST /checkout/dry-run with body: {json.dumps(large_checkout_payload)}")
    r = requests.post(f"{BASE_URL}/checkout/dry-run", json=large_checkout_payload)
    large_dry_run_res = r.json()
    log_system_response(large_dry_run_res)

    if large_dry_run_res.get("requires_human_approval"):
        log_agent_thought("The budget check failed as expected! Handshake token generated, but flag requires_human_approval=True is active.")
        print("=" * 65)
        print("\033[91m             ⚠️ HUMAN APPROVAL REQUIRED ⚠️\033[0m")
        print(f"Reason:  {large_dry_run_res['approval_reason']}")
        print(f"Product: {large_quantity}x {sticker_product['name']}")
        print(f"Total:   ${large_dry_run_res['total_cost']:.2f}")
        print("-" * 65)
        print("Agent Status: PAUSED. Waiting for human operator to approve.")
        print("=" * 65)
    else:
        print("Stickers checkout didn't require approval. (Stock/price logic unexpected)")

if __name__ == "__main__":
    main()
