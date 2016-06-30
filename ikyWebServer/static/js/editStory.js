$(document).ready(function() {
	var NS = {};
	$(document).on('click', "button#saveStory", function() {
		var r =confirm("Do you want to continue?");
		if (r == true) {
		$.post("/saveEditStory", {
		        _id:$("input[name=story_id]").val(),
				user_id:"1",
				story_name:$("#story_name").val(),
				action_type:$("#action_type").val(),
				action_name:$("#action_name").val(),
				labels:$("#labels").val()
			},
			function(data) {
				 alert('Saved!');
			});
	}
	});

});