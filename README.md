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
