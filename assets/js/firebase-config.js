/**
 * CRASH LENS - Firebase Configuration
 *
 * This file initializes Firebase using config from config.json
 * Note: Firebase API keys are designed to be public - security is enforced via Firebase Security Rules.
 */

// Will be populated from config.json
let firebaseConfig = null;
let isConfigured = false;

// Initialize Firebase when config is loaded
function initializeFirebase(config) {
  if (!config || !config.apiKey) {
    console.warn('%c⚠️ Firebase not configured', 'color: orange; font-weight: bold;');
    return;
  }

  firebaseConfig = config;
  isConfigured = true;

  if (typeof firebase !== 'undefined') {
    // Check if already initialized
    if (!firebase.apps.length) {
      firebase.initializeApp(firebaseConfig);
      console.log('%c✓ Firebase initialized', 'color: green; font-weight: bold;');
    }

    // Initialize services
    window.firebaseAuth = firebase.auth();
    window.firebaseDb = firebase.firestore();
  } else {
    console.error('Firebase SDK not loaded. Make sure to include Firebase scripts before this file.');
  }

  // Export for use in other modules
  window.firebaseConfig = firebaseConfig;
  window.isFirebaseConfigured = isConfigured;
}

// Try to get config from appConfig (loaded from config.json)
function loadFirebaseFromConfig() {
  if (window.appConfig && window.appConfig.apis && window.appConfig.apis.firebase) {
    initializeFirebase(window.appConfig.apis.firebase);
  } else {
    // Wait for config to load and try again
    setTimeout(loadFirebaseFromConfig, 100);
  }
}

// Start loading
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadFirebaseFromConfig);
} else {
  loadFirebaseFromConfig();
}
