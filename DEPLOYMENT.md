# Deploying ValiChord to GitHub Pages

## Quick setup (10 minutes)

### 1. Update your repository

Replace the contents of your repository at `https://github.com/topeuph-ai/ValiChord` with the files from this folder:

```
ValiChord/
  README.md                 ← Updated project overview
  DEPLOYMENT.md             ← This file (can delete after setup)
  docs/
    index.html              ← Landing page (valichord project page)
    at-home.html            ← ValiChord at Home tool
  scaffold/
    valichord_scaffold.rs   ← Rust architecture scaffold
```

### 2. Enable GitHub Pages

1. Go to `https://github.com/topeuph-ai/ValiChord/settings/pages`
2. Under **Source**, select **Deploy from a branch**
3. Under **Branch**, select `main` (or `master`) and folder `/docs`
4. Click **Save**
5. Wait 1–2 minutes for deployment

### 3. Your site is live

- Landing page: `https://topeuph-ai.github.io/ValiChord/`
- ValiChord at Home: `https://topeuph-ai.github.io/ValiChord/at-home.html`

### 4. Optional: Custom domain

If you register `valichord.org` (or similar):

1. Go to your domain registrar
2. Add a CNAME record: `www` → `topeuph-ai.github.io`
3. In GitHub Pages settings, enter `www.valichord.org` as custom domain
4. Enable **Enforce HTTPS**

Your site becomes: `https://www.valichord.org/` and `https://www.valichord.org/at-home.html`

Domain registrars: Namecheap (~£8/year), Cloudflare (~£8/year), Google Domains.

## How to update files

### Via GitHub web interface (easiest)

1. Navigate to the file on GitHub
2. Click the pencil icon (edit)
3. Make changes
4. Click "Commit changes"
5. Site updates automatically in ~1 minute

### Via Git command line

```bash
git clone https://github.com/topeuph-ai/ValiChord.git
cd ValiChord
# Make changes
git add .
git commit -m "Update description"
git push
```

## File sizes

- `docs/index.html` — ~580KB (mostly the embedded logo image)
- `docs/at-home.html` — ~620KB (mostly the embedded logo image)
- `scaffold/valichord_scaffold.rs` — ~55KB

The logo is embedded as base64 directly in the HTML files so everything is self-contained — no external image files to manage.

## Notes

- Both HTML files are completely self-contained (no external dependencies except Google Fonts)
- If Google Fonts fail to load, the pages fall back to Georgia and Helvetica
- The ValiChord at Home tool runs entirely in the browser — no server needed
- Nothing is tracked, stored, or sent anywhere
- The markdown export feature generates a file locally in the user's browser
