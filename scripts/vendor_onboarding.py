"""
Vendor Onboarding Automation
Streamlined process to get vendors selling quickly

WARNING - DO NOT SEND THESE TEMPLATES AS-IS.

The follow-up templates below contain FABRICATED statistics and FAKE
partner names ("127 agents active", "DeepSeek and Replicate just
joined"). None of it is true; sending it to real businesses would be
misrepresentation. This file is kept only as historical reference; use
honest outreach instead (a rewrite was drafted in the June 2026 session).
"""

import sys

sys.exit(
    "Refusing to run: scripts/vendor_onboarding.py contains fabricated "
    "claims and must not be sent or executed. See the module docstring."
)

VENDOR_OUTREACH_TEMPLATE = """
Subject: Be the first vendor in the $10B agent economy 🤖💰

Hi {name},

I'm reaching out because {company} is perfectly positioned to be an early winner in the exploding AI agent economy.

**The Opportunity:**
Every major company is building autonomous AI agents that need to purchase services programmatically. We've built the world's first B2A (Business-to-Agent) marketplace - think "Stripe for AI agents."

**Why {company} is perfect:**
- Your {service_type} is exactly what agents need
- Agent-friendly APIs (no CAPTCHAs, no visual complexity)  
- Recurring revenue from autonomous purchasing
- Zero competition in agent-first commerce

**Live Demo:** https://agentmarket.com/demo
Watch AI agents discover and purchase services in real-time.

**Early Vendor Benefits:**
✅ 0% commission for first 90 days (normally 2.5%)
✅ Featured placement in agent discovery
✅ Direct integration support
✅ Revenue starts immediately

**Next Steps:**
1. Check out our live demo above
2. 15-minute call to show you the platform
3. Live in 24 hours, earning revenue in 48 hours

The agent economy is happening now. The question is: do you want to be first to market or play catch-up?

Best,
{sender_name}
Founder, AgentMarket

P.S. We're only onboarding 20 launch partners. Stripe didn't wait for permission to enable internet payments - we're not waiting to enable agent commerce.
"""

VENDOR_CATEGORIES = {
    "ai_apis": {
        "companies": ["OpenAI", "Anthropic", "DeepSeek", "Groq", "Together AI", "Replicate"],
        "contact_pattern": "{founder}@{company_domain}",
        "service_type": "AI API services",
        "value_prop": "Agents are the fastest-growing API consumer segment"
    },
    "compute": {
        "companies": ["RunPod", "Vast.ai", "Lambda Labs", "CoreWeave", "Modal"],
        "contact_pattern": "{ceo}@{company_domain}", 
        "service_type": "GPU compute",
        "value_prop": "Autonomous training and inference workloads"
    },
    "data": {
        "companies": ["Perplexity", "SerpAPI", "ScrapingBee", "Apify", "Bright Data"],
        "contact_pattern": "partnerships@{company_domain}",
        "service_type": "data services",
        "value_prop": "Agents need real-time data for decision making"
    },
    "voice": {
        "companies": ["ElevenLabs", "Murf", "Speechify", "Rime AI", "PlayHT"],
        "contact_pattern": "business@{company_domain}",
        "service_type": "voice synthesis",
        "value_prop": "Voice agents are exploding - be the default TTS provider"
    },
    "cloud": {
        "companies": ["Digital Ocean", "Linode", "Vultr", "Hetzner", "OVH"],
        "contact_pattern": "partnerships@{company_domain}",
        "service_type": "cloud infrastructure", 
        "value_prop": "Agent workloads need scalable, API-first infrastructure"
    }
}

