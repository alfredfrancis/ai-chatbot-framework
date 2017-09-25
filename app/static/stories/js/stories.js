$(document).ready(function() {
	story = {};
	$("#prompt").hide();
	function getStories()
	{
		$.get("/stories", {},
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
			if($("input#apiTrigger")[0].checked)
			{
				story.apiTrigger = true;
				story.apiDetails = {
				    "isJson":false,
					"url":$("input#apiUrl")[0].value,
					"requestType":$( "select#requestType option:selected" )[0].value,

				};
				if($("input#apiTrigger")[0].checked)
				{
				    story.apiDetails.isJson = true;
				    story.apiDetails.jsonData = $("textarea#jsonData")[0].value;
                }


			}else{
				story.apiTrigger = false ;
			}
			story.storyName=$("#storyName")[0].value;
			story.intentName=$("#intentName")[0].value;
			story.speechResponse=$("#speechResponse")[0].value;
			console.log(story);
			$.ajax({
				url: '/stories/',
				type: 'POST',
				data: JSON.stringify(story),
				contentType: 'application/json; charset=utf-8',
				dataType: 'json',
				async: false,
				success: function(msg) {
					alert("Story created successfully.");
					getStories();
					story = {};
					$(".panel-footer")[0].innerHTML="";
					$("#storyName")[0].value="";
					$("#intentName")[0].value="";
					$("#speechResponse")[0].value="";
				}
			});
        }

	});

	$(document).on('click', "button#btnEdit", function() {
		_id = $(this).attr("objId");
		window.open("/stories/edit/"+_id);
	});

	$(document).on('click', "button#btnTrain", function() {
		_id = $(this).attr("objId");
		window.open("/train/"+_id);
	});

	$(document).on('click', "button#btnDelete", function() {
		var r =confirm("Do you want to continue?");
		if (r == true)
		{
			_id = $(this).attr("objId");
			$.ajax({
				url:"/stories/"+_id,
				type: 'DELETE',
				success: function(result) {
					 $( "div[objId="+_id+"]" ).remove();
					 getStories();
				}
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

	$(document).on('change', "input#apiTrigger", function() {
		 if(this.checked){
		 	$("input#apiUrl").prop( "disabled", false );
		 	$("select#requestType").prop( "disabled", false );
		 	$("input#isJson").prop( "disabled", false );
		 }else{
		 	$("input#apiUrl").prop( "disabled", true );
		 	$("select#requestType").prop( "disabled", true );
		 	$("input#isJson").prop( "disabled", true );
		 	$("input#isJson").prop( "checked", false );
		 	$("textarea#jsonData").hide();
		 }
	});

    $(document).on('change', "input#isJson", function() {
		 if(this.checked){
		 	$("textarea#jsonData").show();
		 }else{
            $("textarea#jsonData").hide();
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
			"name":$("#paramName")[0].value,
			"type":$("#paramEntityType")[0].value
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
		$.post("/core/buildModel/"+_id, {
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
