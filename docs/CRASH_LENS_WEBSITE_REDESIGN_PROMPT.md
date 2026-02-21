# CRASH LENS Website Redesign — Claude Code Prompt

> **Purpose:** Use this prompt with Claude Code to transform all CRASH LENS landing pages into a world-class, conversion-optimized SaaS website that rivals tools like Linear, Vercel, and Stripe in design quality.

---

## Prompt (Copy everything below into Claude Code)

---

You are a **world-class UI/UX designer and front-end engineer** specializing in high-converting B2B SaaS websites. Your task is to redesign all CRASH LENS marketing pages to achieve **best-in-class visual design** that converts government transportation professionals into paying customers.

### Files to Modify

1. `index.html` — Main landing page (homepage)
2. `features.html` — Features showcase page
3. `pricing.html` — Pricing page
4. `contact.html` — Contact page
5. `resources.html` — Resources & downloads page
6. `assets/css/styles.css` — Shared stylesheet

**Do NOT modify** `app/index.html` (the actual application).

---

## PART 1: GLOBAL DESIGN SYSTEM OVERHAUL (`assets/css/styles.css`)

### 1.1 Typography Upgrade
- Replace the system font stack with **Inter** (from Google Fonts) as primary, with system fallbacks
- Add `<link>` to all HTML `<head>` sections: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap`
- Set `font-feature-settings: 'cv11', 'ss01'` for cleaner number rendering
- Increase `letter-spacing: -0.02em` on headings for tighter, more modern feel
- Hero titles: bump to `font-weight: 800` and `line-height: 1.1`
- Body text: `line-height: 1.75` for better readability on dark backgrounds
- Subheadings should be `font-weight: 500`, `color: rgba(173, 189, 204, 0.9)`

### 1.2 Color System Enhancement
Keep the dark theme but add depth and richness:
```css
:root {
  /* Richer primary palette */
  --primary: #2563eb;           /* Brighter blue */
  --primary-hover: #1d4ed8;
  --primary-glow: rgba(37, 99, 235, 0.4);

  /* Add accent color for CTAs */
  --accent: #06b6d4;            /* Cyan accent for standout elements */
  --accent-glow: rgba(6, 182, 212, 0.3);

  /* Warmer, richer dark backgrounds */
  --bg-dark: #030712;           /* Near-black (gray-950) */
  --bg-dark-secondary: #0f172a; /* Slate-900 */
  --bg-dark-card: rgba(15, 23, 42, 0.6);  /* Semi-transparent for glassmorphism */
  --bg-dark-elevated: rgba(30, 41, 59, 0.5);

  /* Better text contrast */
  --text-primary: #f1f5f9;      /* Almost white */
  --text-secondary: #94a3b8;    /* Slate-400 */
  --text-muted: #64748b;        /* Slate-500 */

  /* Refined borders */
  --border-subtle: rgba(148, 163, 184, 0.08);
  --border-hover: rgba(148, 163, 184, 0.15);

  /* Gradient upgrades */
  --gradient-hero: linear-gradient(135deg, #030712 0%, #0f172a 50%, #1e1b4b 100%);
  --gradient-cta: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  --gradient-card: linear-gradient(135deg, rgba(15, 23, 42, 0.8) 0%, rgba(30, 41, 59, 0.4) 100%);

  /* Glow effects */
  --shadow-glow-blue: 0 0 60px rgba(37, 99, 235, 0.15);
  --shadow-glow-purple: 0 0 60px rgba(124, 58, 237, 0.1);
}
```

### 1.3 Glassmorphism Card System
Replace the current flat dark cards with modern glassmorphism:
```css
.card-glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.08);
  border-radius: 16px;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-glass:hover {
  border-color: rgba(148, 163, 184, 0.15);
  transform: translateY(-2px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3), 0 0 30px rgba(37, 99, 235, 0.05);
}
```

### 1.4 Button Redesign
Current buttons are generic. Create premium, high-converting buttons:
```css
/* Primary CTA — the "money" button */
.btn-cta {
  background: var(--gradient-cta);
  color: white;
  padding: 0.875rem 2rem;
  border-radius: 12px;
  font-weight: 600;
  font-size: 0.9375rem;
  letter-spacing: -0.01em;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3), inset 0 1px 0 rgba(255,255,255,0.1);
}

.btn-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(37, 99, 235, 0.4), inset 0 1px 0 rgba(255,255,255,0.15);
}

/* Ghost/secondary button */
.btn-ghost {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  padding: 0.875rem 2rem;
  border-radius: 12px;
  font-weight: 500;
  backdrop-filter: blur(8px);
}

.btn-ghost:hover {
  background: rgba(255,255,255,0.05);
  border-color: var(--border-hover);
}
```

### 1.5 Smooth Animations
Add a refined animation system:
```css
/* Scroll-triggered fade-up */
.reveal {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}
.reveal.visible {
  opacity: 1;
  transform: translateY(0);
}

