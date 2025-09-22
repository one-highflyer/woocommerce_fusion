# WooCommerce → ERPNext: Minimal Defaults for Address Fields (Single‑Customer Mode)

## Overview

Avoid populating non‑mandatory Address fields with the literal string "Not Provided" when syncing WooCommerce orders into ERPNext in single‑customer mode. Use minimal defaults so only ERPNext‑required fields are filled; optional fields remain empty. This reduces noisy data, improves address matching/reuse, and keeps forms cleaner.

## Goals

- Stop writing "Not Provided" into optional fields (`address_line2`, `state`, `pincode`, `phone`).
- Preserve reliable equality checks and address reuse via canonicalization.
- Keep required fields satisfiable per ERPNext Address doctype.
- Do not auto‑flip preferred address flags.

## Non‑Goals

- No fuzzy matching or geocoding; equality remains exact on canonicalized values.
- No change to customer creation outside single‑customer mode (optional follow‑up).

## Current Behavior (for reference)

- Canonicalization sets "Not Provided" for `address_line1`, `address_line2`, `city` (and blanks for some others):
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:681`
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:682`
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:683`
- Matching existing addresses reuses the same “Not Provided” fallbacks:
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:725`
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:726`
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:727`
- Non single‑customer helpers also default “Not Provided” on create/update.
  - Create: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:1093` (and :1094, :1095)
  - Update: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:1120` (and :1121, :1122)
- ERPNext Address mandatory fields: `address_type`, `address_line1`, `city`, `country`.
  - `apps/frappe/frappe/contacts/doctype/address/address.json:48`, `:55`, `:69`, `:89`

## Proposed Behavior

Scope: Single‑customer mode paths only (optional later extension to general paths).

1) Canonicalization (single‑customer mode)
- Required fields
  - `address_line1`: if missing, default to "-" (dash) to meet ERPNext reqd.
  - `city`: if missing, default to "-" (dash) to meet ERPNext reqd.
  - `country`: resolve from Woo country code to ERPNext Country name; fallback to System Settings country if missing.
- Optional fields
  - `address_line2`, `state`, `pincode`, `phone`: default to empty string, not "Not Provided".
- Case‑insensitive comparisons; trim whitespace.

2) Matching existing addresses
- Continue to prefilter by type and minimal mandatory fields.
- When computing canonical for existing Address rows:
  - Use empty string for optional fields rather than "Not Provided" to keep matching consistent with creation.
  - Normalize legacy values of required fields so that the literal "Not Provided" is treated as "-" during comparison (ensures reuse of previously created addresses).

3) Creating new Address (single‑customer mode)
- Create Address from canonical values; optional fields stored blank.
- Do not set `is_primary_address` or `is_shipping_address` automatically.
- Preserve `address_title_convention` behavior.

4) Sales Order linkage
- No change beyond current single‑customer flow that writes `customer_address` and `shipping_address_name` from the chosen Address(es).

## Affected Code

- Canonicalize address data (adjust optional field defaults):
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:681` (address_line1)
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:682` (address_line2)
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:683` (city)
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:684–687` (state, pincode, country, phone)
- Match existing (adjust optional field canonicalization):
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:725–733`
- Create new address (single‑customer path already uses canonical values):
  - `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:772–779`
- Optional: Mirror in non‑single‑customer create/update helpers for consistency:
  - Create: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:1093–1099`
  - Update: `apps/woocommerce_fusion/woocommerce_fusion/tasks/sync_sales_orders.py:1120–1126`

## Backward Compatibility

- Existing addresses containing “Not Provided” remain usable; comparison normalizes legacy "Not Provided" in required fields to "-" and treats optional missing values as empty strings.
- No impact to status sync, items, or payment flows.

## Testing Plan

- Extend `TestSingleCustomerSync` to assert:
  - Optional fields are blank when WooCommerce omits them.
  - Address reuse works when optional fields differ between "" and previously created "" (no “Not Provided” mismatch).
  - Required field fallbacks use "-" (dash) and still satisfy Address creation.
  - Reuse works against legacy addresses where required fields were previously stored as "Not Provided".

## Rollout

1) Change canonicalization and matching as above in single‑customer code path.
2) Verify with existing `test_single_customer_mode_*` tests; add new tests for optional‑field handling.
3) Optionally backport the same minimal defaults to non single‑customer helpers if desired.
