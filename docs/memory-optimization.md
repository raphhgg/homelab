# Memory Optimization (Debian VM on Proxmox)

VM specs: 32 GB RAM, Debian (Proxmox guest).

## 1. Sysctl tuning

Config file: `/etc/sysctl.d/99-memory-tuning.conf`

```
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

| Parameter | Default | Set to | Why |
|-----------|---------|--------|-----|
| `swappiness` | 60 | 10 | Keep app memory in RAM, only swap under real pressure |
| `vfs_cache_pressure` | 100 | 50 | Retain filesystem caches longer (benefits Docker overlayfs) |
| `dirty_ratio` | 20 | 15 | Smoother disk writes, avoids IO stalls |
| `dirty_background_ratio` | 10 | 5 | Start flushing dirty pages earlier in background |

Apply changes: `sudo sysctl --system`

## 2. earlyoom

Prevents full system freezes under OOM by gracefully killing the largest process before the kernel OOM killer kicks in.

```bash
sudo apt install -y earlyoom
sudo systemctl enable --now earlyoom
```

Config: `/etc/default/earlyoom` (default: kills when both RAM and swap drop below 10%).

## 3. zram (compressed in-memory swap)

Creates a compressed swap device in RAM — much faster than disk swap, especially useful in a VM where disk I/O is virtualized.

```bash
sudo apt install -y zram-tools
```

Config: `/etc/default/zramswap`

```
PERCENTAGE=25
```

Uses 25% of RAM (~8 GB) which effectively provides ~16 GB of compressed swap. Apply: `sudo systemctl restart zramswap`.

## 4. Swap reclaim (one-time)

After freeing memory (e.g., closing idle dev sessions), force swapped pages back into RAM:

```bash
sudo swapoff -a && sudo swapon -a
```

Only run this when enough free RAM is available.

## Result

| Metric | Before | After |
|--------|--------|-------|
| Disk swap used | 6 GB | ~13 MB |
| zram swap | none | ~16 GB available |
| Total swap capacity | 32 GB (disk only) | ~48 GB (zram + disk) |
| Swap priority | disk only | zram first (priority 100), disk fallback (priority -2) |
