# Oracle Cloud — ValiChord Server Setup

## What you already have
- Oracle Cloud account (UK South / London region)
- Reserved public IP: **144.21.50.199** (already reserved, don't release it)
- SSH private key already downloaded (`ssh-key-2026-04-12.key`)

---

## Step 1 — Create the instance

**Compute → Instances → Create instance**

### Name
`valichord-demo`

### Availability domain
**AD-2** (AD-3 was out of A1 capacity; AD-2 worked)

### Image
Change from Oracle Linux to **Canonical Ubuntu 20.04**  
_(Changing the image is what unlocks the rest of the form)_

### Shape
`VM.Standard.A1.Flex` — if it assigns `VM.Standard.E5.Flex` instead, that is fine (12 GB RAM, x86)

### Networking
- Create new virtual cloud network
- Create new public subnet
- **"Automatically assign public IPv4 address"** — make sure the checkbox has an actual tick in it

### SSH keys
You already have the key downloaded. Choose **Paste public key** and paste the contents of your `.pub` file.  
_(Or generate a new pair if you can't find the old one)_

### Before clicking Create — check the summary
Scroll to the summary and confirm:
- **Public IPv4 address: Yes** ← if this says No or -, go back and fix it before creating

---

## Step 2 — Open the ports

Once the instance is **Running**:

1. Instance details page → click the **subnet** link
2. **Security Lists** → **Default Security List**
3. **Add Ingress Rules** — add these two:

| Source CIDR | Protocol | Port |
|---|---|---|
| `0.0.0.0/0` | TCP | 5000 |
| `0.0.0.0/0` | TCP | 8090 |

---

## Step 3 — Assign the reserved public IP

If the instance was created without a public IP (summary showed No):

**Networking → IP Management → Reserved Public IPs**  
→ find `valichord-ip` (144.21.50.199) → assign it to the instance VNIC

---

## Step 4 — SSH in

```bash
chmod 400 /path/to/ssh-key-2026-04-12.key
ssh -i /path/to/ssh-key-2026-04-12.key ubuntu@144.21.50.199
```

Once you're at the `ubuntu@...` prompt, stop here and pick this up with Claude — the next steps are installing the stack on the server.

---

## Notes
- The Oracle Cloud Shell (`>_` icon, top right of console) can sometimes be used to SSH to the instance without a public IP — useful if the public IP assignment fails again
- If A1 is out of capacity in AD-2, try AD-1
- E5.Flex (x86, 12 GB RAM) is a fine substitute for A1.Flex — the Docker setup works on x86
