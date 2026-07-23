# sync-image
Scripts for syncing container images from public registries to offline local registry

## Usage

1. Create a `list.json` that contains an JSON array (of string) including source images to sync.

The images MUST containing the host name and port of source registry (like `docker.io`, `quay.io` etc.).


2. Execute the sync script:
```bash
# Required flag -r <target_local_regisry>

python3 sync.py -r <local_repo_host_name>:[local_repo_port]/<local_repo_sub_paths>/<without_ending_slash>

# Optional flag
# -l list.json
```

By default, the source image path after the registry is preserved. For example:

```text
quay.io/calico/node:v3.31.4
-> 10.102.32.251:1121/calico/calico/node:v3.31.4
```

Use `--no-preserve-source-path` (or `--flatten-source-path`) to keep only the
final image name and tag:

```bash
python3 sync.py \
  -r 10.102.32.251:1121/calico \
  -l list.json \
  --no-preserve-source-path
```

The resulting target image is:

```text
10.102.32.251:1121/calico/node:v3.31.4
```
