'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';

const ResourcesPage: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');

  const filters = ['All', 'SOP', 'Resume', 'Application', 'Visa', 'University', 'Scholarship'];

  const resources = [
    {
      id: 1,
      title: 'SOP Writing Guide',
      description: 'Learn how to craft a compelling Statement of Purpose that stands out to admissions committees.',
      category: 'SOP',
      image: 'https://images.unsplash.com/photo-1455390582262-044cdead277a?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 2,
      title: 'Resume Templates for Graduate School',
      description: 'Professional resume templates designed specifically for graduate school applications.',
      category: 'Resume',
      image: 'https://images.unsplash.com/photo-1586281380349-632531db7ed4?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 3,
      title: 'Application Timeline Planner',
      description: 'A comprehensive timeline to help you plan your application process from start to finish.',
      category: 'Application',
      image: 'https://images.unsplash.com/photo-1506784365847-bbad939e9335?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 4,
      title: 'Visa Interview Preparation',
      description: 'Tips and common questions to help you prepare for your student visa interview.',
      category: 'Visa',
      image: 'https://images.unsplash.com/photo-1551836022-deb4988cc6c0?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 5,
      title: 'Research Statement Guide',
      description: 'How to write a compelling research statement for PhD applications.',
      category: 'SOP',
      image: 'https://images.unsplash.com/photo-1532619675605-1ede6c2ed2b0?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 6,
      title: 'University Comparison Worksheet',
      description: 'A template to help you compare different universities and make informed decisions.',
      category: 'University',
      image: 'https://images.unsplash.com/photo-1498243691581-b145c3f54a5a?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 7,
      title: 'Scholarship Application Checklist',
      description: 'A comprehensive checklist to ensure your scholarship applications are complete.',
      category: 'Scholarship',
      image: 'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 8,
      title: 'Academic CV Template',
      description: 'Professional CV template designed for academic and research positions.',
      category: 'Resume',
      image: 'https://images.unsplash.com/photo-1586282391129-76a6df230234?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    },
    {
      id: 9,
      title: 'Faculty Email Templates',
      description: 'Templates for reaching out to potential faculty advisors and research supervisors.',
      category: 'Application',
      image: 'https://images.unsplash.com/photo-1557200134-90327ee9fafa?ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=80'
    }
  ];

  const filteredResources = resources.filter(resource => {
    const matchesSearch = resource.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         resource.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = activeFilter === 'All' || resource.category === activeFilter;
    return matchesSearch && matchesFilter;
  });

  useEffect(() => {
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-fadeInUp');
        }
      });
    }, observerOptions);

    const animatedElements = document.querySelectorAll('.animate-delay-200, .animate-delay-400, .animate-delay-600');
    animatedElements.forEach(el => observer.observe(el));

    return () => {
      animatedElements.forEach(el => observer.unobserve(el));
    };
  }, []);

  const getCategoryColor = (category: string) => {
    const colors: { [key: string]: string } = {
      'SOP': '#00d4ff',
      'Resume': '#7f5eff',
      'Application': '#ff5eff',
      'Visa': '#00d4ff',
      'University': '#00d4ff',
      'Scholarship': '#7f5eff'
    };
    return colors[category] || '#00d4ff';
  };

  return (
    <div className="bg-[#0a1a2e] text-[#adbdcc] min-h-screen">
      <style jsx global>{`
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
        
        .animate-delay-600 {
          animation-delay: 0.6s;
          opacity: 0;
        }
        
        .resource-card {
          transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .resource-card:hover {
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
      `}</style>

      {/* Header Section */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#061220]/80 backdrop-blur-md border-b border-[#1a3045]">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="text-white text-2xl font-bold">
              <span className="gradient-text">AI</span> Student Success
            </Link>
            
            <nav className="hidden md:flex items-center space-x-8">
              <Link href="/" className="text-[#adbdcc] hover:text-white transition-colors">Home</Link>
              <Link href="/features" className="text-[#adbdcc] hover:text-white transition-colors">Features</Link>
              <Link href="/pricing" className="text-[#adbdcc] hover:text-white transition-colors">Pricing</Link>
              <Link href="/resources" className="text-white font-medium transition-colors">Resources</Link>
              <Link href="/about" className="text-[#adbdcc] hover:text-white transition-colors">About Us</Link>
              <Link href="/contact" className="text-[#adbdcc] hover:text-white transition-colors">Contact Us</Link>
            </nav>
            
            <div className="flex items-center space-x-4">
              <Link href="/signin" className="text-white font-medium py-2 px-4 rounded-lg border border-[#1a3045] hover:border-[#00d4ff] transition-colors">
                Sign In
              </Link>
              <div className="sparkle-button hidden md:block">
                <button className="relative bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-2 px-4 rounded-lg overflow-hidden group">
                  <span className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-20 transition-opacity"></span>
                  <span className="relative z-10">Get Started</span>
                </button>
              </div>
              
              {/* Mobile menu button */}
              <button 
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden text-white"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main>
        {/* Header Section */}
        <section className="pt-32 pb-16 relative overflow-hidden">
          {/* Background glow */}
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-[#00d4ff]/10 rounded-full filter blur-[100px] -z-10"></div>
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-[#7f5eff]/10 rounded-full filter blur-[100px] -z-10"></div>
          
          <div className="container mx-auto px-6 text-center">
            <h1 className="text-4xl md:text-5xl font-bold mb-6 text-white animate-fadeInUp">
              Helpful <span className="gradient-text">Resources</span>
            </h1>
            <p className="text-xl mb-12 max-w-2xl mx-auto animate-fadeInUp animate-delay-200">
              Guides, templates, and tools to help you succeed in your academic journey
            </p>
            
            {/* Search and Filter */}
            <div className="max-w-4xl mx-auto animate-fadeInUp animate-delay-400">
              <div className="mb-8">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search resources..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-[#0a1f35] border border-[#1a3045] rounded-lg py-3 px-4 pl-10 text-white focus:outline-none focus:border-[#00d4ff] transition-colors"
                  />
                  <svg 
                    className="w-5 h-5 text-[#adbdcc] absolute left-3 top-1/2 transform -translate-y-1/2" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                  </svg>
                </div>
              </div>
              
              <div className="flex flex-wrap justify-center gap-3">
                {filters.map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setActiveFilter(filter)}
                    className={`py-2 px-4 rounded-lg font-medium transition-all ${
                      activeFilter === filter
                        ? 'bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black'
                        : 'bg-[#0a1f35] text-[#adbdcc] hover:bg-[#0c2e4e]'
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Resources Grid Section */}
        <section className="pb-24">
          <div className="container mx-auto px-6">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
              {filteredResources.map((resource) => (
                <div key={resource.id} className="resource-card bg-[#0a1f35] rounded-lg overflow-hidden border border-[#1a3045]">
                  <div className="h-48 overflow-hidden">
                    <img src={resource.image} alt={resource.title} className="w-full h-full object-cover" />
                  </div>
                  <div className="p-6">
                    <div className="flex items-center mb-3">
                      <span 
                        className="text-xs font-medium py-1 px-3 rounded-full"
                        style={{
                          backgroundColor: `${getCategoryColor(resource.category)}20`,
                          color: getCategoryColor(resource.category)
                        }}
                      >
                        {resource.category}
                      </span>
                    </div>
                    <h3 className="text-xl font-medium text-white mb-2">{resource.title}</h3>
                    <p className="text-[#adbdcc] mb-4">{resource.description}</p>
                    <a 
                      href="#" 
                      className="inline-flex items-center text-[#00d4ff] hover:text-[#33deff] transition-colors"
                    >
                      <span>Download</span>
                      <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                      </svg>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Newsletter Section */}
        <section className="py-16 bg-[#061220]">
          <div className="container mx-auto px-6">
            <div className="max-w-4xl mx-auto bg-[#0a1f35] rounded-xl p-8 border border-[#1a3045]">
              <div className="flex flex-col md:flex-row items-center">
                <div className="md:w-2/3 mb-6 md:mb-0 md:pr-8">
                  <h3 className="text-2xl font-bold text-white mb-2">Stay Updated</h3>
                  <p className="text-[#adbdcc]">
                    Subscribe to our newsletter to receive new resources, tips, and important deadlines.
                  </p>
                </div>
                <div className="md:w-1/3 w-full">
                  <div className="flex">
                    <input 
                      type="email" 
                      placeholder="Your email" 
                      className="flex-grow bg-[#071527] border border-[#1a3045] rounded-l-lg py-3 px-4 text-white focus:outline-none focus:border-[#00d4ff]"
                    />
                    <button className="bg-gradient-to-r from-[#00d4ff] to-[#7f5eff] text-black font-medium py-3 px-4 rounded-r-lg hover:opacity-90 transition-opacity">
                      Subscribe
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Request Resource Section */}
        <section className="py-16">
          <div className="container mx-auto px-6 text-center">
            <h2 className="text-3xl font-bold mb-6 text-white">Can't find what you need?</h2>
            <p className="text-xl mb-8 max-w-2xl mx-auto">
              Request a specific resource and our team will create it for you
            </p>
            <button className="bg-[#0c2e4e] hover:bg-[#0f395e] text-white font-medium py-3 px-8 rounded-lg transition-colors">
              Request a Resource
            </button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-[#061220] border-t border-[#1a3045] py-12">
        <div className="container mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {/* Company Info */}
            <div>
              <h3 className="text-white text-lg font-medium mb-4">AI Student Success</h3>
              <p className="text-[#adbdcc] mb-4">
                Empowering students on their journey from aspiration to admission with AI-powered tools and guidance.
              </p>
              <div className="flex space-x-4">
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"/>
                  </svg>
                </a>
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                </a>
                <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                  </svg>
                </a>
              </div>
            </div>
            
            {/* Quick Links */}
            <div>
              <h3 className="text-white text-lg font-medium mb-4">Quick Links</h3>
              <ul className="space-y-2">
                <li><Link href="/" className="text-[#adbdcc] hover:text-[#00d4ff]">Home</Link></li>
                <li><Link href="/pricing" className="text-[#adbdcc] hover:text-[#00d4ff]">Pricing</Link></li>
                <li><Link href="/resources" className="text-[#adbdcc] hover:text-[#00d4ff]">Resources</Link></li>
                <li><Link href="/contact" className="text-[#adbdcc] hover:text-[#00d4ff]">Contact</Link></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">About Us</a></li>
              </ul>
            </div>
            
            {/* Features */}
            <div>
              <h3 className="text-white text-lg font-medium mb-4">Features</h3>
              <ul className="space-y-2">
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">University Finder</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">SOP Builder</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">Resume Enhancer</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">Application Manager</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">University GPT Chat</a></li>
              </ul>
            </div>
            
            {/* Legal */}
            <div>
              <h3 className="text-white text-lg font-medium mb-4">Legal</h3>
              <ul className="space-y-2">
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">Terms of Service</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">Privacy Policy</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">Cookie Policy</a></li>
                <li><a href="#" className="text-[#adbdcc] hover:text-[#00d4ff]">GDPR Compliance</a></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-[#1a3045] mt-12 pt-8 flex flex-col md:flex-row justify-between items-center">
            <p className="text-[#adbdcc] text-sm mb-4 md:mb-0">
              &copy; 2025 AI Student Success. All rights reserved.
            </p>
            <div className="flex space-x-6">
              <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] text-sm">Terms</a>
              <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] text-sm">Privacy</a>
              <a href="#" className="text-[#adbdcc] hover:text-[#00d4ff] text-sm">Cookies</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default ResourcesPage;