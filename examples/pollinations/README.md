# Pollinations.AI Integration for AI Chatbot Framework

This directory contains examples of how to use the Pollinations.AI integration with the AI Chatbot Framework. Pollinations.AI provides free, no-signup APIs for text, image, and audio generation with no API keys required.

## Features

- Generate images in chatbot responses
- Generate creative text using Pollinations.AI's text generation API
- No API keys or signup required
- Simple integration with existing chatbot flows

## Example Intents

### Image Generation

The `example_intent.json` file demonstrates how to create an intent that generates images using Pollinations.AI. The intent:

1. Asks the user what kind of image they want to generate
2. Uses the Pollinations.AI image generation API to create the image
3. Returns the image URL in the response

### Text Generation

The `text_generation_intent.json` file demonstrates how to create an intent that generates creative text using Pollinations.AI. The intent:

1. Asks the user what they want to write about
2. Uses the Pollinations.AI text generation API to create a response
3. Returns the generated text in the response

## How to Use

### 1. Import the Example Intents

You can import these example intents into your chatbot using the admin interface or by adding them to your database directly.

### 2. Use Placeholders in Your Responses

To generate images in your responses, use the `{{pollinations_image:prompt}}` placeholder in your intent's speech response. For example:

```
Here's an image of a cat: {{pollinations_image:a cute cat}}
```

### 3. Enable Pollinations.AI for Your Intent

To enable Pollinations.AI for your intent, add a `metadata` field with `use_pollinations` set to `true`:

```json
"metadata": {
  "use_pollinations": true
}
```

## API Options

### Text Generation

- `model`: The model to use (default: "mistral")
- `max_tokens`: Maximum number of tokens to generate (default: 256)
- `temperature`: Controls randomness (0.0-1.0) (default: 0.7)

### Image Generation

- `model`: The model to use (default: "sdxl")
- `width`: Image width (default: 1024)
- `height`: Image height (default: 1024)

## Learn More

For more information about Pollinations.AI, visit:

- [Pollinations.AI Website](https://pollinations.ai)
- [API Documentation](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md)
