# Viewshine Window Cleaning — Website

A fast, self-contained marketing website for **Isaac Larson Orton's** window
cleaning business in **Regina, Saskatchewan**. Built as plain HTML, CSS and
JavaScript — **no build step, no framework, no dependencies**. Just upload the
folder and it works.

> **Real business:** Viewshine Window Cleaning · Regina, SK · **(306) 552-7242** ·
> isaaclarson_orten@icloud.com · **9am–8pm, days vary** (it's fully Isaac's
> call which days he works and which clients he takes — the site never
> promises "open every day" or "always accepts") — which already has a
> **Google Business Profile** (big for local SEO). Isaac is not currently
> insured (new/side-hustle stage), so the site makes **no insurance claims**
> anywhere — don't reintroduce "insured"/"WCB" wording until that's real.
> Still placeholder: the domain (see below).

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

Business name, phone, email and hours are now the **real** ones (Viewshine
Window Cleaning / (306) 552-7242 / isaaclarson_orten@icloud.com / 9am–8pm
daily). Still placeholder:

| Find | Replace with |
|---|---|
| `viewshinewindows.ca` | Real domain, once registered (in canonical/OG/schema/sitemap/robots) |
| `REPLACE_WITH_FORM_ENDPOINT` | Form backend URL (see below) |

Also:
- **`images/isaac.jpg`**: the only photo slot still empty — needs a real photo
  of Isaac (not stock). See `images/README.md`.
- **About page bio** (`about.html`): still a friendly draft — rewrite in
  Isaac's own words once he gives you his real story.
- **Reviews** (`index.html`): swap the sample testimonials for Isaac's real Google
  reviews once he has some. (Only mark up reviews in schema that are visible
  on the page.)
- **Prices**: confirm the real numbers ($149 / $249 are samples) once Isaac's
  decided his rates.
- **No insurance claims anywhere, on purpose**: Isaac isn't currently insured
  (new business). Don't add "insured"/"WCB" language back until that's true —
  it's a real liability if the site claims coverage that doesn't exist.
- **Social links**: the footer icons point to `#` — set the real Facebook /
  Instagram / Google Business Profile URLs.

## Quote form — ✅ wired to Web3Forms

Both quote forms (`index.html` and `contact.html`) POST to
`https://api.web3forms.com/submit` with an `access_key` hidden field, sent via
JavaScript `fetch()` (see `main.js`) so submitters see an inline "thanks, I've
got your details" message instead of being redirected off-site. Client-side
validation and the honeypot spam trap both still run first.

**Before trusting it's live, test it for real:**
1. Fill out the form on the actual site (once deployed) and submit it.
2. Confirm the submission actually lands as an email — check whichever inbox
   was used to create the Web3Forms access key.
3. Web3Forms ties delivery to the email tied to the key. If a "workspace" /
   team invite was sent to a second email (e.g. Isaac's) and it's still
   unverified, submissions may land in the account owner's inbox instead of
   his until that invite is accepted — the fastest way to know for sure is
   this live test, not guessing from the dashboard.

If it ever needs to move to a different backend (Formspree, Netlify Forms,
etc.), swap the `action=` URL and adjust the hidden fields (each service
wants a slightly different field name for its key/ID) — the honeypot and
`main.js` validation logic stay the same either way.

## Set up online booking (`booking.html`)

The booking page is ready — it just needs a free scheduler connected. Pick one,
then paste one `<iframe>` line into `booking.html` (there's a labelled comment
showing exactly where). The scheduler runs entirely on their side; nothing to
build or maintain.

**Isaac has full control over his own schedule — that's a feature, not a gap.**
He doesn't have to work every day and doesn't have to accept every client.
Both tools below are built for exactly that: he opens/closes availability
whenever he wants (block off a day, take a week off, whatever), and he can
decline or cancel any specific booking. The site's copy says "9am–8pm, days
vary" on purpose — never promise "open every day" or "always accepts," since
neither is true and it's his call, job by job.

**Option A — Google Calendar (free, uses Isaac's Gmail):**
1. Open Google Calendar → **Create → Appointment schedule**.
2. Name it (e.g. "Window cleaning"), set a general window of **9:00am–8:00pm**
   for the days he expects to usually work — he can always block off or add
   days later, day by day, from the calendar directly.
3. **Cap it at 2–3 jobs a day** (he's solo — don't let it overbook him): set the
   slot **duration to ~3–3.5 hours** per booking. An 11-hour window (9–8) at
   that length naturally offers about 3 slots/day. Shorten the window or
   lengthen the slot if you want to guarantee exactly 2.
4. Click **Share → embed**, copy the `<iframe>` code.
5. In `booking.html`, find the `BOOKING WIDGET GOES HERE` comment, paste the
   iframe (add `class="booking-embed"`), and delete the `.booking-ph` block.

**Option B — Calendly (free tier, syncs to Google Calendar):**
1. Sign up at calendly.com, create an event type (e.g. "Window cleaning") with
   a 9am–8pm window for his typical days — adjustable any time from Calendly's
   availability settings.
2. Connect his Google Calendar so booked times block out automatically.
3. **Cap daily bookings**: Calendly's paid tiers have a direct "max bookings
   per day" limit; on the free tier, get the same effect by setting the event
   duration to ~3–3.5 hours (same math as above).
4. Copy the event link, and in `booking.html` use:
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
- [x] **Hours** — 9am–8pm window, but days are entirely his call ✓ (Google Business Profile still needs specific days set, since it can't say "varies" — pick whatever he actually plans to work most weeks, and adjust anytime)
- [x] **Booking cap** — 2–3 homes/day max ✓ (reflected in the site copy; set it up for real when connecting the booking calendar — see "Set up online booking" above)
- [ ] **Domain** he wants (e.g. viewshinewindows.ca) + register it
- [ ] Is he a registered business? Legal entity name for the footer/policies
- [ ] **Insurance** — not currently insured (confirmed). Revisit the site copy if/when he gets coverage — that's the only time "insured" should come back.

### Google Business Profile (already exists — big win)
- [ ] **Claim/verify** it if he hasn't (the "Is this your business?" link)
- [ ] Add the **website URL** once it's live
- [ ] Set **hours to a 9am–8pm window** (pick the days he usually plans to work), and add a few **photos**
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