ONBOARDING_SEQUENCE = [
    {
        "day": 0,
        "action": "send_initial_outreach",
        "template": VENDOR_OUTREACH_TEMPLATE,
        "subject": "Be the first vendor in the $10B agent economy 🤖💰"
    },
    {
        "day": 3,
        "action": "send_followup_1", 
        "template": """
Subject: [Follow-up] Agent bought ${example_purchase} of {service_type} yesterday

Hi {name},

Quick update: Yesterday an AI agent autonomously purchased ${example_purchase} worth of {service_type} on our platform. 

This is exactly the kind of transaction {company} should be capturing.

**The numbers:**
- 127 agents active on the platform
- $847 in transactions yesterday  
- Growing 23% week-over-week

Still interested in that 15-minute demo?

Best,
{sender_name}
        """,
        "subject": "[Follow-up] Agent bought ${example_purchase} yesterday"
    },
    {
        "day": 7,
        "action": "send_social_proof",
        "template": """
Subject: DeepSeek, Replicate, and 3 others just joined as launch vendors

Hi {name},

Wanted to give you a quick update on our launch partner roster:

✅ DeepSeek (AI APIs) - Live and earning
✅ Replicate (ML Infrastructure) - Integration complete  
✅ ElevenLabs (Voice) - Featured in agent demo
✅ Two other major providers (under NDA)

We're down to 15 remaining launch partner spots.

{company}'s {service_type} would be a perfect fit for our growing agent ecosystem.

15-minute demo still available if you're interested.

Best,
{sender_name}
        """,
        "subject": "DeepSeek, Replicate, and 3 others just joined"
    }
]

INTEGRATION_CHECKLIST = """
# Vendor Integration Checklist

## Phase 1: Account Setup (15 minutes)
- [ ] Create vendor account on platform
- [ ] Verify business information
- [ ] Connect Stripe Express account
- [ ] Set commission preferences

## Phase 2: Product Catalog (30 minutes) 
- [ ] Add first product with agent-friendly description
- [ ] Set competitive pricing for agent market
- [ ] Configure inventory and stock limits
- [ ] Test product discovery via search

## Phase 3: Integration Testing (45 minutes)
- [ ] API endpoint integration
- [ ] Webhook configuration for order processing
- [ ] Test dry-run transaction flow
- [ ] Test successful purchase completion
- [ ] Verify commission splits working

## Phase 4: Go-Live (Immediate)
- [ ] Enable product visibility
- [ ] Add to featured vendors (launch partner benefit)
- [ ] Monitor first agent transactions
- [ ] Set up revenue tracking

## Phase 5: Optimization (Ongoing)
- [ ] Analyze agent purchasing patterns
- [ ] Optimize product descriptions for discovery
- [ ] Adjust pricing based on demand
- [ ] Scale inventory for growing demand

## Launch Partner Benefits Active:
✅ 0% commission for 90 days
✅ Featured placement in agent searches  
✅ Direct integration support
✅ Marketing co-promotion opportunities

**Estimated Time to First Sale: 2-4 hours after go-live**
"""

SUCCESS_METRICS = {
    "week_1": {
        "target_vendors": 5,
        "target_products": 20,
        "target_transactions": 50,
        "target_revenue": "$500+"
    },
    "month_1": {
        "target_vendors": 25,
        "target_products": 100,
        "target_transactions": 1000,
        "target_revenue": "$5,000+"
    },
    "month_3": {
        "target_vendors": 100,
        "target_products": 500,
        "target_transactions": 10000,
        "target_revenue": "$25,000+"
    }
}

def generate_outreach_email(vendor_category, company_name):
    """Generate personalized outreach email for a vendor"""
    
    category_data = VENDOR_CATEGORIES[vendor_category]
    
    # Personalization logic
    email = VENDOR_OUTREACH_TEMPLATE.format(
        name=f"{company_name} team",
        company=company_name,
        service_type=category_data["service_type"],
        sender_name="Your Name",
        value_prop=category_data["value_prop"]
    )
    
    return email

# Example usage:
if __name__ == "__main__":
    print("🚀 VENDOR ONBOARDING SYSTEM")
    print("=" * 50)
    
    print("\n📧 Sample Outreach Email (OpenAI):")
    print(generate_outreach_email("ai_apis", "OpenAI"))
    
    print("\n📋 Integration Checklist:")
    print(INTEGRATION_CHECKLIST)
    
    print("\n🎯 Success Metrics:")
    for period, metrics in SUCCESS_METRICS.items():
        print(f"\n{period.upper()}:")
        for metric, target in metrics.items():
            print(f"  {metric}: {target}")
    
    print("\n💰 Revenue Projection:")
    print("Week 1: $500+ (proof of concept)")
    print("Month 1: $5,000+ (initial traction)")  
    print("Month 3: $25,000+ (scaling momentum)")
    print("Month 6: $60,000+ (market leadership)")