#!/bin/bash
set -e

service=$1

if [ -z "$service" ]; then
    echo "❌ No service specified"
    echo "Usage: $0 <service_name>"
    exit 1
fi

# Find the project root directory (where scripts/ folder exists)
project_root=""
if [ -d "scripts/tests" ]; then
    # Already in project root
    project_root="."
elif [ -d "../scripts/tests" ]; then
    # One level down (e.g., in a service directory)
    project_root=".."
elif [ -d "../../scripts/tests" ]; then
    # Two levels down
    project_root="../.."
else
    echo "❌ Cannot find scripts/tests directory"
    exit 1
fi

# Path to service-specific test file
test_file="${project_root}/scripts/tests/${service}.sh"

if [ -f "$test_file" ]; then
    echo "🔍 Running specific tests for $service..."
    bash "$test_file"
else
    echo "ℹ️  No specific tests for $service, running default tests..."
    bash "${project_root}/scripts/tests/default.sh" "$service"
fi

echo "✅ Tests completed for $service" 