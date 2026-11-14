# Epicure Frontend

The frontend user interface for the Epicure AI Smart Recipe Discovery system. Built with React and Vite.

## Features
- **Glassmorphism UI**: A sleek, modern, and appetizing visual aesthetic tailored for food discovery.
- **Natural Language Search**: A massive search bar allowing users to input complex, messy dietary requirements in plain English.
- **Real-time Polling**: Automatically polls the Coordinator node to display the "AI is thinking..." state until the complex distributed search is resolved.
- **Admin Dashboard**: A hidden route (`/admin`) for authenticated administrators to ingest new recipes directly into the Qdrant Vector database via the ETL pipeline.

## Development

The frontend is fully Dockerized and runs behind the Nginx Reverse Proxy. 
You **do not** need to run `npm run dev` manually.

When you run `docker-compose up` at the project root:
1. The `frontend` container installs Node.js modules.
2. It starts Vite on port `5173` bound to `0.0.0.0`.
3. The local `frontend` directory is bind-mounted (`volumes`) into the container.
4. **Hot Module Replacement (HMR)** is configured with `usePolling: true` to ensure edits made on the Windows host are instantly reflected in the browser.

### Accessing the App
Simply navigate to:
- **Search App**: `http://epicure.localhost`
- **Admin Dashboard**: `http://epicure.localhost/admin`

*(All API calls dynamically route through the Nginx proxy to avoid CORS and port-hardcoding).*
