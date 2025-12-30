#!/bin/sh

# Replace ${BACKEND_URL} in nginx.conf with the actual environment variable
# If BACKEND_URL is not set, default to localhost for local development compatibility
if [ -z "$BACKEND_URL" ]; then
    export BACKEND_URL="http://backend:8000"
fi

echo "Starting Nginx with Backend URL: $BACKEND_URL"

# We use envsubst to replace the variable. 
# We explicitly list only BACKEND_URL to avoid replacing other nginx variables like $host or $uri
envsubst '${BACKEND_URL}' < /etc/nginx/conf.d/default.conf > /etc/nginx/conf.d/default.conf.tmp && mv /etc/nginx/conf.d/default.conf.tmp /etc/nginx/conf.d/default.conf

# Execute the CMD (nginx)
exec "$@"
