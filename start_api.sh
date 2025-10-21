#!/bin/bash

# Aprep AI Agent System - Quick Start Script

echo "=================================="
echo "Aprep AI Agent System"
echo "=================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/bin/uvicorn" ]; then
    echo "Installing dependencies (this may take a few minutes)..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo "Dependencies installed!"
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY"
    echo ""
fi

# Create data directories
mkdir -p data/ced data/templates data/misconceptions

echo ""
echo "Starting API server..."
echo "API will be available at: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
