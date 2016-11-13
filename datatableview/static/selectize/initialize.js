datatableview.auto_initialize = false;
$(function() {
	var selectize_options = {};
	datatableview.initialize($('.datatable'), {
		fnRowCallback : datatableview.make_selectize(selectize_options),
	});
});