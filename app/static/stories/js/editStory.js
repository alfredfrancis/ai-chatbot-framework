$(document).ready(function() {
	var NS = {};
	$(document).on('click', "button#saveStory", function() {
		var r =confirm("Do you want to continue?");
		if (r == true) {
		$.post("/saveEditStory", {
		        _id:$("input[name=storyId]").val(),
				storyName:$("#storyName").val(),
				actionType:$("#actionType").val(),
				actionName:$("#actionName").val(),
				labels:$("#labels").val()
			},
			function(data) {
                if(data['responseJSON'].errorCode)
                {
                    alert(data['responseJSON'].description);
                }else if (data['responseJSON'].result)
                {
                    alert("Sucess");
                }
			});
	}
	});

});