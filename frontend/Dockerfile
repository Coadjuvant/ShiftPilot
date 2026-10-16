FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ARG VITE_APP_BUILD
ARG VITE_APP_VERSION
ARG VITE_GIT_COMMIT
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_BUILD=$VITE_APP_BUILD
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_GIT_COMMIT=$VITE_GIT_COMMIT
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
