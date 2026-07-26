frappe.ui.form.on('Finapify Payment Batch', {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		if (['Failed', 'Processing', 'Part Success'].includes(frm.doc.status)) {
			frm.add_custom_button(__('Retry'), () => {
				frappe.dom.freeze(__('Enqueuing retry...'));
				frm.call('action_retry')
					.then(() => {
						frappe.dom.unfreeze();
						frm.reload_doc();
					})
					.catch(() => frappe.dom.unfreeze());
			});
		}

		if (['Success', 'Part Success'].includes(frm.doc.status) && frm.doc.reconciliation_status !== 'Reconciled') {
			frm.add_custom_button(__('Retry Reconcile'), () => {
				frappe.dom.freeze(__('Enqueuing reconciliation...'));
				frm.call('action_retry_reconcile')
					.then(() => {
						frappe.dom.unfreeze();
						frm.reload_doc();
					})
					.catch(() => frappe.dom.unfreeze());
			});
		}
	},
});
