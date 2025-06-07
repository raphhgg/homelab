#!/bin/bash
set -e

service=$1

if [ -z "$service" ]; then
    echo "❌ No service specified"
    echo "Usage: $0 <service_name>"
    exit 1
fi

# Path to service-specific test file
test_file="scripts/tests/${service}.sh"

if [ -f "$test_file" ]; then
    echo "🔍 Running specific tests for $service..."
    bash "$test_file"
else
    echo "ℹ️  No specific tests for $service, running default tests..."
    bash "scripts/tests/default.sh" "$service"
fi

echo "✅ Tests completed for $service" 