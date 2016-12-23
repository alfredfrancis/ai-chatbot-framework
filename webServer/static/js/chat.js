$(document).ready(function () {
	function scrollToBottom() {
        $(".chat")[0].scrollTop = $(".chat")[0].scrollHeight;
    }

	var put_text = function(bot_say) {
		console.log(bot_say);
    	if(bot_say["responseJSON"].errorCode)
    	{
    	    result = "I'm sorry. I didn't quite grasp what you just said.";
    	}
    	else if (bot_say["responseJSON"].actionName)
    	{
    	     result = "Action : " + bot_say["responseJSON"].actionName +
                 "<br>Parameters :"+ JSON.stringify(bot_say["responseJSON"].entities);
    	}
    	else if (bot_say["responseJSON"].ikySays)
    	{
    		 result = bot_say["responseJSON"].ikySays;
		}
    	else
    	{
    	    result = "Network error"
    	}

		html_data = '<li class="left clearfix"><div class="chat-body clearfix"><strong class="primary-font">Iky</strong><p>'+result+'</p> </div></li>';

		$("ul.chat").append(html_data);
		scrollToBottom();
	};

	var send_req = function() {
		var userQuery = $("#btn-input").val();
		$("#btn-input").val("");

		$.ajax({
			method: 'POST',
			url: '/api/v1',
			data: {
				userQuery: userQuery
			},
            complete: function(data) {
				put_text(data);
			}
		});
		return true;
	};

	$('#btn-input').keydown(function(e) {
		if (e.keyCode == 13)
		{
            var userQuery = $("#btn-input").val();
		    html_data = '<li class="right clearfix"><div class="chat-body clearfix"><strong class="primary-font">you</strong><p>'+userQuery+'</p> </div></li>';
            $("ul.chat").append(html_data);
			send_req();
		}
	})
});