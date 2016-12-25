$(document).ready(function () {

    payload = {
        "currentNode": "",
        "complete": null,
        "parameters": [
        ],
        "extractedParameters": {},
        "speechResponse": "",
        "intent": {},
        "input": "init_conversation",
        "missingParameters": []
    }
    function scrollToBottom() {
        $(".chat")[0].scrollTop = $(".chat")[0].scrollHeight;
    }

    var put_text = function (bot_say) {
        console.log(bot_say);
        payload  = bot_say;
        html_data = '<li class="left clearfix"><div class="chat-body clearfix"><strong class="primary-font">Iky</strong><p>' + bot_say["speechResponse"] + '</p> </div></li>';
        $("ul.chat").append(html_data);
        scrollToBottom();
    };

    var send_req = function (userQuery) {
        payload["input"] = userQuery;
        $.ajax({
				url: '/api/v1',
				type: 'POST',
				data: JSON.stringify(payload),
				contentType: 'application/json; charset=utf-8',
				dataType: 'json',
				success: function(data) {
				    put_text(data);

				}
        });
        return true;
    };

    send_req("init_conversation");


    $('#btn-input').keydown(function (e) {
        if (e.keyCode == 13) {
            userQuery = $("#btn-input").val();
            $("#btn-input").val("");
            html_data = '<li class="right clearfix"><div class="chat-body clearfix"><strong class="primary-font">you</strong><p>' + userQuery + '</p> </div></li>';
            $("ul.chat").append(html_data);
            send_req(userQuery);

        }
    })
});