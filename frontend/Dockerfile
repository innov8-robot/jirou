# Dev-friendly image for the Jirou frontend (Vite dev server).
# Used by docker-compose (service `frontend`, port 5173).
FROM node:20-alpine

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the source (bind-mounted in dev via compose).
COPY . .

EXPOSE 5173

# host 0.0.0.0 so the server is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
