import aiohttp
import logging
from typing import Dict, Optional, Union, List
from urllib.parse import quote

logger = logging.getLogger("pollinations_service")

class PollinationsService:
    """Service for generating text and images using Pollinations.AI API.

    Pollinations.AI provides free, no-signup APIs for text, image, and audio generation
    with no API keys required. This service integrates with the Pollinations.AI API
    to enable chatbots to generate text and images in responses.

    API Documentation: https://github.com/pollinations/pollinations/blob/master/APIDOCS.md
    """

    BASE_URL = "https://pollinations.ai/api"

    @staticmethod
    async def generate_text(prompt: str, model: str = "mistral", max_tokens: int = 256, temperature: float = 0.7) -> str:
        """Generate text using Pollinations.AI API.

        Args:
            prompt: The text prompt to generate from
            model: The model to use (default: "mistral")
            max_tokens: Maximum number of tokens to generate
            temperature: Controls randomness (0.0-1.0)

        Returns:
            Generated text as string
        """
        try:
            # Encode the prompt for URL
            encoded_prompt = quote(prompt)

            # Construct the API URL
            url = f"{PollinationsService.BASE_URL}/text?p={encoded_prompt}&model={model}&max_tokens={max_tokens}&temperature={temperature}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("text", "")
                    else:
                        logger.error(f"Error generating text: {response.status}")
                        return ""
        except Exception as e:
            logger.error(f"Error in generate_text: {e}")
            return ""

    @staticmethod
    async def generate_image(prompt: str, model: str = "sdxl", width: int = 1024, height: int = 1024) -> Optional[str]:
        """Generate an image using Pollinations.AI API.

        Args:
            prompt: The text prompt to generate the image from
            model: The model to use (default: "sdxl")
            width: Image width
            height: Image height

        Returns:
            URL to the generated image or None if generation failed
        """
        try:
            # Encode the prompt for URL
            encoded_prompt = quote(prompt)

            # Construct the API URL
            url = f"{PollinationsService.BASE_URL}/image?p={encoded_prompt}&model={model}&width={width}&height={height}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("imageUrl")
                    else:
                        logger.error(f"Error generating image: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in generate_image: {e}")
            return None

    @staticmethod
    async def enhance_bot_response(response: List[Dict], generate_images: bool = False) -> List[Dict]:
        """Enhance bot response with generated content.

        This method can be used to enhance bot responses with generated text or images.
        If the response contains placeholders like {{pollinations_image:prompt}}, they will
        be replaced with generated content.

        Args:
            response: List of response message dictionaries
            generate_images: Whether to generate images for responses

        Returns:
            Enhanced response with generated content
        """
        enhanced_response = []

        for message in response:
            text = message.get("text", "")

            # Check for image generation placeholders
            if generate_images and "{{pollinations_image:" in text:
                # Extract the prompt from the placeholder
                start_idx = text.find("{{pollinations_image:") + len("{{pollinations_image:")
                end_idx = text.find("}}", start_idx)

                if start_idx > 0 and end_idx > 0:
                    image_prompt = text[start_idx:end_idx].strip()
                    image_url = await PollinationsService.generate_image(image_prompt)

                    if image_url:
                        # Replace the placeholder with the image URL
                        text = text.replace(f"{{{{pollinations_image:{image_prompt}}}}}", "")

                        # Add the text message
                        if text.strip():
                            enhanced_response.append({"text": text.strip()})

                        # Add the image message
                        enhanced_response.append({"image": image_url})
                        continue

            # If no image placeholder or image generation failed, just add the original message
            enhanced_response.append(message)

        return enhanced_response