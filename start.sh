#!/bin/bash

echo "Starting SECI Query Explorer System..."
echo "=================================="

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama is not running. Please start it with:"
    echo "   ollama serve"
    echo ""
    echo "   And make sure you have the required model:"
    echo "   ollama pull qwen2.5:7b-instruct"
    echo ""
    echo "Continue anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🚀 Starting backend server..."
cd backend
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8000)" &
BACKEND_PID=$!

echo "⏳ Waiting for backend to start..."
sleep 3

echo "🎨 Starting frontend server..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Services started!"
echo "   Backend: http://localhost:8000"
echo "   Frontend: http://localhost:3000 (or 3001/3002/3003 if needed)"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt signal
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT

wait