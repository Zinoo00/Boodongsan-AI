# AWS EC2 Deployment - Step-by-Step Guide

## What You'll Do

1. Launch an EC2 instance (~5 min)
2. Connect to it via SSH (~2 min)
3. Install Docker (~5 min)
4. Deploy your code (~10 min)
5. Start data collection (~2 min)

**Total time: ~30 minutes**
**Monthly cost: ~$50**

---

## Step 1: Launch EC2 Instance

### 1.1 Go to AWS Console

Open: https://console.aws.amazon.com/ec2/

### 1.2 Launch Instance

Click the big **"Launch Instance"** button.

### 1.3 Configure Instance

Fill in these settings:

**Name**: `boda-production`

**Application and OS Images (Amazon Machine Image)**:

- Click "Quick Start"
- Select **Ubuntu**
- Choose **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type**
- Architecture: **64-bit (Arm)** ← Cheaper!

**Instance type**:

- Select **t4g.medium** (2 vCPU, 4GB RAM)
- Cost: ~$25/month
- Or use **t4g.small** (2 vCPU, 2GB RAM) for ~$13/month if you want to save money

**Key pair (login)**:

- Click **"Create new key pair"**
- Key pair name: `boda-key`
- Key pair type: **RSA**
- Private key file format: **.pem**
- Click **"Create key pair"**
- **IMPORTANT**: The file `boda-key.pem` will download - save it to a safe place!

**Network settings**:

- Click **"Edit"**
- Auto-assign public IP: **Enable**

**Firewall (security groups)**:

- Click **"Create security group"**
- Security group name: `boda-sg`
- Description: `BODA production security group`

Add these rules:

1. **SSH**

   - Type: SSH
   - Protocol: TCP
   - Port: 22
   - Source: **My IP** ← IMPORTANT! Only your IP can SSH

2. **HTTP**

   - Type: HTTP
   - Protocol: TCP
   - Port: 80
   - Source: Anywhere (0.0.0.0/0)

3. **HTTPS**

   - Type: HTTPS
   - Protocol: TCP
   - Port: 443
   - Source: Anywhere (0.0.0.0/0)

4. **Custom TCP (API)**

   - Type: Custom TCP
   - Protocol: TCP
   - Port: 8000
   - Source: Anywhere (0.0.0.0/0)

5. **Custom TCP (Flower - optional)**
   - Type: Custom TCP
   - Protocol: TCP
   - Port: 5555
   - Source: **My IP** ← Only you can see monitoring

**Configure storage**:

- Root volume: **30 GB**
- Volume type: **gp3**

### 1.4 Launch!

Click **"Launch instance"**

Wait ~2 minutes for it to start. You'll see "Instance state: Running" with a green checkmark.

### 1.5 Get Your Instance Public IP

1. Click on your instance ID
2. Copy the **"Public IPv4 address"** (looks like: 54.123.45.67)
3. Save this somewhere - you'll need it!

---

## Step 2: Connect to EC2

### 2.1 Prepare Your Key File

Open Terminal and run:

```bash
# Move the key file to a safe location
mv ~/Downloads/boda-key.pem ~/.ssh/

# Set correct permissions (required for SSH)
chmod 400 ~/.ssh/boda-key.pem
```

### 2.2 Connect via SSH

Replace `<YOUR-EC2-PUBLIC-IP>` with the IP you copied:

```bash
ssh -i ~/.ssh/boda-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

Example:

```bash
ssh -i ~/.ssh/boda-key.pem ubuntu@54.123.45.67
```

**First time connecting?** You'll see:

```
The authenticity of host '54.123.45.67' can't be established.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

Type: `yes` and press Enter.

You should now see:

```
ubuntu@ip-172-31-xx-xx:~$
```

✅ **You're now connected to your EC2 instance!**

---

## Step 3: Install Docker

