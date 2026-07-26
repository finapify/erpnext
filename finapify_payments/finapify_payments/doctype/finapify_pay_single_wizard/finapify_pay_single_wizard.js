frappe.ui.form.on('Finapify Pay Single Wizard', {
	refresh(frm) {
		frm.disable_save();
		frm.page.set_primary_action(__('Confirm & Pay'), () => {
			pay(frm);
		});
	},
});

function pay(frm) {
	if (frm.__finapify_paying) {
		return;
	}

	for (const fieldname of ['vendor_bill', 'amount', 'source_bank_id', 'vendor_bank_id', 'otp']) {
		if (!frm.doc[fieldname]) {
			frappe.throw(__('{0} is required.', [frm.get_field(fieldname).df.label]));
		}
	}

	frm.__finapify_paying = true;
	frappe.dom.freeze(__('Submitting payment to Finapify...'));

	frm.save()
		.then(() => frm.call('action_pay'))
		.then((r) => {
			frappe.dom.unfreeze();
			frm.__finapify_paying = false;
			if (r.message && r.message.name) {
				frappe.show_alert({
					message: __('Payment request {0} submitted.', [r.message.name]),
					indicator: 'green',
				});
				frappe.set_route('Form', r.message.doctype, r.message.name);
			}
		})
		.catch(() => {
			frappe.dom.unfreeze();
			frm.__finapify_paying = false;
		});
}
