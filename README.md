# Lyfta MCP Server

Wraps the Lyfta workout-tracker API as an MCP server so Claude can read your
workouts, exercises, and progress, and create new programs/templates.

## Tools exposed

| Tool | Type | Description |
|---|---|---|
| `get_workouts` | read | Full workout + exercise + set detail |
| `get_workouts_summary` | read | Lightweight workout history (up to 1000/call) |
| `get_exercises` | read | Exercises you've actually performed |
| `search_exercise_library` | read | Search the full Lyfta exercise catalog |
| `get_exercise_progress` | read | Weight/reps/volume/1RM trend for one exercise |
| `create_collection` | **write** | Create a new program/collection |
| `create_template` | **write** | Add a workout template to a collection |

## 1. Get your Lyfta API key

Go to `my.lyfta.app` → Community → API Access → **Generate API Key**.
It's shown once — copy it immediately. Generating a new key revokes the old one.

## 2. Run locally (optional, for testing)

```bash
cd lyfta-mcp
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

export LYFTA_API_KEY=your_key_here   # Windows: set LYFTA_API_KEY=your_key_here
python server.py
```

Test it with the official MCP inspector:

```bash
npx @modelcontextprotocol/inspector python server.py
```

## 3. Deploy to Render (free, no credit card)

Claude's custom connectors need a server reachable over the public internet —
a local script isn't enough. Render's free tier works well here since it
needs no payment method at all. The one tradeoff: after 15 minutes of no
traffic the service spins down, and the next request takes 30–60 seconds to
wake it back up. Since Claude only calls this on-demand (not continuously),
that's a fine tradeoff — you'll just notice a slow first response after a
quiet period.

1. Push this folder to a new GitHub repo (e.g. `cherylcfl/lyfta-mcp`).
2. Go to [render.com](https://render.com) → sign up (GitHub login is easiest,
   no card needed) → **New → Blueprint** → connect the repo. Render will
   detect `render.yaml` automatically and set the plan to Free.
   - Alternatively: **New → Web Service** → connect the repo → set
     **Build Command** to `pip install -r requirements.txt` and
     **Start Command** to `python server.py --http` → select the **Free** plan.
3. When prompted for environment variables (or in the service's
   **Environment** tab after creation), add:
   - `LYFTA_API_KEY` = your Lyfta API key
   - Render sets `PORT` automatically — no action needed.
4. Once deployed, Render gives you a public URL like
   `https://lyfta-mcp.onrender.com`. That's your MCP endpoint.

## 4. Connect it to Claude

1. In Claude: **Settings → Connectors → Add custom connector**.
2. Name it "Lyfta".
3. Paste your Railway deployment URL.
4. Since the API key lives server-side as an environment variable, there's
   no further OAuth step for this simple version — Claude just calls your
   server, and your server calls Lyfta using the key it already holds.

## Notes

- **Cold starts**: the free plan sleeps after 15 min idle. First request
  after a quiet spell will take 30-60s while it wakes up — Claude will just
  wait it out, no action needed on your end.
- Rate limits: 60 requests/minute, 5,000/day, 100 workouts/page (Lyfta-side).
  If you hit this a lot, consider adding simple in-memory caching to `_get`.
- `create_collection` and `create_template` are write actions — Claude will
  ask you to confirm before calling them, same as any other side-effectful
  action.
- If you ever want to lock this server down further (e.g. so only you can
  hit it even though it's public), you can add a shared-secret header check
  before each tool call — happy to add that if you want it.
