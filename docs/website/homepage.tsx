'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import Script from 'next/script';

declare global {
  interface Window {
    VANTA: any;
  }
}

const HomePage: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [vantaEffect, setVantaEffect] = useState<any>(null);

  useEffect(() => {
    const syncPointer = ({ x, y }: MouseEvent) => {
      document.documentElement.style.setProperty('--x', `${x}px`);
      document.documentElement.style.setProperty('--y', `${y}px`);
    };
    
    document.addEventListener('pointermove', syncPointer);
    
    return () => {
      document.removeEventListener('pointermove', syncPointer);
    };
  }, []);

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

  return (
    <>
      <Script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js" strategy="beforeInteractive" />
      <Script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.net.min.js" strategy="afterInteractive" />
      
      <div className="bg-[#0a1a2e] text-[#adbdcc] font-['Inter',sans-serif]">
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
          
          .animate-delay-800 {
            animation-delay: 0.8s;
            opacity: 0;
          }
          
          .animate-delay-1000 {
            animation-delay: 1s;
            opacity: 0;
          }
          
          .animate-delay-1200 {
            animation-delay: 1.2s;
            opacity: 0;
          }
          
          .feature-card {
            transition: transform 0.3s ease, box-shadow 0.3s ease;
          }
          
          .feature-card:hover {
            transform: scale(1.03);
            box-shadow: 0 10px 30px -10px rgba(0, 212, 255, 0.3);
          }
          
          .testimonial-card {
            transition: transform 0.3s ease;
          }
          
          .testimonial-card:hover {
            transform: translateY(-5px);
          }
          
          .gradient-text {
            background: linear-gradient(to right, #00d4ff, #7f5eff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }
          
          @keyframes expandWidth {
            from { width: 15rem; opacity: 0.5; }
            to { width: 30rem; opacity: 1; }
          }
          
          @keyframes moveUp {
            from { opacity: 0.5; transform: translateY(100px); }
            to { opacity: 1; transform: translateY(0); }
          }
          
          @keyframes expandSmallWidth {
            from { width: 8rem; }
            to { width: 16rem; }
          }
          
          .animate-width {
            animation: expandWidth 0.8s ease-in-out 0.3s forwards;
          }
          
          .animate-up {
            animation: moveUp 0.8s ease-in-out 0.3s forwards;
          }
          
          .animate-small-width {
            animation: expandSmallWidth 0.8s ease-in-out 0.3s forwards;
          }
          
          .conic-left {
            background-image: conic-gradient(from 70deg at center top, rgb(0, 212, 255), transparent, transparent);
          }
          
          .conic-right {
            background-image: conic-gradient(from 290deg at center top, transparent, transparent, rgb(127, 94, 255));
          }
          
          .flow-card {
            --border-size: 1px;
            --spotlight-size: 150px;
            --hue: 210;
            background-image: radial-gradient(
              var(--spotlight-size) var(--spotlight-size) at
              var(--x, 50%)
              var(--y, 50%),
              hsl(var(--hue, 210) 100% 70% / 0.1),
              transparent
            );
            background-size: calc(100% + (2 * var(--border-size))) calc(100% + (2 * var(--border-size)));
            background-position: 50% 50%;
            background-attachment: fixed;
            position: relative;
            transition: all 0.3s cubic-bezier(.4,0,.2,1);
          }
          
          .flow-card::before,
          .flow-card::after {
            pointer-events: none;
            content: "";
            position: absolute;
            inset: calc(var(--border-size) * -1);
            border: var(--border-size) solid transparent;
            border-radius: 12px;
            background-attachment: fixed;
            background-size: calc(100% + (2 * var(--border-size))) calc(100% + (2 * var(--border-size)));
            background-repeat: no-repeat;
            background-position: 50% 50%;
            mask:
                linear-gradient(transparent, transparent),
                linear-gradient(white, white);
            mask-clip: padding-box, border-box;
            mask-composite: intersect;
            transition: opacity 0.3s ease;
          }
          
          .flow-card::before {
            background-image: radial-gradient(
              calc(var(--spotlight-size) * 0.75) calc(var(--spotlight-size) * 0.75) at
              var(--x, 50%)
              var(--y, 50%),
              hsl(var(--hue, 210) 100% 50% / 0.35),
              transparent 100%
            );
            filter: brightness(1.5);
          }
          
          .flow-card::after {
            background-image: radial-gradient(
              calc(var(--spotlight-size) * 0.4) calc(var(--spotlight-size) * 0.4) at
              var(--x, 50%)
              var(--y, 50%),
              hsl(0 100% 100% / 0.4),
              transparent 100%
            );
          }
          
          .flow-card:hover {
            transform: translateY(-4px) scale(1.02);
            box-shadow: 
              0 20px 35px rgba(0, 0, 0, 0.3),
              0 8px 40px 0 rgba(0, 212, 255, 0.25), 
              0 0 0 1px rgba(0, 212, 255, 0.6);
            border-color: rgba(0, 212, 255, 0.7);
            z-index: 10;
          }
          
          .flow-card:hover::before {
            opacity: 1.6;
          }
          
          .flow-card:hover::after {
            opacity: 1.2;
          }
          
          .glass-card {
            backdrop-filter: blur(12px);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
          }
          
          .quote-mark {
            background: linear-gradient(135deg, #00d4ff 0%, #7f5eff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
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
          
          .sparkle-button button .spark {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            border-radius: 8px;
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
          
          .carousel {
            scroll-snap-type: x mandatory;
            scroll-behavior: smooth;
          }
          
          .carousel-item {
            scroll-snap-align: start;
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
                <Link href="/" className="text-white font-medium transition-colors">Home</Link>
                <Link href="/features" className="text-[#adbdcc] hover:text-white transition-colors">Features</Link>
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
                <Link href="/" className="text-white font-medium py-2">Home</Link>
                <Link href="/features" className="text-[#adbdcc] hover:text-white py-2">Features</Link>
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

        {/* Hero Section with Vanta.js Background */}
        <div className="relative min-h-screen overflow-hidden pt-20">
          {/* Vanta.js background */}
          <div id="vanta-bg" className="absolute inset-0 z-0"></div>
          
          {/* Hero content */}
          <div className="relative z-10 flex flex-col items-center justify-center px-6 pt-16 pb-32 md:pt-32 md:pb-40 text-center">
            <div className="absolute top-1/2 left-1/2 w-[600px] h-[600px] -translate-x-1/2 -translate-y-1/2 bg-[#7f5eff] opacity-10 blur-[100px] rounded-full pointer-events-none"></div>
            
            <span className="px-3 py-1 text-xs font-medium text-[#00d4ff] bg-[#00d4ff] bg-opacity-10 rounded-full mb-8">Your Path to Academic Excellence</span>
            
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-4xl leading-tight text-white">
              Empowering your journey from <span className="gradient-text">aspiration to admission</span>
            </h1>
            
            <p className="mt-6 text-lg md:text-xl text-[#adbdcc] max-w-2xl">
              Every feature – from discovering universities to building your resume – is designed to bring your dream one step closer.
            </p>
            
            <div className="mt-12 flex flex-col sm:flex-row gap-4">
              <div className="sparkle-button">
                <button className="relative bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-8 rounded-lg overflow-hidden group">
                  <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                  <span className="backdrop"></span>
                  <svg className="sparkle" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z" fill="black" stroke="black" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="relative z-10">Get Started Your Dream</span>
                </button>
              </div>
              <button className="py-3 px-8 rounded-lg border border-[#0f395e] text-white font-medium hover:border-[#00d4ff] hover:text-[#00d4ff] transition-colors flex items-center justify-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                Watch demo
              </button>
            </div>
            
            {/* App showcase */}
            <div className="mt-20 w-full max-w-4xl">
              <div className="w-full h-[400px] bg-[#0c2e4e] rounded-lg shadow-2xl border border-[#1a3045] overflow-hidden">
                <div className="h-8 border-b border-[#1a3045] flex items-center px-4">
                  <div className="flex space-x-2">
                    <div className="w-3 h-3 rounded-full bg-[#FF5F57]"></div>
                    <div className="w-3 h-3 rounded-full bg-[#FEBC2E]"></div>
                    <div className="w-3 h-3 rounded-full bg-[#28C840]"></div>
                  </div>
                </div>
                <div className="p-4">
                  {/* App placeholder content */}
                  <div className="flex space-x-4 h-[350px]">
                    <div className="w-48 bg-[#061220] rounded p-3">
                      <div className="w-full h-4 bg-[#1a3045] rounded mb-3"></div>
                      <div className="w-3/4 h-3 bg-[#1a3045] rounded mb-4"></div>
                      <div className="space-y-2">
                        <div className="w-full h-8 bg-[#0c2e4e] rounded"></div>
                        <div className="w-full h-8 bg-[#0c2e4e] rounded"></div>
                        <div className="w-full h-8 bg-[#0c2e4e] rounded"></div>
                      </div>
                    </div>
                    <div className="flex-1 bg-[#061220] rounded p-3">
                      <div className="w-1/3 h-4 bg-[#1a3045] rounded mb-3"></div>
                      <div className="w-full h-[320px] bg-[#0c2e4e] rounded"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* User Journey Section with Lamp-light Gradient */}
        <section className="py-16 relative overflow-hidden">
          {/* Lamp-light gradient animation */}
          <div className="relative flex w-full flex-1 scale-y-125 items-center justify-center isolate z-0">
            {/* Left lamp gradient */}
            <div className="absolute inset-auto right-1/2 h-56 overflow-visible w-[15rem] conic-left text-white animate-width">
              <div className="absolute w-[100%] left-0 bg-[#0a1a2e] h-40 bottom-0 z-20 [mask-image:linear-gradient(to_top,white,transparent)]"></div>
              <div className="absolute w-40 h-[100%] left-0 bg-[#0a1a2e] bottom-0 z-20 [mask-image:linear-gradient(to_right,white,transparent)]"></div>
            </div>
            
            {/* Right lamp gradient */}
            <div className="absolute inset-auto left-1/2 h-56 w-[15rem] conic-right text-white animate-width">
              <div className="absolute w-40 h-[100%] right-0 bg-[#0a1a2e] bottom-0 z-20 [mask-image:linear-gradient(to_left,white,transparent)]"></div>
              <div className="absolute w-[100%] right-0 bg-[#0a1a2e] h-40 bottom-0 z-20 [mask-image:linear-gradient(to_top,white,transparent)]"></div>
            </div>
            
            {/* Shadow and glow effects */}
            <div className="absolute top-1/2 h-48 w-full translate-y-12 scale-x-150 bg-[#0a1a2e] blur-2xl"></div>
            <div className="absolute top-1/2 z-50 h-48 w-full bg-transparent opacity-10 backdrop-blur-md"></div>
            <div className="absolute inset-auto z-50 h-36 w-[28rem] -translate-y-1/2 rounded-full bg-[#7f5eff] opacity-50 blur-3xl"></div>
            
            {/* Center glow */}
            <div className="absolute inset-auto z-30 h-36 w-[8rem] -translate-y-[6rem] rounded-full bg-[#00d4ff] blur-2xl animate-small-width"></div>
            
            {/* Lamp line */}
            <div className="absolute inset-auto z-50 h-0.5 w-[15rem] -translate-y-[7rem] bg-[#00d4ff] animate-width"></div>
          </div>
          
          <div className="container mx-auto px-6 relative z-10 mt-16">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">Your <span className="gradient-text">Journey</span> to Success</h2>
              <p className="text-xl max-w-3xl mx-auto">
                We simplify the complex process of university applications into manageable steps
              </p>
            </div>
            
            <div className="grid md:grid-cols-2 gap-16">
              <div className="space-y-16">
                {/* Journey Step 1 */}
                <div className="relative group">
                  <div className="flex items-start">
                    <div className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] rounded-full w-14 h-14 flex items-center justify-center text-black font-bold text-xl mr-6 transition-transform group-hover:scale-110">
                      1
                    </div>
                    <div>
                      <h3 className="text-white text-2xl font-medium mb-3">Discover Universities</h3>
                      <p className="text-[#adbdcc] text-lg">Use our intelligent search to find universities that match your academic profile, preferences, and career goals.</p>
                    </div>
                  </div>
                  <div className="absolute left-7 top-16 h-20 w-px bg-gradient-to-b from-[#00d4ff] to-transparent"></div>
                  
                  {/* Illustrative graphic */}
                  <div className="mt-6 ml-14">
                    <svg className="w-16 h-16 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
                
                {/* Journey Step 2 */}
                <div className="relative group">
                  <div className="flex items-start">
                    <div className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] rounded-full w-14 h-14 flex items-center justify-center text-black font-bold text-xl mr-6 transition-transform group-hover:scale-110">
                      2
                    </div>
                    <div>
                      <h3 className="text-white text-2xl font-medium mb-3">Prepare Documents</h3>
                      <p className="text-[#adbdcc] text-lg">Create compelling resumes and statements of purpose with our AI-powered tools and expert guidance.</p>
                    </div>
                  </div>
                  <div className="absolute left-7 top-16 h-20 w-px bg-gradient-to-b from-[#00d4ff] to-transparent"></div>
                  
                  {/* Illustrative graphic */}
                  <div className="mt-6 ml-14">
                    <svg className="w-16 h-16 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M16 13H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M16 17H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M10 9H9H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
              </div>
              
              <div className="space-y-16">
                {/* Journey Step 3 */}
                <div className="relative group">
                  <div className="flex items-start">
                    <div className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] rounded-full w-14 h-14 flex items-center justify-center text-black font-bold text-xl mr-6 transition-transform group-hover:scale-110">
                      3
                    </div>
                    <div>
                      <h3 className="text-white text-2xl font-medium mb-3">Apply with Confidence</h3>
                      <p className="text-[#adbdcc] text-lg">Manage all your applications in one place with deadline reminders and status tracking.</p>
                    </div>
                  </div>
                  <div className="absolute left-7 top-16 h-20 w-px bg-gradient-to-b from-[#00d4ff] to-transparent"></div>
                  
                  {/* Illustrative graphic */}
                  <div className="mt-6 ml-14">
                    <svg className="w-16 h-16 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M22 11.08V12C21.9988 14.1564 21.3005 16.2547 20.0093 17.9818C18.7182 19.709 16.9033 20.9725 14.8354 21.5839C12.7674 22.1953 10.5573 22.1219 8.53447 21.3746C6.51168 20.6273 4.78465 19.2461 3.61096 17.4371C2.43727 15.628 1.87979 13.4881 2.02168 11.3363C2.16356 9.18455 2.99721 7.13631 4.39828 5.49706C5.79935 3.85781 7.69279 2.71537 9.79619 2.24013C11.8996 1.7649 14.1003 1.98232 16.07 2.85999" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M22 4L12 14.01L9 11.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
                
                {/* Journey Step 4 */}
                <div className="relative group">
                  <div className="flex items-start">
                    <div className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] rounded-full w-14 h-14 flex items-center justify-center text-black font-bold text-xl mr-6 transition-transform group-hover:scale-110">
                      4
                    </div>
                    <div>
                      <h3 className="text-white text-2xl font-medium mb-3">Secure Your Future</h3>
                      <p className="text-[#adbdcc] text-lg">Get visa support, scholarship information, and everything you need to start your academic journey.</p>
                    </div>
                  </div>
                  
                  {/* Illustrative graphic */}
                  <div className="mt-6 ml-14">
                    <svg className="w-16 h-16 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M12 6V12L16 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section with Interactive Grid */}
        <section className="py-24 bg-[#061220] relative overflow-hidden">
          {/* Background elements */}
          <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#00d4ff] rounded-full mix-blend-multiply filter blur-3xl opacity-10"></div>
            <div className="absolute bottom-1/3 right-1/3 w-80 h-80 bg-[#7f5eff] rounded-full mix-blend-multiply filter blur-3xl opacity-10"></div>
          </div>
          
          <div className="container mx-auto px-6 relative z-10">
            {/* Section Header */}
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">Powerful <span className="gradient-text">Features</span> for Your Success</h2>
              <p className="text-lg text-[#adbdcc] max-w-2xl mx-auto">
                Everything you need to connect, apply, and succeed in your higher education journey with unprecedented efficiency.
              </p>
            </div>
            
            {/* Features Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 max-w-7xl mx-auto">
              {/* Feature 1: University Finder */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 210}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1"></path>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">University Finder</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Find your perfect university match with AI-powered recommendations based on your academic profile, preferences, and career goals.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Universities</div>
                    <div className="text-white font-semibold">10,000+</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Countries</div>
                    <div className="text-white font-semibold">150+</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 2: SOP Builder */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 260}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 20h9"></path>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">SOP Builder</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Create, edit, and enhance your Statement of Purpose with AI assistance, templates, examples, and enhancement tools.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Templates</div>
                    <div className="text-white font-semibold">25+</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Success Rate</div>
                    <div className="text-white font-semibold">95%</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 3: Resume Builder */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 180}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14,2 14,8 20,8"></polyline>
                      <line x1="16" y1="13" x2="8" y2="13"></line>
                      <line x1="16" y1="17" x2="8" y2="17"></line>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">Resume Builder</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Create professional resumes tailored for academic applications with AI-powered enhancement suggestions to strengthen your profile.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Templates</div>
                    <div className="text-white font-semibold">30+</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">ATS Optimized</div>
                    <div className="text-white font-semibold">Yes</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 4: Application Manager */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 40}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">Application Manager</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Track and manage all your applications in one place with monitoring for deadlines, status updates, and required documents.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Reminders</div>
                    <div className="text-white font-semibold">Automated</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Dashboard</div>
                    <div className="text-white font-semibold">Real-time</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 5: Scholarship Finder */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 260}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#7f5eff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#7f5eff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">Scholarship Finder</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Discover scholarships tailored to your academic profile and background with filters for amount, eligibility, and application deadlines.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Scholarships</div>
                    <div className="text-white font-semibold">50,000+</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Matching</div>
                    <div className="text-white font-semibold">AI-Powered</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 6: Education Counselor */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 210}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z"></path>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">Education Counselor</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Get personalized guidance from experienced counselors who help you navigate the complex application process and make informed decisions.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Counselors</div>
                    <div className="text-white font-semibold">Expert</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Sessions</div>
                    <div className="text-white font-semibold">1-on-1</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 7: University GPT */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 180}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">University GPT</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Get instant answers to your questions about universities, programs, admissions requirements, and application processes.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">AI Model</div>
                    <div className="text-white font-semibold">Advanced</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Database</div>
                    <div className="text-white font-semibold">Up-to-date</div>
                  </div>
                </div>
              </div>
              
              {/* Feature 8: Visa Support */}
              <div className="flow-card bg-[#0c2e4e] p-6 rounded-xl border border-[#1a3045]" style={{['--hue' as any]: 40}}>
                <div className="flex items-center mb-4">
                  <div className="bg-[#00d4ff]/10 rounded-lg w-12 h-12 flex items-center justify-center mr-4">
                    <svg className="h-6 w-6 text-[#00d4ff]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="4" width="18" height="16" rx="2"></rect>
                      <line x1="8" y1="2" x2="8" y2="4"></line>
                      <line x1="16" y1="2" x2="16" y2="4"></line>
                      <line x1="3" y1="10" x2="21" y2="10"></line>
                    </svg>
                  </div>
                  <h3 className="text-xl font-medium text-white">Visa Support</h3>
                </div>
                <div className="border-t border-[#1a3045] my-4"></div>
                <p className="text-[#adbdcc] mb-4">
                  Navigate the visa application process with step-by-step guidance, document checklists, and interview preparation resources.
                </p>
                <div className="flex justify-between">
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Countries</div>
                    <div className="text-white font-semibold">All Major</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#adbdcc]/70">Guidance</div>
                    <div className="text-white font-semibold">Comprehensive</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Testimonials Section */}
        <section className="py-20 relative overflow-hidden">
          {/* Background Elements */}
          <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#00d4ff] rounded-full mix-blend-multiply filter blur-3xl opacity-10"></div>
            <div className="absolute bottom-1/3 right-1/3 w-80 h-80 bg-[#7f5eff] rounded-full mix-blend-multiply filter blur-3xl opacity-10"></div>
          </div>

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            {/* Section Header */}
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">What Our Students Say</h2>
              <p className="text-lg text-[#adbdcc] max-w-2xl mx-auto">
                Discover how AI Student Success has helped students around the world achieve their academic dreams.
              </p>
            </div>

            {/* Featured Testimonial */}
            <div className="glass-card rounded-2xl p-8 md:p-10 mb-16 relative overflow-hidden">
              <div className="absolute -top-6 -left-6 text-8xl font-bold quote-mark opacity-20">"</div>
              <div className="relative z-10">
                <p className="text-xl md:text-2xl text-white/90 italic mb-8 max-w-4xl">
                  AI Student Success completely transformed my application journey. I was overwhelmed by the process until I found this platform. The University Finder helped me discover programs I hadn&apos;t even considered, and the SOP Builder helped me craft a compelling personal statement that got me into my dream school!
                </p>
                <div className="flex items-center">
                  <div className="w-14 h-14 rounded-full mr-4 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold text-xl">S</div>
                  <div>
                    <h4 className="font-semibold text-lg text-white">Sarah Johnson</h4>
                    <p className="text-[#adbdcc]">Admitted to Stanford University</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Testimonial Carousel for Desktop / Grid for Mobile */}
            <div className="hidden md:block relative">
              {/* Desktop Carousel */}
              <div className="carousel flex overflow-x-auto pb-6 space-x-6 scrollbar-hide">
                {/* Testimonial 1 */}
                <div className="carousel-item glass-card rounded-xl p-6 min-w-[350px] max-w-[350px] transition-all duration-300 hover:shadow-xl hover:shadow-[#00d4ff]/10">
                  <div className="text-4xl font-bold quote-mark mb-4">"</div>
                  <p className="text-white/80 mb-6">The application manager feature saved me so much time. I could track all my applications in one place and never missed a deadline.</p>
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">M</div>
                    <div>
                      <h4 className="font-medium text-white">Michael Torres</h4>
                      <p className="text-[#adbdcc]/70 text-sm">MIT Graduate Student</p>
                    </div>
                  </div>
                </div>

                {/* Testimonial 2 */}
                <div className="carousel-item glass-card rounded-xl p-6 min-w-[350px] max-w-[350px] transition-all duration-300 hover:shadow-xl hover:shadow-[#00d4ff]/10">
                  <div className="text-4xl font-bold quote-mark mb-4">"</div>
                  <p className="text-white/80 mb-6">As an international student, the visa support feature was invaluable. It guided me through every step of the process with clear instructions.</p>
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">R</div>
                    <div>
                      <h4 className="font-medium text-white">Rebecca Chen</h4>
                      <p className="text-[#adbdcc]/70 text-sm">International Student</p>
                    </div>
                  </div>
                </div>

                {/* Testimonial 3 */}
                <div className="carousel-item glass-card rounded-xl p-6 min-w-[350px] max-w-[350px] transition-all duration-300 hover:shadow-xl hover:shadow-[#00d4ff]/10">
                  <div className="text-4xl font-bold quote-mark mb-4">"</div>
                  <p className="text-white/80 mb-6">The scholarship finder helped me secure funding I didn&apos;t even know I was eligible for. I&apos;m now studying debt-free thanks to AI Student Success.</p>
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">D</div>
                    <div>
                      <h4 className="font-medium text-white">David Washington</h4>
                      <p className="text-[#adbdcc]/70 text-sm">Harvard University</p>
                    </div>
                  </div>
                </div>

                {/* Testimonial 4 */}
                <div className="carousel-item glass-card rounded-xl p-6 min-w-[350px] max-w-[350px] transition-all duration-300 hover:shadow-xl hover:shadow-[#00d4ff]/10">
                  <div className="text-4xl font-bold quote-mark mb-4">"</div>
                  <p className="text-white/80 mb-6">The education counselors provided personalized guidance that made all the difference. They helped me choose the right program for my career goals.</p>
                  <div className="flex items-center">
                    <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">A</div>
                    <div>
                      <h4 className="font-medium text-white">Alicia Patel</h4>
                      <p className="text-[#adbdcc]/70 text-sm">Columbia University</p>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Carousel Controls */}
              <div className="flex justify-center mt-6 space-x-2">
                <button className="w-3 h-3 rounded-full bg-[#00d4ff]"></button>
                <button className="w-3 h-3 rounded-full bg-[#1a3045] hover:bg-[#00d4ff]/50"></button>
                <button className="w-3 h-3 rounded-full bg-[#1a3045] hover:bg-[#00d4ff]/50"></button>
                <button className="w-3 h-3 rounded-full bg-[#1a3045] hover:bg-[#00d4ff]/50"></button>
              </div>
            </div>
            
            {/* Mobile Testimonial Grid */}
            <div className="md:hidden grid grid-cols-1 gap-6">
              {/* Testimonial 1 */}
              <div className="glass-card rounded-xl p-6 transition-all duration-300">
                <div className="text-4xl font-bold quote-mark mb-4">"</div>
                <p className="text-white/80 mb-6">The application manager feature saved me so much time. I could track all my applications in one place and never missed a deadline.</p>
                <div className="flex items-center">
                  <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">M</div>
                  <div>
                    <h4 className="font-medium text-white">Michael Torres</h4>
                    <p className="text-[#adbdcc]/70 text-sm">MIT Graduate Student</p>
                  </div>
                </div>
              </div>

              {/* Testimonial 2 */}
              <div className="glass-card rounded-xl p-6 transition-all duration-300">
                <div className="text-4xl font-bold quote-mark mb-4">"</div>
                <p className="text-white/80 mb-6">As an international student, the visa support feature was invaluable. It guided me through every step of the process with clear instructions.</p>
                <div className="flex items-center">
                  <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">R</div>
                  <div>
                    <h4 className="font-medium text-white">Rebecca Chen</h4>
                    <p className="text-[#adbdcc]/70 text-sm">International Student</p>
                  </div>
                </div>
              </div>

              {/* Testimonial 3 */}
              <div className="glass-card rounded-xl p-6 transition-all duration-300">
                <div className="text-4xl font-bold quote-mark mb-4">"</div>
                <p className="text-white/80 mb-6">The scholarship finder helped me secure funding I didn&apos;t even know I was eligible for. I&apos;m now studying debt-free thanks to AI Student Success.</p>
                <div className="flex items-center">
                  <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] flex items-center justify-center text-white font-bold">D</div>
                  <div>
                    <h4 className="font-medium text-white">David Washington</h4>
                    <p className="text-[#adbdcc]/70 text-sm">Harvard University</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Universities Banner */}
            <div className="mt-20 text-center">
              <p className="text-[#adbdcc]/50 mb-8">Helping students get admitted to top universities worldwide</p>
              <div className="flex flex-wrap justify-center items-center gap-8 md:gap-16">
                <div className="h-8 text-[#adbdcc]/50 font-bold">HARVARD</div>
                <div className="h-8 text-[#adbdcc]/50 font-bold">STANFORD</div>
                <div className="h-8 text-[#adbdcc]/50 font-bold">MIT</div>
                <div className="h-8 text-[#adbdcc]/50 font-bold">OXFORD</div>
                <div className="h-8 text-[#adbdcc]/50 font-bold">CAMBRIDGE</div>
              </div>
            </div>
          </div>
        </section>

        {/* Primary CTA Section */}
        <section className="py-16 bg-gradient-to-r from-[#0c2e4e] to-[#061220] relative overflow-hidden">
          {/* Background glow effects */}
          <div className="absolute top-1/2 left-1/4 w-96 h-96 bg-[#00d4ff]/20 rounded-full filter blur-[100px] -z-10"></div>
          <div className="absolute top-1/2 right-1/4 w-96 h-96 bg-[#7f5eff]/20 rounded-full filter blur-[100px] -z-10"></div>
          
          <div className="container mx-auto px-6 text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-6 text-white">Ready to Begin Your <span className="gradient-text">Academic Journey</span>?</h2>
            <p className="text-xl mb-10 max-w-2xl mx-auto text-[#adbdcc]">
              Join thousands of students who have successfully navigated their path to higher education with our AI-powered platform.
            </p>
            
            <div className="sparkle-button inline-block">
              <button className="relative bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-4 px-10 rounded-lg overflow-hidden group text-lg">
                <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                <span className="backdrop"></span>
                <svg className="sparkle absolute top-3 right-3" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="16" height="16">
                  <path d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z" fill="black" stroke="black" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className="relative z-10">Start Your Journey</span>
              </button>
            </div>
            
            <p className="text-[#adbdcc]/70 mt-6">
              No credit card required. Start with our free plan today.
            </p>
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
                  <li><Link href="/" className="text-[#00d4ff]">Home</Link></li>
                  <li><Link href="/features" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Features</Link></li>
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
    </>
  );
};

export default HomePage;