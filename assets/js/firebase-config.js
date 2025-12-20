/**
 * CRASH LENS - Firebase Configuration
 *
 * INSTRUCTIONS:
 * 1. Go to https://console.firebase.google.com
 * 2. Create a new project (or select existing)
 * 3. Add a web app to your project
 * 4. Copy the config values below
 * 5. Replace the placeholder values with your actual Firebase config
 */

// Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyBg1QtvbcYxyrhbw0tmpyBiD-zzoCWbxyM",
  authDomain: "crash-lens-f50e7.firebaseapp.com",
  projectId: "crash-lens-f50e7",
  storageBucket: "crash-lens-f50e7.firebasestorage.app",
  messagingSenderId: "345091421318",
  appId: "1:345091421318:web:88f99469eb0ce73c734d07"
};

// Check if config is set
const isConfigured = firebaseConfig.apiKey !== "YOUR_API_KEY_HERE";

if (!isConfigured) {
  console.warn(
    '%c⚠️ Firebase not configured!',
    'color: orange; font-size: 14px; font-weight: bold;',
    '\n\nPlease update assets/js/firebase-config.js with your Firebase project credentials.',
    '\n\nSee: https://console.firebase.google.com'
  );
}

// Initialize Firebase (only if configured)
if (isConfigured && typeof firebase !== 'undefined') {
  firebase.initializeApp(firebaseConfig);

  // Initialize services
  const auth = firebase.auth();
  const db = firebase.firestore();

  console.log('%c✓ Firebase initialized', 'color: green; font-weight: bold;');
} else if (typeof firebase === 'undefined') {
  console.error('Firebase SDK not loaded. Make sure to include Firebase scripts before this file.');
}

// Export for use in other modules
window.firebaseConfig = firebaseConfig;
window.isFirebaseConfigured = isConfigured;
