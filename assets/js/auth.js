/**
 * CRASH LENS - Authentication Module
 *
 * Handles user authentication with Firebase
 * Supports: Microsoft, Google, Email/Password
 */

// Dynamic base path detection - works for both root and subdirectory deployments
const CRASH_LENS_BASE = (function() {
  const path = window.location.pathname;
  // Check if deployed in a subdirectory (e.g., /henrico_crash_tool/)
  const match = path.match(/^(\/[^/]+)\//);
  if (match && match[1] !== '/login' && match[1] !== '/app') {
    return match[1];
  }
  return '';
})();

const CrashLensAuth = {
  // Current user state
  currentUser: null,
  userData: null,

  // Promise that resolves once the first auth state check completes
  _authReadyResolve: null,
  authReady: null,

  /**
   * Wait for auth to be fully initialized (first onAuthStateChanged).
   * Returns a promise that resolves to the current user (or null).
   */
  waitForAuth: function() {
    return this.authReady || Promise.resolve(null);
  },

  /**
   * Initialize authentication listener
   * Call this on every page that needs auth state
   */
  init: function(callback) {
    // Create the authReady promise (only once)
    if (!this.authReady) {
      this.authReady = new Promise((resolve) => {
        this._authReadyResolve = resolve;
      });
    }

    if (!window.isFirebaseConfigured) {
      console.warn('Firebase not configured - auth disabled');
      if (this._authReadyResolve) {
        this._authReadyResolve(null);
        this._authReadyResolve = null;
      }
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

      // Resolve authReady on the first callback
      if (this._authReadyResolve) {
        this._authReadyResolve(user);
        this._authReadyResolve = null;
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

      // Set currentUser immediately to avoid race conditions
      this.currentUser = result.user;

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
  signUpWithEmail: async function(email, password, displayName, profileData) {
    try {
      const result = await firebase.auth().createUserWithEmailAndPassword(email, password);

      // Update display name
      if (displayName) {
        await result.user.updateProfile({ displayName });
      }

      // Set currentUser immediately to avoid race condition with sendVerificationEmail
      this.currentUser = result.user;

      // Store profile data for ensureUserDocument to consume
      this._pendingProfileData = profileData || null;

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
   * Send email verification to current user
   */
  sendVerificationEmail: async function() {
    if (!this.currentUser) {
      throw new Error('No user signed in');
    }

    try {
      await this.currentUser.sendEmailVerification({
        url: window.location.origin + CRASH_LENS_BASE + '/login/?verified=true',
        handleCodeInApp: false
      });
      console.log('Verification email sent');
      return true;
    } catch (error) {
      console.error('Send verification email error:', error);
      throw error;
    }
  },

  /**
   * Check if current user's email is verified
   */
  isEmailVerified: function() {
    if (!this.currentUser) return false;

    // OAuth providers (Google, Microsoft) are considered pre-verified
    const provider = this.currentUser.providerData[0]?.providerId;
    if (provider === 'google.com' || provider === 'microsoft.com') {
      return true;
    }

    return this.currentUser.emailVerified;
  },

  /**
   * Reload user and check email verification status
   * Call this to get fresh verification status
   */
  checkEmailVerification: async function() {
    if (!this.currentUser) return false;

    try {
      await this.currentUser.reload();
      // Update current user reference after reload
      this.currentUser = firebase.auth().currentUser;

      const verified = this.isEmailVerified();

      // If just verified, activate trial
      if (verified && this.userData && !this.userData.emailVerified) {
        await this.activateTrialAfterVerification();
      }

      return verified;
    } catch (error) {
      console.error('Error checking email verification:', error);
      return false;
    }
  },

  /**
   * Activate trial period after email verification
   * Called when user verifies their email
   */
  activateTrialAfterVerification: async function() {
    if (!this.currentUser) return;

    const userRef = firebase.firestore().collection('users').doc(this.currentUser.uid);
    const now = firebase.firestore.Timestamp.now();
    const trialEndsAt = new firebase.firestore.Timestamp(
      now.seconds + (14 * 24 * 60 * 60), // 14 days from verification
      now.nanoseconds
    );

    try {
      await userRef.update({
        emailVerified: true,
        emailVerifiedAt: now,
        trialEndsAt: trialEndsAt,
        trialStartedAt: now,
        subscriptionStatus: 'active'
      });

      // Update local userData
      this.userData = await this.getUserData();
      console.log('Trial activated after email verification');
    } catch (error) {
      console.error('Error activating trial:', error);
    }
  },

  /**
   * Sign out
   */
  signOut: async function() {
    try {
      await firebase.auth().signOut();
      console.log('Sign out successful');
      window.location.href = CRASH_LENS_BASE + '/login/';
    } catch (error) {
      console.error('Sign out error:', error);
      throw error;
    }
  },

  /**
   * Ensure user document exists in Firestore
   * Creates new document for first-time users
   * Trial only starts after email verification for email/password users
   */
  ensureUserDocument: async function(user) {
    if (!user) return null;

    const userRef = firebase.firestore().collection('users').doc(user.uid);
    const doc = await userRef.get();

    if (!doc.exists) {
      // Create new user document
      const now = firebase.firestore.Timestamp.now();
      const provider = user.providerData[0]?.providerId || 'unknown';

      // Retrieve pending profile data from email sign-up form
      const profile = this._pendingProfileData || {};
      this._pendingProfileData = null;

      // OAuth providers (Google, Microsoft) are pre-verified
      const isOAuthProvider = provider === 'google.com' || provider === 'microsoft.com';
      const isVerified = isOAuthProvider || user.emailVerified;

      // Only start trial if email is verified (OAuth users start immediately)
      const trialEndsAt = isVerified
        ? new firebase.firestore.Timestamp(
            now.seconds + (14 * 24 * 60 * 60), // 14 days from now
            now.nanoseconds
          )
        : null; // No trial until verified

      const newUser = {
        email: user.email,
        displayName: user.displayName || '',
        photoURL: user.photoURL || '',
        provider: provider,
        createdAt: now,

        // Email verification tracking
        emailVerified: isVerified,
        emailVerifiedAt: isVerified ? now : null,

        // Subscription (default to trial)
        // Plan values: 'trial', 'individual', 'team', 'agency'
        plan: 'trial',
        billingCycle: null,
        trialEndsAt: trialEndsAt,
        trialStartedAt: isVerified ? now : null,
        subscriptionStatus: isVerified ? 'active' : 'pending_verification',
        stripeCustomerId: null,
        stripeSubscriptionId: null,

        // AI Assistant
        ai: {
          queriesUsedThisMonth: 0,
          queriesLimit: 0, // 0 for trial (BYOK only)
          quotaResetDate: now,
          useBYOK: true
        },

        // Organization (for team/agency)
        organizationId: null,

        // User profile fields (organization, role, jurisdiction)
        organizationName: profile.organizationName || '',
        employeeType: profile.employeeType || '',
        userState: profile.userState || '',
        userStateName: profile.userStateName || '',
        userJurisdiction: profile.userJurisdiction || '',
        userJurisdictionName: profile.userJurisdictionName || '',
        profileComplete: !!(profile.employeeType && profile.userState),
        profileCompletedAt: (profile.employeeType && profile.userState) ? now : null
      };

      await userRef.set(newUser);
      console.log('New user document created', isVerified ? '(trial started)' : '(pending verification)');
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
   * Returns false if trial has expired - user needs to upgrade
   */
  hasActiveSubscription: function() {
    if (!this.userData) return false;

    const { plan, subscriptionStatus, trialEndsAt } = this.userData;

    // Pending verification - no active subscription yet
    if (subscriptionStatus === 'pending_verification') {
      return false;
    }

    // Check trial - deny access if expired
    if (plan === 'trial') {
      if (trialEndsAt && trialEndsAt.toDate() > new Date()) {
        return true; // Trial still active
      }
      return false; // Trial expired - deny access
    }

    // Check paid subscription (trialing and past_due still allow access)
    return subscriptionStatus === 'active' || subscriptionStatus === 'trialing' || subscriptionStatus === 'past_due';
  },

  /**
   * Check if trial period is still active (for display purposes)
   */
  isTrialActive: function() {
    if (!this.userData) return false;

    const { plan, trialEndsAt } = this.userData;

    if (plan !== 'trial') return false;
    if (!trialEndsAt) return false;

    return trialEndsAt.toDate() > new Date();
  },

  /**
   * Check if trial has expired (for display/upgrade prompts)
   */
  isTrialExpired: function() {
    if (!this.userData) return false;

    const { plan, trialEndsAt } = this.userData;

    if (plan !== 'trial') return false;
    if (!trialEndsAt) return true;

    return trialEndsAt.toDate() <= new Date();
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
  requireAuth: function(redirectUrl = null) {
    redirectUrl = redirectUrl || (CRASH_LENS_BASE + '/login/');
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
  redirectIfAuthenticated: function(redirectUrl = null) {
    redirectUrl = redirectUrl || (CRASH_LENS_BASE + '/app/');
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
      'auth/account-exists-with-different-credential': 'An account already exists with this email using a different sign in method.',
      'auth/too-many-requests': 'Too many verification emails sent. Please wait before trying again.'
    };

    return errorMessages[error.code] || error.message || 'An error occurred. Please try again.';
  },

  /**
   * Update user profile data (organization, role, jurisdiction)
   * Used by the profile completion modal for OAuth users
   */
  updateUserProfile: async function(profileData) {
    if (!this.currentUser) throw new Error('No user signed in');

    const userRef = firebase.firestore().collection('users').doc(this.currentUser.uid);
    const now = firebase.firestore.Timestamp.now();

    const updates = {
      organizationName: profileData.organizationName || '',
      employeeType: profileData.employeeType || '',
      userState: profileData.userState || '',
      userStateName: profileData.userStateName || '',
      userJurisdiction: profileData.userJurisdiction || '',
      userJurisdictionName: profileData.userJurisdictionName || '',
      profileComplete: true,
      profileCompletedAt: now
    };

    await userRef.update(updates);
    this.userData = await this.getUserData();
    console.log('User profile updated');
    return this.userData;
  },

  /**
   * Check if user needs email verification
   */
  needsEmailVerification: function() {
    if (!this.currentUser) return false;

    // OAuth providers don't need verification
    const provider = this.currentUser.providerData[0]?.providerId;
    if (provider === 'google.com' || provider === 'microsoft.com') {
      return false;
    }

    return !this.currentUser.emailVerified;
  },

  /**
   * Check if user has a paid plan (not trial)
   */
  isPaidPlan: function() {
    if (!this.userData) return false;
    return ['individual', 'team', 'agency'].includes(this.userData.plan);
  },

  /**
   * Check if subscription payment is past due
   */
  isPaymentPastDue: function() {
    if (!this.userData) return false;
    return this.userData.subscriptionStatus === 'past_due';
  },

  /**
   * Get display name for current plan
   */
  getPlanDisplayName: function() {
    if (!this.userData) return 'Unknown';
    const names = {
      'trial': 'Free Trial',
      'individual': 'Individual',
      'team': 'Team',
      'agency': 'Agency'
    };
    return names[this.userData.plan] || this.userData.plan;
  },

  /**
   * Initiate Stripe Checkout for a plan
   * Redirects user to Stripe's hosted checkout page
   * @param {string} plan - 'individual' or 'team'
   * @param {string} billingCycle - 'monthly' or 'annual'
   */
  initiateCheckout: async function(plan, billingCycle) {
    if (!this.currentUser) {
      throw new Error('User must be signed in to checkout');
    }

    const response = await fetch(CRASH_LENS_BASE + '/api/stripe/create-checkout-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plan: plan,
        billingCycle: billingCycle,
        firebaseUid: this.currentUser.uid,
        email: this.currentUser.email
      })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || 'Failed to create checkout session');
    }

    const { url } = await response.json();
    window.location.href = url;
  },

  /**
   * Open Stripe Customer Portal for subscription management
   * User can cancel, change plan, update payment method
   */
  openBillingPortal: async function() {
    if (!this.userData?.stripeCustomerId) {
      throw new Error('No billing account found');
    }

    const response = await fetch(CRASH_LENS_BASE + '/api/stripe/create-portal-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stripeCustomerId: this.userData.stripeCustomerId
      })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || 'Failed to open billing portal');
    }

    const { url } = await response.json();
    window.location.href = url;
  },

  /**
   * Store pending plan selection (for post-auth checkout redirect)
   */
  setPendingCheckout: function(plan, billingCycle) {
    sessionStorage.setItem('pendingPlan', plan);
    sessionStorage.setItem('pendingBilling', billingCycle);
  },

  /**
   * Get and clear pending plan selection
   * @returns {{ plan: string, billingCycle: string } | null}
   */
  getPendingCheckout: function() {
    const plan = sessionStorage.getItem('pendingPlan');
    const billingCycle = sessionStorage.getItem('pendingBilling');
    if (plan && billingCycle) {
      sessionStorage.removeItem('pendingPlan');
      sessionStorage.removeItem('pendingBilling');
      return { plan, billingCycle };
    }
    return null;
  },

  /**
   * Check if there's a pending checkout from the pricing page
   */
  hasPendingCheckout: function() {
    return !!(sessionStorage.getItem('pendingPlan') && sessionStorage.getItem('pendingBilling'));
  }
};

// Export for global use
window.CrashLensAuth = CrashLensAuth;
