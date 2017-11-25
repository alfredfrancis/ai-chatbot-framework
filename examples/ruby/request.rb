require 'net/http'
require 'json'

uri = URI('http://localhost:8001/api/v1')
http = Net::HTTP.new(uri.host, uri.port)
request = Net::HTTP::Post.new(uri.path, 'Content-Type' => 'application/json')

request.body = {
  'currentNode': '',
  'complete': nil,
  'context': {},
  'parameters': [],
  'extractedParameters': {},
  'speechResponse': '',
  'intent': {},
  'input': 'init_conversation',
  'missingParameters': []
}.to_json

while true
  response = http.request(request).body
  json_response = JSON.load(response)

  puts "Iky #{json_response['speechResponse']}"

  original_request_body = JSON.load(request.body)
  original_request_body['input'] = gets.chomp
  request.body = original_request_body.to_json
end
