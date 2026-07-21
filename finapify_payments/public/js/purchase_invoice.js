frappe.ui.form.on('Purchase Invoice', {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 2) {
			return;
		}
		if (!flt(frm.doc.outstanding_amount)) {
			return;
		}
		if (!frappe.model.can_create('Finapify Pay Single Wizard')) {
			return;
		}

		frm.add_custom_button(__('Pay with Finapify'), () => {
			frappe.dom.freeze(__('Preparing payment...'));
			frm.call('action_finapify_pay')
				.then((r) => {
					frappe.dom.unfreeze();
					if (!r.message) {
						return;
					}
					frappe.new_doc(r.message.doctype, r.message.context || {});
				})
				.catch(() => {
					frappe.dom.unfreeze();
				});
		});
	},
});
