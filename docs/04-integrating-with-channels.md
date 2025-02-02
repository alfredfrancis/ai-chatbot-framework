# Integrating with Channels

This guide explains how to integrate your chatbot with different communication channels to make it accessible to your users.

## Chat Widget

### Setting Up the Widget
1. Navigate to the Integrations section under Settings
2. Enable the chat widget integration
3. Configure widget settings:
   - Set base URL (`iky_base_url`)
   - Add custom context (`chat_context`)

### Implementation
1. Copy the widget code snippet
2. Paste it into your website's HTML:
   ```html
   <html>
    <head>...</head>
   <body>
    ...
   </body>
    <script type="text/javascript">
    !function(win,doc){"use strict";var script_loader=()=>{try
    {var head=doc.head||doc.getElementsByTagName("head")[0],script=doc.createElement("script");script.setAttribute("type","text/javascript"),script.setAttribute("src","https://alfredfrancis.in/ai-chatbot-framework/app/static/widget/script.js"),head.appendChild(script)}
    catch(e){}};win.chat_context={"username":"John"},win.iky_base_url="http://localhost:8080/admin/",script_loader()}(window,document);
    </script>
    </html>
   ```

## REST API

### Authentication
1. Generate an API key from the admin dashboard
2. Include the key in your API requests:
   ```
   Authorization: Bearer YOUR_API_KEY
   ```

### Making Requests
- Endpoint: `POST /api/bots/channels/rest/webbook`
- Request format:
  ```json
  {
    "thread_id":"123456",
    "text": "hello world",
    "context": {
      "Name": "Alfred"
      // additional context data
    }
  }
  ```
- Response Format:
  ```json
  [{"text":"Hello Alfred 👋 "},{"text":" What can i do for you ?"}]
  ```

Sample cURL request:
```sh
curl 'http://<your-external-ip>:8080/api/bots/channels/rest/webbook' \
  -H 'Content-Type: application/json' \
  --data-raw '{"thread_id":"test-user","text":"/init_conversation","context":{"username":"Admin"}}'
```

## Facebook Messenger

### Prerequisites
- Facebook Developer Account
- Facebook Page for your chatbot

### Configuration Steps
1. Create a Facebook App
2. Enable Messenger integration
3. In your chatbot admin panel:
   - Enable Facebook integration
   - Configure webhook URL
   - Set up authentication:
     - Verify token
     - App secret
     - Page access token

### Testing the Integration
1. Send a test message to your Facebook Page
2. Verify the chatbot responds correctly
3. Check webhook events in the Facebook Developer Console