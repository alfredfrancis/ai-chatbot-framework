$(document).ready(function(){

		var put_text = function(bot_say){
			console.log(bot_say);
			$(".result_area").prepend('\
				<div class="alert alert-success fade in">\
				<a href="#" class="close" data-dismiss="alert">&times;</a>\
				'+bot_say['responseText']+'\
				</div>');
		};

		var send_req = function()
		{	
			var user_say=$("#user-say").val();
			$("#user-say").val("");

			$.ajax({
			method:'POST',
			url: '/req',
			data: {user_say: user_say},
			beforeSend: function() { $('#wait').show(); },
			complete: function(data) { $('#wait').hide(); put_text(data); }
			});		
			return true;
		};

		$('#user-say').keydown(function (e){
		    if(e.keyCode == 13){
		        send_req();
		    }
		})
});
