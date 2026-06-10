FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_UI_ANALYSIS_ONLY=false
ENV VITE_UI_ANALYSIS_ONLY=${VITE_UI_ANALYSIS_ONLY}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
