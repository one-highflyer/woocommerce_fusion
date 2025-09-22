# WooCommerce Orders: Status Filtering and Realtime Webhooks

## Overview

Synchronize only WooCommerce orders in the "processing" status (skip "failed" and other undesired statuses) and create ERPNext Sales Orders in near‑realtime using a WooCommerce webhook. Keep periodic sync for backfill and deletions.

## Goals

- Restrict scheduled pulls to `processing` status orders (plus `trash` for deletions) to avoid syncing failed orders.
- Use the built‑in webhook endpoint to create orders in realtime.
- Optionally enforce the same status filter for the webhook path.
- Harden webhook security (HMAC verification).

## Current Behavior (for reference)

- Scheduler enqueues sync of all orders modified since a timestamp, plus `status="trash"`:
  - Hook: `apps/woocommerce_fusion/woocommerce_fusion/hooks.py:149`
  - Task: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:105`
- `get_list_of_wc_orders` supports filtering by `status="…"` and maps to Woo parameters:
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:1139`
  - `apps/woocommerce_fusion/woocommerce_fusion/woocommerce/woocommerce_api.py:556`
- Realtime webhook endpoint for "Order created":
  - `apps/woocommerce_fusion/woocommerce_fusion/woocommerce_endpoint.py:42`
  - HMAC verification is present but commented out: `apps/woocommerce_fusion/woocommerce_fusion/woocommerce_endpoint.py:29`

## Proposed Behavior

1) Scheduler: filter by status
- Replace unfiltered call with a filtered list call:
  - `get_list_of_wc_orders(date_time_from=..., status="processing")`
- Keep the `status="trash"` call to process deletions/voiding.
- File change: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:105–107`

2) Webhook: realtime creation
- Continue to accept "Order created" events at:
  - `/api/method/woocommerce_fusion.woocommerce_endpoint.order_created`
- Optional: gate by status to match scheduler behavior (create only when `order["status"] == "processing"`).
  - File: `apps/woocommerce_fusion/woocommerce_fusion/woocommerce_endpoint.py:61`

3) Webhook: security
- Re‑enable HMAC signature verification so only Woo‑signed payloads are processed.
  - Uncomment the validation block at: `apps/woocommerce_fusion/woocommerce_fusion/woocommerce_endpoint.py:29–35`
  - Ensure Woo and ERPNext share the same secret stored on `WooCommerce Server.secret`.

## Optional Configuration (future‑proofing)

- If broader flexibility is needed, add a JSON field to `WooCommerce Integration Settings` or `WooCommerce Server` for allowed WC statuses to sync (e.g., `["processing", "completed"]`). For now, keep the scope to `processing`.

## Backward Compatibility

- Existing sync logic remains intact aside from filtering. Trash handling remains unchanged. Webhook endpoint URL stays the same.

## Testing Plan

- Unit/integration tests for:
  - Scheduler calls `get_list_of_wc_orders(..., status="processing")` and also with `status="trash"`).
  - Webhook: events with `status != "processing"` are ignored when gating is enabled.
  - HMAC signature check rejects invalid signatures and accepts valid ones.

## Rollout

1) Implement scheduler status filter and (optionally) webhook status gating.
2) Re‑enable HMAC signature validation and configure Woo webhook with the ERPNext‑provided secret.
3) Monitor Error Logs during initial rollout.

