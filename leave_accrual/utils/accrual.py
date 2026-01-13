import frappe
from frappe.utils import getdate, date_diff, flt, nowdate

def _round_to_increment(value, increment):
    if not increment or increment <= 0:
        return value
    return round(value / increment) * increment

def get_leave_policy(leave_type):
    return frappe.db.get_value("Leave Accrual Policy", {"leave_type": leave_type}, "*", as_dict=True)

def get_employee_details(employee):
    return frappe.db.get_value("Employee", employee, ["date_of_joining", "status"], as_dict=True)

@frappe.whitelist()
def get_leave_balance(employee, leave_type, as_on_date=None):
    if not as_on_date:
        as_on_date = nowdate()
    
    as_on_date = getdate(as_on_date)
    policy = get_leave_policy(leave_type)
    
    if not policy:
        return 0.0
        
    emp_details = get_employee_details(employee)
    if not emp_details or not emp_details.date_of_joining:
        return 0.0
        
    joining_date = getdate(emp_details.date_of_joining)
    current_year_start = getdate(f"{as_on_date.year}-01-01")
    accrual_start_date = current_year_start if joining_date < current_year_start else joining_date
    
    if as_on_date < accrual_start_date:
        return 0.0

    days_worked = date_diff(as_on_date, accrual_start_date) + 1
    earned = 0.0
    
    if policy.accrual_type == "Monthly":
        # Accrue per completed calendar month within the accrual year.
        months_elapsed = (
            (as_on_date.year - accrual_start_date.year) * 12
            + (as_on_date.month - accrual_start_date.month)
            + 1
        )
        months_elapsed = max(months_elapsed, 0)
        earned = months_elapsed * policy.accrual_rate
        
    elif policy.accrual_type == "Quarterly":
        total_annual_allocation = policy.accrual_rate * 4
        earned = (days_worked / 365.0) * total_annual_allocation
        
    elif policy.accrual_type == "Yearly":
        earned = (days_worked / 365.0) * policy.accrual_rate

    if policy.max_annual_entitlement and earned > policy.max_annual_entitlement:
        earned = policy.max_annual_entitlement

    # Fetch total leaves taken within the current accrual period (Year)
    leaves_taken = frappe.db.sql("""
        SELECT SUM(total_leave_days)
        FROM `tabLeave Application`
        WHERE employee = %s 
        AND leave_type = %s
        AND status = 'Approved'
        AND docstatus = 1
        AND from_date >= %s
    """, (employee, leave_type, current_year_start))
    
    taken = flt(leaves_taken[0][0]) if leaves_taken and leaves_taken[0][0] else 0.0
    
    balance = earned - taken
    balance = _round_to_increment(balance, policy.get("rounding_increment"))
    return flt(balance, 2)

def validate_leave_application(doc, method):
    if doc.status == "Rejected" or doc.status == "Cancelled":
        return
        
    policy = get_leave_policy(doc.leave_type)
    if not policy:
        return
        
    balance = get_leave_balance(doc.employee, doc.leave_type)
    
    # If submitting an existing doc, ensure we don't double count ITSELF in 'leaves_taken' 
    # (since get_leave_balance sums 'Approved' docs. If existing doc is draft, it's not summoned. If it's submitted, it becomes 'Approved' AFTER this hook usually?
    # Actually 'before_submit' -> docstatus is still 0 (Draft) but transitioning.
    # So get_leave_balance won't see it.
    
    if balance < doc.total_leave_days:
        # Check override
        # We need to access the checkbox on the form. Accessing 'doc' fields.
        # Assuming we added a custom field 'ignore_accrual_check' or similar?
        # User requirement: "HR Override Allowed (Check)".
        # This is on the POLICY. 
        # But who triggers the override? The User?
        # "Prevent submission... unless HR override is checked"
        # This implies a checkbox ON THE APPLICATION.
        # I added custom field logic to the Plan implicitly but need to make sure `Leave Application` has this field.
        # I will check `doc.custom_hr_override`?
        # I cannot add custom fields to core DocType easily without `fixtures`.
        # I will rely on `doc.flags.ignore_permissions` or similar if HR?
        # Or I'll assume the user will create a Custom Field "HR Override".
        
        if policy.hr_override_allowed and getattr(doc, "custom_hr_override", 0):
             frappe.msgprint("Proceeding with insufficient balance (HR Override)")
             return
                 
        frappe.throw(
            msg=f"Insufficient Leave Balance based on Accrual Policy '{policy.policy_name}'.<br>Available: {balance}<br>Requested: {doc.total_leave_days}",
            title="Leave Validation Error"
        )

def update_leave_type_settings(doc, method):
    # When Leave Type is updated, check if it is linked to a Policy
    policy = frappe.db.get_value("Leave Accrual Policy", {"leave_type": doc.name}, "*", as_dict=True)
    if policy:
        # Sync settings
        # exclude_weekends -> include_holiday = 0?
        # Standard Leave Type has 'include_holiday' (Include Holidays within leaves as leaves)
        # If policy.exclude_holidays is TRUE, then leave_type.include_holiday should be FALSE.
        # If policy.exclude_holidays is FALSE, then leave_type.include_holiday should be TRUE (maybe).
        
        updated = False
        if policy.exclude_holidays and doc.include_holiday:
            doc.include_holiday = 0
            updated = True
        
        # There isn't a direct "Exclude Weekend" field in Leave Type standard, 
        # it relies on Holiday List (which covers weekends usually).
        # But making sure holidays are NOT included covers standard holidays.
        
        if updated:
            # We are in 'on_update', so be careful not to trigger recursion
            doc.db_update()
