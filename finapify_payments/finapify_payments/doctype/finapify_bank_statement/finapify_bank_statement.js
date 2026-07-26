frappe.ui.form.on('Finapify Bank Statement', {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		if (frm.doc.state === 'Draft') {
			frm.add_custom_button(__('Fetch Statement'), () => {
				frappe.dom.freeze(__('Fetching bank statement...'));
				frm.call('fetch_bank_statement')
					.then(() => {
						frappe.dom.unfreeze();
						frm.reload_doc();
					})
					.catch(() => frappe.dom.unfreeze());
			});
		}

		if (['Loaded', 'Failed'].includes(frm.doc.state)) {
			frm.add_custom_button(__('Reload'), () => {
				frappe.dom.freeze(__('Reloading bank statement...'));
				frm.call('action_reload_statement')
					.then(() => {
						frappe.dom.unfreeze();
						frm.reload_doc();
					})
					.catch(() => frappe.dom.unfreeze());
			});

			frm.add_custom_button(__('Set Draft'), () => {
				frm.call('action_set_draft').then(() => frm.reload_doc());
			});
		}
	},
});
