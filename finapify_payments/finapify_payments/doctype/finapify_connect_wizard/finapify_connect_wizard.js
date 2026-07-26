frappe.ui.form.on('Finapify Connect Wizard', {
	refresh(frm) {
		frm.disable_save();
		frm.page.set_primary_action(__('Connect'), () => {
			connect(frm);
		});
	},
});

function connect(frm) {
	if (frm.__finapify_connecting) {
		return;
	}

	for (const fieldname of ['company', 'consent_id', 'default_source_bank_id', 'supabase_jwt']) {
		if (!frm.doc[fieldname]) {
			frappe.throw(__('{0} is required.', [frm.get_field(fieldname).df.label]));
		}
	}

	frm.__finapify_connecting = true;
	frappe.dom.freeze(__('Connecting to Finapify...'));

	frm.save()
		.then(() => frm.call('action_connect'))
		.then((r) => {
			frappe.dom.unfreeze();
			frm.__finapify_connecting = false;
			if (r.message) {
				frappe.set_route('List', 'Finapify Connection');
			}
		})
		.catch(() => {
			frappe.dom.unfreeze();
			frm.__finapify_connecting = false;
		});
}
