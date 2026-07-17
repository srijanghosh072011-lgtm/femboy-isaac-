# Viewshine Window Cleaning — Website

A fast, self-contained marketing website for **Isaac Larson Orton's** window
cleaning business in **Regina, Saskatchewan**. Built as plain HTML, CSS and
JavaScript — **no build step, no framework, no dependencies**. Just upload the
folder and it works.

> **Real business:** Viewshine Window Cleaning · Regina, SK · **(306) 552-7242** —
> which already has a **Google Business Profile** (big for local SEO). Still
> placeholders: the domain, email and business hours (see below).

---

## What's inside

**Scope:** residential window cleaning, Regina only. (No eavestroughs, no
commercial, no out-of-town pages — those were removed by request.)

| File | Page |
|---|---|
| `index.html` | Home (hero, services, why-us, process, stats, reviews, service area, pricing, FAQ, quote form) — the main "window cleaning Regina" page |
| `residential-window-cleaning-regina.html` | Local SEO — "house window cleaning Regina" |
| `services.html` | What's included (window services only) |
| `pricing.html` | Pricing tiers + factors |
| `about.html` | About Isaac |
| `contact.html` | Contact + free-quote form |
| `privacy.html` / `terms.html` | Legal (PIPEDA + CASL aware) |
| `404.html` | Custom not-found page |
| `styles.css` / `main.js` | Shared design system + interactions |
| `favicon.svg` | Site icon |
| `robots.txt` / `sitemap.xml` | Search + AI crawler visibility |

## Design

- **Palette:** ocean/sky **blue** (primary) + **coral sunset** accent (the "sun" —
  chosen instead of yellow for a bright summer feel) + fresh aqua + warm cream.
- **Fonts:** Montserrat (headings, light weights) + Plus Jakarta Sans (body), via Google Fonts.
- Light, airy, "summer vibes" throughout — inspired by, but deliberately not a
  copy of, sunnydayz.ca.

## Run it locally

Just open `index.html` in a browser, or serve the repo folder:

```bash
python3 -m http.server 8000   # then visit http://localhost:8000
```

## Deploy (pick one — all free tiers work)

All the site files live at the **repository root** (so `index.html` is the
homepage). That's what GitHub Pages and other hosts expect.

- **GitHub Pages:** Settings → Pages → Build from a branch → pick the branch
  and folder **`/ (root)`** → Save. A `.nojekyll` file is included so Pages
  serves the files as-is. Give it a minute, then load the Pages URL.
- **Netlify / Vercel / Cloudflare Pages:** connect this repo (no build command,
  publish directory = root) or drag-and-drop the folder. HTTPS is automatic.
- Any web host: upload the files so `index.html` sits at the site root.

---

## ⚠️ Before launch — replace these placeholders

Everything below is a stand-in. Do a global find-and-replace across all `.html`
files:

Business name, phone and email are now the **real** ones (Viewshine Window
Cleaning / (306) 552-7242 / isaaclarson_orten@icloud.com). Still placeholders
to replace:

| Find | Replace with |
|---|---|
| `viewshinewindows.ca` | Real domain, once registered (in canonical/OG/schema/sitemap/robots) |
| `REPLACE_WITH_FORM_ENDPOINT` | Form backend URL (see below) |
| "By appointment" | Real business hours, once confirmed (they should match the Google Business Profile) |

Also:
- **About page** (`about.html`): replace the "IO" avatar block with a real photo
  of Isaac and rewrite the bio in his own words.
- **Reviews** (`index.html`): swap the sample testimonials for Isaac's real Google
  reviews. (Only mark up reviews in schema that are visible on the page.)
- **Prices**: confirm the real numbers ($149 / $249 / $349 / $129 are samples).
- **Photos**: the sky/cream gradient panels are intentional placeholders — drop in
  real before/after job photos where you see `.media-frame` blocks.
- **Business hours & service areas**: confirm they're correct everywhere.
- **Social links**: the footer icons point to `#` — set the real Facebook /
  Instagram / Google Business Profile URLs.

## Wiring up the quote form

The form is static, so it needs a form backend to actually email Isaac. Easiest
free options — sign up, get an endpoint URL, paste it into every
`action="REPLACE_WITH_FORM_ENDPOINT"`:

