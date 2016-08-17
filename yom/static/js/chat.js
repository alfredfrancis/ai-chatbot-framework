$(document).ready(function () {
    $(document).on('click', '.panel-heading a', function (e) {
        var $this = $(this);
        if (!$this.hasClass('panel-collapsed')) {
            $this.parents('.panel').find('.panel-body').slideUp();
            $this.addClass('panel-collapsed');
            $this.text("+");
            $(".inputBottom").hide();
        } else {
            $this.parents('.panel').find('.panel-body').slideDown();
            $this.removeClass('panel-collapsed');
            $this.text("-");
            $(".inputBottom").show();
        }
    });
    	var NS = {};

	var put_text = function(bot_say) {
    	if(bot_say["responseJSON"].errorCode)
    	{
    	    result = bot_say["responseJSON"].description;
    	}
    	else if (bot_say["responseJSON"].output)
    	{
    	     result = bot_say["responseJSON"].output;
    	}
    	else
    	{
    	    result = "Network error"
    	}

		html_data = '<div class="clearfix"><blockquote class="you pull-left">'+result+'</blockquote></div>'
		$(".panel-body").append(html_data);
	};

	var send_req = function() {
		var userQuery = $("#userSay").val();
		$("#userSay").val("");
		$.support.cors = true;
		$.ajax({
			method: 'POST',
			url: 'http://10.45.0.172:8080/ikyParseAndExecute',
			data: {
				userQuery: userQuery
			},
            complete: function(data) {
				put_text(data);
			}
		});
		return true;
	};

	$('#userSay').keydown(function(e) {
		if (e.keyCode == 13)
		{
            var userQuery = $("#userSay").val();
		    html_data = '<div class="clearfix"><blockquote class="me pull-right">'+userQuery+'</blockquote></div>'
            $(".panel-body").append(html_data);
			send_req();
		}
	})
});/**
 * Created by iky on 16/8/16.
 */
