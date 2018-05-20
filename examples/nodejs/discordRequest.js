module.exports = {
  //"msg" here is equal to the "message" object in discord.js. It represents a message sent by the user.
  chatRequest: function (msg) {
    //These are just here for modularity and can be removed if they're already set in the file calling this function.
    const Discord = require('discord.js');
    const request = require('request');
 
    var payload = {
      "currentNode": "",
      "complete": null,
      "context":{},
      "parameters": [],
      "extractedParameters": {},
      "speechResponse": "",
      "intent": {},
      "input": '',
      "missingParameters": []
    };
    //Set the input to a clean string of the user's message.
    var userInput= msg.cleanContent;
    payload["input"] = userInput;

    var options = {
       uri: 'http://localhost:8001/api/v1',
       headers: {
         'Content-Type': 'application/json'
       },
       json: payload
    };

    request.post(options, function(err, res, body) {
      //Log any errors, along with the payload that got sent and the response you got and then have the bot respond to the user.
      console.log('ERROR: \n', err);
      console.log('PAYLOAD: \n', options['json']);
      console.log('RESPONSE: \n', body);
      msg.channel.send(body.speechResponse);
    });
  }
};
