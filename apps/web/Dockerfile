FROM node:22-alpine AS builder
WORKDIR /app
COPY apps/web/package.json apps/web/tsconfig.json apps/web/next.config.ts apps/web/next-env.d.ts /app/
RUN npm install --no-audit --no-fund
COPY apps/web/app /app/app
COPY apps/web/components /app/components
COPY apps/web/lib /app/lib
COPY apps/web/public /app/public
RUN npm run build
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app /app
EXPOSE 3000
CMD ["npm","run","start"]
