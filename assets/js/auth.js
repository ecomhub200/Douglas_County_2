/**
 * CRASH LENS - Authentication Module
 *
 * Handles user authentication with Firebase
 * Supports: Microsoft, Google, Email/Password
 */

const CrashLensAuth = {
  // Current user state
  currentUser: null,
  userData: null,

  /**
   * Initialize authentication listener
   * Call this on every page that needs auth state
   */
  init: function(callback) {
    if (!window.isFirebaseConfigured) {
      console.warn('Firebase not configured - auth disabled');
      if (callback) callback(null);
      return;
    }

    firebase.auth().onAuthStateChanged(async (user) => {
      this.currentUser = user;

      if (user) {
        // User is signed in
        console.log('User signed in:', user.email);

        // Get or create user document in Firestore
        await this.ensureUserDocument(user);

        // Load user data
        this.userData = await this.getUserData();
      } else {
        // User is signed out
        console.log('User signed out');
        this.userData = null;
      }

      if (callback) callback(user);
    });
  },

  /**
   * Sign in with Microsoft
   */
  signInWithMicrosoft: async function() {
    const provider = new firebase.auth.OAuthProvider('microsoft.com');
    provider.setCustomParameters({
      prompt: 'select_account'
    });

    try {
      const result = await firebase.auth().signInWithPopup(provider);
      console.log('Microsoft sign in successful');
      return result.user;
    } catch (error) {
      console.error('Microsoft sign in error:', error);
      throw error;
    }
  },

  /**
   * Sign in with Google
   */
  signInWithGoogle: async function() {
    const provider = new firebase.auth.GoogleAuthProvider();

    try {
      const result = await firebase.auth().signInWithPopup(provider);
      console.log('Google sign in successful');
      return result.user;
    } catch (error) {
      console.error('Google sign in error:', error);
      throw error;
    }
  },

  /**
   * Sign in with Email/Password
   */
  signInWithEmail: async function(email, password) {
    try {
      const result = await firebase.auth().signInWithEmailAndPassword(email, password);
      console.log('Email sign in successful');
      return result.user;
    } catch (error) {
      console.error('Email sign in error:', error);
      throw error;
    }
  },

  /**
   * Sign up with Email/Password
   */
  signUpWithEmail: async function(email, password, displayName) {
    try {
      const result = await firebase.auth().createUserWithEmailAndPassword(email, password);

      // Update display name
      if (displayName) {
        await result.user.updateProfile({ displayName });
      }

      console.log('Email sign up successful');
      return result.user;
    } catch (error) {
      console.error('Email sign up error:', error);
      throw error;
    }
  },

  /**
   * Send password reset email
   */
  resetPassword: async function(email) {
    try {
      await firebase.auth().sendPasswordResetEmail(email);
      console.log('Password reset email sent');
      return true;
    } catch (error) {
      console.error('Password reset error:', error);
      throw error;
    }
  },

  /**
   * Sign out
   */
  signOut: async function() {
    try {
      await firebase.auth().signOut();
      console.log('Sign out successful');
      window.location.href = '/henrico_crash_tool/login/';
    } catch (error) {
      console.error('Sign out error:', error);
      throw error;
    }
  },

  /**
   * Ensure user document exists in Firestore
   * Creates new document for first-time users
   */
  ensureUserDocument: async function(user) {
    if (!user) return null;

    const userRef = firebase.firestore().collection('users').doc(user.uid);
    const doc = await userRef.get();

    if (!doc.exists) {
      // Create new user document
      const now = firebase.firestore.Timestamp.now();
      const trialEndsAt = new firebase.firestore.Timestamp(
        now.seconds + (14 * 24 * 60 * 60), // 14 days from now
        now.nanoseconds
      );

      const newUser = {
        email: user.email,
        displayName: user.displayName || '',
        photoURL: user.photoURL || '',
        provider: user.providerData[0]?.providerId || 'unknown',
        createdAt: now,

        // Subscription (default to trial)
        plan: 'trial',
        billingCycle: null,
        trialEndsAt: trialEndsAt,
        subscriptionStatus: 'active',
        stripeCustomerId: null,

        // AI Assistant
        ai: {
          queriesUsedThisMonth: 0,
          queriesLimit: 0, // 0 for trial (BYOK only)
          quotaResetDate: now,
          useBYOK: true
        },

        // Organization (for team/agency)
        organizationId: null
      };

      await userRef.set(newUser);
      console.log('New user document created');
      return newUser;
    }

    return doc.data();
  },

  /**
   * Get current user's data from Firestore
   */
  getUserData: async function() {
    if (!this.currentUser) return null;

    try {
      const doc = await firebase.firestore()
        .collection('users')
        .doc(this.currentUser.uid)
        .get();

      return doc.exists ? doc.data() : null;
    } catch (error) {
      console.error('Error getting user data:', error);
      return null;
    }
  },

  /**
   * Check if user has active subscription
   */
  hasActiveSubscription: function() {
    if (!this.userData) return false;

    const { plan, subscriptionStatus, trialEndsAt } = this.userData;

    // Check trial
    if (plan === 'trial') {
      if (trialEndsAt && trialEndsAt.toDate() > new Date()) {
        return true;
      }
      return false;
    }

    // Check paid subscription
    return subscriptionStatus === 'active';
  },

  /**
   * Get days remaining in trial
   */
  getTrialDaysRemaining: function() {
    if (!this.userData || this.userData.plan !== 'trial') return 0;

    const trialEndsAt = this.userData.trialEndsAt?.toDate();
    if (!trialEndsAt) return 0;

    const now = new Date();
    const diff = trialEndsAt - now;
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));

    return Math.max(0, days);
  },

  /**
   * Require authentication - redirect to login if not signed in
   * Use at the top of protected pages
   */
  requireAuth: function(redirectUrl = '/henrico_crash_tool/login/') {
    return new Promise((resolve) => {
      this.init((user) => {
        if (!user) {
          // Store intended destination
          sessionStorage.setItem('authRedirect', window.location.pathname);
          window.location.href = redirectUrl;
          resolve(null);
        } else {
          resolve(user);
        }
      });
    });
  },

  /**
   * Redirect to app if already signed in
   * Use on login page to skip login if already authenticated
   */
  redirectIfAuthenticated: function(redirectUrl = '/henrico_crash_tool/app/') {
    return new Promise((resolve) => {
      this.init((user) => {
        if (user) {
          // Check for stored redirect destination
          const intended = sessionStorage.getItem('authRedirect');
          sessionStorage.removeItem('authRedirect');

          window.location.href = intended || redirectUrl;
          resolve(true);
        } else {
          resolve(false);
        }
      });
    });
  },

  /**
   * Get error message for Firebase auth errors
   */
  getErrorMessage: function(error) {
    const errorMessages = {
      'auth/user-not-found': 'No account found with this email.',
      'auth/wrong-password': 'Incorrect password.',
      'auth/email-already-in-use': 'An account with this email already exists.',
      'auth/weak-password': 'Password should be at least 6 characters.',
      'auth/invalid-email': 'Please enter a valid email address.',
      'auth/too-many-requests': 'Too many attempts. Please try again later.',
      'auth/popup-closed-by-user': 'Sign in cancelled.',
      'auth/account-exists-with-different-credential': 'An account already exists with this email using a different sign in method.'
    };

    return errorMessages[error.code] || error.message || 'An error occurred. Please try again.';
  }
};

// Export for global use
window.CrashLensAuth = CrashLensAuth;
