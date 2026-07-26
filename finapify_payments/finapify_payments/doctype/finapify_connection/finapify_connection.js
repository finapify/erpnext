frappe.ui.form.on('Finapify Connection', {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		if (frm.doc.is_connected) {
			frm.add_custom_button(__('Refresh Accounts'), () => {
				frappe.dom.freeze(__('Refreshing accounts...'));
				frm.call('action_refresh_accounts')
					.then(() => {
						frappe.dom.unfreeze();
						frm.reload_doc();
					})
					.catch(() => frappe.dom.unfreeze());
			});

			frm.add_custom_button(__('Disconnect'), () => {
				frappe.confirm(
					__('Disconnect Finapify for this company? You will need to reconnect to make payments.'),
					() => {
						frappe.dom.freeze(__('Disconnecting...'));
						frm.call('action_disconnect')
							.then(() => {
								frappe.dom.unfreeze();
								frm.reload_doc();
							})
							.catch(() => frappe.dom.unfreeze());
					}
				);
			});
		}
	},
});