Run these commands **on the EC2 instance**:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (so you don't need sudo)
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login for group changes to take effect
exit
```

### 3.1 Reconnect to EC2

```bash
ssh -i ~/.ssh/boda-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

### 3.2 Verify Installation

```bash
docker --version
docker-compose --version
```

You should see version numbers. ✅

---

## Step 4: Deploy Your Code

### 4.1 Clone Repository

```bash
git clone https://github.com/Zinoo00/Boodongsan-AI.git
cd Boodongsan-AI
git checkout feature/LightRAG-jin
cd backend
```

### 4.2 Create .env File

```bash
nano .env
```

Paste this and **REPLACE the placeholder values**:

```bash
# Storage Backend
STORAGE_BACKEND=local

# Redis
REDIS_URL=redis://redis:6379/0

# LightRAG
LIGHTRAG_WORKING_DIR=./lightrag_storage
LIGHTRAG_WORKSPACE=BODA

# AWS Bedrock (IMPORTANT: Use your actual credentials!)
AWS_ACCESS_KEY_ID=AKIAXDBNWHAPO2CKP6GX
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY_HERE
AWS_REGION=ap-northeast-2
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0

# OpenAPI (IMPORTANT: Use your actual API key!)
MOLIT_API_KEY=YOUR_MOLIT_KEY_HERE

# Environment
ENVIRONMENT=production
DEBUG=false
```

**To save and exit nano**:

1. Press `Ctrl + X`
2. Press `Y` (yes to save)
3. Press `Enter`

### 4.3 Start All Services

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

This will:

- Build Docker images (~3-5 minutes first time)
- Start Redis, Backend, Worker, Beat, Flower
- All services will auto-start on reboot

### 4.4 Check Services Status

```bash
docker-compose -f docker-compose.prod.yml ps
```

You should see all services with "Up" status:

```
NAME           STATUS
boda_backend   Up (healthy)
boda_worker    Up
boda_beat      Up
boda_flower    Up
boda_redis     Up (healthy)
```

### 4.5 Test Backend

```bash
curl http://localhost:8000/api/v1/health/
```

You should see JSON response with `"status": "healthy"` ✅

---

## Step 5: Start Data Collection

### 5.1 Start Small Test Job (10 documents)

```bash
curl -X POST http://localhost:8000/api/v1/admin/jobs/load-data \
  -H "Content-Type: application/json" \
  -d '{"mode": "sample", "max_records": 10}'
```

You'll get a response with a `job_id`. Copy it!

### 5.2 Check Job Status

Replace `<JOB_ID>` with your actual job ID:

```bash
curl http://localhost:8000/api/v1/admin/jobs/<JOB_ID>
```

### 5.3 Start FULL Data Collection (Thousands of Documents)

Once the test works, start the real job:

```bash
curl -X POST http://localhost:8000/api/v1/admin/jobs/load-data \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "full",
    "districts": ["강남구", "서초구", "송파구", "마포구", "용산구"],
    "max_records": 10000
  }'
```

Save the `job_id` from the response!

### 5.4 Monitor Progress

**Option 1: Flower UI** (Visual)

From your laptop browser:

```
http://<YOUR-EC2-PUBLIC-IP>:5555
```

**Option 2: API** (Terminal)

```bash
curl http://localhost:8000/api/v1/admin/jobs/<JOB_ID>
```

**Option 3: Worker Logs**

```bash
docker-compose -f docker-compose.prod.yml logs -f worker
```

---

## Step 6: Close Your Laptop! 🎉

**The job will keep running on EC2!**

You can now:

- Close your laptop
- Disconnect from WiFi
- Go to sleep

The data collection will continue for hours and save checkpoints every 50 documents.

---

## How to Check Progress Later

### From Your Laptop

```bash
# 1. SSH back into EC2
ssh -i ~/.ssh/boda-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>

# 2. Check job status
curl http://localhost:8000/api/v1/admin/jobs/<JOB_ID>

# 3. Or check all active jobs
curl http://localhost:8000/api/v1/admin/jobs
```

### From Browser

Open: `http://<YOUR-EC2-PUBLIC-IP>:5555` (Flower UI)

---

## Stopping the Job (If Needed)

### Cancel a specific job:

```bash
curl -X DELETE http://localhost:8000/api/v1/admin/jobs/<JOB_ID>
```

### Stop all services:

```bash
docker-compose -f docker-compose.prod.yml down
```

### Restart all services:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Troubleshooting

### Can't connect to EC2?

1. Check security group allows SSH from your IP
2. Verify you're using the correct key file
3. Make sure instance is "Running" in AWS console

### Services not starting?

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Restart a specific service
docker-compose -f docker-compose.prod.yml restart worker
```

### Out of disk space?

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a
```

### Job stuck in PENDING?

```bash
# Check worker is running
docker-compose -f docker-compose.prod.yml ps worker

# Check worker logs
docker-compose -f docker-compose.prod.yml logs worker
```

---

## Cost Management

### Current Setup Cost (~$50/month)

- EC2 t4g.medium: ~$25/month
- EBS storage (30GB): ~$3/month
- Data transfer: ~$2/month
- **Total: ~$30/month**

### To Reduce Costs

**Option 1: Use smaller instance**

- Use t4g.small instead of t4g.medium
- Saves ~$12/month
- Trade-off: Slower processing

**Option 2: Stop when not in use**

```bash
# From AWS Console
Instance → Actions → Instance State → Stop
```

- You only pay for storage (~$3/month) when stopped
- Restart anytime: Instance → Actions → Instance State → Start

**Option 3: Use Spot Instances**

- 70% cheaper but can be terminated by AWS
- Not recommended for long-running jobs

---

## What's Running on Your EC2

| Service     | Port | Purpose                   |
| ----------- | ---- | ------------------------- |
| Backend API | 8000 | REST API endpoints        |
| Flower UI   | 5555 | Job monitoring            |
| Redis       | 6379 | Message broker (internal) |
| Worker      | -    | Background job processor  |
| Beat        | -    | Periodic task scheduler   |

---

## Next Steps After Data Collection

1. **Query the data** via API:

   ```bash
   curl -X POST http://<YOUR-EC2-PUBLIC-IP>:8000/api/v1/query \
     -H "Content-Type: application/json" \
     -d '{"question": "강남구 아파트 평균 가격은?"}'
   ```

2. **Set up auto-start on reboot**:
   Already configured! Services will auto-start if EC2 reboots.

3. **Add HTTPS** (optional):

   - Get a domain name
   - Use Let's Encrypt for free SSL certificate
   - Configure Nginx reverse proxy

4. **Set up CloudWatch monitoring** (optional):
   See `BACKGROUND_JOBS.md` for detailed instructions

---

## Summary

✅ **What you did:**

1. Launched EC2 instance
2. Installed Docker
3. Deployed your code
4. Started data collection job
5. Closed your laptop while it runs!

✅ **What's happening now:**

- EC2 is collecting real estate data
- Worker saves checkpoints every 50 documents
- If it crashes, it will resume from last checkpoint
- All logs are being saved

✅ **Access your system:**

- API: `http://<YOUR-EC2-PUBLIC-IP>:8000/docs`
- Monitoring: `http://<YOUR-EC2-PUBLIC-IP>:5555`
- SSH: `ssh -i ~/.ssh/boda-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>`

🎉 **Congratulations! You're running on AWS!**
