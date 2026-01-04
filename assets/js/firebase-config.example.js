/**
 * CRASH LENS - Firebase Configuration Template
 *
 * SETUP INSTRUCTIONS:
 * 1. Copy this file to firebase-config.js in the same directory
 * 2. Go to https://console.firebase.google.com
 * 3. Create a new project (or select existing)
 * 4. Add a web app to your project
 * 5. Copy the config values from Firebase Console
 * 6. Replace the placeholder values below with your actual Firebase config
 *
 * SECURITY NOTE:
 * - firebase-config.js is gitignored and should NEVER be committed
 * - Firebase API keys are designed to be public (security is enforced via Firebase Security Rules)
 * - Always configure proper Security Rules in Firebase Console
 */

// Firebase configuration - REPLACE THESE VALUES
const firebaseConfig = {
  apiKey: "YOUR_FIREBASE_API_KEY_HERE",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT_ID.firebasestorage.app",
  messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Check if config is set
const isConfigured = firebaseConfig.apiKey !== "YOUR_FIREBASE_API_KEY_HERE";

if (!isConfigured) {
  console.warn(
    '%c⚠️ Firebase not configured!',
    'color: orange; font-size: 14px; font-weight: bold;',
    '\n\nPlease update assets/js/firebase-config.js with your Firebase project credentials.',
    '\n\nSetup instructions:',
    '\n1. Copy firebase-config.example.js to firebase-config.js',
    '\n2. Get your config from https://console.firebase.google.com',
    '\n3. Replace the placeholder values'
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
