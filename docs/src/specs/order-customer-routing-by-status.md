# Conditional Customer Routing For Woo Orders (By Status)

## Overview
- Goal: Allow routing of inbound WooCommerce orders to either a single, preconfigured ERPNext Customer or to a per-order Customer (matched/created by email), based on the Woo order’s status slug.
- Primary use case: “Trade” orders (e.g., status slug `trade-order`) should create/match a Customer by email; all other orders should route to a single Customer if configured.
- Scope: Woo → ERPNext direction only (order creation/update). Does not change item sync or payments logic.

## Current Behavior (Reference)
- Routing is mutually exclusive today:
  - If “Use a single Customer” is enabled on the server, every inbound order routes to that single Customer.
  - Otherwise, each inbound order creates/matches a Customer using the billing email (with guest handling and optional dual accounts).
- Key code paths:
  - `woocommerce_fusion/tasks/sync_sales_orders.py`
    - `create_or_link_customer_and_address(...)`: chooses single-customer flow vs per-order flow.
    - `create_sales_order(...)`: builds and inserts the ERPNext Sales Order.
  - Woo status mapping and inbound gating:
    - `woocommerce/doctype/woocommerce_server/woocommerce_server.py` (effective status map, inbound gating).
    - `woocommerce/doctype/woocommerce_server/woocommerce_server.json` (fields: `custom_status_map`, `allowed_inbound_statuses`, `use_single_customer`, `single_customer`).

## Problem
Some businesses need a hybrid routing model:
- “Trade” orders (a custom status on Woo) should go to distinct Customers (by email), while
- Normal web orders should continue to route to one single Customer.

## Requirements
- Per-server configurability (each WooCommerce Server can define its own status slugs).
- Backward compatible with existing setups.
- Minimal code and UX changes; leverage existing single-customer and per-order logic.

## Proposed Data Model Changes
- Add a new JSON field on DocType “WooCommerce Server”:
  - Fieldname: `statuses_to_route_to_order_customer`
  - Label: “Statuses to Route to Order Customer”
  - Type: JSON (expects a JSON array of Woo status slugs)
  - Default: `[]`
  - Placement: under the “Customers Sync” section (near `use_single_customer` / `single_customer`).
  - Help text: “JSON array of Woo status slugs for which incoming orders should create/match the Customer by email (trade orders). All other orders follow Single Customer if enabled.”

Notes:
- Merchants can define a custom “Trade Order” in `custom_status_map` (e.g., `{ "label": "Trade Order", "slug": "trade-order" }`).
- If inbound gating is used, include `trade-order` in `allowed_inbound_statuses` to permit creation.

## Routing Logic (Runtime)
Given an inbound `WooCommerce Order` (wc_order) and its server (wc_server):

1) Parse `wc_server.statuses_to_route_to_order_customer` as a list of slugs (empty list if unset/invalid).
2) Compute `route_to_order_customer = wc_order.status in statuses_to_route_to_order_customer`.
3) Branch:
   - If `route_to_order_customer` is true: run the existing per-order Customer logic (create/match by email; guest ID fallback).
   - Else if `wc_server.use_single_customer and wc_server.single_customer`: run the existing single-customer path.
   - Else: run the existing per-order Customer logic (backward compatibility when no single customer is configured).

Implementation detail:
- In `create_or_link_customer_and_address(...)`, derive the branch using the above rules.
- Set an instance flag (e.g., `self._used_single_customer = True/False`) to indicate which branch was used.
- In `create_sales_order(...)`, only apply the single-customer-specific address/contact assignment when `self._used_single_customer` is true. This prevents applying single-customer address/contact reuse to trade orders.

## Interactions With Status Configuration
- Custom Status Mapping (`custom_status_map`):
  - Admins add new label/slug pairs (e.g., `Trade Order` → `trade-order`). These are merged with base status mappings and used for UI dropdowns and runtime resolution.
