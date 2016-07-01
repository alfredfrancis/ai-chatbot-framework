$(document).ready(function() {
	var NS = {};
	function getStories()
	{
		$.post("/getStories", {},
			function(data)
			{
			    html = "<center>No stories found!</center>"
			    if(data[0])
			    {
			        html =""
                    $.each(data, function(idx, obj)
                    {
                        html += '<div class="story" objId='+obj._id.$oid+'>\
                                    <h2 class="">'+ obj.storyName +'</h2> \
                                    <button type="button" class="btn btn-primary" id="btnEdit" objId='+obj._id.$oid+' >Edit</button>\
                                    <button type="button" class="btn btn-primary" id="btnTrain" objId='+obj._id.$oid+' >Train</button>\
                                    <button type="button" class="btn btn-primary" id="btnDelete" objId='+obj._id.$oid+' >Delete</button>\
                                    <button type="button" class="btn btn-primary" id="btnBuild" objId='+obj._id.$oid+' >Build Model</button>\
                                </div>';
                    });
                }
				$('.stories').html(html);
			});
	}

	getStories();

	$("#btnCreateStory").click(function()
	{
		$.post("/createStory", {
				userId:"1",
				storyName:$("#storyName").val(),
				actionType:$("#actionType").val(),
				actionName:$("#actionName").val(),
				labels:$("#labels").val()
			});
		$('#newStory').val ="";
		getStories();
	});

	$(document).on('click', "button#btnEdit", function() {
		_id = $(this).attr("objId");
		window.open("/editStory?storyId="+_id);
	});

	$(document).on('click', "button#btnTrain", function() {
		_id = $(this).attr("objId");
		window.open("/train?storyId="+_id);
	});

	$(document).on('click', "button#btnDelete", function() {
		var r =confirm("Do you want to continue?");
		if (r == true) {
		_id = $(this).attr("objId");
		$.post("/deleteStory", {
				userId:"1",
				storyId:_id
			},
			function(data) {
				 $( "div[objId="+_id+"]" ).remove();
				 getStories();
			});
	}
	});
	$(document).on('click', "button#btnBuild", function() {
		_id = $(this).attr("objId");
		$.post("/buildModel", {
				userId:"1",
				storyId:_id
			},
			function(data) {
				 alert('build sucessfull');
			});
	});

	$(".flip").click(function()
	{
		$(".panel").toggle();
	});

});