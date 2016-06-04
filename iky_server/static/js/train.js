$(document).ready(function() {
	var NS = {};
	
	$('#train_query').keydown(function(e) {
		if (e.keyCode == 13) {
			var user_say = $('#train_query').html().replace(/\&lt;br\&gt;/gi, "\n").replace(/(&lt;([^&gt;]+)&gt;)/gi, "");
			$.post("/pos_tag", {
					text: user_say
				},
				function(data) {
					NS.tagged_data = data;
					$('#output').html("<pre>" + JSON.stringify(data) + "</pre>");
				});
			$("#token_label").prop('disabled', false);
			return e.which != 13;
		}
	});

	$("#token_label").prop('disabled', true);

	function getSelected() {
		var t = '';
		if (window.getSelection) {
			t = window.getSelection();
		} else if (document.getSelection) {
			t = document.getSelection();
		} else if (document.selection) {
			t = document.selection.createRange().text;
		}
		return t;
	}
	editableEl = document.getElementById("train_query");
	$("#train_query").mouseup(function() {
		selected = getSelected();
		if (selected.toString().length > 1) {
			NS.selected = selected.toString();
			range = selected.getRangeAt(0).cloneRange();
			range.collapse(true);
			range.setStart(editableEl, 0);

			$.post("/query_tokenize", {
					text: range.toString().trim()
				},
				function(data) {
					if (data.trim()) {
						NS.num_words = data.split(" ").length;
					} else {
						NS.num_words = 0;
					}

				});

			$.post("/query_tokenize", {
					text: NS.selected.trim()
				},
				function(data) {
					if (data.trim()) {
						NS.num_sel_words = data.split(" ").length;
					} else {
						NS.num_sel_words = 0;
					}
				});


			var range = selected.getRangeAt(0);
			var selectionContents = range.extractContents();
			var span = document.createElement("span");
			span.appendChild(selectionContents);
			span.setAttribute("class", "Highlight");
			span.style.backgroundColor = "green";
			span.style.color = "white";
			range.insertNode(span);
			$("#token_label").focus();
		}
	});

	$('#token_label').keydown(function(e) {
		if (e.keyCode == 13) {
			//alert(NS.num_sel_words)
			var label = $("#token_label").val().toUpperCase();
			/*if($("#labels").val()!="")
			{
				$("#labels").val($("#labels").val() +"," + $("#token_label").val());
			}
			else{
				$("#labels").val($("#token_label").val());	
			}*/
			
			//$('#instance').append("before:"+NS.num_words+",count:"+NS.num_sel_words+"\n");
			for (var i = 1; i <= NS.num_sel_words; i++) {
				if (i == 1) {
					bio = "B-" + label;
				} else {
					bio = "I-" + label;
				}
				//$('#instance').append(","+NS.tagged_data[(NS.num_words + i)-1]+","+NS.tagged_data[(NS.num_words + i)-1][2]+"\n");
				NS.tagged_data[(NS.num_words + i) - 1][2] = bio;
			}
			$('#output').html("<pre>" + JSON.stringify(NS.tagged_data) + "</pre>");
			$("#token_label").val("");
		}
	});
	$("#btn_add_test").click(function() 
	{
		$.post("/_insert_tagged", {
				story_id: $("input[name=story_id]").val(),
				labeled_info: JSON.stringify(NS.tagged_data)
			},
			function(data) {
				$('#output').html("Insertion sucessfull!");
			});
		$('#train_query').html("");
	});
	$("#btn_clear").click(function() {
		$('#train_query').html("");
	});

	$("a#btn_dlt_sent").click(function(){
		var r =confirm("Do you want to continue?");
		if (r == true)
		{
			_id = $(this).attr("_id");
			$.post("/delete_sent", {
					user_id:"1",
					sent_id:_id 
				},
				function(data) {
					 $( "li[_id="+_id+"]" ).remove();
				});
		}
	});
	$(".flip").click(function()
	{
		$(".panel").toggle();
	});
});