/* Stagger children animation */
.stagger > * {
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.stagger.visible > *:nth-child(1) { transition-delay: 0.05s; }
.stagger.visible > *:nth-child(2) { transition-delay: 0.1s; }
.stagger.visible > *:nth-child(3) { transition-delay: 0.15s; }
.stagger.visible > *:nth-child(4) { transition-delay: 0.2s; }
.stagger.visible > *:nth-child(5) { transition-delay: 0.25s; }
.stagger.visible > *:nth-child(6) { transition-delay: 0.3s; }
.stagger.visible > * { opacity: 1; transform: translateY(0); }
```

---

## PART 2: HOMEPAGE REDESIGN (`index.html`)

### 2.1 Hero Section — Complete Overhaul

**Current Problem:** The hero headline is good but the layout feels standard. The app preview window is a basic card with a screenshot.

**Redesign Requirements:**

1. **Add a radial gradient glow** behind the hero text area — a large, soft blue/purple orb:
```css
.hero::before {
  content: '';
  position: absolute;
  top: -20%;
  left: 50%;
  transform: translateX(-50%);
  width: 800px;
  height: 600px;
  background: radial-gradient(ellipse, rgba(37, 99, 235, 0.15) 0%, transparent 70%);
  pointer-events: none;
}
```

2. **Add a grid dot pattern** as subtle background texture (like Linear.app):
```css
.hero-grid-pattern {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 24px 24px;
  mask-image: radial-gradient(ellipse 70% 50% at 50% 50%, black 40%, transparent 100%);
}
```

3. **Redesign the app preview** — Replace the basic macOS window chrome with a perspective-tilted, floating screenshot with reflection:
```css
.hero-preview {
  perspective: 1200px;
}
.hero-preview-inner {
  transform: rotateY(-5deg) rotateX(2deg);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 40px 80px rgba(0,0,0,0.5), 0 0 60px rgba(37, 99, 235, 0.1);
  border: 1px solid rgba(148, 163, 184, 0.1);
}
```

4. **Add animated gradient border** to the hero CTA button that subtly pulses

5. **Social proof bar** right below hero buttons — Replace current trust indicators with a sleek horizontal bar:
```html
<div class="social-proof-bar">
  <div class="proof-item">
    <span class="proof-metric">12+</span>
    <span class="proof-label">Virginia Agencies</span>
  </div>
  <div class="proof-divider"></div>
  <div class="proof-item">
    <span class="proof-metric">$10M+</span>
    <span class="proof-label">HSIP Funding Secured</span>
  </div>
  <div class="proof-divider"></div>
  <div class="proof-item">
    <span class="proof-metric">500K+</span>
    <span class="proof-label">Crashes Analyzed</span>
  </div>
</div>
```

### 2.2 "Trusted By" Logo Bar
**Current Problem:** Text-only placeholders for agency logos. Looks unfinished.

**Fix:**
- If logo images don't exist, create **stylized text badges** with proper styling instead of broken image fallbacks
- Design them as rounded, semi-transparent pills with subtle borders:
```css
.agency-badge {
  padding: 0.5rem 1.25rem;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 8px;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 0.875rem;
  white-space: nowrap;
}
```
- Add a horizontal auto-scrolling marquee effect for the logos on mobile

### 2.3 Features Section
**Current Problem:** Standard card grid, visually flat, nothing special.

**Redesign:**
- Add a **gradient icon background** that's unique per feature (blue, purple, cyan, green)
- Each card should have a subtle **top-border gradient** (2px colored line at top):
```css
.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--card-accent-gradient);
  border-radius: 16px 16px 0 0;
}
```
- Increase card padding to `2rem`
- Use `border-radius: 16px` (not 12px)

### 2.4 Case Studies Section
**Current Problem:** Decent structure but quotes feel generic, images are small.

**Redesign:**
- Make case study cards **full-width, horizontal layout** on desktop (image left, content right)
- Add **large quotation mark** decorative element (SVG) behind the quote text
- Highlight the key metric prominently with a large number + label:
```html
<div class="case-study-hero-metric">
  <span class="metric-number">$2.4M</span>
  <span class="metric-context">in HSIP Funding Secured</span>
