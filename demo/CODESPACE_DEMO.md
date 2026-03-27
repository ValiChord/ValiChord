# Running the ValiChord Demo in a GitHub Codespace

## 1. Open a Codespace

Go to the repo on GitHub → green **Code** button → **Codespaces** tab → **Create codespace on main**.

Or use the direct link: https://codespaces.new/topeuph-ai/ValiChord

Wait ~30 seconds for the Codespace to finish setting up.

## 2. Run the demo

In the terminal at the bottom of the editor:

```bash
bash demo/start.sh
```

This will:
- Start the Holochain conductor
- Install the happ (~2 minutes on first run — the WASMs are JIT-compiled)
- Launch the web server on port 8888

On subsequent runs the happ is already installed, so it starts in seconds.

## 3. Make port 8888 public

- Click the **Ports** tab in the bottom panel
- Find port **8888**
- Right-click → **Port Visibility** → **Public**
- Copy the URL (e.g. `https://improved-space-couscous-...8888.app.github.dev`)

## 4. Share the URL

Anyone with the link can open the demo in their browser. It stays live as long as the Codespace is running.

## Stopping and restarting

- **Stop:** `Ctrl+C` in the terminal
- **Restart:** run `bash demo/start.sh` again — reuses existing conductor data, no 2-min wait
- **Fresh start:** `bash demo/start.sh --fresh` — wipes conductor data and reinstalls from scratch
