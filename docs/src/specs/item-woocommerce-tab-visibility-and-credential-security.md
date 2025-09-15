# Spec: Secure WooCommerce API Credentials

## Overview
Store the WooCommerce API consumer secret securely (encrypted) using a Password field while maintaining backward compatibility for existing installations.

## Goals
- Store API consumer secret securely using Frappe's Password field.
- Maintain backward compatibility and avoid breaking existing installations.

## Non-Goals
- Changing existing business logic for sync and item linkage.
- Removing legacy fields immediately (deprecate first, remove later).

## Current State
- WooCommerce API consumer secret is stored as a Data field on `WooCommerce Server` (see `apps/woocommerce_fusion/woocommerce_fusion/woocommerce/doctype/woocommerce_server/woocommerce_server.json`). Code reads it directly when building the API client (`apps/woocommerce_fusion/woocommerce_fusion/woocommerce/woocommerce_api.py`).

## High-Level Design
1. Add a new Password field on `WooCommerce Server` to securely store the API consumer secret; read the secret from this new field when available, with a safe fallback to the old Data field.
2. Migrate existing secrets from the old Data field to the new Password field via a patch, without breaking running systems.
3. Deprecate the old Data field in a later release; remove it in a subsequent release once safe.

## Data Model Changes
### WooCommerce Server
- Add `api_consumer_secret_password` (Password)
  - Label: "API consumer secret"
  - Replace the UI use of the old Data field over time.
  - Keep the old Data field `api_consumer_secret` in the schema for now for backward compatibility.

## Backward Compatibility and Migration
1. Servers' secrets remain functional during transition:
   - New code reads secret from `api_consumer_secret_password` via `get_decrypted_password(...)` first, and falls back to `api_consumer_secret` when the Password field is empty.
   - Data patch copies existing `api_consumer_secret` to `api_consumer_secret_password` if empty.
   - In the same patch or later release, optionally clear `api_consumer_secret` value after migration (or only hide it in UI first, see rollout plan).

## Implementation Steps
### Release N
- DocType change
  - Add `api_consumer_secret_password` (Password) to `WooCommerce Server`.

- Code (backward-compatible)
  - Centralize secret retrieval when creating the WooCommerce API client:
    - Try `frappe.utils.password.get_decrypted_password('WooCommerce Server', server.name, 'api_consumer_secret_password', raise_exception=False)`.
    - If not present, fallback to `server.api_consumer_secret`.

- Patches (data migrations)
  - WooCommerce Server secret backfill: if `api_consumer_secret_password` empty and `api_consumer_secret` has a value, copy it to the Password field.

### Release N+1
- UI tightening
  - Hide `api_consumer_secret` (Data) field in `WooCommerce Server` or relabel as "Deprecated" and set `hidden: 1`.

- Keep runtime fallback
  - Continue to support fallback reads for one more release.

### Release N+2
- Cleanup
  - Remove `api_consumer_secret` (Data) from the DocType and delete fallback code.

## Testing
### Manual
- WooCommerce Server UI
  - Secret entry is masked in UI via Password field.
  - Existing servers function without re-entering secrets.

### Automated (where applicable)
- Add unit test for secret retrieval priority: Password field first, fallback to Data if empty.
- Ensure Item sync/stock/price flows operate unaffected (regression tests).

## Rollout and Deployment
1. Ship Release N with DocType field, code fallback, and patches.
2. Monitor error logs for any secret retrieval failures or UI issues.
3. In Release N+1, hide/deprecate the old Data field in the UI.
4. In Release N+2, remove the old Data field and fallback code.

## Risks and Mitigations
- Users with custom scripts referencing the old Data field:
  - Mitigation: deprecate gradually; communicate in change log; keep fallback reads for two releases.
- Patch timing/order issues:
  - Mitigation: write idempotent patches; guard checks for field existence and values.

## Acceptance Criteria
- WooCommerce Server secrets are stored encrypted via Password field, and API calls succeed without requiring reconfiguration.
- Old secret field is deprecated in UI by N+1 and fully removed by N+2.