- **Formspree** (formspree.io) — paste your form URL.
- **Web3Forms** (web3forms.com) — add your access key.
- **Netlify Forms** — if hosting on Netlify, add `netlify` to the `<form>` tag.

The form already includes client-side validation and a hidden honeypot field for
basic spam protection. For more, add Cloudflare Turnstile or reCAPTCHA.

## Set up online booking (`booking.html`)

The booking page is ready — it just needs a free scheduler connected. Pick one,
then paste one `<iframe>` line into `booking.html` (there's a labelled comment
showing exactly where). The scheduler runs entirely on their side; nothing to
build or maintain.

**Option A — Google Calendar (free, uses Isaac's Gmail):**
1. Open Google Calendar → **Create → Appointment schedule**.
2. Name it (e.g. "Window cleaning"), set his availability and slot length.
3. Click **Share → embed**, copy the `<iframe>` code.
4. In `booking.html`, find the `BOOKING WIDGET GOES HERE` comment, paste the
   iframe (add `class="booking-embed"`), and delete the `.booking-ph` block.

**Option B — Calendly (free tier, syncs to Google Calendar):**
1. Sign up at calendly.com, create an event type (e.g. "Window cleaning").
2. Connect his Google Calendar so booked times block out automatically.
3. Copy the event link, and in `booking.html` use:
   `<iframe class="booking-embed" src="https://calendly.com/your-name/window-cleaning" title="Book a window cleaning"></iframe>`

Until that's connected, the booking page shows a tidy "call or text to book"
panel, so it's never broken. The quiz's **Book your clean** button and the
footer **Book online** link already point at this page.

---

## 📋 Info to collect from Isaac

Send Isaac this list. Grouped by where it's used on the site.

### Business basics
- [x] **Business name** — Viewshine Window Cleaning ✓
- [x] **Phone** — (306) 552-7242 ✓ (confirm texting is OK)
- [x] **Email** — isaaclarson_orten@icloud.com ✓ (double-check the "orten" spelling is correct)
- [ ] **Domain** he wants (e.g. viewshinewindows.ca) + register it
- [ ] Exact **service hours** — site says "by appointment" for now; set real hours to match the Google Business Profile
- [ ] Is he a registered business? Legal entity name for the footer/policies
- [ ] **Insurance / WCB** — confirm coverage so we can say "insured" truthfully

### Google Business Profile (already exists — big win)
- [ ] **Claim/verify** it if he hasn't (the "Is this your business?" link)
- [ ] Add the **website URL** once it's live
- [ ] Add **hours** and a few **photos**
- [ ] Ask happy customers for the **first reviews** (currently zero)

### Services & pricing
- [ ] Real **starting prices** (the $149 / $249 figures are samples) and how he likes to quote
- [ ] Confirm the add-ons offered (screens & tracks, hard-water spots, second-storey, new-build)
- [ ] Does he want the spring & fall repeat plan?

### Service area
- [ ] Site is set to **Regina only**. If he'll travel to a nearby town, tell me and I'll add it back.

### Trust & social proof
- [ ] 3–6 real **customer reviews / testimonials** (name + neighbourhood)
- [ ] **Google Business Profile** link (create one if he hasn't — huge for local)
- [ ] Facebook / Instagram links if he has them
- [ ] Years in business / anything that builds credibility

### About & photos
- [ ] A friendly **photo of Isaac** (and/or his vehicle/logo)
- [ ] A short bio in his own words — why he started, what he cares about
- [ ] Real **before/after job photos** (great for the site AND Google Business Profile)
- [ ] A **logo**, if he has one (otherwise the current icon works fine)

### Legal
- [ ] Name + contact for the **privacy contact person** (PIPEDA requires this)
- [ ] Have a lawyer glance at `privacy.html` and `terms.html` before going live

---

## Post-launch quick wins (from the pre-launch playbook)

- Set up **Google Business Profile** (single most important thing for local leads)
  and keep the name/phone/address identical to this site.
- Submit `sitemap.xml` in **Google Search Console**.
- Add **GA4** and mark phone-click + form-submit as key events.
- Confirm HTTPS is on and `robots.txt` isn't blocking anything.
- Ask happy customers for Google reviews early and often.
