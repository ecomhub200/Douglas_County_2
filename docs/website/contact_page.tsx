'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Script from 'next/script';

declare global {
  interface Window {
    VANTA: any;
  }
}

const ContactPage: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [vantaEffect, setVantaEffect] = useState<any>(null);
  const [activeFAQ, setActiveFAQ] = useState<number | null>(null);

  const toggleFAQ = (index: number) => {
    setActiveFAQ(activeFAQ === index ? null : index);
  };

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
      
      <div className="bg-[#0a1a2e] text-[#adbdcc] min-h-screen font-['Inter',sans-serif]">
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
          
          .gradient-text {
            background: linear-gradient(to right, #00d4ff, #7f5eff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }
          
          .feature-card {
            transition: transform 0.3s ease, box-shadow 0.3s ease;
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
          
          .glass-card {
            backdrop-filter: blur(12px);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
          }
          
          .social-link {
            transition: transform 0.3s ease;
          }
          
          .social-link:hover {
            transform: scale(1.1);
          }
        `}</style>

        {/* Navigation Bar - Matching About Page Exactly */}
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
                <Link href="/pricing" className="text-[#adbdcc] hover:text-white transition-colors">Pricing</Link>
                <Link href="/resources" className="text-[#adbdcc] hover:text-white transition-colors">Resources</Link>
                <Link href="/about" className="text-[#adbdcc] hover:text-white transition-colors">About Us</Link>
                <Link href="/contact" className="text-white font-medium transition-colors">Contact Us</Link>
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
                <Link href="/features" className="text-[#adbdcc] hover:text-white py-2">Features</Link>
                <Link href="/pricing" className="text-[#adbdcc] hover:text-white py-2">Pricing</Link>
                <Link href="/resources" className="text-[#adbdcc] hover:text-white py-2">Resources</Link>
                <Link href="/about" className="text-[#adbdcc] hover:text-white py-2">About Us</Link>
                <Link href="/contact" className="text-white font-medium py-2">Contact Us</Link>
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
        <div className="relative min-h-[600px] overflow-hidden pt-20">
          {/* Vanta.js background */}
          <div id="vanta-bg" className="absolute inset-0 z-0"></div>
          
          {/* Hero content */}
          <div className="relative z-10 flex flex-col items-center justify-center px-6 pt-16 pb-24 text-center">
            <div className="absolute top-1/2 left-1/2 w-[600px] h-[600px] -translate-x-1/2 -translate-y-1/2 bg-[#7f5eff] opacity-10 blur-[100px] rounded-full pointer-events-none"></div>
            
            <span className="px-3 py-1 text-xs font-medium text-[#00d4ff] bg-[#00d4ff] bg-opacity-10 rounded-full mb-8 animate-fadeInUp">We&apos;re Here to Help</span>
            
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-4xl leading-tight text-white animate-fadeInUp animate-delay-200">
              Get in <span className="gradient-text">Touch</span>
            </h1>
            
            <p className="mt-6 text-lg md:text-xl text-[#adbdcc] max-w-2xl animate-fadeInUp animate-delay-400">
              Have questions or need assistance? We&apos;re here to help you succeed in your academic journey.
            </p>
          </div>
        </div>

        {/* Main Content */}
        <main>
          {/* Contact Section */}
          <section className="py-16">
            <div className="container mx-auto px-6">
              <div className="flex flex-col lg:flex-row gap-8">
                {/* Left Column - Contact Info */}
                <div className="lg:w-1/2">
                  <div className="bg-[#0c2e4e] rounded-xl p-8 shadow-xl mb-8 feature-card">
                    <h3 className="text-2xl font-bold text-white mb-6">Contact Information</h3>
                    
                    <div className="space-y-6">
                      {/* Email */}
                      <div className="flex items-start">
                        <div className="bg-[#0a1a2e] p-3 rounded-lg mr-4">
                          <svg className="w-6 h-6 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                          </svg>
                        </div>
                        <div>
                          <h4 className="text-white font-medium mb-1">Email</h4>
                          <p className="text-[#adbdcc]">support@aistudentsuccess.com</p>
                        </div>
                      </div>
                      
                      {/* Phone */}
                      <div className="flex items-start">
                        <div className="bg-[#0a1a2e] p-3 rounded-lg mr-4">
                          <svg className="w-6 h-6 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                          </svg>
                        </div>
                        <div>
                          <h4 className="text-white font-medium mb-1">Phone</h4>
                          <p className="text-[#adbdcc]">+1 (555) 123-4567</p>
                        </div>
                      </div>
                      
                      {/* Office */}
                      <div className="flex items-start">
                        <div className="bg-[#0a1a2e] p-3 rounded-lg mr-4">
                          <svg className="w-6 h-6 text-[#00d4ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                          </svg>
                        </div>
                        <div>
                          <h4 className="text-white font-medium mb-1">Office</h4>
                          <p className="text-[#adbdcc]">123 Education Lane, Suite 500, San Francisco, CA 94107</p>
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-8">
                      <h4 className="text-white font-medium mb-4">Connect with us</h4>
                      <div className="flex space-x-4">
                        {/* LinkedIn */}
                        <a 
                          href="#" 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="social-link flex items-center justify-center bg-[#0077b5] rounded-full p-3 transition-transform"
                        >
                          <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                          </svg>
                        </a>
                        
                        {/* Twitter */}
                        <a 
                          href="#" 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="social-link flex items-center justify-center bg-[#1da1f2] rounded-full p-3 transition-transform"
                        >
                          <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"/>
                          </svg>
                        </a>
                        
                        {/* Facebook */}
                        <a 
                          href="#" 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="social-link flex items-center justify-center bg-[#1877f2] rounded-full p-3 transition-transform"
                        >
                          <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M13.397 20.997v-8.196h2.765l.411-3.209h-3.176V7.548c0-.926.258-1.56 1.587-1.56h1.684V3.127A22.336 22.336 0 0014.201 3c-2.444 0-4.122 1.492-4.122 4.231v2.355H7.332v3.209h2.753v8.202h3.312z"/>
                          </svg>
                        </a>
                        
                        {/* Instagram */}
                        <a 
                          href="#" 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="social-link flex items-center justify-center bg-gradient-to-br from-[#f9ce34] via-[#ee2a7b] to-[#6228d7] rounded-full p-3 transition-transform"
                        >
                          <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                          </svg>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Right Column - Contact Form */}
                <div className="lg:w-1/2">
                  <div className="bg-[#0c2e4e] rounded-xl p-8 shadow-xl feature-card">
                    <h3 className="text-2xl font-bold text-white mb-6">Send Us a Message</h3>
                    <form>
                      <div className="space-y-6">
                        {/* Name */}
                        <div>
                          <label className="block text-[#adbdcc] mb-2">Name</label>
                          <input 
                            type="text" 
                            className="w-full bg-[#0a1a2e] border border-[#1a3045] rounded-lg py-3 px-4 text-white focus:outline-none focus:border-[#00d4ff] transition-colors"
                            placeholder="Your name"
                          />
                        </div>
                        
                        {/* Email */}
                        <div>
                          <label className="block text-[#adbdcc] mb-2">Email</label>
                          <input 
                            type="email" 
                            className="w-full bg-[#0a1a2e] border border-[#1a3045] rounded-lg py-3 px-4 text-white focus:outline-none focus:border-[#00d4ff] transition-colors"
                            placeholder="your.email@example.com"
                          />
                        </div>
                        
                        {/* Message */}
                        <div>
                          <label className="block text-[#adbdcc] mb-2">Message</label>
                          <textarea 
                            className="w-full bg-[#0a1a2e] border border-[#1a3045] rounded-lg py-3 px-4 text-white focus:outline-none focus:border-[#00d4ff] transition-colors min-h-[150px]"
                            placeholder="How can we help you?"
                          ></textarea>
                        </div>
                        
                        {/* Submit Button */}
                        <div className="sparkle-button w-full">
                          <button 
                            type="submit"
                            className="relative w-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-6 rounded-lg overflow-hidden group"
                          >
                            <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                            <span className="backdrop"></span>
                            <svg
                              className="sparkle absolute top-3 right-3"
                              viewBox="0 0 24 24"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                            >
                              <path
                                d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z"
                                fill="black"
                                stroke="black"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                            <span className="relative z-10">Send Message</span>
                          </button>
                        </div>
                      </div>
                    </form>
                  </div>
                  
                  {/* FAQ Section */}
                  <div className="mt-8 bg-[#0c2e4e] rounded-xl p-8 shadow-xl feature-card">
                    <h3 className="text-2xl font-bold text-white mb-6">Frequently Asked Questions</h3>
                    
                    <div className="space-y-2">
                      {/* FAQ Items */}
                      {[
                        {
                          question: "How quickly will I receive a response?",
                          answer: "We typically respond to all inquiries within 24-48 business hours. For urgent matters, please indicate in your message subject."
                        },
                        {
                          question: "Do you offer support in multiple languages?",
                          answer: "Yes, our support team can assist in English, Spanish, Mandarin, and Hindi. Please specify your preferred language in your message."
                        },
                        {
                          question: "Can I schedule a demo of the platform?",
                          answer: "Absolutely! You can request a personalized demo through this contact form or by emailing demo@aistudentsuccess.com directly."
                        },
                        {
                          question: "Where can I find tutorials for using the platform?",
                          answer: "We have comprehensive tutorials available in our Resources section. For specific guidance, our support team is happy to help."
                        }
                      ].map((faq, index) => (
                        <div key={index} className="border-b border-[#1a3045] last:border-b-0">
                          <button 
                            className="w-full text-left py-4 flex justify-between items-center"
                            onClick={() => toggleFAQ(index)}
                          >
                            <span className="text-white font-medium">{faq.question}</span>
                            <svg 
                              className={`w-5 h-5 text-[#adbdcc] transition-transform duration-300 ${activeFAQ === index ? 'transform rotate-180' : ''}`}
                              fill="none" 
                              stroke="currentColor" 
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                            </svg>
                          </button>
                          <div className={`pb-4 text-[#adbdcc] ${activeFAQ === index ? '' : 'hidden'}`}>
                            {faq.answer}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* CTA Section */}
          <section className="py-16 bg-[#061220] relative overflow-hidden">
            {/* Background glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-4xl h-64 bg-gradient-to-b from-[#00d4ff]/20 to-transparent blur-3xl"></div>
            
            <div className="container mx-auto px-6 relative z-10">
              <div className="max-w-4xl mx-auto text-center">
                <h2 className="text-3xl font-bold mb-6 text-white">Ready to Start Your <span className="gradient-text">Academic Journey?</span></h2>
                <p className="text-xl mb-10 max-w-2xl mx-auto">
                  Join thousands of students who have successfully navigated their path to top universities worldwide.
                </p>
                <div className="sparkle-button inline-block">
                  <button className="relative bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-8 rounded-lg overflow-hidden group">
                    <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                    <span className="backdrop"></span>
                    <svg
                      className="sparkle absolute top-3 right-3"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                    >
                      <path
                        d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z"
                        fill="black"
                        stroke="black"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <span className="relative z-10">Get Started Free</span>
                  </button>
                </div>
              </div>
            </div>
          </section>
        </main>

        {/* Footer - Matching About Page */}
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
                  <li><Link href="/" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Home</Link></li>
                  <li><Link href="/features" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Features</Link></li>
                  <li><Link href="/pricing" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Pricing</Link></li>
                  <li><Link href="/resources" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Resources</Link></li>
                  <li><Link href="/about" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">About Us</Link></li>
                  <li><Link href="/contact" className="text-[#00d4ff]">Contact Us</Link></li>
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

export default ContactPage;