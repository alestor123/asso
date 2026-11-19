#!/bin/sh
set -e

PUBLIC_PORT="${PORT:-10000}"

sed "s/listen 3000;/listen ${PUBLIC_PORT};/; s/http:\/\/asso-backend:8000/http:\/\/127.0.0.1:8000/g" \
  /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

export FLASK_HOST=127.0.0.1
export FLASK_PORT=6001
export NODE_HOST=127.0.0.1
export NODE_PORT=6002

exec supervisord -c /etc/supervisor/conf.d/asso.conf
