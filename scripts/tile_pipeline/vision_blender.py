"""
LLM Vision → Blender code generator.

The LLM sees satellite imagery and generates Blender rendering parameters.
This enables creative style transfer while maintaining:
- CONSISTENT colors across all tiles in a batch
- DETERMINISTIC output (cached for reproducibility)
- PIXEL-PERFECT geometry (always from your data)

Key insight: The LLM generates PARAMETERS (JSON), not images.
This is cheap (~$0.01/tile) vs image generation (~$0.04/tile).

Tile Consistency:
- Style is generated ONCE per render session, applied to ALL tiles
- Per-object variations use deterministic seeds (object ID → color)
- Adjacent tiles are guaranteed to match

Usage:
    generator = VisionBlenderGenerator()

    # Generate style once for entire tile batch
    style_params = generator.analyze_and_generate_style(
        reference_satellite=satellite_tile,
        style_prompt="winter snow",
    )

    # Apply same style to all tiles
    for tile in tiles:
        render_tile(tile, style_params)
"""

import json
import hashlib
import base64
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import os

import numpy as np
from numpy.typing import NDArray

from .llm_variation import LLMStyleOutput


@dataclass
class VisionAnalysis:
    """Analysis of a satellite tile by the LLM."""

    # Observed features
    dominant_roof_colors: List[Tuple[float, float, float]] = field(default_factory=list)
    dominant_ground_colors: List[Tuple[float, float, float]] = field(default_factory=list)
    tree_coverage: str = "medium"  # none, sparse, medium, dense
    apparent_season: str = "summer"  # spring, summer, autumn, winter
    shadow_direction: str = "southwest"  # indicates sun position
    time_of_day: str = "afternoon"  # morning, noon, afternoon, evening
    weather: str = "clear"  # clear, overcast, cloudy

    # LLM observations
    observations: str = ""


@dataclass
class BatchStyleConfig:
    """Style configuration for an entire tile batch.

    This ensures ALL tiles in a render batch use identical styling,
    creating seamless tile boundaries.
    """

    # Style parameters (identical for all tiles)
    style: LLMStyleOutput = field(default_factory=LLMStyleOutput)

    # Analysis from reference tile
    analysis: VisionAnalysis = field(default_factory=VisionAnalysis)

    # Consistency settings
    batch_id: str = ""  # Unique ID for this render batch
    seed: int = 42  # Deterministic seed
    style_prompt: str = ""

    # Per-object variation seeds (based on object ID, not tile)
    # This ensures the same building/tree has same color in any tile
    use_object_id_seeds: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for caching/transmission."""
        return {
            "style": self.style.to_dict(),
            "analysis": self.analysis.__dict__,
            "batch_id": self.batch_id,
            "seed": self.seed,
            "style_prompt": self.style_prompt,
            "use_object_id_seeds": self.use_object_id_seeds,
        }


class VisionBlenderGenerator:
    """Generates Blender parameters from satellite imagery using LLM vision.

    The LLM analyzes satellite imagery to understand:
    - Actual roof colors in the area
    - Tree density and seasonal state
    - Sun position from shadows
    - Time of day / weather conditions

    Then generates appropriate Blender rendering parameters that:
    - Match the observed reality
    - Apply the requested creative style
    - Maintain consistency across all tiles
    """

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        cache_dir: Optional[Path] = None,
    ):
        """Initialize the generator.

        Args:
            model: Vision-capable LLM model
            cache_dir: Directory for caching (ensures consistency)
        """
        self.model = model
        self.cache_dir = cache_dir or Path(".vision_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def analyze_and_generate_style(
        self,
        reference_satellite: NDArray[np.uint8],
        style_prompt: str,
        seed: int = 42,
        use_cache: bool = True,
    ) -> BatchStyleConfig:
        """Analyze satellite tile and generate consistent style for batch.

        This should be called ONCE per render session. The returned
        BatchStyleConfig is then applied to ALL tiles identically.

        Args:
            reference_satellite: Representative satellite tile (512x512 RGB)
            style_prompt: Creative style to apply (e.g., "winter snow")
            seed: Random seed for determinism
            use_cache: Whether to use cached results

        Returns:
            BatchStyleConfig to apply to all tiles in the batch
        """
        # Create batch ID from prompt + seed
        batch_id = hashlib.sha256(f"{style_prompt}_{seed}".encode()).hexdigest()[:12]

        # Check cache first
        cache_path = self.cache_dir / f"batch_{batch_id}.json"
        if use_cache and cache_path.exists():
            return self._load_batch_config(cache_path)

        # Step 1: Analyze the satellite image
        analysis = self._analyze_satellite(reference_satellite)

        # Step 2: Generate style parameters
        style = self._generate_style_from_analysis(
            analysis=analysis,
            style_prompt=style_prompt,
            seed=seed,
        )

        # Create batch config
        config = BatchStyleConfig(
            style=style,
            analysis=analysis,
            batch_id=batch_id,
            seed=seed,
            style_prompt=style_prompt,
            use_object_id_seeds=True,
        )

        # Cache for consistency
        if use_cache:
            self._save_batch_config(cache_path, config)

        return config

    def _analyze_satellite(
        self,
        image: NDArray[np.uint8],
    ) -> VisionAnalysis:
        """Use LLM vision to analyze satellite imagery.

        Args:
            image: Satellite tile (H, W, 3) uint8

        Returns:
            VisionAnalysis with observed features
        """
        # Encode image for API
        image_b64 = self._encode_image(image)

        system_prompt = """You are analyzing satellite imagery of Zurich, Switzerland.
Describe what you observe about:
1. Dominant roof colors (terracotta, gray flat, green copper, etc.)
2. Ground/street colors
3. Tree coverage (none, sparse, medium, dense)
4. Apparent season (look at tree foliage)
5. Shadow direction (indicates sun position)
6. Time of day (from shadow length)
7. Weather (clear, overcast)

Return JSON:
{
  "dominant_roof_colors": [[R,G,B], ...],  // 0-1 range
  "dominant_ground_colors": [[R,G,B], ...],
  "tree_coverage": "medium",
  "apparent_season": "summer",
  "shadow_direction": "southwest",
  "time_of_day": "afternoon",
  "weather": "clear",
  "observations": "Brief description of what you see"
}"""

        user_prompt = "Analyze this satellite tile of Zurich. Return ONLY JSON."

        try:
            response = self._call_vision_llm(system_prompt, user_prompt, image_b64)
            return self._parse_analysis(response)
        except Exception as e:
            print(f"Vision analysis failed ({e}), using defaults")
            return VisionAnalysis()

    def _generate_style_from_analysis(
        self,
        analysis: VisionAnalysis,
        style_prompt: str,
        seed: int,
    ) -> LLMStyleOutput:
        """Generate Blender style parameters based on analysis and prompt.

        Args:
            analysis: VisionAnalysis from satellite
            style_prompt: Creative style to apply
            seed: Random seed

        Returns:
            LLMStyleOutput with rendering parameters
        """
        system_prompt = f"""You are an art director for 3D city tile rendering.

Based on satellite analysis:
- Observed roofs: {analysis.observations}
- Season: {analysis.apparent_season}
- Weather: {analysis.weather}
- Sun direction: {analysis.shadow_direction}

Generate Blender rendering parameters that:
1. START from the observed reality (actual roof colors, etc.)
2. APPLY the requested creative style
3. MAINTAIN consistency (these params apply to ALL tiles)

Style to apply: "{style_prompt}"

Return JSON with all visual parameters. The geometry is FIXED from data -
you're only controlling colors, lighting, atmosphere, effects.

{self._get_style_json_schema()}"""

        user_prompt = f"""Create consistent style parameters for: "{style_prompt}"

Observed in satellite:
{analysis.observations}