</div>
```
- Add a **"Read Full Case Study →"** link to each

### 2.5 ROI Calculator Section
**Current Problem:** Functional but visually standard.

**Redesign:**
- Add input **range sliders** (styled) alongside the number inputs for a more interactive feel
- The result cards should **animate counting up** when they scroll into view
- Add a **pulsing green glow** around the total savings card
- Include micro-copy below each input explaining the default values

### 2.6 Video Demo Section
**Current Problem:** Placeholder with no actual video. Play button is basic.

**Redesign:**
- Add a **blurred, gradient overlay** over the video placeholder that looks premium
- Play button: centered, 80px, with a **ripple animation** on hover
- Add a **YouTube embed** if a video URL exists, otherwise show an elegant "Demo coming soon" state
- Add **3 feature pills** below the video: "2-Min Setup", "No Coding Required", "FHWA Compliant"

### 2.7 New Section: "How It Works" (add if not present or enhance existing)
- **3-step horizontal flow** with numbered circles connected by a dashed line
- Each step: Icon + Title + Short description
- Steps: "1. Upload Your Data" → "2. AI Analyzes Patterns" → "3. Generate Reports"
- Add **subtle animation**: each step fades in sequentially on scroll

### 2.8 Footer Redesign
**Current Problem:** Basic, minimal footer.

**Redesign:**
- 4-column layout: Brand (with tagline), Product links, Resources links, Legal links
- Add a **newsletter signup row** above the footer links
- Add **social media icon links** (LinkedIn, Twitter/X, GitHub)
- Add a subtle **gradient line** at the top of the footer
- Copyright should include current year dynamically

---

## PART 3: FEATURES PAGE REDESIGN (`features.html`)

### 3.1 Hero
- Add **animated badge**: "All Features Included in Every Plan" with a sparkle icon
- Hero title: "Everything You Need to Save Lives Through Better Data"
- Add **a scroll-down indicator** (animated chevron)

### 3.2 Feature Rows
**Current Problem:** Alternating image-text layout is fine but images are mostly placeholders.

**Redesign:**
- Where screenshots exist (`feature-mapping.png`, `feature-ai-assistant.png`), wrap them in a **browser mockup frame** with glassmorphism
- Where screenshots DON'T exist, create **illustrative SVG/CSS compositions** instead of showing placeholder text. For example:
  - Signal Warrants: CSS-only traffic light with animated color phases
  - Report Generation: A styled document preview with fake lines of text
- Add a **"Learn more →"** link under each feature description
- Each feature row should **fade in from the side** (left features slide from left, right from right)

### 3.3 All-Features Grid
- Increase to **3 columns** at desktop
- Add **hover effect**: card lifts, icon glows, border brightens
- Group features into categories with small labels: "Analysis", "Visualization", "Reporting", "Safety"

---

## PART 4: PRICING PAGE REDESIGN (`pricing.html`)

### 4.1 Pricing Cards
**Current Problem:** Standard 3-column pricing grid. Nothing differentiated.

**Redesign:**
- **Center the "Professional" plan** and make it 10% larger than Basic/Enterprise
- Professional plan: **Gradient border** with glow effect, "Most Popular" badge floating above
- Add a **subtle animated shimmer** on the Professional card border:
```css
@keyframes shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}
.pricing-card-featured {
  border-image: linear-gradient(135deg, #2563eb, #7c3aed, #06b6d4, #2563eb) 1;
}
```
- Price should use **tabular font feature** for clean number alignment
- Add **annual savings callout**: "Save 20% with annual billing" in green

### 4.2 Feature Comparison Table
- Add **sticky header** so plan names stay visible when scrolling
- Use **green checkmarks** (✓) and **gray dashes** (—) with better visual weight
- Highlight the "Professional" column with a subtle blue background tint
- Add **tooltips** on hover for features that need explanation

### 4.3 FAQ Section
- Style as an **accordion** with smooth open/close animations
- Add a `+` / `−` icon that rotates on toggle
- Questions should have `font-weight: 600`

### 4.4 Add "Money-Back Guarantee" Section
- Below the pricing cards, add a trust section:
  - Shield icon + "30-Day Money-Back Guarantee"
  - "Cancel anytime, no questions asked"
  - Security badges: SOC2, HTTPS encrypted, etc.

---

## PART 5: CONTACT PAGE REDESIGN (`contact.html`)

### 5.1 Layout
**Current Problem:** Standard 2-column (info + form). Functional but uninspiring.

**Redesign:**
- Move contact info into **icon cards** above the form (3-column: Email, Phone, Office)
- Contact form: full-width below, with **glassmorphism background**
- Add **real-time form validation** with green checkmarks and red errors
- Submit button: full-width at bottom, gradient with loading state
- Add **response time promise**: "We typically respond within 4 business hours"

### 5.2 Services Section
- Redesign as **horizontal scroll cards** on mobile
- Add an icon for each service type
- Add pricing starting-at amounts if applicable

### 5.3 Add Map
- Embed a **styled dark-theme map** (Mapbox or just a dark static image) showing office location
- Or use a clean CSS illustration of Virginia state outline

---

## PART 6: RESOURCES PAGE REDESIGN (`resources.html`)

### 6.1 Download Cards
**Current Problem:** Basic card grid for downloadable resources.

**Redesign:**
- Add **file type badges** (PDF, XLSX, DOCX) with colored icons
- Show **page count and file size** on each resource
- Add a **preview thumbnail** for each document
- Download button should show "Download Free" with a download icon
- Lead capture modal: modernize with glassmorphism, better input styling

### 6.2 Resource Categories
- Add **tab-based filtering**: All, Guides, Templates, Checklists, Webinars
- Tabs should be **pill-shaped** with active state gradient

### 6.3 External Resources
- Style as a separate "Industry Resources" section
- Link to VDOT, FHWA, MUTCD with **small logo icons** next to each

---

## PART 7: CROSS-CUTTING IMPROVEMENTS

### 7.1 Navigation Bar (All Pages)
**Current Problem:** Functional but basic glass nav.

**Redesign:**
- Increase nav height slightly: `padding: 1rem 1.5rem` → `padding: 1.125rem 2rem`
- Add **active page indicator**: a small gradient dot or underline below active nav link
- "Get Started" button in nav: use the gradient CTA style with subtle glow
- On scroll: nav should **shrink slightly** and **increase blur** (more compact sticky nav)
- Mobile hamburger: animate into an **X** with smooth CSS transition

### 7.2 Page Transitions
- Add **smooth scroll behavior**: `html { scroll-behavior: smooth; }`
- Use **IntersectionObserver** for all section reveals (already partially implemented — make consistent)

### 7.3 Micro-Interactions
- All links should have a subtle **color transition** (0.2s ease)
- Cards: on hover, add a very subtle **cursor glow** effect following the mouse (CSS `radial-gradient` that follows pointer, via JavaScript)
- Buttons: add a subtle **scale(1.02)** on `active` state

### 7.4 Responsive Design Fixes
- Test and fix all pages at these breakpoints: 375px, 768px, 1024px, 1280px, 1536px
- Mobile: stack all grids to single column
- Tablet: 2-column where appropriate
- Nav: hamburger below 768px (already implemented, verify it works)
- Hero: reduce font sizes by ~20% on mobile
- Cards: reduce padding on mobile from `2rem` to `1.25rem`

### 7.5 Performance
- Add `loading="lazy"` to all images below the fold
- Add `decoding="async"` to all images
- Preload the Inter font: `<link rel="preload" href="..." as="font" type="font/woff2" crossorigin>`
- Use `will-change: transform` on animated elements (sparingly)
- Add `prefers-reduced-motion` media query to disable animations for accessibility

### 7.6 SEO & Meta
- Each page needs unique `<title>` and `<meta description>`
- Add `<meta property="og:image">` to all pages (currently only on index.html)
- Add structured data (JSON-LD) for the Organization and SoftwareApplication
- Ensure all images have descriptive `alt` text
- Update copyright year to 2026 across all pages

### 7.7 Accessibility
- Ensure all interactive elements have `:focus-visible` styles
- All color contrast ratios must pass WCAG AA (4.5:1 for text)
- Add `aria-labels` to icon-only buttons
- Ensure keyboard navigation works on all interactive elements
- Add `skip-to-content` link at top of each page

---

## DESIGN REFERENCES

For visual inspiration, model the redesign after:
- **Linear.app** — Clean dark UI, grid patterns, subtle glows
- **Vercel.com** — Masterful dark theme, typography, spacing
- **Stripe.com** — Premium feel, gradients, attention to detail
- **Raycast.com** — Glassmorphism, smooth animations
- **Arc.net** — Bold typography, colorful accents on dark

---

## IMPLEMENTATION ORDER

1. `assets/css/styles.css` — Design system foundations (colors, typography, buttons, cards)
2. `index.html` — Homepage hero, sections, footer
3. `features.html` — Feature rows, grid, CTA
4. `pricing.html` — Cards, comparison table, FAQ
5. `contact.html` — Form, contact info, map
6. `resources.html` — Downloads, categories, lead capture

**After each page, verify:**
- [ ] Responsive on mobile (375px), tablet (768px), desktop (1280px)
- [ ] No broken images or placeholder text visible
- [ ] All animations trigger correctly on scroll
- [ ] All links work correctly
- [ ] Dark theme looks consistent
- [ ] Page loads in under 3 seconds

---

## KEY RULES

1. **Keep the single-file architecture** — all page-specific styles stay in `<style>` within each HTML file, shared styles in `styles.css`
2. **Do NOT use any JavaScript frameworks** — vanilla JS only
3. **Do NOT add npm/build tools** — this is a static site
4. **Preserve ALL existing functionality** — forms, modals, the 3D visualization, ROI calculator must still work
5. **Create a PR** when done — do not push directly to main
6. **Test every page** visually before committing

---

*This prompt was generated by analyzing all 6 CRASH LENS marketing pages, their CSS architecture, content structure, and comparing against industry-leading B2B SaaS websites. Follow these instructions precisely to achieve a world-class result.*
