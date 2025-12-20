'use client';

import React, { useState } from 'react';
import Link from 'next/link';

const SignInPage: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    firstName: '',
    lastName: '',
    rememberMe: false,
    termsAgreement: false
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (activeTab === 'login') {
      // Handle login
      console.log('Login attempt:', { email: formData.email, password: formData.password });
    } else {
      // Handle registration
      console.log('Registration attempt:', formData);
    }
  };

  const handleSocialAuth = (provider: string) => {
    console.log(`${provider} auth clicked`);
  };

  return (
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

      {/* Main Content */}
      <main className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative pt-20">
        {/* Background glow */}
        <div className="absolute top-20 left-1/4 w-96 h-96 bg-[#00d4ff]/10 rounded-full filter blur-[100px] -z-10"></div>
        <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-[#7f5eff]/10 rounded-full filter blur-[100px] -z-10"></div>
        
        <div className="max-w-md w-full animate-fadeInUp">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-white">
              {activeTab === 'login' ? 'Welcome Back' : 'Create Account'}
            </h2>
            <p className="mt-2 text-[#adbdcc]">
              {activeTab === 'login' 
                ? 'Sign in to access your AI Student Success account'
                : 'Join thousands of students on their path to academic success'
              }
            </p>
          </div>
          
          <div className="bg-[#0a1f35] rounded-xl p-8 border border-[#1a3045] shadow-xl">
            {/* Auth Tabs */}
            <div className="flex mb-8 border-b border-[#1a3045]">
              <button
                className={`py-3 px-6 font-medium ${
                  activeTab === 'login' 
                    ? 'text-white border-b-2 border-[#00d4ff]' 
                    : 'text-[#adbdcc] hover:text-white'
                }`}
                onClick={() => setActiveTab('login')}
              >
                Sign In
              </button>
              <button
                className={`py-3 px-6 font-medium ${
                  activeTab === 'register' 
                    ? 'text-white border-b-2 border-[#00d4ff]' 
                    : 'text-[#adbdcc] hover:text-white'
                }`}
                onClick={() => setActiveTab('register')}
              >
                Register
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              {activeTab === 'login' ? (
                // Login Form
                <>
                  {/* Email Input */}
                  <div className="mb-6">
                    <label className="block text-[#adbdcc] mb-2">Email</label>
                    <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                      <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <input
                        type="email"
                        name="email"
                        value={formData.email}
                        onChange={handleInputChange}
                        className="w-full bg-transparent py-3 px-4 pl-10 text-white focus:outline-none"
                        placeholder="your.email@example.com"
                        required
                      />
                    </div>
                  </div>
                  
                  {/* Password Input */}
                  <div className="mb-6">
                    <label className="block text-[#adbdcc] mb-2">Password</label>
                    <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                      <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      </div>
                      <input
                        type={showPassword ? "text" : "password"}
                        name="password"
                        value={formData.password}
                        onChange={handleInputChange}
                        className="w-full bg-transparent py-3 px-4 pl-10 pr-10 text-white focus:outline-none"
                        placeholder="••••••••"
                        required
                      />
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc] hover:text-white"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  {/* Remember Me & Forgot Password */}
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="remember"
                        name="rememberMe"
                        checked={formData.rememberMe}
                        onChange={handleInputChange}
                        className="w-4 h-4 bg-[#071527] border border-[#1a3045] rounded focus:ring-[#00d4ff]"
                      />
                      <label htmlFor="remember" className="ml-2 text-sm text-[#adbdcc]">
                        Remember me
                      </label>
                    </div>
                    <Link href="#" className="text-sm text-[#00d4ff] hover:underline">
                      Forgot password?
                    </Link>
                  </div>
                </>
              ) : (
                // Register Form
                <>
                  {/* First Name & Last Name */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* First Name */}
                    <div className="mb-6">
                      <label className="block text-[#adbdcc] mb-2">First Name</label>
                      <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                        <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                          </svg>
                        </div>
                        <input
                          type="text"
                          name="firstName"
                          value={formData.firstName}
                          onChange={handleInputChange}
                          className="w-full bg-transparent py-3 px-4 pl-10 text-white focus:outline-none"
                          placeholder="John"
                          required
                        />
                      </div>
                    </div>
                    
                    {/* Last Name */}
                    <div className="mb-6">
                      <label className="block text-[#adbdcc] mb-2">Last Name</label>
                      <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                        <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                          </svg>
                        </div>
                        <input
                          type="text"
                          name="lastName"
                          value={formData.lastName}
                          onChange={handleInputChange}
                          className="w-full bg-transparent py-3 px-4 pl-10 text-white focus:outline-none"
                          placeholder="Doe"
                          required
                        />
                      </div>
                    </div>
                  </div>
                  
                  {/* Email Input */}
                  <div className="mb-6">
                    <label className="block text-[#adbdcc] mb-2">Email</label>
                    <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                      <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <input
                        type="email"
                        name="email"
                        value={formData.email}
                        onChange={handleInputChange}
                        className="w-full bg-transparent py-3 px-4 pl-10 text-white focus:outline-none"
                        placeholder="your.email@example.com"
                        required
                      />
                    </div>
                  </div>
                  
                  {/* Password Input */}
                  <div className="mb-6">
                    <label className="block text-[#adbdcc] mb-2">Password</label>
                    <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                      <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      </div>
                      <input
                        type={showPassword ? "text" : "password"}
                        name="password"
                        value={formData.password}
                        onChange={handleInputChange}
                        className="w-full bg-transparent py-3 px-4 pl-10 pr-10 text-white focus:outline-none"
                        placeholder="••••••••"
                        required
                      />
                      <button
                        type="button"
                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc] hover:text-white"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  {/* Confirm Password Input */}
                  <div className="mb-6">
                    <label className="block text-[#adbdcc] mb-2">Confirm Password</label>
                    <div className="relative border border-[#1a3045] rounded-lg bg-[#071527] transition-colors">
                      <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#adbdcc]">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      </div>
                      <input
                        type="password"
                        name="confirmPassword"
                        value={formData.confirmPassword}
                        onChange={handleInputChange}
                        className="w-full bg-transparent py-3 px-4 pl-10 text-white focus:outline-none"
                        placeholder="••••••••"
                        required
                      />
                    </div>
                  </div>
                  
                  {/* Terms Agreement */}
                  <div className="flex items-center mb-6">
                    <input
                      type="checkbox"
                      id="terms"
                      name="termsAgreement"
                      checked={formData.termsAgreement}
                      onChange={handleInputChange}
                      className="w-4 h-4 bg-[#071527] border border-[#1a3045] rounded focus:ring-[#00d4ff]"
                      required
                    />
                    <label htmlFor="terms" className="ml-2 text-sm text-[#adbdcc]">
                      I agree to the <Link href="#" className="text-[#00d4ff] hover:underline">Terms of Service</Link> and <Link href="#" className="text-[#00d4ff] hover:underline">Privacy Policy</Link>
                    </label>
                  </div>
                </>
              )}
              
              {/* Submit Button */}
              <div className="sparkle-button mb-6">
                <button
                  type="submit"
                  className="relative w-full bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-6 rounded-lg overflow-hidden group"
                >
                  <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                  <span className="backdrop"></span>
                  <svg
                    className="sparkle"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M14.187 8.096L15 5.25L15.813 8.096C16.0231 8.83114 16.4171 9.50062 16.9577 10.0413C17.4984 10.5819 18.1679 10.9759 18.903 11.186L21.75 12L18.904 12.813C18.1689 13.0231 17.4994 13.4171 16.9587 13.9577C16.4181 14.4984 16.0241 15.1679 15.814 15.903L15 18.75L14.187 15.904C13.9769 15.1689 13.5829 14.4994 13.0423 13.9587C12.5016 13.4181 11.8321 13.0241 11.097 12.814L8.25 12L11.096 11.187C11.8311 10.9769 12.5006 10.5829 13.0413 10.0423C13.5819 9.50162 13.9759 8.83214 14.186 8.097L14.187 8.096Z"
                      fill="black"
                      stroke="black"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span className="relative z-10">{activeTab === 'login' ? 'Sign In' : 'Create Account'}</span>
                </button>
              </div>
              
              {/* Or Continue With */}
              <div className="relative flex items-center justify-center mb-6">
                <div className="flex-grow h-px bg-[#1a3045]"></div>
                <span className="flex-shrink px-4 text-[#adbdcc]">
                  or {activeTab === 'login' ? 'continue' : 'register'} with
                </span>
                <div className="flex-grow h-px bg-[#1a3045]"></div>
              </div>
              
              {/* Social Login Buttons */}
              <div className="space-y-3">
                {/* Google */}
                <button 
                  type="button"
                  onClick={() => handleSocialAuth('Google')}
                  className="w-full flex items-center justify-center py-3 px-4 rounded-lg bg-white/10 hover:bg-white/20 text-white font-medium mb-3 hover:opacity-90 transition-opacity"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    <path d="M1 1h22v22H1z" fill="none"/>
                  </svg>
                  <span className="ml-2">Google</span>
                </button>
                
                {/* Facebook */}
                <button 
                  type="button"
                  onClick={() => handleSocialAuth('Facebook')}
                  className="w-full flex items-center justify-center py-3 px-4 rounded-lg bg-[#1877f2] hover:bg-[#166fe5] text-white font-medium mb-3 hover:opacity-90 transition-opacity"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M13.397 20.997v-8.196h2.765l.411-3.209h-3.176V7.548c0-.926.258-1.56 1.587-1.56h1.684V3.127A22.336 22.336 0 0014.201 3c-2.444 0-4.122 1.492-4.122 4.231v2.355H7.332v3.209h2.753v8.202h3.312z"/>
                  </svg>
                  <span className="ml-2">Facebook</span>
                </button>
                
                {activeTab === 'login' && (
                  // GitHub (only for login)
                  <button 
                    type="button"
                    onClick={() => handleSocialAuth('GitHub')}
                    className="w-full flex items-center justify-center py-3 px-4 rounded-lg bg-[#24292e] hover:bg-[#2f363d] text-white font-medium mb-3 hover:opacity-90 transition-opacity"
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                    </svg>
                    <span className="ml-2">GitHub</span>
                  </button>
                )}
              </div>
            </form>
          </div>
          
          {/* Switch between login and register */}
          <div className="text-center mt-6">
            <p className="text-[#adbdcc]">
              <span>
                {activeTab === 'login' ? "Don't have an account?" : "Already have an account?"}
              </span>
              <button 
                className="text-[#00d4ff] hover:underline ml-1"
                onClick={() => setActiveTab(activeTab === 'login' ? 'register' : 'login')}
              >
                {activeTab === 'login' ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </main>

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
                <li><Link href="/" className="text-[#adbdcc] hover:text-[#00d4ff] transition-colors">Home</Link></li>
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
  );
};

export default SignInPage;