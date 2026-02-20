/**
 * CRASH LENS - Firebase Configuration
 *
 * This file initializes Firebase using config from config.json,
 * with overrides from config/api-keys.json (injected by entrypoint.sh
 * from Coolify environment variables at container startup).
 *
 * Note: Firebase API keys are designed to be public - security is enforced via Firebase Security Rules.
 */

// Initialize immediately by fetching config.json
(async function initFirebase() {
  try {
    // Fetch config.json directly
    const response = await fetch('../config.json');
    if (!response.ok) {
      throw new Error('Failed to load config.json');
    }

    const config = await response.json();
    let firebaseConfig = config?.apis?.firebase;

    // Try to load overrides from api-keys.json (set via Coolify env vars)
    try {
      const apiKeysResp = await fetch('../config/api-keys.json');
      if (apiKeysResp.ok) {
        const apiKeys = await apiKeysResp.json();
        if (apiKeys?.firebase?.apiKey) {
          firebaseConfig = { ...firebaseConfig, ...apiKeys.firebase };
          console.log('[Firebase] Using api-keys.json overrides');
        }
      }
    } catch (e) {
      // api-keys.json doesn't exist or failed to load - that's fine, use config.json values
    }

    if (!firebaseConfig || !firebaseConfig.apiKey) {
      console.warn('%c⚠️ Firebase not configured in config.json', 'color: orange; font-weight: bold;');
      window.isFirebaseConfigured = false;
      return;
    }

    // Initialize Firebase
    if (typeof firebase !== 'undefined') {
      // Check if already initialized
      if (!firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
      }

      // Set global flags
      window.firebaseConfig = firebaseConfig;
      window.isFirebaseConfigured = true;
      window.firebaseAuth = firebase.auth();
      window.firebaseDb = firebase.firestore();

      console.log('%c✓ Firebase initialized', 'color: green; font-weight: bold;');

      // Dispatch event to notify other scripts that Firebase is ready
      window.dispatchEvent(new CustomEvent('firebaseReady'));
    } else {
      console.error('Firebase SDK not loaded');
      window.isFirebaseConfigured = false;
    }
  } catch (error) {
    console.error('Error initializing Firebase:', error);
    window.isFirebaseConfigured = false;
  }
})();
