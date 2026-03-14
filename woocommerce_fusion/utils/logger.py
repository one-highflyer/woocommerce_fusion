import logging

import frappe


def get_logger(logger_name=None) -> logging.Logger:
	logger_name = logger_name if logger_name else "woocommerce_fusion"
	logger = frappe.logger(logger_name, allow_site=True)
	logger.setLevel(logging.INFO)
	return logger
