# AlphaStack website

*Automatically synced with your [v0.app](https://v0.app) deployments*

[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?style=for-the-badge&logo=vercel)](https://vercel.com/mantissagithubs-projects/v0-alpha-stack-website)
[![Built with v0](https://img.shields.io/badge/Built%20with-v0.app-black?style=for-the-badge)](https://v0.app/chat/jEfj6Kec3Je)

## Overview

This repository will stay in sync with your deployed chats on [v0.app](https://v0.app).
Any changes you make to your deployed app will be automatically pushed to this repository from [v0.app](https://v0.app).

## Deployment

Your project is live at:

**[https://vercel.com/mantissagithubs-projects/v0-alpha-stack-website](https://vercel.com/mantissagithubs-projects/v0-alpha-stack-website)**

## Build your app

Continue building your app on:

**[https://v0.app/chat/jEfj6Kec3Je](https://v0.app/chat/jEfj6Kec3Je)**

## Claude-style terminal page

This website now includes a terminal route at `/terminal` that renders ANSI output using `xterm.js`.

### One-command startup

From repo root:

```bash
alphastack terminal
```

### Local setup

1. Start AlphaStack backend stream server from repo root:

```bash
alphastack terminal-backend --host 127.0.0.1 --port 8765
```

2. Start this Next.js app:

```bash
cd website
npm install
NEXT_PUBLIC_TERMINAL_BACKEND_URL=http://127.0.0.1:8765 npm run dev
```

3. Open `http://localhost:3000/terminal`.

## How It Works

1. Create and modify your project using [v0.app](https://v0.app)
2. Deploy your chats from the v0 interface
3. Changes are automatically pushed to this repository
4. Vercel deploys the latest version from this repository