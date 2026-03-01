"""
Image Generation via Gemini Nano Banana

Generates charcoal-style illustrations using the Gemini API.
Post-processes with ImageMagick for center cropping and watermark removal.
"""

import os
import subprocess
import base64
from pathlib import Path
from typing import Optional

from src.core.config import ConfigLoader


class ImageGenerator:
    """Generates images using Gemini Nano Banana and ImageMagick post-processing."""

    def __init__(self, config: Optional[ConfigLoader] = None):
        self.config = config or ConfigLoader()

    def generate_charcoal_image(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Optional[Path]:
        """Generate a charcoal-style image and post-process it.

        Args:
            prompt: Image generation prompt.
            output_path: Where to save the final image.
            width: Desired output width.
            height: Desired output height.

        Returns:
            Path to the generated image, or None on failure.
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY not set, skipping image generation")
            return None

        network = self.config.load_network()
        image_config = network.get("image", {})

        # Add default style suffix
        suffix = image_config.get("default_prompt_suffix", "")
        full_prompt = f"{prompt}. {suffix}"

        # Generate image via Gemini API
        raw_path = output_path.parent / f"raw_{output_path.name}"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        success = self._generate_via_gemini(full_prompt, raw_path, api_key)
        if not success:
            return None

        # Post-process with ImageMagick
        crop_percent = image_config.get("crop_percent", 90)
        final_path = self._postprocess(
            raw_path, output_path, width, height, crop_percent
        )

        # Clean up raw file
        if raw_path.exists() and final_path and final_path != raw_path:
            raw_path.unlink()

        return final_path

    def _generate_via_gemini(
        self, prompt: str, output_path: Path, api_key: str
    ) -> bool:
        """Generate image using Gemini Nano Banana API."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "image/png",
                },
            )

            # Extract image data from response
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        image_data = part.inline_data.data
                        output_path.write_bytes(
                            base64.b64decode(image_data)
                            if isinstance(image_data, str)
                            else image_data
                        )
                        return True

            print("No image data in Gemini response")
            return False

        except Exception as e:
            print(f"Gemini image generation failed: {e}")
            return False

    def _postprocess(
        self,
        input_path: Path,
        output_path: Path,
        width: int,
        height: int,
        crop_percent: int,
    ) -> Optional[Path]:
        """Post-process image with ImageMagick.

        - Center crop to remove SynthID watermark (typically bottom-right)
        - Resize to target dimensions
        """
        try:
            # Step 1: Center crop to remove watermark
            crop_spec = f"{crop_percent}%x{crop_percent}%+0+0"
            cmd_crop = [
                "magick", str(input_path),
                "-gravity", "Center",
                "-crop", crop_spec,
                "+repage",
                str(output_path),
            ]
            subprocess.run(cmd_crop, check=True, capture_output=True)

            # Step 2: Resize to target dimensions
            cmd_resize = [
                "magick", str(output_path),
                "-resize", f"{width}x{height}^",
                "-gravity", "Center",
                "-extent", f"{width}x{height}",
                str(output_path),
            ]
            subprocess.run(cmd_resize, check=True, capture_output=True)

            return output_path

        except subprocess.CalledProcessError as e:
            print(f"ImageMagick processing failed: {e.stderr}")
            # Fall back to using the raw image
            if input_path.exists():
                import shutil
                shutil.copy(input_path, output_path)
                return output_path
            return None
        except FileNotFoundError:
            print("ImageMagick not found. Install with: brew install imagemagick")
            import shutil
            if input_path.exists():
                shutil.copy(input_path, output_path)
                return output_path
            return None

    def generate_thumbnail(
        self,
        image_path: Path,
        output_path: Path,
        width: int = 1280,
        height: int = 720,
    ) -> Optional[Path]:
        """Create a YouTube-sized thumbnail from an image."""
        try:
            cmd = [
                "magick", str(image_path),
                "-resize", f"{width}x{height}^",
                "-gravity", "Center",
                "-extent", f"{width}x{height}",
                str(output_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except Exception as e:
            print(f"Thumbnail generation failed: {e}")
            return None
