#!/bin/bash

# AgentMarket Quick Setup & Deployment Script

set -e

echo "🤖 AgentMarket Production Setup & Deployment"
echo "=============================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Create virtual environment
echo "📦 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "⬇️  Installing dependencies..."
pip install -r requirements.txt

# Copy environment template if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Setting up environment configuration..."
    cp .env.example .env
    echo "✏️  Please edit .env file with your configuration!"
    echo "   - Set your SECRET_KEY"
    echo "   - Configure Stripe keys for payments"
    echo "   - Set your database URL (PostgreSQL recommended for production)"
fi

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "
import asyncio
import sys
sys.path.append('.')
from agentmarket.models import init_db
asyncio.run(init_db())
print('✅ Database initialized!')
"

echo ""
echo "🎉 Setup complete! Next steps:"
echo ""
echo "1. Edit your .env file with production settings"
echo "2. For development: python main.py"
echo "3. For production: gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker"
echo ""
echo "📚 Available endpoints:"
echo "   - Landing page: http://localhost:8000"
echo "   - API docs: http://localhost:8000/docs"  
echo "   - Agent manifest: http://localhost:8000/.well-known/agent-manifest.json"
echo ""
echo "🚀 Ready to launch your B2A marketplace!"