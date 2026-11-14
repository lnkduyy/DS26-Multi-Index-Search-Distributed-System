# Nginx API Gateway (Reverse Proxy)

This directory contains the configuration for the system's edge router and reverse proxy.

## 🌟 Purpose
To provide a single, unified domain (`http://localhost`) for the entire application, masking all the complex internal ports and routing rules from the end-user. 

## 🧩 How it works
The Nginx container listens on port `80` (standard HTTP). Based on the URL path, it intelligently routes traffic to the appropriate internal Docker container:

1. **Frontend Traffic (`/`)**: 
   - Routed directly to the `frontend` container (Vite React server).
   - WebSockets are supported to ensure Hot Module Replacement (HMR) functions correctly during development.

2. **Backend API Traffic (`/api/`, `/search`, `/get`)**:
   - Acts as a **Layer 7 Load Balancer**.
   - Traffic is load-balanced (distributed) across all active Coordinator nodes (`coordinator-1`, `coordinator-2`, `coordinator-3`).
   - This ensures that if 100 users search for recipes at the same time, the load is spread out, preventing any single node from crashing.

## 🚀 Configuration
See `nginx.conf` for the exact routing and upstream load-balancing rules.

If you add a new microservice that needs to be exposed directly to the internet, you will need to add a new `location` block in `nginx.conf` and restart the container using `docker-compose restart nginx`.
