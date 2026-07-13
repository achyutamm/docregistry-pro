FROM node:20-alpine

WORKDIR /app

# Copy from baileys_service/ since build context is repo root
COPY baileys_service/package*.json ./
RUN npm install

COPY baileys_service/ .

EXPOSE 3001

CMD ["node", "server.js"]
