$(document).ready(function() {
	var NS = {};
	function get_stories() 
	{
		$.post("/get_stories", {},
			function(data) {
				var obj = JSON.parse(data);
				//alert(JSON.stringify(obj));
				html =""
				$.each(obj, function(idx, obj) 
				{
					html += '<div class="story" objid='+obj._id.$oid+'>\
								<h2 class="">'+ obj.story_name +'</h2> \
								<button type="button" class="btn btn-primary" id="btn_train" objid='+obj._id.$oid+' >Train</button>\
								<button type="button" class="btn btn-primary" id="btn_delete" objid='+obj._id.$oid+' >Delete</button>\
							</div>';
				});
				$('.stories').html(html);
			});
	}

	get_stories();

	$("#new_story").click(function() 
	{
		$.post("/create_story", {
				user_id:"1",
				story_name:$("#story_name").val() 
			});
		$('#new_story').val ="";
		get_stories();
	});

	$(document).on('click', "button#btn_train", function() {
		_id = $(this).attr("objid");
		window.open("/train?story_id="+_id);
	});

	$(document).on('click', "button#btn_delete", function() {
		_id = $(this).attr("objid");
		$.post("/delete_story", {
				user_id:"1",
				story_id:_id 
			},
			function(data) {
				 $( "div[objid="+_id+"]" ).remove();
			});
	});
});