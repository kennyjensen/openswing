# Hosting OpenSwing at openswing.vibefoil.com

The repository includes a GitHub Actions deployment workflow at
[`.github/workflows/pages.yml`](../.github/workflows/pages.yml). It builds the
application on GitHub and publishes `dist/` on pushes to `master`, or when run
manually. The numerical kernel still runs entirely in the visitor's browser.

## One-time setup

1. Push this project, including the workflow, to your GitHub repository's
   `master` branch.
2. Open **Settings → Pages**. Under **Build and deployment**, select
   **Source: GitHub Actions**.
3. Set **Custom domain** to **openswing.vibefoil.com** and save it.
4. In your DNS provider's settings for `vibefoil.com`, create:

   | Type | Name | Target |
   |---|---|---|
   | CNAME | `openswing` | `<repository-owner>.github.io` |

   Replace `<repository-owner>` with the GitHub user or organization that owns
   the repository. The target has no protocol, repository name or path. Set
   the custom domain on GitHub before adding the DNS record.
   [GitHub's custom-domain instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site#configuring-a-subdomain).
5. Under **Actions → Deploy OpenSwing to GitHub Pages**, choose **Run workflow**
   on `master` (or rerun the initial push's workflow after completing setup).
6. When GitHub's certificate is ready, enable **Enforce HTTPS** in Pages
   settings. DNS and certificate provisioning may take up to 24 hours.
   [GitHub's HTTPS/custom-domain instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site#configuring-a-subdomain).

`public/CNAME` records the intended hostname and is copied into the build.
For an Actions deployment, GitHub uses the repository's **Custom domain**
setting; the CNAME file does not configure that setting by itself.
[GitHub's publishing-source distinction](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site#configuring-a-subdomain).

## Build and paths

The workflow uses Node.js 24, Python 3.12 and `npm ci`, creates the `.venv`
interpreter used by the existing prebuild script, and runs `npm run build`.
No native NumPy/SciPy installation or numerical validation solve is required.
The build downloads and verifies the pinned browser runtime, bundles the
Python kernel/examples/fonts and creates the existing source/local-app ZIPs.
Only `dist/` is uploaded to Pages. Deployment uses GitHub's Pages artifact and
OIDC actions; no personal access token is needed.
[GitHub Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

The app is configured for the root of **https://openswing.vibefoil.com/**.
Its worker, numerical runtime and example paths are rooted at `/`; a
repository-subdirectory URL such as `<owner>.github.io/<repository>/` is not
the target of this configuration. Keep `vite.config.js`'s `base: '/'` for this
custom domain. The canonical URL, social preview metadata and web manifest
use the same origin/root.

## Icons

The favicon and home-screen icons derive from the existing trimmed Daedalus
logo, using its plot colors with thicker outlines for small sizes:

- `public/favicon.svg` and `public/favicon.ico` (16, 32 and 48 pixels).
- `public/apple-touch-icon.png` (180 pixels).
- `public/openswing-icon-192.png` and `public/openswing-icon-512.png`.
- `public/site.webmanifest`.

These assets are committed; building and deploying do not regenerate them.
To refresh them after changing `public/openswing-logo.svg`, run
`python3 scripts/generate-favicons.py` in an environment with Pillow and
PyMuPDF installed. This only exports images and does not start the solver.

The manifest supplies home-screen branding; it does not install an offline
cache. The existing downloadable local app remains the offline distribution.
