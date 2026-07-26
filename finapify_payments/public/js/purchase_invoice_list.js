frappe.listview_settings['Purchase Invoice'] = frappe.listview_settings['Purchase Invoice'] || {};

frappe.listview_settings['Purchase Invoice'].onload = function (listview) {
	if (!frappe.model.can_create('Finapify Pay Bulk Wizard')) {
		return;
	}

	listview.page.add_action_item(__('Pay with Finapify'), () => {
		const checked = listview.get_checked_items();
		const names = checked
			.filter((d) => d.docstatus === 1 && flt(d.outstanding_amount) > 0)
			.map((d) => d.name);

		if (!names.length) {
			frappe.msgprint(__('Select at least one submitted bill with an outstanding amount.'));
			return;
		}

		frappe.dom.freeze(__('Preparing bulk payment...'));
		frappe
			.call('finapify_payments.wizards.finapify_pay_bulk_wizard.create_bulk_pay_wizard', {
				bill_names: names,
			})
			.then((r) => {
				frappe.dom.unfreeze();
				if (r.message) {
					frappe.set_route('Form', 'Finapify Pay Bulk Wizard', r.message);
				}
			})
			.catch(() => frappe.dom.unfreeze());
	});
};
