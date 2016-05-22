$(document).ready(function() {

	var NS = {};

	$("#new_story").click(function() {
		$.post("/create_story", {
				user_id:"1",
				story_name:$("#story_name").val() 
			},
			function(data) {
				alert(data);
			});
		$('#new_story').val ="";
	});
});