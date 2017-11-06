



const Speech = function (say) {
    if ('speechSynthesis' in window && state.talking) {
        var utterance = new SpeechSynthesisUtterance(say);
        //utterance.volume = 1; // 0 to 1
        // utterance.rate = 0.9; // 0.1 to 10
        //utterance.pitch = 1; //0 to 2
        //utterance.text = 'Hello World';
        //utterance.lang = 'en-US';
        speechSynthesis.speak(utterance);
    }
}

const getTime = function () {
    var dt = new Date();
    var h = dt.getHours(), m = dt.getMinutes();
    var stime = (h > 12) ? (h - 12 + ':' + m + ' PM') : (h + ':' + m + ' AM');
    return stime;
}

const scrollToBottom = function () {
    $(".chat")[0].scrollTop = $(".chat")[0].scrollHeight;
}

const put_text = function (bot_say) {
    $(".payloadPreview")[0].innerHTML = JSON.stringify(bot_say, null, 5);
    state.payload = bot_say;
    Speech(bot_say["speechResponse"]);
    html_data = '<li class="left clearfix"><div class="chat-body clearfix"><strong class="primary-font">Iky</strong><p>' + bot_say["speechResponse"] + '</p> </div></li>';
    $("ul.chat").append(html_data);
    scrollToBottom();
};

const send_req = function (userQuery) {
    state.payload["input"] = userQuery;
    $.ajax({
        url: '/api/v1',
        type: 'POST',
        data: JSON.stringify(state.payload),
        contentType: 'application/json; charset=utf-8',
        datatype: "json",
        success: successRoutes,
        error: errorRoutes,
    });
    return true;
};


const successRoutes = function (response) {
    var responseObject;
    if (typeof response == 'object') {
        responseObject = response;
    }
    else {
        var parsedResponse = JSON.parse(response);
        responseObject = parsedResponse.responseData;
    }
    put_text(responseObject);
};

const errorRoutes = function (x, t, m) {
    responseObject = {};
    if (t === "timeout") {
        responseObject["speechResponse"] = state.translate.errorBand
    } else {
        responseObject["speechResponse"] = state.translate.errorNotAble
    }
    put_text(responseObject);
};


const sendMessage = function (userQuery = null) {
    if (!userQuery) userQuery = $("#btn-input").val();
    validateAnswer(userQuery)
        .then(r => {
            $("#btn-input").val("");
            if (r) {
                html_data = '<li class="right clearfix"><div class="chat-body clearfix"><strong class="primary-font">you</strong><p>' + userQuery + '</p> </div></li>';
                send_req(userQuery);
            } else {
                html_data = '<li class="right clearfix"><div class="chat-body clearfix"><strong class="primary-font">Iky</strong><p>This is not a valid input, please try again</p> </div></li>';
            }
            $("ul.chat").append(html_data);
        })
}

const validateAnswer = function (value) {
    return new Promise((resolve, reject) => {
        bot_say = state.payload;
        if (bot_say.missingParameters && bot_say.missingParameters.length > 0) {
            const missing = bot_say.missingParameters[0];
            const parameter = bot_say.parameters.find(p => p.name === missing);
            if (parameter) {
                switch (parameter.type) {
                    case "name":
                        return resolve(/^[A-Za-z\s]+ [A-Za-z\s]+$/.test(value));
                        break;
                    case "free_text":
                        return resolve(value.length > 0);
                        break;
                    case "mobile":
                        return resolve(/^(\+91-|\+91|0)?\d{10}$/.test(value));
                        break;
                    case "email":
                        return resolve(/^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$/.test(value));
                        break;
                    case "number":
                        return resolve(!isNaN(value));
                        break;
                    case "api":
                        return resolve(true);
                        break;
                }

            }
        }
        return resolve(true);
    });
}

const translations = {
    en: {
        errorNotAble: "I'm not able to serve you at the moment, please try again later",
        errorBand: "Due to band-width constraints, I'm not able to serve you now, please try again later"
    },
    pt: {
        errorNotAble: "I'm not able to serve you at the moment, please try again later",
        errorBand: "Due to band-width constraints, I'm not able to serve you now, please try again later"
    }

}

const state ={
    talking: true,
    translate: translations.en,
    last_bot_say: null
}

$(document).ready(function () {

    if (typeof (Storage) !== "undefined") {
        localStorage.setItem("firstname", "alfred");
    }

    if (typeof state.payload == "undefined") {
        state.payload = {
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

    send_req("init_conversation");

    $('#btn-input').keydown(function (e) {
        if (e.keyCode == 13) {
            sendMessage();
        }
    })

    $('#btn-chat').click(function () {
        sendMessage();
    });

});
