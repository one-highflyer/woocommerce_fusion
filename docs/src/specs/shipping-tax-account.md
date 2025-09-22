# Shipping Tax Posting: Use Tax/GST Account Instead of Freight

## Overview

When creating ERPNext Sales Orders from WooCommerce, shipping tax is currently posted to the Freight and Forwarding account (F&F) when no Shipping Rule is applied. This spec routes shipping tax to the Tax/GST account instead, while keeping the shipping total itself in F&F.

## Goals

- Post shipping tax amounts to the configured Tax Account on the WooCommerce Server doctype.
- Retain current behavior for shipping total (freight/charges) to F&F Account.
- Preserve Shipping Rule behavior—when a Shipping Rule is present, rates/taxes remain governed by the rule.

## Current Behavior (for reference)

- Item‐level taxes (when using "Use 'Actual' Tax Type") are posted to `wc_server.tax_account`:
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:918`
- When no Shipping Rule is set, shipping tax and shipping total both post to F&F Account:
  - Shipping tax line uses F&F: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:924`
  - Shipping total line uses F&F: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:925`–`:930`

## Proposed Behavior

1) Shipping tax → Tax account
- If `wc_server.enable_tax_lines_sync` is on and we are adding a shipping tax line in the "no Shipping Rule" path, use `wc_server.tax_account` for the tax line’s `account_head` instead of `wc_server.f_n_f_account`.
- Fallback: if `tax_account` is not defined (or "Use 'Actual' Tax Type" is not enabled), fall back to current F&F behavior to avoid validation errors.

2) Shipping total → Freight account
- No change: continue posting the shipping total amount to `wc_server.f_n_f_account`.

## Affected Code

- Change account head for shipping tax line:
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:924`

## Backward Compatibility

- Maintains existing ledger behavior for shipping total (freight/charges).
- Only the shipping tax account changes when a Tax Account is configured; otherwise behavior is unchanged via fallback.

## Testing Plan

- Add/extend tests to verify:
  - With `use_actual_tax_type=1` and `tax_account` set, the shipping tax line’s `account_head` equals the Tax Account.
  - With `tax_account` missing, the shipping tax line falls back to F&F.
  - Shipping total continues to post to F&F.

## Rollout

1) Implement the account change for shipping tax as described.
2) Validate with a test order having shipping tax and no Shipping Rule.
3) Monitor GL entries in a test/staging environment.

