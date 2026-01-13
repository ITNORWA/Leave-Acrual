
import os
import sys

# Add current directory to sys.path to simulate being in the app root or python path
sys.path.append(os.getcwd())

try:
    import leave_accrual.leave_accrual
    print("SUCCESS: leave_accrual.leave_accrual imported")
except ImportError as e:
    print(f"ERROR: {e}")

try:
    import leave_accrual.leave_accrual.doctype
    print("SUCCESS: leave_accrual.leave_accrual.doctype imported")
except ImportError as e:
    print(f"ERROR: {e}")
