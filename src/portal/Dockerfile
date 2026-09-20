# syntax=docker/dockerfile:1.7
#
# The cache mounts below need BuildKit, which the `syntax` line above pins. Without it
# the `--mount` flags are a parse error rather than a silent no-op, so a builder that
# cannot honour them fails loudly instead of quietly building slowly.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
# The npm cache is mounted rather than baked into a layer: it survives across builds, so
# a rebuild that changes no dependencies re-resolves from local cache in seconds instead
# of re-downloading the tree. It is deliberately not COPYed into the image — nothing at
# runtime needs it, and it would be dead weight in every layer below.
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_GATEWAY_URL
ARG NEXT_PUBLIC_DOCUMENT_URL
ARG NEXT_PUBLIC_ANNOTATION_URL
ARG NEXT_PUBLIC_TRAINING_URL
ARG NEXT_PUBLIC_MODEL_SERVING_URL
ARG NEXT_PUBLIC_EXTRACTION_URL
ARG NEXT_PUBLIC_ANALYTICS_URL
# `.next/cache` holds Next's compiler and minifier caches. Mounting it lets an unchanged
# module skip recompilation entirely, which is where most of a rebuild's time goes once
# dependencies are cached. It must not be COPYed into the runtime image: it is build
# scratch, not output, and `.next/standalone` is what actually ships.
RUN --mount=type=cache,target=/app/.next/cache,sharing=locked \
    npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
