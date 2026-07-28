FROM node:20-alpine
WORKDIR /app
RUN apk add --no-cache curl
COPY package*.json ./
RUN npm install
COPY . .
COPY run_autonomous.sh /app/
RUN chmod +x /app/run_autonomous.sh
ENV DEPENDENCIES_CMD="npm ci"
ENV START_CMD="node server.js &"
ENV TEST_CMD="npm test"
ENV VERIFY_CMD="curl -s -X POST http://localhost:3000/api/notifications -H \"Content-Type: application/json\" -d '{\"recipient\":\"test@example.com\",\"subject\":\"Test\",\"body\":\"Hello\",\"priority\":\"high\"}' | grep -q \"id\""
ENTRYPOINT ["/app/run_autonomous.sh"]