#!/bin/bash
# ---------------------------------------------------------------------------
# import-images.sh
#
# 在服务器执行：docker load 导入镜像包，逐个 push，
# 再按 -arm64 / -amd64 配对创建并推送 multi-arch manifest。
#
# 镜像命名约定 (来自 sync.py 缓存):
#   <repo>/<name>:<tag>-arm64
#   <repo>/<name>:<tag>-amd64
# 对应的 manifest 目标为去掉 arch 后缀:
#   <repo>/<name>:<tag>
#
# 用法:
#   ./import-images.sh <images.tar.gz> <images_json> [container_cli] [insecure]
#
# 示例 (私有仓库为 http，需要 insecure):
#   ./import-images.sh images.tar.gz "images_cached-....json" docker true
# ---------------------------------------------------------------------------
set -euo pipefail

TARBALL="${1:?用法: ./import-images.sh <images.tar.gz> <images_json> [container_cli] [insecure]}"
IMAGES_JSON="${2:?缺少镜像列表 JSON}"
CLI="${3:-docker}"
INSECURE="${4:-true}"   # 私有仓库 10.102.32.251:1121 走 http，默认 true

INSECURE_FLAG=""
if [ "$INSECURE" = "true" ]; then
    INSECURE_FLAG="--insecure"
fi

for f in "$TARBALL" "$IMAGES_JSON"; do
    [ -f "$f" ] || { echo "找不到文件: $f" >&2; exit 1; }
done

read_images() {
    if command -v jq >/dev/null 2>&1; then
        jq -r '.[]' "$IMAGES_JSON"
    else
        python3 -c 'import json,sys; [print(i) for i in json.load(open(sys.argv[1]))]' "$IMAGES_JSON"
    fi
}

IMAGES=()
while IFS= read -r image; do
    IMAGES+=("$image")
done < <(read_images)
if [ "${#IMAGES[@]}" -eq 0 ]; then
    echo "镜像列表为空: $IMAGES_JSON" >&2
    exit 1
fi

# --- 1. 导入镜像 --------------------------------------------------------------
echo "==> 正在 load 镜像包: $TARBALL"
gunzip -c "$TARBALL" | "$CLI" load

# --- 2. 逐个 push -------------------------------------------------------------
echo "==> 正在 push 各架构镜像"
for img in "${IMAGES[@]}"; do
    echo "    push $img"
    "$CLI" push "$img"
done

# --- 3. 按 base 分组，配对创建 manifest ---------------------------------------
# 去掉结尾的 -arm64 / -amd64 得到 manifest 目标名
declare -A HAS_ARM64
declare -A HAS_AMD64
declare -A BASES

for img in "${IMAGES[@]}"; do
    case "$img" in
        *-arm64)
            base="${img%-arm64}"
            HAS_ARM64["$base"]="$img"
            BASES["$base"]=1
            ;;
        *-amd64)
            base="${img%-amd64}"
            HAS_AMD64["$base"]="$img"
            BASES["$base"]=1
            ;;
        *)
            # 无 arch 后缀的单架构镜像，push 已完成，跳过 manifest
            echo "    [单架构] 跳过 manifest: $img"
            ;;
    esac
done

echo "==> 正在创建并推送 multi-arch manifest"
for base in "${!BASES[@]}"; do
    arm="${HAS_ARM64[$base]:-}"
    amd="${HAS_AMD64[$base]:-}"

    if [ -n "$arm" ] && [ -n "$amd" ]; then
        echo "    manifest: $base  <=  arm64 + amd64"
        "$CLI" manifest rm "$base" >/dev/null 2>&1 || true
        "$CLI" manifest create $INSECURE_FLAG "$base" "$arm" "$amd"
        "$CLI" manifest push $INSECURE_FLAG "$base"
    else
        # 只有单一架构，manifest 仅含一个平台
        only="${arm:-$amd}"
        echo "    [仅单架构] $base  <=  $only"
        "$CLI" manifest rm "$base" >/dev/null 2>&1 || true
        "$CLI" manifest create $INSECURE_FLAG "$base" "$only"
        "$CLI" manifest push $INSECURE_FLAG "$base"
    fi
done

echo "==> 完成"
