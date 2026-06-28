FROM node:20-alpine AS base
WORKDIR /app
# Prisma needs openssl on alpine.
RUN apk add --no-cache openssl

# Install dependencies
FROM base AS deps
COPY package*.json ./
COPY packages/Vibe-Workflow/packages/workflow-builder/package*.json ./packages/Vibe-Workflow/packages/workflow-builder/
COPY packages/Open-Poe-AI/packages/agents/package*.json ./packages/Open-Poe-AI/packages/agents/
COPY packages/studio/package*.json ./packages/studio/
# Prisma schema must exist before install because postinstall runs `prisma generate`.
COPY prisma ./prisma
RUN npm install

# Build sub-packages + Next.js app
FROM deps AS builder
COPY . .
RUN npm run build:packages
RUN npm run build

# Production runner
FROM base AS runner
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/prisma ./prisma
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
# Sync the DB schema (creates tables on first run, no-op once in sync), then start.
# `db push` avoids needing pre-generated migration files for self-host setups.
CMD ["sh", "-c", "npx prisma db push --skip-generate && npm start"]
