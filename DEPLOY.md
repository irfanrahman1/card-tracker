# Deploying Card Tracker (free)

Free setup, no credit card:

| Part | Service | How it runs |
|---|---|---|
| Website | **Vercel** (Hobby plan) | Built from `frontend/` and served from Vercel's global CDN, so it loads instantly |
| API | **Vercel** Python function | `api/index.py` runs the FastAPI app in `backend/` on demand (a short warm-up after idle time) |
| Database | **Neon** (free plan) | Postgres. Data isn't deleted; it stops at the limit instead of charging |

Settings live in `vercel.json` (build, routing, security headers). Vercel's Hobby
plan is for personal, non-commercial projects, and it pauses rather than bills if a
limit is reached.

> Plans and screens change over time. If a button below is named differently, look
> for the closest match.

## 1. Database (Neon)

1. Sign up at neon.com with GitHub and create a project in **AWS US East 1 (N. Virginia)**
   ("Just Postgres" is all you need).
2. Click **Connect** and copy the connection string (`postgresql://...`). The **pooled**
   one (host contains `-pooler`) is best for Vercel.

**The string contains your database password. Never put it in the code, GitHub, or a chat.**

## 2. App (Vercel)

1. Sign up at vercel.com with GitHub (Hobby plan, no card).
2. **Add New → Project**, import `card-tracker`. Framework preset: **Other**. Leave the
   build settings alone; `vercel.json` sets them.
3. **Environment Variables:**

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string |
   | `COOKIE_SECURE` | `true` |
   | `TRUSTED_PROXY_HOPS` | `1` |

   For **forgot password** emails, also add (free with a Gmail account; see below):

   | Name | Value |
   |---|---|
   | `APP_URL` | your site's address, e.g. `https://card-tracker-three-steel.vercel.app` |
   | `SMTP_HOST` | `smtp.gmail.com` |
   | `SMTP_PORT` | `587` |
   | `SMTP_USER` | your Gmail address |
   | `SMTP_PASSWORD` | a Gmail **app password** (mark as sensitive) |
   | `EMAIL_FROM` | `Card Tracker <your Gmail address>` |

4. **Deploy.** When it's done you get an address like `https://card-tracker-xxxx.vercel.app`.
5. In the project's **Settings → Functions**, set the function region to **Washington, D.C.
   (iad1)**, next to the Neon database (it's usually the default).

Every `git push` to `main` redeploys automatically.

## 3. Check it

- The login page loads over `https://` (padlock in the address bar).
- **Try the demo** works.
- Create your real account. (A fresh database starts empty; upload your CSVs again.)

## Password reset emails (Gmail, free)

1. Turn on **2-Step Verification** for the Google account (myaccount.google.com → Security).
2. Open **myaccount.google.com/apppasswords**, create an app password named `Card Tracker`,
   and copy the 16-character password.
3. Put it in Vercel as `SMTP_PASSWORD` (with the other SMTP settings above) and redeploy.

Gmail allows about 500 emails a day, plenty for a small app. Without these settings the
reset email isn't sent; on your own computer the link is printed in the terminal instead.

## Other hosts

The `Dockerfile` builds the same app as one container (website + API) for any host
that runs containers, e.g. Google Cloud Run:

```bash
gcloud run deploy card-tracker --source . --region us-east4 --allow-unauthenticated \
  --max-instances 1 --set-env-vars COOKIE_SECURE=true,TRUSTED_PROXY_HOPS=1
```

(Set `DATABASE_URL` with Secret Manager, not on the command line.) To try the container
on your own computer with Docker Desktop:

```bash
docker build -t card-tracker .
docker run -p 8000:8000 -e DATABASE_URL="postgresql://..." card-tracker
```
