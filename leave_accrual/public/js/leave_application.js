frappe.ui.form.on('Leave Application', {
    refresh: function (frm) {
        if (frm.doc.employee && frm.doc.leave_type) {
            frm.trigger('show_accrual_balance');
        }
    },
    employee: function (frm) {
        frm.trigger('show_accrual_balance');
    },
    leave_type: function (frm) {
        frm.trigger('show_accrual_balance');
    },
    show_accrual_balance: function (frm) {
        if (!frm.doc.employee || !frm.doc.leave_type) return;

        frappe.call({
            method: "leave_accrual.utils.accrual.get_leave_balance",
            args: {
                employee: frm.doc.employee,
                leave_type: frm.doc.leave_type
            },
            callback: function (r) {
                if (!r.message) return;

                let balance = r.message;

                // Show as dashboard indicator
                let color = balance > 0 ? "green" : "red";
                let msg = `Real-time Accrued Balance: ${balance} days`;

                frm.dashboard.add_indicator(msg, color);

                // Also set intro for better visibility
                // frm.set_intro(msg, http_status=color == 'green' ? 'blue' : 'red');
            }
        });
    }
});
