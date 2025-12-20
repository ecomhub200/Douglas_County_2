'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import Image from 'next/image';

const FeaturesPage: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext('webgl');
    if (!gl) {
      console.error('WebGL not supported');
      return;
    }

    // Vertex shader
    const vsSource = `
      attribute vec4 aVertexPosition;
      void main() {
        gl_Position = aVertexPosition;
      }
    `;

    // Fragment shader with purple/blue plasma effect
    const fsSource = `
      precision highp float;
      uniform vec2 iResolution;
      uniform float iTime;
      
      const float overallSpeed = 0.2;
      const float gridSmoothWidth = 0.015;
      const float axisWidth = 0.05;
      const float majorLineWidth = 0.025;
      const float minorLineWidth = 0.0125;
      const float majorLineFrequency = 5.0;
      const float minorLineFrequency = 1.0;
      const vec4 gridColor = vec4(0.5);
      const float scale = 5.0;
      const vec4 lineColor = vec4(0.4, 0.2, 0.8, 1.0);
      const float minLineWidth = 0.01;
      const float maxLineWidth = 0.2;
      const float lineSpeed = 1.0 * overallSpeed;
      const float lineAmplitude = 1.0;
      const float lineFrequency = 0.2;
      const float warpSpeed = 0.2 * overallSpeed;
      const float warpFrequency = 0.5;
      const float warpAmplitude = 1.0;
      const float offsetFrequency = 0.5;
      const float offsetSpeed = 1.33 * overallSpeed;
      const float minOffsetSpread = 0.6;
      const float maxOffsetSpread = 2.0;
      const int linesPerGroup = 16;
      
      #define drawCircle(pos, radius, coord) smoothstep(radius + gridSmoothWidth, radius, length(coord - (pos)))
      #define drawSmoothLine(pos, halfWidth, t) smoothstep(halfWidth, 0.0, abs(pos - (t)))
      #define drawCrispLine(pos, halfWidth, t) smoothstep(halfWidth + gridSmoothWidth, halfWidth, abs(pos - (t)))
      #define drawPeriodicLine(freq, width, t) drawCrispLine(freq / 2.0, width, abs(mod(t, freq) - (freq) / 2.0))
      
      float drawGridLines(float axis) {
        return drawCrispLine(0.0, axisWidth, axis)
              + drawPeriodicLine(majorLineFrequency, majorLineWidth, axis)
              + drawPeriodicLine(minorLineFrequency, minorLineWidth, axis);
      }
      
      float drawGrid(vec2 space) {
        return min(1.0, drawGridLines(space.x) + drawGridLines(space.y));
      }
      
      float random(float t) {
        return (cos(t) + cos(t * 1.3 + 1.3) + cos(t * 1.4 + 1.4)) / 3.0;   
      }
      
      float getPlasmaY(float x, float horizontalFade, float offset) {
        return random(x * lineFrequency + iTime * lineSpeed) * horizontalFade * lineAmplitude + offset;
      }
      
      void main() {
        vec2 fragCoord = gl_FragCoord.xy;
        vec4 fragColor;
        
        vec2 uv = fragCoord.xy / iResolution.xy;
        vec2 space = (fragCoord - iResolution.xy / 2.0) / iResolution.x * 2.0 * scale;
        
        float horizontalFade = 1.0 - (cos(uv.x * 6.28) * 0.5 + 0.5);
        float verticalFade = 1.0 - (cos(uv.y * 6.28) * 0.5 + 0.5);
      
        space.y += random(space.x * warpFrequency + iTime * warpSpeed) * warpAmplitude * (0.5 + horizontalFade);
        space.x += random(space.y * warpFrequency + iTime * warpSpeed + 2.0) * warpAmplitude * horizontalFade;
        
        vec4 lines = vec4(0.0);
        vec4 bgColor1 = vec4(0.1, 0.1, 0.3, 1.0);
        vec4 bgColor2 = vec4(0.3, 0.1, 0.5, 1.0);
        
        for(int l = 0; l < linesPerGroup; l++) {
          float normalizedLineIndex = float(l) / float(linesPerGroup);
          float offsetTime = iTime * offsetSpeed;
          float offsetPosition = float(l) + space.x * offsetFrequency;
          float rand = random(offsetPosition + offsetTime) * 0.5 + 0.5;
          float halfWidth = mix(minLineWidth, maxLineWidth, rand * horizontalFade) / 2.0;
          float offset = random(offsetPosition + offsetTime * (1.0 + normalizedLineIndex)) * mix(minOffsetSpread, maxOffsetSpread, horizontalFade);
          float linePosition = getPlasmaY(space.x, horizontalFade, offset);
          float line = drawSmoothLine(linePosition, halfWidth, space.y) / 2.0 + drawCrispLine(linePosition, halfWidth * 0.15, space.y);
          
          float circleX = mod(float(l) + iTime * lineSpeed, 25.0) - 12.0;
          vec2 circlePosition = vec2(circleX, getPlasmaY(circleX, horizontalFade, offset));
          float circle = drawCircle(circlePosition, 0.01, space) * 4.0;
          
          line = line + circle;
          lines += line * lineColor * rand;
        }
        
        fragColor = mix(bgColor1, bgColor2, uv.x);
        fragColor *= verticalFade;
        fragColor.a = 1.0;
        fragColor += lines;
        
        gl_FragColor = fragColor;
      }
    `;

    // Initialize shaders
    function loadShader(gl: WebGLRenderingContext, type: number, source: string) {
      const shader = gl.createShader(type);
      if (!shader) return null;
      
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compilation error:', gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
      }
      
      return shader;
    }

    function initShaderProgram(gl: WebGLRenderingContext, vsSource: string, fsSource: string) {
      const vertexShader = loadShader(gl, gl.VERTEX_SHADER, vsSource);
      const fragmentShader = loadShader(gl, gl.FRAGMENT_SHADER, fsSource);
      
      if (!vertexShader || !fragmentShader) return null;
      
      const shaderProgram = gl.createProgram();
      if (!shaderProgram) return null;
      
      gl.attachShader(shaderProgram, vertexShader);
      gl.attachShader(shaderProgram, fragmentShader);
      gl.linkProgram(shaderProgram);
      
      if (!gl.getProgramParameter(shaderProgram, gl.LINK_STATUS)) {
        console.error('Shader program linking error:', gl.getProgramInfoLog(shaderProgram));
        return null;
      }
      
      return shaderProgram;
    }

    const shaderProgram = initShaderProgram(gl, vsSource, fsSource);
    if (!shaderProgram) return;

    // Setup geometry
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    const positions = new Float32Array([
      -1.0, -1.0,
       1.0, -1.0,
      -1.0,  1.0,
       1.0,  1.0,
    ]);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    // Get locations
    const programInfo = {
      attribLocations: {
        vertexPosition: gl.getAttribLocation(shaderProgram, 'aVertexPosition'),
      },
      uniformLocations: {
        resolution: gl.getUniformLocation(shaderProgram, 'iResolution'),
        time: gl.getUniformLocation(shaderProgram, 'iTime'),
      },
    };

    // Resize handler
    function resizeCanvas() {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
    }

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Animation loop
    const startTime = Date.now();
    function render() {
      const currentTime = (Date.now() - startTime) / 1000;
      
      gl.clearColor(0.0, 0.0, 0.0, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      
      gl.useProgram(shaderProgram);
      
      gl.uniform2f(programInfo.uniformLocations.resolution, canvas.width, canvas.height);
      gl.uniform1f(programInfo.uniformLocations.time, currentTime);
      
      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
      gl.vertexAttribPointer(
        programInfo.attribLocations.vertexPosition,
        2,
        gl.FLOAT,
        false,
        0,
        0
      );
      gl.enableVertexAttribArray(programInfo.attribLocations.vertexPosition);
      
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      
      animationFrameRef.current = requestAnimationFrame(render);
    }

    animationFrameRef.current = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -10% 0px'
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-fadeInUp');
        }
      });
    }, observerOptions);

    const elements = document.querySelectorAll('.feature-card');
    elements.forEach(el => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  return (
    <div className="bg-[#0a1a2e] text-[#adbdcc] min-h-screen font-['Inter',sans-serif] relative overflow-hidden">
      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-20px); }
        }
        
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes glow {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 0.8; }
        }
        
        @keyframes rotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        .animate-fadeInUp {
          animation: fadeInUp 0.6s ease-out forwards;
        }
        
        .animate-delay-200 {
          animation-delay: 0.2s;
          opacity: 0;
        }
        
        .animate-delay-400 {
          animation-delay: 0.4s;
          opacity: 0;
        }
        
        .animate-delay-600 {
          animation-delay: 0.6s;
          opacity: 0;
        }
        
        .gradient-text {
          background: linear-gradient(to right, #00d4ff, #7f5eff);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        
        .feature-card {
          transition: transform 0.3s ease, box-shadow 0.3s ease;
          opacity: 0;
        }
        
        .feature-card:hover {
          transform: scale(1.03);
          box-shadow: 0 10px 30px -10px rgba(0, 212, 255, 0.3);
        }
        
        .sparkle-button {
          position: relative;
        }
        
        .sparkle-button button {
          position: relative;
          z-index: 1;
          overflow: hidden;
          transition: all 0.3s ease;
        }
        
        .sparkle-button button:hover {
          transform: translateY(-3px);
          box-shadow: 0 10px 25px -5px rgba(0, 212, 255, 0.4);
        }
        
        .sparkle-button button .backdrop {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.1);
          opacity: 0;
          transition: opacity 0.3s ease;
        }
        
        .sparkle-button button:hover .backdrop {
          opacity: 1;
        }
        
        .sparkle-button button .sparkle {
          position: absolute;
          top: 8px;
          right: 8px;
          width: 20px;
          height: 20px;
          opacity: 0.5;
          transition: all 0.3s ease;
        }
        
        .sparkle-button button:hover .sparkle {
          transform: rotate(15deg) scale(1.2);
          opacity: 1;
        }
        
        .mobile-menu {
          transition: transform 0.3s ease, opacity 0.3s ease;
          transform: translateY(-100%);
          opacity: 0;
        }
        
        .mobile-menu.open {
          transform: translateY(0);
          opacity: 1;
        }
        
        #plasma-canvas {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          z-index: 0;
          opacity: 0.3;
        }
      `}</style>

      {/* WebGL Plasma Background */}
      <canvas ref={canvasRef} id="plasma-canvas" />

      {/* Navigation Bar */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#061220]/90 backdrop-blur-md border-b border-[#1a3045]">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center">
              <div className="h-10 w-10 rounded-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] mr-3 flex items-center justify-center">
                <span className="text-white font-bold">AI</span>
              </div>
              <span className="text-white text-xl font-bold">
                <span className="gradient-text">AI</span> Student Success
              </span>
            </Link>
            
            <div className="hidden md:flex items-center space-x-8">
              <Link href="/" className="text-[#adbdcc] hover:text-white transition-colors">Home</Link>
              <Link href="/features" className="text-white font-medium transition-colors">Features</Link>
              <Link href="/pricing" className="text-[#adbdcc] hover:text-white transition-colors">Pricing</Link>
              <Link href="/resources" className="text-[#adbdcc] hover:text-white transition-colors">Resources</Link>
              <Link href="/about" className="text-[#adbdcc] hover:text-white transition-colors">About Us</Link>
              <Link href="/contact" className="text-[#adbdcc] hover:text-white transition-colors">Contact Us</Link>
            </div>
            
            <div className="flex items-center space-x-4">
              <Link href="/signin" className="hidden md:inline-block text-white font-medium py-2 px-4 rounded-lg border border-[#1a3045] hover:border-[#00d4ff] transition-colors">
                Sign In
              </Link>
              <div className="sparkle-button hidden md:block">
                <button className="relative bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-2 px-6 rounded-lg overflow-hidden group">
                  <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                  <span className="backdrop"></span>
                  <svg className="sparkle" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z" fill="black" stroke="black" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="relative z-10">Get Started</span>
                </button>
              </div>
              
              {/* Mobile menu button */}
              <button 
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden text-white focus:outline-none"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
              </button>
            </div>
          </div>
          
          {/* Mobile menu */}
          <div className={`mobile-menu md:hidden absolute left-0 right-0 bg-[#061220] border-b border-[#1a3045] shadow-lg p-4 ${mobileMenuOpen ? 'open' : ''}`}>
            <div className="flex flex-col space-y-4">
              <Link href="/" className="text-[#adbdcc] hover:text-white py-2">Home</Link>
              <Link href="/features" className="text-white font-medium py-2">Features</Link>
              <Link href="/pricing" className="text-[#adbdcc] hover:text-white py-2">Pricing</Link>
              <Link href="/resources" className="text-[#adbdcc] hover:text-white py-2">Resources</Link>
              <Link href="/about" className="text-[#adbdcc] hover:text-white py-2">About Us</Link>
              <Link href="/contact" className="text-[#adbdcc] hover:text-white py-2">Contact Us</Link>
              <Link href="/signin" className="text-white font-medium py-2">Sign In</Link>
              <div className="sparkle-button">
                <button className="relative w-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-6 rounded-lg overflow-hidden group">
                  <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                  <span className="backdrop"></span>
                  <svg className="sparkle" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z" fill="black" stroke="black" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="relative z-10">Get Started</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-36 pb-24 z-10">
        <div className="container mx-auto px-6 text-center">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 text-white leading-tight animate-fadeInUp">
            Powerful <span className="gradient-text">Features</span> for Your Academic Journey
          </h1>
          <p className="text-xl mb-8 max-w-3xl mx-auto animate-fadeInUp animate-delay-200">
            Everything you need to discover, apply, and succeed in your higher education goals with AI-powered tools and personalized support.
          </p>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-[#061220]/80 backdrop-blur-md relative z-10">
        <div className="container mx-auto px-6">
          {/* Section Header */}
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-light tracking-tight mb-4">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#00d4ff] to-[#7f5eff]">Comprehensive tools</span> 
              <span className="text-white"> for your success</span>
            </h2>
            <p className="text-[#adbdcc] text-xl max-w-2xl mx-auto font-light">
              Everything you need to connect, apply, and succeed in your higher education journey with unprecedented efficiency.
            </p>
          </div>
          
          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1: University Finder */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#00d4ff]/20 transition-all">
                <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">University Finder</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Find your perfect university match with AI-powered recommendations based on your academic profile, preferences, and career goals.
              </p>
            </div>
            
            {/* Feature 2: Scholarship Finder */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#7f5eff]/20 transition-all">
                <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3.09 8.26l1.82 1.544L12 4.5l7.09 5.304L21 8.26L12 2z"></path>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M22 10v6c0 1.105-.895 2-2 2H4c-1.105 0-2-.895-2-2v-6"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Scholarship Finder</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Discover scholarships tailored to your academic profile and background with filters for amount, eligibility, and application deadlines.
              </p>
            </div>
            
            {/* Feature 3: Student Loan Finder */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#00d4ff]/20 transition-all">
                <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Student Loan Finder</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Compare student loan options with favorable terms, competitive interest rates, and flexible repayment plans tailored to your needs.
              </p>
            </div>
            
            {/* Feature 4: Faculty Finder */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#7f5eff]/20 transition-all">
                <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="7" r="4"></circle>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.5 21h13c.8 0 1.5-.7 1.5-1.5v-1c0-3.3-4.3-5.5-8-5.5s-8 2.2-8 5.5v1C4 20.3 4.7 21 5.5 21z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Faculty Finder</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Connect with professors and researchers in your field of interest and automatically generate personalized email templates for outreach.
              </p>
            </div>
            
            {/* Feature 5: Resume Builder */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#00d4ff]/20 transition-all">
                <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14,2 14,8 20,8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Resume Builder</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Create professional resumes tailored for academic applications with AI-powered enhancement suggestions to strengthen your profile.
              </p>
            </div>
            
            {/* Feature 6: SOP Builder */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#7f5eff]/20 transition-all">
                <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 20h9"></path>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">SOP Builder</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Create, edit, and enhance your Statement of Purpose with AI assistance, templates, examples, and enhancement tools.
              </p>
            </div>
            
            {/* Feature 7: Application Manager */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#00d4ff]/20 transition-all">
                <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Application Manager</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Track and manage all your applications in one place with monitoring for deadlines, status updates, and required documents.
              </p>
            </div>
            
            {/* Feature 8: Education Counselor */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#7f5eff]/20 transition-all">
                <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Education Counselor</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Get personalized guidance from AI education counselors on university selection, application strategy, and more.
              </p>
            </div>
            
            {/* Feature 9: University GPT */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#00d4ff]/20 transition-all">
                <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">University GPT</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Ask questions about specific universities and programs to get detailed information about admission requirements, campus life, and more.
              </p>
            </div>
            
            {/* Feature 10: Visa Support */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#7f5eff]/20 transition-all">
                <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7h-3V4c0-.6-.4-1-1-1H8c-.6 0-1 .4-1 1v3H4c-.6 0-1 .4-1 1v8c0 .6.4 1 1 1h3v3c0 .6.4 1 1 1h8c.6 0 1-.4 1-1v-3h3c.6 0 1-.4 1-1V8c0-.6-.4-1-1-1z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Visa Support</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Navigate the visa application process with step-by-step guidance, document templates, and application checklists.
              </p>
            </div>
            
            {/* Feature 11: Deadline Notifications */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#00d4ff]/20 transition-all">
                <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Deadline Notifications</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Receive timely alerts for application deadlines and never miss important submission dates for applications, scholarships, or documents.
              </p>
            </div>
            
            {/* Feature 12: Unified Dashboard */}
            <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all group feature-card">
              <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mb-6 group-hover:bg-[#7f5eff]/20 transition-all">
                <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8v-10h-8v10zm0-18v6h8V3h-8z"></path>
                </svg>
              </div>
              <h3 className="text-xl font-light mb-3 text-white">Unified Dashboard</h3>
              <p className="text-[#adbdcc] font-light leading-relaxed">
                Access all tools and features from a centralized dashboard and track your application progress and next steps in one place.
              </p>
            </div>
          </div>
          
          {/* Call to Action */}
          <div className="mt-16 text-center">
            <button className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium rounded-lg px-8 py-3 hover:opacity-90 transition-all">
              Get Started Today
            </button>
          </div>
        </div>
      </section>

      {/* Feature Categories Section */}
      <section className="py-16 relative z-10">
        <div className="container mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">Feature <span className="gradient-text">Categories</span></h2>
            <p className="text-xl max-w-3xl mx-auto">
              Our comprehensive suite of tools is organized to support every stage of your academic journey
            </p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            {/* Discovery Tools */}
            <div className="bg-[#0c2e4e] p-8 rounded-lg shadow-xl feature-card">
              <div className="w-16 h-16 bg-gradient-to-r from-[#00d4ff]/20 to-[#7f5eff]/20 rounded-full flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">Discovery Tools</h3>
              <ul className="space-y-3">
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>University Finder</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Scholarship Finder</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Student Loan Finder</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Faculty Finder</span>
                </li>
              </ul>
            </div>
            
            {/* Application Tools */}
            <div className="bg-[#0c2e4e] p-8 rounded-lg shadow-xl feature-card">
              <div className="w-16 h-16 bg-gradient-to-r from-[#00d4ff]/20 to-[#7f5eff]/20 rounded-full flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-[#7f5eff]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">Application Tools</h3>
              <ul className="space-y-3">
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#7f5eff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Resume Builder</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#7f5eff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>SOP Builder</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#7f5eff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Application Manager</span>
                </li>
              </ul>
            </div>
            
            {/* Support Tools */}
            <div className="bg-[#0c2e4e] p-8 rounded-lg shadow-xl feature-card">
              <div className="w-16 h-16 bg-gradient-to-r from-[#00d4ff]/20 to-[#7f5eff]/20 rounded-full flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z"></path>
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-white mb-4">Support Tools</h3>
              <ul className="space-y-3">
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Education Counselor</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>University GPT</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Visa Support</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Deadline Notifications</span>
                </li>
                <li className="flex items-center">
                  <svg className="w-5 h-5 text-[#00d4ff] mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <span>Unified Dashboard</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#061220] pt-16 pb-8 relative z-10">
        <div className="container mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-12">
            {/* Company Info */}
            <div>
              <div className="flex items-center mb-6">
                <div className="h-10 w-10 rounded-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] mr-3 flex items-center justify-center">
                  <span className="text-white font-bold">AI</span>
                </div>
                <span className="text-white text-xl font-bold">
                  <span className="gradient-text">AI</span> Student Success
                </span>
              </div>
              <p className="text-[#adbdcc] mb-4">Your complete platform for higher education success.</p>
              <div className="flex space-x-4">
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M22.675 0h-21.35c-.732 0-1.325.593-1.325 1.325v21.351c0 .731.593 1.324 1.325 1.324h11.495v-9.294h-3.128v-3.622h3.128v-2.671c0-3.1 1.893-4.788 4.659-4.788 1.325 0 2.463.099 2.795.143v3.24l-1.918.001c-1.504 0-1.795.715-1.795 1.763v2.313h3.587l-.467 3.622h-3.12v9.293h6.116c.73 0 1.323-.593 1.323-1.325v-21.35c0-.732-.593-1.325-1.325-1.325z"/>
                  </svg>
                </a>
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723 10.054 10.054 0 01-3.127 1.184 4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
                  </svg>
                </a>
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                  </svg>
                </a>
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                </a>
              </div>
            </div>
            
            {/* Quick Links */}
            <div>
              <h3 className="text-xl font-bold text-white mb-4">Quick Links</h3>
              <ul className="space-y-2">
                <li><Link href="/" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Home</Link></li>
                <li><Link href="/features" className="text-[#00d4ff]">Features</Link></li>
                <li><Link href="/pricing" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Pricing</Link></li>
                <li><Link href="/resources" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Resources</Link></li>
                <li><Link href="/about" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">About Us</Link></li>
                <li><Link href="/contact" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Contact Us</Link></li>
              </ul>
            </div>
            
            {/* Features */}
            <div>
              <h3 className="text-xl font-bold text-white mb-4">Features</h3>
              <ul className="space-y-2">
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">University Finder</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">SOP Builder</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Resume Builder</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Application Manager</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Scholarship Finder</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Visa Support</a></li>
              </ul>
            </div>
            
            {/* Contact */}
            <div>
              <h3 className="text-xl font-bold text-white mb-4">Contact Us</h3>
              <ul className="space-y-4">
                <li className="flex items-start">
                  <svg className="w-5 h-5 mr-3 text-[#00d4ff] mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                  </svg>
                  <span className="text-[#adbdcc]">+1 (800) 123-4567</span>
                </li>
                <li className="flex items-start">
                  <svg className="w-5 h-5 mr-3 text-[#00d4ff] mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                  </svg>
                  <span className="text-[#adbdcc]">info@aistudentsuccess.com</span>
                </li>
                <li className="flex items-start">
                  <svg className="w-5 h-5 mr-3 text-[#00d4ff] mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                  </svg>
                  <span className="text-[#adbdcc]">123 Education Street<br/>San Francisco, CA 94105</span>
                </li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-[#1a3045] pt-8">
            <div className="flex flex-col md:flex-row justify-between items-center">
              <p className="text-[#8b9cad] mb-4 md:mb-0">&copy; 2025 AI Student Success. All rights reserved.</p>
              <div className="flex space-x-6">
                <a href="#" className="text-[#8b9cad] hover:text-[#00d4ff] transition-colors">Privacy Policy</a>
                <a href="#" className="text-[#8b9cad] hover:text-[#00d4ff] transition-colors">Terms of Service</a>
                <a href="#" className="text-[#8b9cad] hover:text-[#00d4ff] transition-colors">Cookie Policy</a>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default FeaturesPage;