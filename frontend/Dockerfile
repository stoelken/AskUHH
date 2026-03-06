FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm config set strict-ssl false
RUN npm install

COPY . .

# VITE_BACKEND_URL is NOT needed at build time — the Vite dev proxy or nginx
# handles routing at runtime. Pass it only if you want a custom build target.
ARG VITE_BACKEND_URL=http://backend:8000
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80