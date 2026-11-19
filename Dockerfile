FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx nodejs npm supervisor curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY demo-apps/flask-api/ /app/flask-api/
RUN pip install --no-cache-dir -r /app/flask-api/requirements.txt

COPY demo-apps/node-workload/package*.json /app/node-workload/
COPY demo-apps/node-workload/server.js /app/node-workload/

COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf.template

COPY docker/supervisord.conf /etc/supervisor/conf.d/asso.conf

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PORT=10000 \
    DATABASE_URL=sqlite+aiosqlite:///./asso.db

EXPOSE 10000

CMD ["/entrypoint.sh"]
