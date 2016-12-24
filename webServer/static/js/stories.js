$(document).ready(function() {
	story = {};
	$("#prompt").hide();
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
		if($("#storyName")[0].value && $("#intentName")[0].value && $("#speechResponse")[0].value )
		{
			story.storyName=$("#storyName")[0].value;
			story.intentName=$("#intentName")[0].value;
			story.speechResponse=$("#speechResponse")[0].value;
			console.log(story);
			$.ajax({
				url: '/createStory',
				type: 'POST',
				data: JSON.stringify(story),
				contentType: 'application/json; charset=utf-8',
				dataType: 'json',
				async: false,
				success: function(msg) {
					alert("Story created successfully.");
					getStories();
					$("#storyName")[0].value="";
					$("#intentName")[0].value="";
					$("#speechResponse")[0].value="";
				}
			});
        }

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

	$(document).on('change', "input#paramRequired", function() {
		 if(this.checked){
		 	$("#prompt").show();
		 }else{
		 	$("#prompt").hide();
		 }

	});

	renderParams =function() {

		html ='<div class="row"><div class="col-md-2"><h4>No</h4></div> <div class="col-md-2"><h4>Name</h4></div> <div class="col-md-2"><h4>Required</h4></div> <div class="col-md-2"><h4>Prompt</h4></div> </div>';


		$.each(story.parameters, function( index, param )
		{
			if(!param.required){
				req = "False";
				prom = "_";

			}else{
				req = "True";
				prom = param.prompt;
			}
					html +='<div class="row"><div class="col-md-2">'+(index+1)+'</div> <div class="col-md-2">'+param.name+'</div> <div class="col-md-2">'+req+'</div> <div class="col-md-2">'+prom+'</div> </div>';
		});

		$(".panel-footer")[0].innerHTML=html;

    }

	$(document).on('click', "button#btnAddParam", function()
	{
		if(!$("#paramName")[0].value){
			alert("Param name cant be empty");
			$("#paramName")[0].focus();
			return;
		}else{
			if($("#paramRequired")[0].checked && !$("#prompt")[0].value){
				alert("prompt cant be empty");
				$("#prompt")[0].focus();
				return;
			}
		}

		param = {
			"name":$("#paramName")[0].value
		}

		$("#paramName")[0].value="";

		 if($("#paramRequired")[0].checked){
			param.required=$("#paramRequired")[0].checked;
				param.prompt=$("#prompt")[0].value;
		 }
		 $("#paramRequired")[0].value="";
		 $("#prompt")[0].value="";
		 if(!story.parameters){
		 	story.parameters = [];
		 }
		 story.parameters.push(param);
		 renderParams();
	});





	$(document).on('click', "button#btnBuild", function() {
		_id = $(this).attr("objId");
		$.post("/buildModel", {
				userId:"1",
				storyId:_id
			},
			function(data) {
			console.log(data);
                if(data.errorCode)
                {
                    alert(data.description);
                }else if (data.result)
                {
                    alert("Sucess");
                }
			});
	});

});