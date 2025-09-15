# WooCommerce → ERPNext: Single-Customer Order Mapping

## Overview

Map every WooCommerce order from a given WooCommerce Server to a single ERPNext Customer, while still creating and linking addresses (and contacts) from each order. Reuse existing addresses/contacts when they match 100% to prevent uncontrolled growth.

## Goals

- All orders for a configured WooCommerce Server map to one ERPNext Customer.
- Create and link Sales Order delivery/billing addresses from Woo data.
- Reuse addresses when content is identical; otherwise create new.
- Reuse contacts primarily by email; otherwise by name + phone; otherwise create new.
- Avoid changing the Customer’s preferred/primary address/contact unless empty.

## Non‑Goals

- No deduplication across different Customers.
- No attempt to normalize addresses beyond straightforward canonicalization (no geocoding or fuzzy matching).
- No change to stock, item, payment, or order status syncing logic.

## Configuration

Add settings on the WooCommerce Server doctype:

- `use_single_customer` (Check): Use a single ERPNext Customer for all incoming orders on this server.
- `single_customer` (Link to Customer): Required when `use_single_customer` is checked.

Default: disabled (existing behavior unchanged).

## Sync Flow Changes

Entry point: `create_or_link_customer_and_address(wc_order)` in `tasks/sync_sales_orders.py`.

1) Server selection

- If `wc_server.use_single_customer` is enabled:
  - Set `self.customer` to `frappe.get_doc("Customer", wc_server.single_customer)`.
  - Perform address reuse/creation for this Customer (see Address Matching).
  - Perform contact reuse/creation (see Contact Matching).
  - Return `self.customer.name`.
- Else: Keep the current behavior (identifier-based Customer creation/linking, address/contact sync as it is).

2) Sales Order linking

- In `create_sales_order(...)`, after items/fees are set but before insert:
  - If single-customer mode, set `new_sales_order.customer = wc_server.single_customer`.
  - Set `new_sales_order.customer_address` and `new_sales_order.shipping_address_name` from the chosen addresses (reused or newly created for the order).

## Address Matching

Scope: Only addresses linked to the selected single Customer.

Types: Match separately for `Billing` and `Shipping`. If Woo billing and shipping are identical (post-canonicalization), use a single address for both.

Canonicalization rules before comparing:

- Trim whitespace and collapse internal whitespace where appropriate.
- Lowercase compare for string fields (except where ERPNext dictates case sensitivity; typically not required for addresses).
- Country: Resolve Woo country code to ERPNext Country name (same path used during creation).
- Missing values treated as empty strings. Apply the same fallback values used at creation (e.g., "Not Provided") so creation and comparison are consistent.

Fields compared for exact equality:

- `address_line1`
- `address_line2`
- `city`
- `state`
- `pincode`
- `country`
- `phone`
- `address_type` (Billing/Shipping)

Reuse-or-create algorithm:

- If billing and shipping blocks are identical → compute one canonical address; search for a match in existing addresses of the same `address_type`; if found reuse, else create one and link for both roles.
- If they differ → process billing and shipping independently using the same matching rules.
- Do not modify `is_primary_address` or `is_shipping_address` on existing addresses; for newly created addresses set both flags to 0 unless both roles share the same address and no preferred addresses exist yet (optional policy, see below).

Optional optimization (fast path):

- Compute an address signature as a stable hash over the canonicalized fields (e.g., `sha1(json.dumps(canon, sort_keys=True))`).
- Store the signature in a custom field on Address (e.g., `woocommerce_address_signature`) to accelerate matching. If present, attempt an exact signature match first, then fall back to field-by-field comparison to guard against schema drift.

## Contact Matching

Scope: Only Contacts linked to the selected single Customer.

Primary key: Email (case-insensitive exact match).

Secondary key (when email missing): Name + Phone.

Normalization:

- Email → lowercase.
- Phone → strip non-digits for comparison; if country code present, keep it; do not attempt number formatting beyond this.
- Names → trim whitespace; use `first_name` and `last_name` as given.

Reuse-or-create algorithm:

- If a linked Contact exists with the same normalized email → reuse; optionally backfill empty phone.
- Else if a linked Contact exists with the same normalized phone and same `first_name`+`last_name` → reuse.
- Else → create a new Contact linked to the Customer; set `is_primary_contact`/`is_billing_contact` to 0 (do not mark new contacts as primary in single‑customer mode).
- If the Customer has no `customer_primary_contact`, set it to the reused/created contact. Do not overwrite an existing primary contact.

## Error Handling & Edge Cases

- Missing email and phone → skip contact creation; continue without error.
- Billing == Shipping → ensure both Sales Order address fields point to the same Address record.
- Deleted/empty Woo fields → normalized to empty strings or “Not Provided” in the same manner as creation, so equality is stable.
- Country/state code vs name → always resolve using the same logic used during creation prior to comparison.

## Backward Compatibility

- When `use_single_customer` is disabled, behavior is unchanged.
- Enabling the setting impacts only orders for that WooCommerce Server.

## Security & Permissions

- Respect existing usage of `creation_user` on WooCommerce Server for document creation.
- Ensure the user has permission to read/write Customer, Address, Contact, and Sales Order.

## Testing Plan

Integration tests (extend `test_integration_so_sync.py`):

- Single-customer mode routes all orders to the configured Customer.
- Address reuse:
  - Order #1 with address A creates Address A and links it.
  - Order #2 with address A reuses Address A (no new address count), links it.
- Address creation on change:
  - Order #3 with address B (different canonical values) creates new Address B and links it.
- Billing == Shipping creates or reuses a single address and links both SO fields to it.
- Contact reuse by email; creation when email changes; reuse by name+phone when email absent.
- Primary address/contact are not overwritten unless empty (if this policy is implemented).

Unit tests:

- Canonicalization correctness for casing, whitespace, and country resolution.
- Signature stability (if signature optimization is implemented).

## Rollout Plan

1) Add the two WooCommerce Server fields and ship migrations.
2) Implement the single-customer branch in the sync flow (customer selection, address/contact reuse).
3) Link chosen addresses to Sales Order (`customer_address`, `shipping_address_name`).
4) Add tests; run CI; monitor Error Logs in staging.
5) Enable `use_single_customer` and set `single_customer` in production for the relevant server(s).

## Implementation Notes

- Contact flags: The current helper that creates contacts may set `is_primary_contact`/`is_billing_contact` to 1 by default. In single‑customer mode, ensure newly created contacts have these flags set to 0, and only set `Customer.customer_primary_contact` when it is empty.
- Address signature: If implementing the fast‑path optimization, use a dedicated custom field on Address named `woocommerce_address_signature` (read‑only). Use signature match as a pre‑check, then confirm with field equality to remain robust.

## Open Questions

- Do we want to ever set `is_primary_address`/`is_shipping_address` on the single Customer automatically (e.g., only for the first created address)? Default proposal: no.
- Should we attempt phone normalization to full E.164 when country is known? Default proposal: no; keep simple digit-stripping.
- Do we want to persist an address signature field on Address for faster matching? Default proposal: optional; field can be added later without changing behavior.
