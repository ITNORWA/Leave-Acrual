app_name = "leave_accrual"
app_title = "Leave Accrual Management"
app_publisher = "Antigravity"
app_description = "Custom Leave Accrual Policy for ERPNext HR"
app_email = "bot@example.com"
app_license = "MIT"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "leave_accrual",
# 		"logo": "/assets/leave_accrual/logo.png",
# 		"title": "Leave Accrual Management",
# 		"route": "/leave_accrual",
# 		"has_permission": "leave_accrual.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/leave_accrual/css/leave_accrual.css"
# app_include_js = "/assets/leave_accrual/js/leave_accrual.js"

doctype_js = {
    "Leave Application": "public/js/leave_application.js"
}

# ------------------

# Document Events
# ------------------
# Hook on document methods and events

doc_events = {
	"Leave Application": {
        "validate": "leave_accrual.utils.accrual.validate_leave_application",
        "before_submit": "leave_accrual.utils.accrual.validate_leave_application"
    },
    "Leave Type": {
        "on_update": "leave_accrual.utils.accrual.update_leave_type_settings"
    }
}
