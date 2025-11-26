#!/bin/bash

# Function to kill background processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    exit
}

trap cleanup SIGINT SIGTERM

echo "Starting Backend..."
# Run from /home/console/app so that 'app' module is resolvable if we use 'uvicorn main:app'
# OR run from /home/console and use 'uvicorn app.main:app'
# Let's use the latter as it's cleaner
cd /home/console
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

echo "Starting Frontend..."
cd /home/console/app/frontend
npm run dev -- --host &

echo "Services started. Press Ctrl+C to stop."
wait
