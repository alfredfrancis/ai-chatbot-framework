$(document).ready(function() {

	var NS = {};

	$("#new_story").click(function() {
		$.post("/insert_story", {
				labeled_info: JSON.stringify(NS.tagged_data)
			},
			function(data) {
				alert(data);
			});
		$('#new_story').value ="";
	});
});