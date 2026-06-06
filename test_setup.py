"""
AgentMarket Application Test Script
Quick verification that the core functionality works
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_application():
    """Test the AgentMarket application setup"""
    
    print("🤖 AgentMarket Application Test")
    print("=" * 40)
    
    try:
        # Test imports
        print("📦 Testing imports...")
        from agentmarket.utils.config import settings
        from agentmarket.models.database import Base, User, Vendor, Product, Agent, Transaction
        from agentmarket.models import init_db
        print("✅ All imports successful")
        
        # Test configuration
        print("⚙️ Testing configuration...")
        print(f"   Database URL: {settings.DATABASE_URL}")
        print(f"   Debug mode: {settings.DEBUG}")
        print(f"   Commission rate: {settings.COMMISSION_RATE}")
        print("✅ Configuration loaded")
        
        # Test database initialization
        print("🗄️ Testing database setup...")
        await init_db()
        print("✅ Database initialization successful")
        
        # Test FastAPI app creation
        print("🚀 Testing FastAPI application...")
        from main import app
        print(f"   App title: {app.title}")
        print(f"   App version: {app.version}")
        print("✅ FastAPI application created successfully")
        
        print("\n🎉 All tests passed! AgentMarket is ready to launch!")
        print("\nNext steps:")
        print("1. Run: python main.py")
        print("2. Visit: http://localhost:8000")
        print("3. Check agent manifest: http://localhost:8000/.well-known/agent-manifest.json")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Try: pip install -r requirements.txt")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Check your configuration and dependencies")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_application())
    sys.exit(0 if success else 1)