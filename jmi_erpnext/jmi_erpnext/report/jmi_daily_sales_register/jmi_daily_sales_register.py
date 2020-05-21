# Copyright (c) 2020, JMI Barcodes

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _


def execute(filters=None, additional_table_columns=None, additional_query_columns=None):
	""" Standard execute() function for all Frappe Script Reports."""
	if not filters:
		filters = frappe._dict({})

	columns, modes_of_payment = get_columns(additional_table_columns, filters)

	invoice_list = get_invoices(filters, additional_query_columns)  # List of Dictionary.
	if not invoice_list:
		msgprint(_("No invoices found."))
		return columns, invoice_list

	data = []
	for inv in invoice_list:
		row = []
		row += [inv.name, inv.customer_name, inv.total, inv.total_taxes_and_charges, inv.discount_amount, inv.grand_total]
		
		amt_list = get_amount_by_paymentmode(inv.name)
		for col in modes_of_payment:
			credit = [a_entry.amount for a_entry in amt_list if a_entry.mode_of_payment == col]
			row.append(credit[0] if len(credit) > 0 else 0.0)
		
		row += [inv.change_amount, inv.owner]
		data.append(row)

	return columns, data


def get_columns(additional_table_columns, filters):
	"""Return columns based on filters"""
	# May 11 2020: Added Discount Amount

	columns = [
		_("Invoice") + ":Link/Sales Invoice:100",
		_("Customer Name") + "::120",
	]

	if additional_table_columns:
		columns += additional_table_columns

	columns += [_("Net Total") + ":Currency/currency:100"] + \
	[_("Total Tax") + ":Currency/currency:100"] + \
	[_("Discount Amount") + ":Currency/currency:100"] + \
	[_("Grand Total") + ":Currency/currency:100"]

	# Add column for each Mode of payment that exists *given current criteria*
	mop_columns = []
	mop = frappe.db.sql_list(
		"""
		SELECT DISTINCT
			mode_of_payment
		FROM `tabSales Invoice Payment`
		""".format(
			conditions=get_conditions(filters)
		),
		filters)
	
	for a in mop:
		mop_columns = _(a) + ":Currency/currency:110"
		columns.append(mop_columns)

	columns.append(_("Change Amount") + ":Currency/Currency:100")
	columns.append(_("Owner") + "::150")

	return columns, mop


def get_conditions(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " and company=%(company)s"

	if filters.get("customer"):
		conditions += " and customer = %(customer)s"

	if filters.get("from_date"):
		conditions += " and posting_date >= %(from_date)s"

	if filters.get("to_date"):
		conditions += " and posting_date <= %(to_date)s"

	if filters.get("owner"):
		conditions += " and owner = %(owner)s"

	if filters.get("mode_of_payment"):
		conditions += """ and exists(select name from `tabSales Invoice Payment`
			 where parent=`tabSales Invoice`.name
			 	and ifnull(`tabSales Invoice Payment`.mode_of_payment, '') = %(mode_of_payment)s)"""

	if filters.get("cost_center"):
		conditions += """ and exists(select name from `tabSales Invoice Item`
			 where parent=`tabSales Invoice`.name
			 	and ifnull(`tabSales Invoice Item`.cost_center, '') = %(cost_center)s)"""

	if filters.get("warehouse"):
		conditions += """ and exists(select name from `tabSales Invoice Item`
			 where parent=`tabSales Invoice`.name
			 	and ifnull(`tabSales Invoice Item`.warehouse, '') = %(warehouse)s)"""

	return conditions


def get_invoices(filters, additional_query_columns):
	""" Document Status:  0(Draft), 1(Unpaid), 2(Paid) """

	if additional_query_columns:
		additional_query_columns = ', ' + ', '.join(additional_query_columns)

	conditions = get_conditions(filters)
	return frappe.db.sql("""select name, posting_date, customer, customer_name, owner,
		total, grand_total, change_amount,
		CASE WHEN apply_discount_on = 'Grand Total' THEN
			total_taxes_and_charges + (discount_amount - (total - net_total))
			ELSE total_taxes_and_charges
		END AS total_taxes_and_charges, discount_amount {0}
		from `tabSales Invoice`
		where docstatus = 1 AND is_pos= 1 %s order by posting_date desc, name desc""".format(additional_query_columns or '') %
	                     conditions, filters, as_dict=1)


def get_amount_by_paymentmode(inv_name):
	query = """SELECT parent, mode_of_payment, amount
			FROM `tabSales Invoice Payment`
			WHERE parent = '{inv_name}'
			order by parent desc""".format(inv_name=inv_name)
	return frappe.db.sql(query, as_dict=1)
