FROM node:22-bookworm-slim

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/shared/package.json packages/shared/package.json
COPY packages/api/package.json packages/api/package.json
COPY packages/extension/package.json packages/extension/package.json

RUN pnpm install --frozen-lockfile

COPY contracts ./contracts
COPY packages/shared ./packages/shared
COPY packages/api ./packages/api

ENV NODE_ENV=production
EXPOSE 47821

WORKDIR /app/packages/api
CMD ["pnpm", "start"]
