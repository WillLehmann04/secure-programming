#!/bin/bash

# Messaging App Backend Startup Script

echo "🚀 Starting Secure Messaging App Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit .env file with your configuration before running again"
    exit 1
fi

# Check if MongoDB is running
echo "🗄️ Checking MongoDB connection..."
if ! nc -z localhost 27017 2>/dev/null; then
    echo "❌ MongoDB is not running. Please start MongoDB first:"
    echo "   brew services start mongodb-community"
    echo "   or"
    echo "   sudo systemctl start mongod"
    exit 1
fi

# Create uploads directory
echo "📁 Creating uploads directory..."
mkdir -p uploads/avatars

# Start the application
echo "🌟 Starting FastAPI server..."
echo "📍 Backend will be available at: http://localhost:8000"
echo "📚 API documentation at: http://localhost:8000/docs"
echo "🔌 WebSocket endpoint: ws://localhost:8000/ws/{user_id}/{session_id}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python run.py
