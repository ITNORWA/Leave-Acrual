import math
from frappe.utils import getdate, date_diff, flt, nowdate, add_months, month_diff

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

    earned = 0.0
    
    if policy.accrual_type == "Monthly":
        # Full month accrual: Calculate months passed including the current starting month
        # Requirement: "Acrued leave days is 1.75 anytime of the month"
        # We calculate diff in months. If start=Jan 1, now=Jan 2, diff=0, but we want 1 month credit.
        months_passed = month_diff(as_on_date, accrual_start_date)
        if as_on_date >= accrual_start_date:
             # month_diff(jan_15, jan_01) might be 0. We need to count the start month.
             # Actually month_diff usually rounds or is diff in numbers.
             # Let's use simple calculation:
             months_passed = (as_on_date.year - accrual_start_date.year) * 12 + (as_on_date.month - accrual_start_date.month) + 1
             
        earned = months_passed * policy.accrual_rate
        
    elif policy.accrual_type == "Quarterly":
        # Similar logic or keep pro-rata if not specified? 
        # Requirement specific to "1.75" which implies Monthly rate. Keeping pro-rata for others or applying similar logic.
        # Let's stick to pro-rata for Quarterly unless asked, to avoid breakage.
        days_worked = date_diff(as_on_date, accrual_start_date) + 1
        total_annual_allocation = policy.accrual_rate * 4
        earned = (days_worked / 365.0) * total_annual_allocation
        
    elif policy.accrual_type == "Yearly":
        days_worked = date_diff(as_on_date, accrual_start_date) + 1
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
    
    return flt(earned - taken, 2)

def validate_leave_application(doc, method):
    if doc.status == "Rejected" or doc.status == "Cancelled":
        return
        
    policy = get_leave_policy(doc.leave_type)
    if not policy:
        return
        
    balance = get_leave_balance(doc.employee, doc.leave_type)
    
    # Check 1: Existing Negative Balance Recovery
    # If the balance is ALREADY negative (before this application), we block unless date is future enough.
    # Note: get_leave_balance returns (Earned - Approved). 
    # If I have -3.0 balance.
    if balance < 0:
        deficit = abs(balance)
        monthly_rate = policy.accrual_rate
        if not monthly_rate: 
            monthly_rate = 1.0 # fallback prevention
            
        months_to_recover = math.ceil(deficit / monthly_rate)
        
        # Calculate when the balance would be restored to >= 0 (ignoring new accruals helping? No, accruals help)
        # We need to find the date where Earned increases by 'deficit'.
        # Since we use Monthly full accrual:
        # unlock_date should be N months from now? Or from Accrual Start?
        # Actually simplest is: You are -3.25. Rate 1.75. You need 2 months.
        # Unlock date = Now + 2 months. 
        # (Assuming current month accrual is already consumed/counted in Balance).
        
        # If balance calculation includes Current Month, then we need Future Months.
        recovery_date = add_months(nowdate(), months_to_recover)
        recovery_date = getdate(recovery_date)
        
        if getdate(doc.from_date) < recovery_date:
             frappe.throw(
                msg=f"You have a negative leave balance of {balance}. You need {months_to_recover} months to recover. You can only apply for leave starting from {recovery_date}.",
                title="Negative Balance Verification"
            )
    
    # Check 2: New Application causing Negative Balance
    # If we are here, either balance >= 0 OR balance < 0 but applying for future date.
    
    # We need a check for the CURRENT request logic.
    # If I have 1.0 day. Request 5 days. Balance becomes -4.0.
    # Requirement: "system will allow ... only if hr manager clicked hr overide"
    
    projected_balance = balance - doc.total_leave_days
    
    if projected_balance < 0:
        # Check override
        # We rely on a custom field 'custom_hr_override' (checkbox) on Leave Application
        if policy.hr_override_allowed and getattr(doc, "custom_hr_override", 0):
             frappe.msgprint(f"Proceeding with negative balance: {projected_balance} (HR Override)")
             return

        # If applying in future (after recovery), we might want to allow?
        # Requirement says: "if in April is when they will be allowed ... system will allow it"
        # That refers to the Blocking Check 1.
        # But for a NEW request that GOES negative, we generally need the override?
        # "The system will allow an application to exceed the current balance ... only if hr manager clicked hr overide"
        # This implies STRICT prohibition of going negative without override.
        
        frappe.throw(
            msg=f"Insufficient Leave Balance based on Accrual Policy '{policy.policy_name}'.<br>Available: {balance}<br>Requested: {doc.total_leave_days}<br>Projected: {projected_balance}<br><br>HR Override is required to proceed with negative balance.",
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
