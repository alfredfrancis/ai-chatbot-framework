$(document).ready(function () {
    talking = true;

    if (typeof(Storage) !== "undefined") {
        localStorage.setItem("firstname", "alfred");
    }

    if (typeof payload == "undefined") {
        payload = {
            "currentNode": "",
            "complete": null,
            "context": {},
            "parameters": [],
            "extractedParameters": {},
            "speechResponse": "",
            "intent": {},
            "input": "init_conversation",
            "missingParameters": []
        }

    }

    function getTime(){
     var dt = new Date();
       var h =  dt.getHours(), m = dt.getMinutes();
       var stime = (h > 12) ? (h-12 + ':' + m +' PM') : (h + ':' + m +' AM');
        return stime;
    }

    function scrollToBottom() {
        $(".chat")[0].scrollTop = $(".chat")[0].scrollHeight;
    }

    var put_text = function (bot_say) {
        $(".payloadPreview")[0].innerHTML = JSON.stringify(bot_say, null,5);
        payload  = bot_say;
        Speech(bot_say["speechResponse"]);
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
            datatype: "json",
            success: successRoutes,
            error: errorRoutes,
        });
        return true;
    };


    successRoutes = function (response) {
        var responseObject;
        if (typeof response == 'object') {
           responseObject= response;
        }
        else {
            var parsedResponse = JSON.parse(response);
            responseObject = parsedResponse.responseData;
        }
        put_text(responseObject);
    };

    errorRoutes = function (x, t, m) {
        responseObject = {};
        if(t==="timeout") {
            responseObject["speechResponse"] = "Due to band-width constraints, I'm not able to serve you now, please try again later"
        }else{
            responseObject["speechResponse"] = "I'm not able to serve you at the moment, please try again later"
        }
        put_text(responseObject);
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

    $('#btn-chat').click(function () {
        userQuery = $("#btn-input").val();
        $("#btn-input").val("");
        html_data = '<li class="right clearfix"><div class="chat-body clearfix"><strong class="primary-font">you</strong><p>' + userQuery + '</p> </div></li>';
        $("ul.chat").append(html_data);
        send_req(userQuery);
    })

    function Speech(say) {
      if ('speechSynthesis' in window && talking) {
        var utterance = new SpeechSynthesisUtterance(say);
        //utterance.volume = 1; // 0 to 1
        // utterance.rate = 0.9; // 0.1 to 10
        //utterance.pitch = 1; //0 to 2
        //utterance.text = 'Hello World';
        //utterance.lang = 'en-US';
        speechSynthesis.speak(utterance);
      }
    }

});