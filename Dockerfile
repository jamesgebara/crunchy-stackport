FROM node:20-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY backend/ ./backend/
COPY --from=ui-build /app/ui/dist ./ui/dist
EXPOSE 8080
CMD ["python", "-m", "backend.main"]
