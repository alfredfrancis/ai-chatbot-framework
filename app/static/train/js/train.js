$(document).ready(function() {
	var NS = {};
	
	$("#trainButton").click(function() {
			var sentences = $('#sentences').html().replace("<br>"," ");

			$.post("/core/posTagAndLabel", {
					sentences: sentences
				},
				function(data) {
					NS.taggedSentences = data;
					$('#output').html("<pre>" + JSON.stringify(data) + "</pre>");
				});
			$("#tokenLabel").prop('disabled', false);
			$("#btnInsertLabeledSentence").prop('disabled', false);
	});

	$("#tokenLabel").prop('disabled', true);
    $("#btnInsertLabeledSentence").prop('disabled', true);

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
	editableEl = document.getElementById("sentences");
	$("#sentences").mouseup(function() {
		selected = getSelected();
		if (selected.toString().length > 1) {
			NS.selected = selected.toString();
			range = selected.getRangeAt(0).cloneRange();
			range.collapse(true);
			range.setStart(editableEl, 0);

            console.log($('<div>').append(range.cloneContents()).html());

			$.post("/core/sentenceTokenize", {
					sentences: $('<div>').append(range.cloneContents()).html()
				},
				function(data) {
					if (data.trim()) {
						NS.wordCount = data.split(" ").length;
					} else {
						NS.wordCount = 0;
					}

				});

			$.post("/core/sentenceTokenize", {
					sentences: NS.selected.trim()
				},
				function(data) {
					if (data.trim()) {
						NS.selectedWordsCount = data.split(" ").length;
					} else {
						NS.selectedWordsCount = 0;
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
			$("#tokenLabel").focus();
		}
	});

	$('#tokenLabel').keydown(function(e) {
		if (e.keyCode == 13) {
			//alert(NS.selectedWordsCount)
			var label = $("#tokenLabel").val();
			/*if($("#labels").val()!="")
			{
				$("#labels").val($("#labels").val() +"," + $("#token_label").val());
			}
			else{
				$("#labels").val($("#token_label").val());
			}*/

			//$('#instance').append("before:"+NS.wordCount+",count:"+NS.selectedWordsCount+"\n");
			for (var i = 1; i <= NS.selectedWordsCount; i++) {
				if (i == 1) {
					bio = "B-" + label;
				} else {
					bio = "I-" + label;
				}
				//$('#instance').append(","+NS.taggedSentences[(NS.wordCount + i)-1]+","+NS.taggedSentences[(NS.wordCount + i)-1][2]+"\n");
				NS.taggedSentences[(NS.wordCount + i) - 1][2] = bio;
			}
			$('#output').html("<pre>" + JSON.stringify(NS.taggedSentences) + "</pre>");
			$("#tokenLabel").val("");
		}
	});

	$("#btnInsertLabeledSentence").click(function()
	{
		$.post("/train/insertLabeledSentence", {
				storyId: $("input[name=storyId]").val(),
				labeledSentence: JSON.stringify(NS.taggedSentences)
			},
			function(data) {
				$('#output').html("Insertion sucessfull!");
			});
		$('#sentences').html("");
	});

	$("#btnClear").click(function() {
		$('#sentences').html("");
	});

	$("a#btnDeleteSentence").click(function(){
		var r =confirm("Do you want to continue?");
		if (r == true)
		{
			_id = $(this).attr("_id");
			$.post("/train/deleteLabeledSentences", {
					storyId: $("input[name=storyId]").val(),
					sentenceId:_id
				},
				function(data) {
					 $( "li[_id="+_id+"]" ).remove();
				});
		}
	});

	$(document).on('click', "button#btnBuild", function() {
		_id = $(this).attr("objId");
		$.post("/core/buildModel/"+_id, {},
			function(data) {
				 if(data.errorCode)
                {
                    alert(data.description);
                }else if (data.result)
                {
                    alert("Build Sucessful!");
                }
			});
	});

	$(".flip").click(function()
	{
		$(".panel").toggle();
	});
});