from __future__ import unicode_literals

import traceback

import frappe
from frappe import _
from frappe.utils.fixtures import sync_fixtures


def execute():
    """Set woocommerce_enabled = 1 for Items that have woocommerce_servers child table rows"""

    try:
        # Sync fixtures to ensure that the custom field `woocommerce_enabled` exists
        sync_fixtures("woocommerce_fusion")

        # Check if the woocommerce_enabled field exists in Item doctype
        if not frappe.db.has_column("Item", "woocommerce_enabled"):
            # The custom field might not be installed yet
            print(_("woocommerce_enabled field not found in Item, skipping patch"))
            return

        # Get all Items that have at least one WooCommerce Server link
        items_with_woocommerce = frappe.get_all(
            "Item WooCommerce Server",
            fields=["parent"],
            group_by="parent",
            pluck="parent",
        )

        if not items_with_woocommerce:
            print(_("No Items with WooCommerce Server links found"))
            return

        print(
            _("Updating {} Items to have woocommerce_enabled = 1").format(
                len(items_with_woocommerce)
            )
        )

        updated_count = 0

        # Update each Item using Frappe's document API
        for item_name in items_with_woocommerce:
            try:
                # Use db.set_value for efficient updates without loading full document
                if not frappe.db.get_value("Item", item_name, "woocommerce_enabled"):
                    frappe.db.set_value(
                        "Item",
                        item_name,
                        "woocommerce_enabled",
                        1,
                        update_modified=False,
                    )
                    updated_count += 1
            except Exception as item_err:
                print(
                    _("Failed to update Item {}: {}").format(item_name, str(item_err))
                )
                continue

        print(
            _("Successfully updated {} Items to have woocommerce_enabled = 1").format(
                updated_count
            )
        )

    except Exception as err:
        print(_("Failed to backfill woocommerce_enabled field for Items"))
        print(traceback.format_exception(err))
