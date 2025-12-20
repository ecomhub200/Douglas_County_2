'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import Script from 'next/script';

declare global {
  interface Window {
    VANTA: any;
    gsap: any;
    MorphSVGPlugin: any;
    Draggable: any;
  }
}

const PricingPage: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isYearly, setIsYearly] = useState(false);
  const [vantaEffect, setVantaEffect] = useState<any>(null);
  const cordTlRef = useRef<any>(null);
  const stateRef = useRef({ ON: false });

  useEffect(() => {
    if (vantaEffect) vantaEffect.destroy();
    
    const initVanta = () => {
      if (window.VANTA) {
        setVantaEffect(
          window.VANTA.NET({
            el: "#vanta-bg",
            mouseControls: true,
            touchControls: true,
            gyroControls: false,
            minHeight: 200.00,
            minWidth: 200.00,
            scale: 1.00,
            scaleMobile: 1.00,
            color: 0x00d4ff,
            backgroundColor: 0x0a1a2e,
            points: 12.00,
            maxDistance: 22.00,
            spacing: 18.00
          })
        );
      }
    };

    if (window.VANTA) {
      initVanta();
    } else {
      const checkVanta = setInterval(() => {
        if (window.VANTA) {
          initVanta();
          clearInterval(checkVanta);
        }
      }, 100);
      
      return () => clearInterval(checkVanta);
    }

    return () => {
      if (vantaEffect) vantaEffect.destroy();
    };
  }, []);

  // Initialize light bulb animation
  useEffect(() => {
    const initLightBulb = () => {
      if (window.gsap && window.MorphSVGPlugin && window.Draggable) {
        const { gsap, MorphSVGPlugin, Draggable } = window;
        gsap.registerPlugin(MorphSVGPlugin);

        let startX: number;
        let startY: number;

        const CORD_DURATION = 0.1;
        const CORDS = document.querySelectorAll('.toggle-scene__cord');
        const HIT = document.querySelector('.toggle-scene__hit-spot');
        const DUMMY = document.querySelector('.toggle-scene__dummy-cord');
        const DUMMY_CORD = document.querySelector('.toggle-scene__dummy-cord line');
        const PROXY = document.createElement('div');

        if (!DUMMY_CORD) return;

        const ENDX = DUMMY_CORD.getAttribute('x2');
        const ENDY = DUMMY_CORD.getAttribute('y2');

        const RESET = () => {
          gsap.set(PROXY, { x: ENDX, y: ENDY });
        };

        RESET();

        cordTlRef.current = gsap.timeline({
          paused: true,
          onStart: () => {
            stateRef.current.ON = !stateRef.current.ON;
            setIsYearly(stateRef.current.ON);
            gsap.set(document.documentElement, { '--on': stateRef.current.ON ? 1 : 0 });
            gsap.set([DUMMY, HIT], { display: 'none' });
            gsap.set(CORDS[0], { display: 'block' });
          },
          onComplete: () => {
            gsap.set([DUMMY, HIT], { display: 'block' });
            gsap.set(CORDS[0], { display: 'none' });
            RESET();
          }
        });

        for (let i = 1; i < CORDS.length; i++) {
          cordTlRef.current.add(
            gsap.to(CORDS[0], {
              morphSVG: CORDS[i],
              duration: CORD_DURATION,
              repeat: 1,
              yoyo: true
            })
          );
        }

        Draggable.create(PROXY, {
          trigger: HIT,
          type: 'x,y',
          onPress: (e: any) => {
            startX = e.x;
            startY = e.y;
          },
          onDrag: function() {
            gsap.set(DUMMY_CORD, {
              attr: {
                x2: this.x,
                y2: this.y
              }
            });
          },
          onRelease: function(e: any) {
            const DISTX = Math.abs(e.x - startX);
            const DISTY = Math.abs(e.y - startY);
            const TRAVELLED = Math.sqrt(DISTX * DISTX + DISTY * DISTY);
            gsap.to(DUMMY_CORD, {
              attr: { x2: ENDX, y2: ENDY },
              duration: CORD_DURATION,
              onComplete: () => {
                if (TRAVELLED > 50) {
                  cordTlRef.current.restart();
                } else {
                  RESET();
                }
              }
            });
          }
        });
      }
    };

    const checkGSAP = setInterval(() => {
      if (window.gsap && window.MorphSVGPlugin && window.Draggable) {
        initLightBulb();
        clearInterval(checkGSAP);
      }
    }, 100);

    return () => clearInterval(checkGSAP);
  }, []);

  return (
    <>
      <Script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js" strategy="beforeInteractive" />
      <Script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.net.min.js" strategy="afterInteractive" />
      <Script src="https://unpkg.co/gsap@3/dist/gsap.min.js" strategy="afterInteractive" />
      <Script src="https://assets.codepen.io/16327/MorphSVGPlugin3.min.js" strategy="afterInteractive" />
      <Script src="https://unpkg.com/gsap@3/dist/Draggable.min.js" strategy="afterInteractive" />
      
      <div className="bg-[#0a1a2e] text-[#adbdcc] min-h-screen font-['Inter',sans-serif]">
        <style jsx global>{`
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
          
          :root {
            --on: 0;
            --bg: hsl(calc(200 - (var(--on) * 160)), calc((20 + (var(--on) * 50)) * 1%), calc((20 + (var(--on) * 60)) * 1%));
            --cord: hsl(0, 0%, calc((60 - (var(--on) * 50)) * 1%));
            --stroke: hsl(0, 0%, calc((60 - (var(--on) * 50)) * 1%));
            --shine: hsla(0, 0%, 100%, calc(0.75 - (var(--on) * 0.5)));
            --cap: hsl(0, 0%, calc((40 + (var(--on) * 30)) * 1%));
            --filament: hsl(45, calc(var(--on) * 80%), calc((25 + (var(--on) * 75)) * 1%));
          }
          
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
          
          .animate-delay-800 {
            animation-delay: 0.8s;
            opacity: 0;
          }
          
          .pricing-card {
            transition: transform 0.3s ease, box-shadow 0.3s ease;
          }
          
          .pricing-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px -10px rgba(0, 212, 255, 0.3);
          }
          
          .sparkle-button button {
            transition: all 0.3s ease;
          }
          
          .sparkle-button button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 212, 255, 0.4);
          }
          
          .gradient-text {
            background: linear-gradient(to right, #00d4ff, #7f5eff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
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
          
          /* Light bulb styles */
          .toggle-scene {
            overflow: visible !important;
            height: 80px;
            width: 80px;
          }
          
          .toggle-scene__cord {
            stroke: var(--cord);
            cursor: move;
          }
          
          .toggle-scene__cord:nth-of-type(1) {
            display: none;
          }
          
          .toggle-scene__cord:nth-of-type(2),
          .toggle-scene__cord:nth-of-type(3),
          .toggle-scene__cord:nth-of-type(4),
          .toggle-scene__cord:nth-of-type(5) {
            display: none;
          }
          
          .toggle-scene__cord-end {
            stroke: var(--cord);
            fill: var(--cord);
          }
          
          .toggle-scene__dummy-cord {
            stroke-width: 6;
            stroke: var(--cord);
          }
          
          .bulb__filament {
            stroke: var(--filament);
          }
          
          .bulb__shine {
            stroke: var(--shine);
          }
          
          .bulb__flash {
            stroke: #f5e0a3;
            display: none;
          }
          
          .bulb__bulb {
            stroke: var(--stroke);
            fill: hsla(calc(180 - (95 * var(--on))), 80%, 80%, calc(0.1 + (0.4 * var(--on))));
          }
          
          .bulb__cap {
            fill: var(--cap);
          }
          
          .bulb__cap-shine {
            fill: var(--shine);
          }
          
          .bulb__cap-outline {
            stroke: var(--stroke);
          }
        `}</style>

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
                <Link href="/features" className="text-[#adbdcc] hover:text-white transition-colors">Features</Link>
                <Link href="/pricing" className="text-white font-medium transition-colors">Pricing</Link>
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
                <Link href="/features" className="text-[#adbdcc] hover:text-white py-2">Features</Link>
                <Link href="/pricing" className="text-white font-medium py-2">Pricing</Link>
                <Link href="/resources" className="text-[#adbdcc] hover:text-white py-2">Resources</Link>
                <Link href="/about" className="text-[#adbdcc] hover:text-white py-2">About Us</Link>
                <Link href="/contact" className="text-[#adbdcc] hover:text-white py-2">Contact Us</Link>
                <Link href="/signin" className="text-white font-medium py-2">Sign In</Link>
                <div className="sparkle-button">
                  <button className="relative w-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-6 rounded-lg overflow-hidden group">
                    <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                    <span className="relative z-10">Get Started</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </nav>

        {/* Hero Section */}
        <section className="relative overflow-hidden pt-32 pb-24">
          {/* Vanta.js background */}
          <div id="vanta-bg" className="absolute inset-0 z-0"></div>
          
          {/* Background glow effects */}
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-[#00d4ff]/20 rounded-full filter blur-[100px] -z-10"></div>
          <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-[#7f5eff]/20 rounded-full filter blur-[100px] -z-10"></div>
          
          <div className="container mx-auto px-6 text-center relative z-10">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 text-white leading-tight animate-fadeInUp">
              Simple, Transparent <span className="gradient-text">Pricing</span>
            </h1>
            <p className="text-xl mb-8 max-w-3xl mx-auto animate-fadeInUp animate-delay-200">
              Choose the perfect plan for your academic journey with no hidden fees or long-term commitments.
            </p>
          </div>
        </section>

        {/* Pricing Section */}
        <section className="py-24 bg-[#061220] relative overflow-hidden">
          {/* Background elements */}
          <div className="absolute top-40 left-20 w-96 h-96 bg-[#00d4ff]/20 rounded-full blur-3xl"></div>
          <div className="absolute bottom-20 right-20 w-96 h-96 bg-[#7f5eff]/20 rounded-full blur-3xl"></div>
          
          <div className="container mx-auto px-6 relative z-10">
            {/* Pricing Toggle with Light Bulb */}
            <div className="flex justify-center items-center mb-12">
              <span className="text-[#adbdcc] mr-4">Monthly</span>
              
              {/* Light Bulb Toggle */}
              <div className="relative" style={{ width: '80px', height: '80px' }}>
                <svg className="toggle-scene" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin" viewBox="0 0 197.451 481.081">
                  <defs>
                    <marker id="e" orient="auto" overflow="visible" refX="0" refY="0">
                      <path className="toggle-scene__cord-end" fillRule="evenodd" strokeWidth=".2666" d="M.98 0a1 1 0 11-2 0 1 1 0 012 0z"></path>
                    </marker>
                    <marker id="d" orient="auto" overflow="visible" refX="0" refY="0">
                      <path className="toggle-scene__cord-end" fillRule="evenodd" strokeWidth=".2666" d="M.98 0a1 1 0 11-2 0 1 1 0 012 0z"></path>
                    </marker>
                    <marker id="c" orient="auto" overflow="visible" refX="0" refY="0">
                      <path className="toggle-scene__cord-end" fillRule="evenodd" strokeWidth=".2666" d="M.98 0a1 1 0 11-2 0 1 1 0 012 0z"></path>
                    </marker>
                    <marker id="b" orient="auto" overflow="visible" refX="0" refY="0">
                      <path className="toggle-scene__cord-end" fillRule="evenodd" strokeWidth=".2666" d="M.98 0a1 1 0 11-2 0 1 1 0 012 0z"></path>
                    </marker>
                    <marker id="a" orient="auto" overflow="visible" refX="0" refY="0">
                      <path className="toggle-scene__cord-end" fillRule="evenodd" strokeWidth=".2666" d="M.98 0a1 1 0 11-2 0 1 1 0 012 0z"></path>
                    </marker>
                    <clipPath id="g" clipPathUnits="userSpaceOnUse">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="4.677" d="M-774.546 827.629s12.917-13.473 29.203-13.412c16.53.062 29.203 13.412 29.203 13.412v53.6s-8.825 16-29.203 16c-21.674 0-29.203-16-29.203-16z"></path>
                    </clipPath>
                    <clipPath id="f" clipPathUnits="userSpaceOnUse">
                      <path d="M-868.418 945.051c-4.188 73.011 78.255 53.244 150.216 52.941 82.387-.346 98.921-19.444 98.921-47.058 0-27.615-4.788-42.55-73.823-42.55-69.036 0-171.436-30.937-175.314 36.667z"></path>
                    </clipPath>
                  </defs>
                  <g className="toggle-scene__cords">
                    <path className="toggle-scene__cord" markerEnd="url(#a)" fill="none" strokeLinecap="square" strokeWidth="6" d="M123.228-28.56v150.493" transform="translate(-24.503 256.106)"></path>
                    <path className="toggle-scene__cord" markerEnd="url(#a)" fill="none" strokeLinecap="square" strokeWidth="6" d="M123.228-28.59s28 8.131 28 19.506-18.667 13.005-28 19.507c-9.333 6.502-28 8.131-28 19.506s28 19.507 28 19.507" transform="translate(-24.503 256.106)"></path>
                    <path className="toggle-scene__cord" markerEnd="url(#a)" fill="none" strokeLinecap="square" strokeWidth="6" d="M123.228-28.575s-20 16.871-20 28.468c0 11.597 13.333 18.978 20 28.468 6.667 9.489 20 16.87 20 28.467 0 11.597-20 28.468-20 28.468" transform="translate(-24.503 256.106)"></path>
                    <path className="toggle-scene__cord" markerEnd="url(#a)" fill="none" strokeLinecap="square" strokeWidth="6" d="M123.228-28.569s16 20.623 16 32.782c0 12.16-10.667 21.855-16 32.782-5.333 10.928-16 20.623-16 32.782 0 12.16 16 32.782 16 32.782" transform="translate(-24.503 256.106)"></path>
                    <path className="toggle-scene__cord" markerEnd="url(#a)" fill="none" strokeLinecap="square" strokeWidth="6" d="M123.228-28.563s-10 24.647-10 37.623c0 12.977 6.667 25.082 10 37.623 3.333 12.541 10 24.647 10 37.623 0 12.977-10 37.623-10 37.623" transform="translate(-24.503 256.106)"></path>
                    <g className="line toggle-scene__dummy-cord">
                      <line markerEnd="url(#a)" x1="98.7255" x2="98.7255" y1="240.5405" y2="380.5405"></line>
                    </g>
                    <circle className="toggle-scene__hit-spot" cx="98.7255" cy="380.5405" r="60" fill="transparent"></circle>
                  </g>
                  <g className="toggle-scene__bulb bulb" transform="translate(844.069 -645.213)">
                    <path className="bulb__cap" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4.677" d="M-774.546 827.629s12.917-13.473 29.203-13.412c16.53.062 29.203 13.412 29.203 13.412v53.6s-8.825 16-29.203 16c-21.674 0-29.203-16-29.203-16z"></path>
                    <path className="bulb__cap-shine" d="M-778.379 802.873h25.512v118.409h-25.512z" clipPath="url(#g)" transform="matrix(.52452 0 0 .90177 -368.282 82.976)"></path>
                    <path className="bulb__cap" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4" d="M-774.546 827.629s12.917-13.473 29.203-13.412c16.53.062 29.203 13.412 29.203 13.412v0s-8.439 10.115-28.817 10.115c-21.673 0-29.59-10.115-29.59-10.115z"></path>
                    <path className="bulb__cap-outline" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="4.677" d="M-774.546 827.629s12.917-13.473 29.203-13.412c16.53.062 29.203 13.412 29.203 13.412v53.6s-8.825 16-29.203 16c-21.674 0-29.203-16-29.203-16z"></path>
                    <g className="bulb__filament" fill="none" strokeLinecap="round" strokeWidth="5">
                      <path d="M-752.914 823.875l-8.858-33.06"></path>
                      <path d="M-737.772 823.875l8.858-33.06"></path>
                    </g>
                    <path className="bulb__bulb" strokeLinecap="round" strokeWidth="5" d="M-783.192 803.855c5.251 8.815 5.295 21.32 13.272 27.774 12.299 8.045 36.46 8.115 49.127 0 7.976-6.454 8.022-18.96 13.273-27.774 3.992-6.7 14.408-19.811 14.408-19.811 8.276-11.539 12.769-24.594 12.769-38.699 0-35.898-29.102-65-65-65-35.899 0-65 29.102-65 65 0 13.667 4.217 26.348 12.405 38.2 0 0 10.754 13.61 14.746 20.31z"></path>
                    <circle className="bulb__flash" cx="-745.343" cy="743.939" r="83.725" fill="none" strokeDasharray="10,30" strokeLinecap="round" strokeLinejoin="round" strokeWidth="10"></circle>
                    <path className="bulb__shine" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="12" d="M-789.19 757.501a45.897 45.897 0 013.915-36.189 45.897 45.897 0 0129.031-21.957"></path>
                  </g>
                </svg>
              </div>
              
              <span className="text-[#adbdcc] ml-4">Yearly <span className="text-xs text-[#00d4ff]">(Save 20%)</span></span>
            </div>
            
            {/* Pricing Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-7xl mx-auto">
              {/* Free Plan */}
              <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-2xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all flex flex-col h-full pricing-card">
                <div className="mb-8">
                  <h3 className="text-xl font-normal mb-2 text-white">Free</h3>
                  <p className="text-[#adbdcc] font-light text-sm mb-4">Perfect for exploring</p>
                  <div className="flex items-baseline">
                    <span className="text-4xl font-light text-white">$0</span>
                    <span className="text-[#adbdcc] ml-2 font-light">/month</span>
                  </div>
                </div>
                <ul className="space-y-3 mb-8 flex-grow">
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    100 credits
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Basic University Search
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    3 Resume Templates
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Application Tracking (up to 3)
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Basic Email Support
                  </li>
                  <li className="flex items-center text-gray-500 font-light">
                    <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    AI-Powered Features
                  </li>
                  <li className="flex items-center text-gray-500 font-light">
                    <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    Counselor Access
                  </li>
                  <li className="flex items-center text-gray-500 font-light">
                    <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    Priority Support
                  </li>
                </ul>
                <button className="w-full bg-transparent border border-[#0f395e] text-white font-medium rounded-lg py-3 px-6 hover:bg-white/5 transition-all">
                  Start Free
                </button>
              </div>
              
              {/* Standard Plan (Featured) */}
              <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-2xl border border-[#00d4ff]/30 hover:border-[#00d4ff]/60 transition-all flex flex-col h-full pricing-card relative">
                <div className="absolute top-0 right-8 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black text-xs font-medium px-3 py-1 rounded-b-md">
                  MOST POPULAR 🔥
                </div>
                <div className="mb-8">
                  <h3 className="text-xl font-normal mb-2 text-white">Standard</h3>
                  <p className="text-[#adbdcc] font-light text-sm mb-4">Most Popular</p>
                  <div className="flex items-baseline">
                    <span className={`text-4xl font-light text-white ${isYearly ? 'hidden' : ''}`}>$19.99</span>
                    <span className={`text-4xl font-light text-white ${!isYearly ? 'hidden' : ''}`}>$191.90</span>
                    <span className={`text-[#adbdcc] ml-2 font-light ${isYearly ? 'hidden' : ''}`}>/month</span>
                    <span className={`text-[#adbdcc] ml-2 font-light ${!isYearly ? 'hidden' : ''}`}>/year</span>
                  </div>
                  <div className={`text-[#00d4ff] text-sm mt-1 ${!isYearly ? 'hidden' : ''}`}>Save $47.98/year</div>
                </div>
                <ul className="space-y-3 mb-8 flex-grow">
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    500 credits per month
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Everything in Free, plus:
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    AI Compatibility Scoring
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    All Resume &amp; SOP Templates
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    University GPT Chat
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Faculty Finder Access
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Email + Chat Support
                  </li>
                  <li className="flex items-center text-gray-500 font-light">
                    <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    Education Counselor
                  </li>
                  <li className="flex items-center text-gray-500 font-light">
                    <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    Visa Support
                  </li>
                </ul>
                <button className="w-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium rounded-lg py-3 px-6 hover:opacity-90 transition-all">
                  Choose Standard
                </button>
              </div>
              
              {/* Premium Plan */}
              <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-2xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all flex flex-col h-full pricing-card">
                <div className="mb-8">
                  <h3 className="text-xl font-normal mb-2 text-white">Premium</h3>
                  <p className="text-[#adbdcc] font-light text-sm mb-4">Complete support</p>
                  <div className="flex items-baseline">
                    <span className={`text-4xl font-light text-white ${isYearly ? 'hidden' : ''}`}>$39.99</span>
                    <span className={`text-4xl font-light text-white ${!isYearly ? 'hidden' : ''}`}>$383.90</span>
                    <span className={`text-[#adbdcc] ml-2 font-light ${isYearly ? 'hidden' : ''}`}>/month</span>
                    <span className={`text-[#adbdcc] ml-2 font-light ${!isYearly ? 'hidden' : ''}`}>/year</span>
                  </div>
                  <div className={`text-[#00d4ff] text-sm mt-1 ${!isYearly ? 'hidden' : ''}`}>Save $95.98/year</div>
                </div>
                <ul className="space-y-3 mb-8 flex-grow">
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    1,500 credits per month
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Everything in Standard, plus:
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Education Counselor Access
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Priority Support
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Visa &amp; Immigration Support
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Interview Preparation
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Personalized Success Plan
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Early Access Features
                  </li>
                </ul>
                <button className="w-full bg-transparent border border-[#0f395e] text-white font-medium rounded-lg py-3 px-6 hover:bg-white/5 transition-all">
                  Go Premium
                </button>
              </div>
              
              {/* Elite Plan */}
              <div className="bg-gradient-to-br from-[#0c2e4e] to-[#061220] p-8 rounded-2xl border border-[#0f395e] hover:border-[#00d4ff]/30 transition-all flex flex-col h-full pricing-card">
                <div className="mb-8">
                  <h3 className="text-xl font-normal mb-2 text-white">Elite</h3>
                  <p className="text-[#adbdcc] font-light text-sm mb-4">VIP Experience 👑</p>
                  <div className="flex items-baseline">
                    <span className={`text-4xl font-light text-white ${isYearly ? 'hidden' : ''}`}>$100</span>
                    <span className={`text-4xl font-light text-white ${!isYearly ? 'hidden' : ''}`}>$959.88</span>
                    <span className={`text-[#adbdcc] ml-2 font-light ${isYearly ? 'hidden' : ''}`}>/month</span>
                    <span className={`text-[#adbdcc] ml-2 font-light ${!isYearly ? 'hidden' : ''}`}>/year</span>
                  </div>
                  <div className={`text-[#00d4ff] text-sm mt-1 ${!isYearly ? 'hidden' : ''}`}>Save $240.12/year</div>
                  <div className="text-[#adbdcc] text-xs mt-1">Limited spots available</div>
                </div>
                <ul className="space-y-3 mb-8 flex-grow">
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    3,000 credits per month
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Everything in Premium, plus:
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Dedicated Success Manager
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Unlimited Counselor Sessions
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    White-glove Application Service
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    1-on-1 Strategy Sessions
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    Priority University Connections
                  </li>
                  <li className="flex items-center text-[#adbdcc] font-light">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                    </svg>
                    100% Credit Rollover
                  </li>
                </ul>
                <button className="w-full bg-transparent border border-[#0f395e] text-white font-medium rounded-lg py-3 px-6 hover:bg-white/5 transition-all">
                  Apply for Elite
                </button>
              </div>
            </div>
            
            {/* Plan Comparison Section */}
            <div className="mt-24 max-w-5xl mx-auto">
              <h3 className="text-2xl font-light mb-8 text-center text-white">Why Upgrade?</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Standard Plan */}
                <div className="bg-[#0c2e4e] p-8 rounded-xl">
                  <h4 className="text-xl font-medium mb-4 text-white">Standard Plan Perfect For:</h4>
                  <ul className="space-y-3">
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Active applicants targeting 5-10 universities</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">DIY students who want AI assistance</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Budget-conscious users needing core features</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Early stage application planning</span>
                    </li>
                  </ul>
                </div>
                
                {/* Premium Plan */}
                <div className="bg-[#0c2e4e] p-8 rounded-xl">
                  <h4 className="text-xl font-medium mb-4 text-white">Premium Plan Perfect For:</h4>
                  <ul className="space-y-3">
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Serious applicants targeting top universities</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">International students needing visa support</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Those wanting expert counselor guidance</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Maximum success probability seekers</span>
                    </li>
                  </ul>
                </div>
                
                {/* Elite Plan */}
                <div className="bg-[#0c2e4e] p-8 rounded-xl">
                  <h4 className="text-xl font-medium mb-4 text-white">Elite Plan Perfect For:</h4>
                  <ul className="space-y-3">
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Ivy League aspirants</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Premium support requirements</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Multiple application cycles</span>
                    </li>
                    <li className="flex items-start">
                      <svg className="w-5 h-5 mr-2 text-[#00d4ff] mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                      </svg>
                      <span className="text-[#adbdcc]">Busy professionals wanting done-for-you service</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
            
            {/* FAQ Section */}
            <div className="mt-24 max-w-3xl mx-auto">
              <h3 className="text-2xl font-light mb-8 text-center text-white">Frequently asked questions</h3>
              
              <div className="space-y-6">
                <div className="border-b border-[#0f395e] pb-6">
                  <h4 className="text-lg font-normal mb-2 text-white">What are credits and how do they work?</h4>
                  <p className="text-[#adbdcc] font-light">Credits are used for AI-powered features like document generation, compatibility scoring, and counselor sessions. Different features use different amounts of credits, and your plan includes a monthly allocation that refreshes each billing cycle.</p>
                </div>
                
                <div className="border-b border-[#0f395e] pb-6">
                  <h4 className="text-lg font-normal mb-2 text-white">Can I change my plan later?</h4>
                  <p className="text-[#adbdcc] font-light">Yes, you can upgrade or downgrade your plan at any time. Changes will be reflected in your next billing cycle.</p>
                </div>
                
                <div className="border-b border-[#0f395e] pb-6">
                  <h4 className="text-lg font-normal mb-2 text-white">Do you offer a free trial?</h4>
                  <p className="text-[#adbdcc] font-light">Yes, our Free plan is available indefinitely with limited features. You can upgrade to a paid plan whenever you're ready to access more features and credits.</p>
                </div>
                
                <div className="border-b border-[#0f395e] pb-6">
                  <h4 className="text-lg font-normal mb-2 text-white">What payment methods do you accept?</h4>
                  <p className="text-[#adbdcc] font-light">We accept all major credit cards, PayPal, and for annual plans, we also support wire transfers.</p>
                </div>
                
                <div className="border-b border-[#0f395e] pb-6">
                  <h4 className="text-lg font-normal mb-2 text-white">Is there a discount for students?</h4>
                  <p className="text-[#adbdcc] font-light">Yes, we offer special pricing for students with valid .edu email addresses. Please contact our support team for details.</p>
                </div>
              </div>
            </div>
            
            {/* CTA Section */}
            <div className="mt-16 text-center">
              <h3 className="text-2xl font-bold mb-6 text-white">Start Your Journey Today</h3>
              <p className="text-xl mb-8 text-[#adbdcc]">Join 25,000+ Students Who Got Into Their Dream Universities</p>
              <div className="flex flex-col sm:flex-row justify-center gap-4">
                <button className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium rounded-lg px-8 py-3 hover:opacity-90 transition-all">
                  Start Free Trial
                </button>
                <button className="py-3 px-8 rounded-lg border border-[#0f395e] text-white font-medium hover:border-[#00d4ff] hover:text-[#00d4ff] transition-colors">
                  See Success Stories
                </button>
              </div>
              <p className="text-[#00d4ff] mt-6">🔥 378 students started their journey in the last 24 hours</p>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="bg-[#061220] pt-16 pb-8">
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
                      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                  </a>
                  <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                    <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                    </svg>
                  </a>
                </div>
              </div>
              
              {/* Quick Links */}
              <div>
                <h3 className="text-xl font-bold text-white mb-4">Quick Links</h3>
                <ul className="space-y-2">
                  <li><Link href="/" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Home</Link></li>
                  <li><Link href="/features" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Features</Link></li>
                  <li><Link href="/pricing" className="text-[#00d4ff]">Pricing</Link></li>
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
                <h3 className="text-xl font-bold text-white mb-4">Still Unsure?</h3>
                <p className="text-[#adbdcc] mb-4">Talk to our Success Team</p>
                <ul className="space-y-2">
                  <li className="flex items-center">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                    </svg>
                    <span className="text-[#adbdcc]">1-800-EDU-DREAM</span>
                  </li>
                  <li className="flex items-center">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
                    </svg>
                    <span className="text-[#adbdcc]">Chat: Available 24/7</span>
                  </li>
                  <li className="flex items-center">
                    <svg className="w-5 h-5 mr-2 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                    </svg>
                    <span className="text-[#adbdcc]">success@aistudentsuccess.com</span>
                  </li>
                </ul>
              </div>
            </div>
            
            <div className="border-t border-[#0f395e] pt-8">
              <p className="text-center text-[#8b9cad]">&copy; 2025 AI Student Success. All rights reserved.</p>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
};

export default PricingPage;