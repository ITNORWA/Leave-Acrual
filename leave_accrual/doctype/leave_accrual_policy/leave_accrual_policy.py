# Copyright (c) 2024, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LeaveAccrualPolicy(Document):
	def validate(self):
		if self.accrual_rate < 0:
			frappe.throw("Accrual Rate cannot be negative")
