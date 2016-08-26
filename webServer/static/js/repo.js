$(document).ready(function() {
	var NS = {};
	function get_stories()
	{
		$.post("/get_stories", {},
			function(data) {
				var obj = JSON.parse(data);
				html ="<select class=\"selectpicker\">"
				$.each(obj, function(idx, obj)
				{
					html += '<option value='+obj._id.$oid+'>'+ obj.story_name +'</option>';
                });
                html +="</select>"
				$('.stories_list').html(html);
			});
	}

	get_stories();

	$("#store").click(function()
	{
	alert($("#raw_data").val());
		$.post("/saveToRepo", {
				story_id:$(".selectpicker").val(),
				//raw_data:$("#raw_data").val().replace(/\n/g, ' ')
				raw_data:$("#raw_data").val().replace(/\n/g, ' ')
			});
		$('#raw_data').value(" ");
	});

});