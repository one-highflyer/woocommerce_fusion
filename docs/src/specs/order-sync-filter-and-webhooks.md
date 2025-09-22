# WooCommerce Orders: Allowed Statuses, Custom Mappings, and Realtime Webhooks

## Overview

Sync WooCommerce orders reliably while supporting site‑specific custom statuses (e.g., `trade-order`).
We will:
- Pull orders modified since last sync, plus a pass for deletions (`trash`).
- Gate processing locally by a per‑server allowlist of Woo statuses (post‑fetch), so custom slugs aren’t missed.
- Layer custom status mappings on top of the default mapping without modifying the defaults.
- Feed the Sales Order “WooCommerce Status” dropdown dynamically from the merged mapping.
- Keep webhook behavior consistent with the scheduler, and enable HMAC verification.

## Current Behavior (reference)

- Scheduler pulls modified orders and a separate `trash` batch:
  - Hook: apps/woocommerce_fusion/woocommerce_fusion/hooks.py:149
  - Task: apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:105
- Status mapping (labels ↔ slugs):
  - Base map: apps/woocommerce_fusion/woocommerce_fusion/woocommerce/doctype/woocommerce_order/woocommerce_order.py:21
  - Reverse lookups used at: apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:238 and :488
- Sales Order field options (static Select):
  - apps/woocommerce_fusion/woocommerce_fusion/fixtures/custom_field.json:858
- Webhook endpoint for order created:
  - apps/woocommerce_fusion/woocommerce_fusion/woocommerce_endpoint.py:42 (HMAC block present but commented at :29)

## Configuration

- Allowed inbound statuses (per server)
  - Field: WooCommerce Server.allowed_inbound_statuses (JSON or MultiSelect of Woo slugs).
  - Example: ["processing", "trade-order"].
  - Default: ["processing"]. Used to gate scheduler (post‑fetch) and webhook handling.

- Custom status mapping overlay (per server)
  - Field: WooCommerce Server.custom_status_map (JSON list of objects: [{"label": "Trade Order", "slug": "trade-order"}]).
  - Purpose: extend (not replace) the base WC_ORDER_STATUS_MAPPING with site‑specific label↔slug pairs.
  - No default; admins add entries as needed for custom slugs.

## Effective Mapping (runtime)

- Base mapping remains in code:
  - apps/woocommerce_fusion/woocommerce_fusion/woocommerce/doctype/woocommerce_order/woocommerce_order.py:21
- At runtime, compute an effective mapping per server:
  - effective_map = base_map union server.custom_status_map (server entries win on duplicate keys).
  - Derive effective_reverse = {slug: label for label, slug in effective_map.items()}.
- Use the effective_map/effective_reverse everywhere instead of the module constants when a server context is available (inbound and outbound paths).

## Inbound Sync (Woo → ERPNext)

- Scheduler:
  - Pull modified orders without status filter: get_list_of_wc_orders(date_time_from=...).
  - Pull deletions: get_list_of_wc_orders(date_time_from=..., status="trash").
  - For each fetched order, if order.status not in allowed_inbound_statuses: skip (log at INFO/WARN).
  - Else, map slug → label using effective_reverse. If missing:
    - Derive a temporary label (title‑cased from slug), log WARN, and continue; or require admins to add a custom map entry (recommended). No crashes.

- Webhook:
  - Accept order created/updated events. Apply the same allowlist gating.
  - Use effective_reverse to set Sales Order.woocommerce_status.

## Outbound Updates (ERPNext → Woo)

- When pushing status changes back to Woo, use effective_map to resolve the ERPNext label → Woo slug.
- If the label is not found in effective_map, skip the update and log WARN (don’t raise).
- Per‑server “Sales Order Status Map” continues to control how ERPNext core statuses map to Woo for outbound transitions:
  - Doctype: WooCommerce Server > Sales Order Status Map
  - Its Woo status picker should be populated from effective_map keys.

## Sales Order UI (dynamic dropdown)

- Replace the static Select options with dynamic options derived per server:
  - Server method: WooCommerceServer.get_woocommerce_order_status_list(self) returns list(effective_map.keys()).
    - Implementation includes custom_status_map JSON in addition to the base mapping.
  - Client script (Sales Order form): on load/change of doc.woocommerce_server, fetch and set options via frm.set_df_property("woocommerce_status", "options", options.join("\n")).
  - List view formatting continues as is; no change required.

## Error Handling and Observability

- KeyError prevention: replace direct dict indexing with .get(...) or effective_reverse.get(...).
- Unknown slugs:
  - If not in allowlist: skip and log INFO/WARN with the slug, order id, server.
  - If in allowlist but not mapped: log WARN, derive a temporary label or ask admins to add a mapping; never crash.
- Add structured logging around gating decisions for easy diagnosis.

## Security

- Re‑enable HMAC verification in the webhook endpoint:
  - apps/woocommerce_fusion/woocommerce_fusion/woocommerce_endpoint.py:29–35
  - Secret sourced from WooCommerce Server.secret

## Backward Compatibility

- Base mapping and existing behavior stay intact for servers that don’t configure allowlists or custom maps.
- Default allowlist ["processing"] mimics current expectations while enabling opt‑in for custom slugs.
- Trash handling remains unchanged.

## Testing Plan

- Effective mapping
  - Merging logic returns base + custom; reverse map resolves custom slugs.
- Scheduler gating
  - Orders with status in allowlist are processed; others skipped.
  - Deletions still processed via status="trash" fetch.
- Webhook gating
  - Events with status in allowlist are created/updated; others ignored.
- Unknown slugs
  - No KeyError; logs carry context; temporary label behavior verified (if enabled).
- Outbound mapping
  - Only mapped labels are pushed; unmapped labels are skipped with WARN.
- UI
  - Sales Order dropdown reflects merged labels for the selected server.

## Rollout

1) Add fields on WooCommerce Server: allowed_inbound_statuses and custom_status_map.
2) Update mapping utilities to compute effective_map/effective_reverse per server.
3) Replace direct mapping usages with effective lookups in inbound and outbound code paths.
4) Make Sales Order dropdown dynamic (server method + client script).
5) Re‑enable webhook HMAC verification.
6) Migrate existing servers to default allowlist ["processing"]. Document how to add e.g., trade-order:
   - Add to allowed_inbound_statuses: ["processing", "trade-order"].
   - Add a custom mapping entry: {label: "Trade Order", slug: "trade-order"}.
   - Verify dropdown now includes "Trade Order" and that inbound/outbound paths work.