- Allowed Inbound Statuses (`allowed_inbound_statuses`):
  - If set and non-empty, inbound creation is allowed only for listed slugs. Include `trade-order` here to allow trade orders. If left empty, all known slugs are allowed (legacy behavior).
- Status-to-Customer Routing (`statuses_to_route_to_order_customer`):
  - Controls which statuses (by slug) will use the per-order Customer path.
  - Typical example: `["trade-order"]`.

## Example Configurations
- Hybrid (trade via email, others to single):
  - `use_single_customer = 1` and `single_customer = <Customer>`
  - `custom_status_map = [{"label":"Trade Order","slug":"trade-order"}]`
  - `allowed_inbound_statuses = ["processing","trade-order"]` (or leave empty to allow all)
  - `statuses_to_route_to_order_customer = ["trade-order"]`

- All single-customer (current default behavior):
  - `use_single_customer = 1`, `single_customer = <Customer>`
  - `statuses_to_route_to_order_customer = []` (omit or empty)

- All per-order customers:
  - `use_single_customer = 0`
  - `statuses_to_route_to_order_customer` ignored; always per-order.

## Pseudocode
In `create_or_link_customer_and_address(self, wc_order)`:

```
statuses = parse_json(wc_server.statuses_to_route_to_order_customer) or []
route_to_order_customer = wc_order.status in statuses

if route_to_order_customer or not (wc_server.use_single_customer and wc_server.single_customer):
    self._used_single_customer = False
    return per_order_customer_flow(wc_order)  # existing logic (email/guest/dual accounts)
else:
    self._used_single_customer = True
    return single_customer_flow(wc_order)     # existing logic (address/contact reuse)
```

In `create_sales_order(self, wc_order)`:

```
if getattr(self, "_used_single_customer", False):
    # set SO.customer_address / SO.shipping_address_name / SO.contact_person
    # using results of handle_single_customer_address_and_contact_sync(...)
```

## Backward Compatibility
- Default `statuses_to_route_to_order_customer = []` preserves current behavior:
  - If single-customer is enabled: all orders route to the single Customer (as today).
  - If single-customer is disabled: per-order Customer matching (as today).
- No migrations needed for existing records besides adding the new DocField.

## Edge Cases
- If a status slug is listed in `statuses_to_route_to_order_customer` but excluded by inbound gating, the order will be skipped (as with any disallowed status).
- If a custom status slug was not defined in Woo or `custom_status_map`, admins won’t see it in dropdowns; however, the raw slug still works if typed into the JSON fields (not recommended). Prefer defining it in `custom_status_map` for clarity and UI consistency.
- Guest orders continue to use `Guest-{order_id}` as identifier in the per-order flow.
- Dual accounts (same email, company set) continue to be respected in per-order flow if enabled via `enable_dual_accounts`.

## Testing Plan
Add/extend tests to cover:
- Hybrid routing (single-customer enabled, `statuses_to_route_to_order_customer = ["trade-order"]`):
  - Woo order with status `trade-order` creates/matches Customer by email (not the single Customer).
  - Woo order with status `processing` routes to the single Customer.
- Single-customer disabled: both statuses create/match per-order Customers (unchanged behavior).
- Backward compatibility: with `statuses_to_route_to_order_customer = []`, single-customer mode routes all orders to the single Customer (existing tests remain valid).

## Implementation Notes
- Minimal changes are required in:
  - `woocommerce_fusion/tasks/sync_sales_orders.py` (branching in `create_or_link_customer_and_address`, conditional address setting in `create_sales_order`).
  - `woocommerce/doctype/woocommerce_server/woocommerce_server.json` (add new JSON field in Customers Sync section).
- Logging and error handling follow existing patterns (no new log types introduced).

## Rollout
1) Add the new DocField and ship the code changes.
2) Update documentation to illustrate typical configurations for trade orders.
3) Optional: provide a UI helper in the server form to prefill `statuses_to_route_to_order_customer` from known slugs.

