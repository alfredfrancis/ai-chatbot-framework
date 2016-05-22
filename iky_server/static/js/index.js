$(document).ready(function() {
	var NS = {};

	var put_text = function(bot_say) {
		html_data = '<div class="alert alert-success fade in">\
				<a href="#" class="close" data-dismiss="alert">&times;</a>';
		$.each(bot_say["responseJSON"], function (index, data) {
			html_data = html_data + index +" : "+data+"<br>";
    	})		

		html_data=html_data+'</div>';
		$(".result_area").prepend(html_data);
	};

	var send_req = function() {
		var user_say = $("#user-say").val();
		$("#user-say").val("");

		$.ajax({
			method: 'POST',
			url: '/req',
			data: {
				user_say: user_say
			},
			beforeSend: function() {
				$('#wait').show();
			},
			complete: function(data) {
				$('#wait').hide();
				put_text(data);
			}
		});
		return true;
	};

	$('#user-say').keydown(function(e) {
		if (e.keyCode == 13) {
			send_req();
		}
	})
});