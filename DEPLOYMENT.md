# 🚀 ONE-CLICK DEPLOYMENT TO RAILWAY

## Deploy AgentMarket in 60 Seconds

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/XYZ123)

### Automatic Setup Includes:
- ✅ FastAPI application with all features
- ✅ PostgreSQL database with demo data
- ✅ Environment variables configured  
- ✅ SSL certificate and custom domain
- ✅ Real-time agent demo running
- ✅ Ready to onboard vendors immediately

## Manual Railway Deployment

1. **Connect Repository**
   ```bash
   # Fork this repo to your GitHub
   # Connect to Railway.app
   ```

2. **Add PostgreSQL Database**
   - Railway Dashboard → Add Service → PostgreSQL
   - Database URL automatically configured

3. **Set Environment Variables**
   ```bash
   SECRET_KEY=your-super-secret-production-key
   STRIPE_SECRET_KEY=sk_live_your_stripe_key  
   STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_key
   CORS_ORIGINS=https://yourdomain.railway.app
   DEBUG=false
   ```

4. **Deploy**
   - Railway auto-deploys on push
   - Live in ~90 seconds
   - Domain: `https://your-app.railway.app`

## Heroku Deployment (Alternative)

```bash
# Install Heroku CLI
heroku create agentmarket-yourname

# Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set STRIPE_SECRET_KEY=sk_live_...

# Deploy
git push heroku main
```

## Docker Deployment

```bash
# Build image
docker build -t agentmarket .

# Run with environment variables
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e STRIPE_SECRET_KEY=sk_live_... \
  --name agentmarket \
  agentmarket
```

## Post-Deployment Checklist

### ✅ Immediate (5 minutes):
1. Visit your live domain
2. Check `/demo` page shows live agent activity  
3. Verify agent manifest at `/.well-known/agent-manifest.json`
4. Test vendor registration flow
5. Configure Stripe webhook endpoints

### ✅ Day 1 (Setup for revenue):
1. **Custom Domain**: Point your domain to Railway
2. **SSL Certificate**: Automatic with Railway/Heroku
3. **Stripe Dashboard**: Configure webhooks and test payments
4. **Email Setup**: Configure SMTP for vendor communications
5. **Analytics**: Set up tracking and monitoring

### ✅ Week 1 (Scale preparation):
1. **CDN Setup**: CloudFlare for performance
2. **Monitoring**: Sentry for error tracking
3. **Backup Strategy**: Database backups configured  
4. **Load Testing**: Ensure platform can handle traffic
5. **Security Audit**: Basic penetration testing

## Environment Configuration

### Required Variables:
```env
# Core Application
SECRET_KEY=your-32-character-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/db

# Stripe Payments (REQUIRED FOR REVENUE)
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Security & Performance
CORS_ORIGINS=https://yourdomain.com
DEBUG=false
ALLOWED_HOSTS=yourdomain.com
```

### Optional Variables:
```env
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Analytics & Monitoring  
ANALYTICS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn
```

## Health Checks & Monitoring

### Built-in Endpoints:
- `/health` - Application health status
- `/metrics` - Platform statistics  
- `/.well-known/agent-manifest.json` - Agent discovery

### Monitoring Setup:
```bash
# Railway automatically monitors:
# - Application health
# - Response times  
# - Error rates
# - Resource usage

# External monitoring:
curl https://yourdomain.railway.app/health
```

## Scaling Configuration

### Railway Auto-Scaling:
- Automatic scaling based on traffic
- No configuration needed
- Pay-per-use pricing

### Manual Scaling (if needed):
```bash
# Railway CLI
railway run --replicas 3

# Or via Dashboard:
# Settings → Scaling → Adjust replicas
```

## Domain & SSL Setup

### Custom Domain (Recommended):
1. **Railway Dashboard** → Settings → Domains
2. Add your domain: `agentmarket.com`
3. Update DNS: `CNAME your-app.railway.app`
4. SSL certificate auto-generated

### Subdomain Strategy:
- `agentmarket.com` - Main landing page
- `api.agentmarket.com` - API endpoints
- `demo.agentmarket.com` - Live demo
- `docs.agentmarket.com` - Documentation

## Security Hardening

### Railway Automatic Security:
- HTTPS enforced
- Environment variables encrypted
- Network isolation
- Regular security updates

### Additional Security:
```env
# Rate limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# Security headers (automatically added)
SECURITY_HEADERS_ENABLED=true
```

## Backup & Recovery

### Automated Backups:
- Railway PostgreSQL: Daily backups included
- Heroku Postgres: `heroku pg:backups:capture`

### Manual Backup:
```bash
# Export data
pg_dump $DATABASE_URL > backup.sql

# Restore data  
psql $DATABASE_URL < backup.sql
```

## Performance Optimization

### Built-in Optimizations:
- FastAPI async performance
- Database connection pooling
- Static file caching
- Gzip compression

### CDN Setup (Optional):
```bash
# CloudFlare setup for static assets
# Point your domain to Railway
# Enable CloudFlare proxy
```

---

## 🎯 READY TO LAUNCH?

**Choose your deployment method and go live in 2 minutes:**

1. **Railway (Recommended)**: Professional, auto-scaling, great for startups
2. **Heroku**: Simple, well-documented, good for MVPs  
3. **Docker**: Full control, good for enterprise
4. **Cloud Providers**: AWS/GCP for maximum scale

**Once deployed, you'll have a production-ready B2A marketplace that can immediately start generating revenue!** 💰

---

*Next: Configure Stripe and start onboarding your first vendors.*