frappe.ui.form.on('Finapify Settings', {
	refresh(frm) {
		frm.add_custom_button(__('Test Authentication'), () => {
			frappe.dom.freeze(__('Testing Finapify authentication...'));
			frm.call('test_finapify_authentication')
				.then(() => {
					frappe.dom.unfreeze();
					frm.reload_doc();
				})
				.catch(() => frappe.dom.unfreeze());
		});
	},
});
