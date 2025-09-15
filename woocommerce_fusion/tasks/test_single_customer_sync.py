import json
from unittest.mock import patch

import frappe

from woocommerce_fusion.tasks.sync_sales_orders import run_sales_order_sync
from woocommerce_fusion.tasks.test_integration_helpers import TestIntegrationWooCommerce


@patch("woocommerce_fusion.tasks.sync_sales_orders.frappe.log_error")
class TestSingleCustomerSync(TestIntegrationWooCommerce):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

	def setUp(self):
		super().setUp()
		wc_server = frappe.get_doc("WooCommerce Server", self.wc_server.name)
		wc_server.submit_sales_orders = 1
		wc_server.enable_payments_sync = 0
		wc_server.enable_shipping_methods_sync = 0
		wc_server.enable_so_status_sync = 0
		wc_server.flags.ignore_mandatory = True
		wc_server.order_line_item_field_map = []
		wc_server.item_field_map = []
		wc_server.save()

	def test_single_customer_mode_routes_all_orders_to_single_customer(self, mock_log_error):
		"""Test that all orders are routed to a single customer when single-customer mode is enabled."""
		# Create a test customer for single-customer mode
		single_customer = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "Single WooCommerce Customer",
			"customer_type": "Individual"
		})
		single_customer.insert()
		
		# Enable single-customer mode
		wc_server = frappe.get_doc("WooCommerce Server", self.wc_server.name)
		wc_server.use_single_customer = 1
		wc_server.single_customer = single_customer.name
		wc_server.save()
		
		# Create two different WooCommerce orders with different billing data
		wc_order_1 = self._create_test_woocommerce_order(
			billing_data={
				"first_name": "John",
				"last_name": "Doe", 
				"email": "john.doe@example.com",
				"address_1": "123 Main St",
				"city": "New York",
				"country": "US"
			}
		)
		wc_order_2 = self._create_test_woocommerce_order(
			billing_data={
				"first_name": "Jane",
				"last_name": "Smith",
				"email": "jane.smith@example.com", 
				"address_1": "456 Oak Ave",
				"city": "Los Angeles",
				"country": "US"
			}
		)
		
		# Sync both orders
		run_sales_order_sync(woocommerce_order=wc_order_1)
		run_sales_order_sync(woocommerce_order=wc_order_2)
		
		# Get the created sales orders
		so_1 = frappe.get_doc("Sales Order", {"woocommerce_id": wc_order_1.id})
		so_2 = frappe.get_doc("Sales Order", {"woocommerce_id": wc_order_2.id})
		
		# Assert both orders use the same single customer
		self.assertEqual(so_1.customer, single_customer.name)
		self.assertEqual(so_2.customer, single_customer.name)

	def test_single_customer_mode_address_reuse(self, mock_log_error):
		"""Test that addresses are reused when they match in single-customer mode."""
		# Create a test customer for single-customer mode
		single_customer = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "Single WooCommerce Customer",
			"customer_type": "Individual"
		})
		single_customer.insert()
		
		# Enable single-customer mode
		wc_server = frappe.get_doc("WooCommerce Server", self.wc_server.name)
		wc_server.use_single_customer = 1
		wc_server.single_customer = single_customer.name
		wc_server.save()
		
		# Create two orders with identical billing addresses
		billing_data = {
			"first_name": "John",
			"last_name": "Doe",
			"email": "john.doe@example.com",
			"address_1": "123 Main St",
			"city": "New York",
			"country": "US"
		}
		
		wc_order_1 = self._create_test_woocommerce_order(billing_data=billing_data)
		wc_order_2 = self._create_test_woocommerce_order(billing_data=billing_data)
		
		# Get initial address count for the single customer
		addresses_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Address"
			}
		)
		initial_address_count = len(addresses_query)
		
		# Sync first order
		run_sales_order_sync(woocommerce_order=wc_order_1)
		
		# Check address was created
		addresses_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Address"
			}
		)
		after_first_sync_count = len(addresses_query)
		self.assertEqual(after_first_sync_count, initial_address_count + 1)
		
		# Sync second order
		run_sales_order_sync(woocommerce_order=wc_order_2)
		
		# Check address was reused (no new address created)
		addresses_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Address"
			}
		)
		after_second_sync_count = len(addresses_query)
		self.assertEqual(after_second_sync_count, after_first_sync_count)

	def test_single_customer_mode_contact_reuse_by_email(self, mock_log_error):
		"""Test that contacts are reused by email in single-customer mode."""
		# Create a test customer for single-customer mode
		single_customer = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "Single WooCommerce Customer",
			"customer_type": "Individual"
		})
		single_customer.insert()
		
		# Enable single-customer mode
		wc_server = frappe.get_doc("WooCommerce Server", self.wc_server.name)
		wc_server.use_single_customer = 1
		wc_server.single_customer = single_customer.name
		wc_server.save()
		
		# Create two orders with same email but different names
		billing_data_1 = {
			"first_name": "John",
			"last_name": "Doe",
			"email": "john.doe@example.com",
			"address_1": "123 Main St",
			"city": "New York",
			"country": "US"
		}
		
		billing_data_2 = {
			"first_name": "Johnny",
			"last_name": "Doe", 
			"email": "john.doe@example.com",  # Same email
			"address_1": "456 Oak Ave",
			"city": "Los Angeles", 
			"country": "US"
		}
		
		wc_order_1 = self._create_test_woocommerce_order(billing_data=billing_data_1)
		wc_order_2 = self._create_test_woocommerce_order(billing_data=billing_data_2)
		
		# Get initial contact count for the single customer
		contacts_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Contact"
			}
		)
		initial_contact_count = len(contacts_query)
		
		# Sync first order
		run_sales_order_sync(woocommerce_order=wc_order_1)
		
		# Check contact was created
		contacts_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Contact"
			}
		)
		after_first_sync_count = len(contacts_query)
		self.assertEqual(after_first_sync_count, initial_contact_count + 1)
		
		# Sync second order
		run_sales_order_sync(woocommerce_order=wc_order_2)
		
		# Check contact was reused (no new contact created)
		contacts_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Contact"
			}
		)
		after_second_sync_count = len(contacts_query)
		self.assertEqual(after_second_sync_count, after_first_sync_count)

	def test_single_customer_mode_billing_shipping_same_address(self, mock_log_error):
		"""Test that a single address is created when billing and shipping are identical."""
		# Create a test customer for single-customer mode
		single_customer = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "Single WooCommerce Customer",
			"customer_type": "Individual"
		})
		single_customer.insert()
		
		# Enable single-customer mode
		wc_server = frappe.get_doc("WooCommerce Server", self.wc_server.name)
		wc_server.use_single_customer = 1
		wc_server.single_customer = single_customer.name
		wc_server.save()
		
		# Create order with identical billing and shipping
		address_data = {
			"first_name": "John",
			"last_name": "Doe",
			"email": "john.doe@example.com",
			"address_1": "123 Main St",
			"city": "New York",
			"country": "US"
		}
		
		wc_order = self._create_test_woocommerce_order(
			billing_data=address_data,
			shipping_data=address_data
		)
		
		# Get initial address count for the single customer
		addresses_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Address"
			}
		)
		initial_address_count = len(addresses_query)
		
		# Sync order
		run_sales_order_sync(woocommerce_order=wc_order)
		
		# Check only one address was created
		addresses_query = frappe.get_all(
			"Dynamic Link",
			filters={
				"link_doctype": "Customer",
				"link_name": single_customer.name,
				"parenttype": "Address"
			}
		)
		after_sync_count = len(addresses_query)
		self.assertEqual(after_sync_count, initial_address_count + 1)
		
		# Check Sales Order uses same address for both billing and shipping
		so = frappe.get_doc("Sales Order", {"woocommerce_id": wc_order.id})
		self.assertEqual(so.customer_address, so.shipping_address_name)

	def test_single_customer_mode_disabled_uses_normal_behavior(self, mock_log_error):
		"""Test that when single-customer mode is disabled, normal behavior is preserved."""
		# Ensure single-customer mode is disabled
		wc_server = frappe.get_doc("WooCommerce Server", self.wc_server.name)
		wc_server.use_single_customer = 0
		wc_server.single_customer = ""
		wc_server.save()
		
		# Create a WooCommerce order
		wc_order = self._create_test_woocommerce_order(
			billing_data={
				"first_name": "John",
				"last_name": "Doe", 
				"email": "john.doe@example.com",
				"address_1": "123 Main St",
				"city": "New York",
				"country": "US"
			}
		)
		
		# Sync the order
		run_sales_order_sync(woocommerce_order=wc_order)
		
		# Get the created sales order
		so = frappe.get_doc("Sales Order", {"woocommerce_id": wc_order.id})
		
		# Assert that a new customer was created based on email (normal behavior)
		customer = frappe.get_doc("Customer", so.customer)
		self.assertEqual(customer.woocommerce_identifier, "john.doe@example.com")

	def _create_test_woocommerce_order(self, billing_data=None, shipping_data=None, **kwargs):
		"""Helper method to create a test WooCommerce order with custom billing/shipping data."""
		default_billing = {
			"first_name": "Test",
			"last_name": "Customer",
			"email": "test@example.com",
			"address_1": "123 Test St",
			"city": "Test City",
			"country": "US"
		}
		
		billing = {**default_billing, **(billing_data or {})}
		shipping = shipping_data or billing
		
		wc_order_data = {
			"doctype": "WooCommerce Order",
			"id": frappe.generate_hash(length=8),
			"woocommerce_server": self.wc_server.name,
			"status": "processing",
			"currency": "USD",
			"billing": json.dumps(billing),
			"shipping": json.dumps(shipping),
			"line_items": json.dumps([{
				"product_id": self.woocommerce_product.id,
				"quantity": 1,
				"price": 100,
				"subtotal": "100",
				"subtotal_tax": "0"
			}]),
			"date_created": "2023-01-01T00:00:00",
			"date_modified": "2023-01-01T00:00:00",
			"fee_lines": "[]",
			"shipping_lines": "[]",
			**kwargs
		}
		
		wc_order = frappe.get_doc(wc_order_data)
		wc_order.insert()
		return wc_order
