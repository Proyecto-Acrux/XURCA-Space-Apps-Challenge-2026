const vertexSource = `
attribute vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}`;

const fragmentSource = `
precision highp float;
uniform sampler2D surface;
uniform vec2 center;
uniform vec2 camera;
uniform float radius;
uniform float pixelScale;
const float PI = 3.14159265359;

float random(vec2 p) {
  vec3 q = fract(vec3(p.xyx) * 0.1031);
  q += dot(q, q.yzx + 33.33);
  return fract((q.x + q.y) * q.z);
}

float stars(vec2 pixels, float spacing) {
  vec2 cell = floor(pixels / spacing);
  vec2 offset = 0.17 + 0.66 * vec2(random(cell), random(cell + 17.0));
  float strength = random(cell + 31.0);
  float distanceToStar = length((fract(pixels / spacing) - offset) * spacing);
  return (1.0 - smoothstep(0.15, 0.8 + 0.65 * strength, distanceToStar)) * strength * strength;
}

void main() {
  vec2 pixel = gl_FragCoord.xy / pixelScale;
  vec3 space = vec3(0.009, 0.015, 0.028);
  space += stars(pixel, 11.0) * vec3(0.26, 0.36, 0.51);
  space += stars(pixel + 17.0, 34.0) * vec3(0.56, 0.60, 0.69);
  vec2 disk = (gl_FragCoord.xy - center) / radius;
  float r = length(disk);
  vec3 sun = normalize(vec3(-0.52, 0.55, 0.74));
  float side = 0.48 + 0.52 * smoothstep(-1.0, 1.0, dot(disk, sun.xy));
  float halo = exp(-max(r - 1.0, 0.0) * 99.0);
  space += vec3(0.09, 0.25, 0.52) * halo * side * 0.53;
  if (r >= 1.0) {
    gl_FragColor = vec4(space, 1.0);
    return;
  }

  vec3 normal = vec3(disk, sqrt(max(0.0, 1.0 - dot(disk, disk))));
  float sinLat = sin(camera.y);
  float cosLat = cos(camera.y);
  // Inverse orthographic projection, matching the D3 overlays and hit testing.
  float latitude = asin(clamp(normal.y * cosLat + normal.z * sinLat, -1.0, 1.0));
  float longitude = camera.x + atan(normal.x, normal.z * cosLat - normal.y * sinLat);
  vec2 uv = vec2(fract(longitude / (2.0 * PI) + 0.5), 0.5 - latitude / PI);
  vec3 earth = texture2D(surface, uv).rgb;
  float lighting = smoothstep(-0.31, 0.85, dot(normal, sun));
  earth *= mix(0.23, 1.13, lighting);
  earth += vec3(0.20, 0.46, 0.83) * pow(1.0 - normal.z, 4.5) * side * 0.45;
  gl_FragColor = vec4(mix(earth, space, smoothstep(1.0 - 1.2 / radius, 1.0, r)), 1.0);
}`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

export function createGlobeTexture(canvas, image) {
  const gl = canvas.getContext('webgl', { alpha: false, antialias: false });
  if (!gl) return null;
  const vertex = compile(gl, gl.VERTEX_SHADER, vertexSource);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource);
  if (!vertex || !fragment) {
    if (vertex) gl.deleteShader(vertex);
    if (fragment) gl.deleteShader(fragment);
    return null;
  }
  const program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program);
    return null;
  }
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, 'position');
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  const limit = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  let pixels = image;
  if (image.width > limit) {
    pixels = document.createElement('canvas');
    pixels.width = limit;
    pixels.height = Math.round(limit * image.height / image.width);
    pixels.getContext('2d').drawImage(image, 0, 0, pixels.width, pixels.height);
  }
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, pixels);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  const uniforms = Object.fromEntries(['center', 'camera', 'radius', 'pixelScale'].map(
    name => [name, gl.getUniformLocation(program, name)]
  ));

  return {
    draw(width, height, [x, y], radius, camera) {
      if (!width || !height || radius <= 0) return;
      const scale = Math.min(window.devicePixelRatio || 1, 2, 1800 / Math.max(width, height));
      const pixelWidth = Math.max(1, Math.round(width * scale));
      const pixelHeight = Math.max(1, Math.round(height * scale));
      if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
      if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
      gl.viewport(0, 0, pixelWidth, pixelHeight);
      gl.uniform2f(uniforms.center, x * scale, pixelHeight - y * scale);
      gl.uniform2f(uniforms.camera, camera.longitude * Math.PI / 180, camera.latitude * Math.PI / 180);
      gl.uniform1f(uniforms.radius, radius * scale);
      gl.uniform1f(uniforms.pixelScale, scale);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
    destroy() {
      gl.deleteTexture(texture);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    }
  };
}
