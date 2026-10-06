# Deploying TaskFlow (free)

The goal is a public URL you can put on your resume. It takes about 15 minutes.

> Hosting providers change their free tiers from time to time. Check the
> current limits on their pricing pages before you rely on them.

## Option A: Render Blueprint (web service + database in one click)

1. Push this repository to GitHub, as a **public** repo named `taskflow`.
2. Sign in at **render.com** with your GitHub account.
3. **New → Blueprint** → select the `taskflow` repo → **Apply**.
   Render reads `render.yaml` and creates:
   - `taskflow`, a Docker web service with a health check on `/health`
   - `taskflow-db`, a PostgreSQL 16 database
   - `JWT_SECRET`, generated automatically
4. Wait for the first build (5–8 minutes). Open the `.onrender.com` URL and
   sign up. That's your live demo.
5. Put the URL at the top of `README.md` and on your resume.

**Free-tier notes:**
- Free web services sleep after about 15 minutes idle, and the first visit
  after that takes 30–60 seconds. Mention "may take a minute to wake up" next
  to the link, or open it yourself before an interview.
- Render's free Postgres databases have historically expired after a fixed
  period (30 days at the time of writing). For a permanent demo, use Option B's database.

## Option B: Render web service + Neon database (no expiry)

1. Create a free project at **neon.tech** → copy the connection string. It
   looks like `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`.
2. On Render: **New → Web Service** → pick the repo → Runtime **Docker** →
   Instance type **Free**.
3. Add these environment variables:
   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string |
   | `JWT_SECRET` | a long random string, e.g. from `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `TRUSTED_PROXIES` | `1` |
4. Set the health check path to `/health` and deploy.

Tables are created automatically on first boot by the migration runner.

## After deploying
- [ ] Sign up and create a few tasks, so the demo doesn't look empty for visitors
- [ ] Create a demo account (e.g. `demo@taskflow.dev`) and list its credentials in the README, so recruiters can look around without signing up
- [ ] Add the live URL to the README, your resume and your LinkedIn "Featured" section
- [ ] CI runs on every push. Keep the badge green.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `RuntimeError: JWT_SECRET must be set in production` | Add the `JWT_SECRET` environment variable |
| `/health` returns `database: unreachable` | Check `DATABASE_URL`. Neon needs `?sslmode=require` |
| Everyone gets rate-limited together | Set `TRUSTED_PROXIES=1`, so the real client IP is used instead of the proxy's |
