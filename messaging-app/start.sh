#!/bin/bash

# Secure Messaging App - Complete Startup Script

echo "🚀 Starting Secure Messaging App..."
echo "=================================="

# Check if we're in the right directory
if [ ! -f "package.json" ] || [ ! -d "backend" ]; then
    echo "❌ Please run this script from the messaging-app root directory"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command_exists node; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

if ! command_exists python3; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

if ! command_exists mongod; then
    echo "❌ MongoDB is not installed. Please install MongoDB first."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Check if MongoDB is running
echo "🗄️ Checking MongoDB..."
if ! nc -z localhost 27017 2>/dev/null; then
    echo "🔄 Starting MongoDB..."
    if command_exists brew; then
        brew services start mongodb-community
    elif command_exists systemctl; then
        sudo systemctl start mongod
    else
        echo "❌ Please start MongoDB manually"
        exit 1
    fi
    
    # Wait for MongoDB to start
    echo "⏳ Waiting for MongoDB to start..."
    sleep 5
fi

echo "✅ MongoDB is running"

# Start backend
echo "🐍 Starting Python backend..."
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install backend dependencies
echo "📥 Installing backend dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️ Creating backend .env file..."
    cp env.example .env
fi

# Start backend in background
echo "🌟 Starting FastAPI server..."
python run.py &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 10

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend failed to start. Check the logs above."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo "✅ Backend is running on http://localhost:8000"

# Go back to root directory
cd ..

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Start frontend
echo "⚛️ Starting Next.js frontend..."
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 10

echo ""
echo "🎉 Secure Messaging App is now running!"
echo "=================================="
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend API: http://localhost:8000"
echo "📍 API Documentation: http://localhost:8000/docs"
echo "🔌 WebSocket: ws://localhost:8000/ws/{user_id}/{session_id}"
echo ""
echo "📚 Quick Start:"
echo "1. Open http://localhost:3000 in your browser"
echo "2. Sign up for a new account or use demo credentials"
echo "3. Start messaging!"
echo ""
echo "🛑 To stop the application, press Ctrl+C"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping application..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Application stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait
