/**
 * GLSL Shaders for Gradient Shadow Layer
 *
 * These shaders create a penumbra effect where shadows are:
 * - Darker (more opaque) near the building/source
 * - Lighter (more transparent) toward the shadow tip
 *
 * The gradient direction follows the sun azimuth dynamically.
 */

/**
 * Vertex shader module for passing normalized distance to fragment shader
 *
 * Calculates distance from source edge for each vertex, which is used
 * to create the penumbra gradient in the fragment shader.
 */
export const shadowVertexShader = `\
#version 300 es
#define SHADER_NAME gradient-shadow-vertex-shader

// Standard deck.gl attributes
in vec3 positions;
in vec3 normals;
in vec4 colors;
in vec3 pickingColors;

// Instanced attributes from data
in vec3 instancePositions;
in vec4 instanceColors;
in vec3 instancePickingColors;
in float instanceDistanceFromSource;
in float instanceMaxDistance;

// Uniforms
uniform float opacity;

// Outputs to fragment shader
out vec4 vColor;
out float vDistanceFromSource;
out float vNormalizedDistance;

void main(void) {
  // Calculate position (standard deck.gl projection)
  vec3 pos = positions + instancePositions;

  // Pass distance information to fragment shader
  vDistanceFromSource = instanceDistanceFromSource;
  vNormalizedDistance = instanceDistanceFromSource / max(instanceMaxDistance, 1.0);

  // Pass color
  vColor = vec4(instanceColors.rgb, instanceColors.a * opacity);

  // Set picking color for interactivity
  picking_setPickingColor(instancePickingColors);
}
`;

/**
 * Fragment shader module for penumbra gradient effect
 *
 * Uses the normalized distance from source to create a soft falloff
 * at the shadow edges, simulating the natural penumbra effect.
 */
export const shadowFragmentShader = `\
#version 300 es
#define SHADER_NAME gradient-shadow-fragment-shader

precision highp float;

// Inputs from vertex shader
in vec4 vColor;
in float vDistanceFromSource;
in float vNormalizedDistance;

// Uniforms for gradient control
uniform float uPenumbraStart;  // Where soft falloff begins (0.0-1.0)
uniform float uPenumbraEnd;    // Where shadow becomes fully transparent (0.0-1.0)
uniform float uMaxOpacity;     // Maximum shadow opacity (at source)
uniform vec3 uShadowColor;     // Shadow color RGB (0-1 range)

out vec4 fragColor;

void main(void) {
  // Penumbra gradient: hard near source, soft at tip
  // smoothstep provides natural easing
  float penumbraFalloff = 1.0 - smoothstep(uPenumbraStart, uPenumbraEnd, vNormalizedDistance);

  // Apply opacity with penumbra effect
  float finalOpacity = uMaxOpacity * penumbraFalloff;

  // Output shadow color with calculated opacity
  fragColor = vec4(uShadowColor, finalOpacity);

  // Apply deck.gl picking filter
  DECKGL_FILTER_COLOR(fragColor, geometry);
}
`;

/**
 * Shader module injection points for deck.gl
 *
 * These are injected into SolidPolygonLayer's existing shaders
 * to add the gradient functionality without rewriting everything.
 */
export const shadowShaderModules = {
  // Inject into vertex shader to calculate distance from centroid
  vs: `\
    // Calculate distance from polygon centroid for gradient
    varying float vDistanceFromCentroid;
    varying float vMaxDistance;
  `,

  // Inject into fragment shader to apply gradient
  fs: `\
    // Penumbra gradient uniforms
    uniform float uPenumbraStart;
    uniform float uPenumbraEnd;
    uniform float uMaxOpacity;

    // Apply penumbra gradient to shadow
    float penumbraFalloff = 1.0 - smoothstep(uPenumbraStart, uPenumbraEnd, vDistanceFromCentroid / vMaxDistance);
    gl_FragColor.a *= penumbraFalloff * uMaxOpacity;
  `,
};

/**
 * Simplified shader injection for SolidPolygonLayer
 *
 * These are GLSL code snippets that get injected at specific points
 * in the base layer's shaders. This approach is more compatible
 * with deck.gl's shader assembly system.
 */
export const gradientShaderInjection = {
  /**
   * Inject at the end of the vertex shader to pass UV/position data
   * The 'position_commonspace' variable is available in deck.gl shaders
   */
  'vs:#decl': `
    varying vec2 vWorldPosition;
  `,
  'vs:#main-end': `
    vWorldPosition = geometry.worldPosition.xy;
  `,

  /**
   * Inject into fragment shader to apply radial gradient from centroid
   */
  'fs:#decl': `
    varying vec2 vWorldPosition;
    uniform vec2 uCentroid;
    uniform float uRadius;
    uniform float uPenumbraStart;
    uniform float uMaxOpacity;
  `,
  'fs:DECKGL_FILTER_COLOR': `
    // Calculate distance from shadow centroid
    float dist = distance(vWorldPosition, uCentroid);
    float normalizedDist = dist / max(uRadius, 1.0);

    // Penumbra gradient: opaque at center, transparent at edges
    float gradient = 1.0 - smoothstep(uPenumbraStart, 1.0, normalizedDist);

    // Apply gradient to alpha
    color.a *= gradient * uMaxOpacity;
  `,
};