The output must create a cohesive look across all tiles in the city.
Return ONLY JSON."""

        try:
            response = self._call_llm(system_prompt, user_prompt, seed)
            return self._parse_style_response(response, style_prompt, seed)
        except Exception as e:
            print(f"Style generation failed ({e}), using fallback")
            return self._fallback_style(style_prompt, analysis, seed)

    def get_object_variation_seed(
        self,
        object_id: str,
        batch_seed: int,
    ) -> int:
        """Get deterministic seed for per-object variation.

        This ensures the same object (building/tree) gets the same
        color variation regardless of which tile it appears in.

        Args:
            object_id: Unique object identifier
            batch_seed: Batch-level seed

        Returns:
            Deterministic seed for this object
        """
        combined = f"{object_id}_{batch_seed}"
        return int(hashlib.sha256(combined.encode()).hexdigest()[:8], 16)

    def _encode_image(self, image: NDArray[np.uint8]) -> str:
        """Encode image to base64 for API."""
        from PIL import Image

        pil_image = Image.fromarray(image)
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    def _call_vision_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str,
    ) -> str:
        """Call vision-capable LLM with image."""
        # Try Anthropic first (Claude vision)
        if os.environ.get("ANTHROPIC_API_KEY"):
            return self._call_anthropic_vision(system_prompt, user_prompt, image_b64)

        # Try OpenAI (GPT-4V)
        if os.environ.get("OPENAI_API_KEY"):
            return self._call_openai_vision(system_prompt, user_prompt, image_b64)

        # Try Google (Gemini)
        if os.environ.get("GOOGLE_API_KEY"):
            return self._call_google_vision(system_prompt, user_prompt, image_b64)

        raise RuntimeError(
            "No vision-capable LLM API key found. Set one of: "
            "ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY"
        )

    def _call_anthropic_vision(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str,
    ) -> str:
        """Call Anthropic Claude with vision."""
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }],
        )
        return response.content[0].text

    def _call_openai_vision(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str,
    ) -> str:
        """Call OpenAI GPT-4V."""
        import openai

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                },
            ],
        )
        return response.choices[0].message.content

    def _call_google_vision(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str,
    ) -> str:
        """Call Google Gemini with vision."""
        import google.generativeai as genai
        from PIL import Image
        import io

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Decode image for Gemini
        image_data = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_data))

        response = model.generate_content([
            f"{system_prompt}\n\n{user_prompt}",
            image,
        ])
        return response.text

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        seed: int,
    ) -> str:
        """Call text-only LLM."""
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        if os.environ.get("OPENAI_API_KEY"):
            import openai
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                seed=seed,
            )
            return response.choices[0].message.content

        if os.environ.get("GOOGLE_API_KEY"):
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
            return response.text

        raise RuntimeError("No LLM API key found")

    def _parse_analysis(self, response: str) -> VisionAnalysis:
        """Parse vision analysis response."""
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        data = json.loads(response.strip())

        return VisionAnalysis(
            dominant_roof_colors=[tuple(c) for c in data.get("dominant_roof_colors", [])],
            dominant_ground_colors=[tuple(c) for c in data.get("dominant_ground_colors", [])],
            tree_coverage=data.get("tree_coverage", "medium"),
            apparent_season=data.get("apparent_season", "summer"),
            shadow_direction=data.get("shadow_direction", "southwest"),
            time_of_day=data.get("time_of_day", "afternoon"),
            weather=data.get("weather", "clear"),
            observations=data.get("observations", ""),
        )

    def _parse_style_response(
        self,
        response: str,
        prompt: str,
        seed: int,
    ) -> LLMStyleOutput:
        """Parse style generation response."""
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        data = json.loads(response.strip())

        return LLMStyleOutput(
            building_wall_color=tuple(data.get("building_wall_color", [0.85, 0.82, 0.78])),
            building_roof_color=tuple(data.get("building_roof_color", [0.45, 0.38, 0.32])),
            building_emission=data.get("building_emission", 0.0),
            building_roughness=data.get("building_roughness", 0.8),
            window_emission_color=tuple(data["window_emission_color"]) if data.get("window_emission_color") else None,
            tree_foliage_color=tuple(data.get("tree_foliage_color", [0.28, 0.48, 0.22])),
            tree_trunk_color=tuple(data.get("tree_trunk_color", [0.35, 0.25, 0.18])),
            tree_color_variation=data.get("tree_color_variation", 0.1),
            ground_color=tuple(data.get("ground_color", [0.35, 0.50, 0.25])),
            terrain_color=tuple(data.get("terrain_color", [0.45, 0.42, 0.38])),
            street_color=tuple(data.get("street_color", [0.35, 0.35, 0.38])),
            street_wetness=data.get("street_wetness", 0.0),
            sun_azimuth=data.get("sun_azimuth", 225.0),
            sun_altitude=data.get("sun_altitude", 35.0),
            sun_color=tuple(data.get("sun_color", [1.0, 0.98, 0.95])),
            sun_strength=data.get("sun_strength", 3.0),
            ambient_color=tuple(data.get("ambient_color", [0.7, 0.8, 1.0])),
            ambient_strength=data.get("ambient_strength", 0.3),
            sky_color=tuple(data.get("sky_color", [0.7, 0.8, 1.0])),
            fog_color=tuple(data["fog_color"]) if data.get("fog_color") else None,
            fog_density=data.get("fog_density", 0.0),
            saturation=data.get("saturation", 1.0),
            contrast=data.get("contrast", 1.0),
            temperature_shift=data.get("temperature_shift", 0.0),
            brightness=data.get("brightness", 1.0),
            snow_coverage=data.get("snow_coverage", 0.0),
            rain_intensity=data.get("rain_intensity", 0.0),
            neon_glow=data.get("neon_glow", False),
            neon_colors=[tuple(c) for c in data["neon_colors"]] if data.get("neon_colors") else None,
            style_prompt=prompt,
            seed=seed,
        )

    def _fallback_style(
        self,
        prompt: str,
        analysis: VisionAnalysis,
        seed: int,
    ) -> LLMStyleOutput:
        """Generate style without LLM, using analysis and prompt keywords."""
        from .llm_variation import LLMVariationGenerator
        generator = LLMVariationGenerator()
        return generator._fallback_style(prompt, seed)

    def _get_style_json_schema(self) -> str:
        """Return the JSON schema for style output."""
        return """JSON schema (all colors [R,G,B] in 0.0-1.0 range):
{
  "building_wall_color": [0.85, 0.82, 0.78],
  "building_roof_color": [0.45, 0.38, 0.32],
  "building_emission": 0.0,
  "building_roughness": 0.8,
  "window_emission_color": null,
  "tree_foliage_color": [0.28, 0.48, 0.22],
  "tree_trunk_color": [0.35, 0.25, 0.18],
  "tree_color_variation": 0.1,
  "ground_color": [0.35, 0.50, 0.25],
  "terrain_color": [0.45, 0.42, 0.38],
  "street_color": [0.35, 0.35, 0.38],
  "street_wetness": 0.0,
  "sun_azimuth": 225.0,
  "sun_altitude": 35.0,
  "sun_color": [1.0, 0.98, 0.95],
  "sun_strength": 3.0,
  "ambient_color": [0.7, 0.8, 1.0],
  "ambient_strength": 0.3,
  "sky_color": [0.7, 0.8, 1.0],
  "fog_color": null,
  "fog_density": 0.0,
  "saturation": 1.0,
  "contrast": 1.0,
  "temperature_shift": 0.0,
  "brightness": 1.0,
  "snow_coverage": 0.0,
  "rain_intensity": 0.0,
  "neon_glow": false,
  "neon_colors": null
}"""

    def _load_batch_config(self, path: Path) -> BatchStyleConfig:
        """Load cached batch configuration."""
        with open(path) as f:
            data = json.load(f)

        style_data = data["style"]
        style = LLMStyleOutput(
            **{k: tuple(v) if isinstance(v, list) and len(v) == 3 else v
               for k, v in style_data.items()
               if k not in ["neon_colors", "window_emission_color", "fog_color"]}
        )
        if style_data.get("neon_colors"):
            style.neon_colors = [tuple(c) for c in style_data["neon_colors"]]
        if style_data.get("window_emission_color"):
            style.window_emission_color = tuple(style_data["window_emission_color"])
        if style_data.get("fog_color"):
            style.fog_color = tuple(style_data["fog_color"])

        analysis = VisionAnalysis(**data.get("analysis", {}))

        return BatchStyleConfig(
            style=style,
            analysis=analysis,
            batch_id=data.get("batch_id", ""),
            seed=data.get("seed", 42),
            style_prompt=data.get("style_prompt", ""),
            use_object_id_seeds=data.get("use_object_id_seeds", True),
        )

    def _save_batch_config(self, path: Path, config: BatchStyleConfig) -> None:
        """Save batch configuration for consistency."""
        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
