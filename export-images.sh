#!/bin/bash
# ---------------------------------------------------------------------------
# export-images.sh
#
# 在本地机器执行：读取 images_cached JSON 列表，把其中所有镜像
# docker save 成一个 tar 包并 gzip 压缩，供上传到服务器。
#
# 用法:
#   ./export-images.sh <images_json> [output.tar.gz] [container_cli]
#
# 示例:
#   ./export-images.sh "images_cached-2026-07-16 18:15:29.984870.json"
#   ./export-images.sh list.json images.tar.gz podman
# ---------------------------------------------------------------------------
set -euo pipefail

IMAGES_JSON="${1:?用法: ./export-images.sh <images_json> [output.tar.gz] [container_cli]}"
OUTPUT="${2:-images-$(date +%Y%m%d-%H%M%S).tar.gz}"
CLI="${3:-docker}"

if [ ! -f "$IMAGES_JSON" ]; then
    echo "找不到镜像列表文件: $IMAGES_JSON" >&2
    exit 1
fi

# 解析 JSON 数组 -> 镜像列表 (优先 jq, 退回 python3)
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

echo "==> 共 ${#IMAGES[@]} 个镜像，准备导出："
printf '    %s\n' "${IMAGES[@]}"

# 校验本地是否存在这些镜像
missing=0
for img in "${IMAGES[@]}"; do
    if ! "$CLI" image inspect "$img" >/dev/null 2>&1; then
        echo "  [缺失] 本地不存在: $img" >&2
        missing=1
    fi
done
if [ "$missing" -ne 0 ]; then
    echo "存在缺失镜像，请先拉取/缓存后再导出。" >&2
    exit 1
fi

echo "==> 正在 save 并压缩到: $OUTPUT"
# 一次性 save 所有镜像，管道直接 gzip，避免生成巨大的中间 tar
"$CLI" save "${IMAGES[@]}" | gzip -c > "$OUTPUT"

# 把镜像列表一并复制到输出目录，方便随包上传
LIST_COPY="$(dirname "$OUTPUT")/$(basename "$IMAGES_JSON")"
if [ "$(cd "$(dirname "$IMAGES_JSON")" && pwd)/$(basename "$IMAGES_JSON")" != "$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$IMAGES_JSON")" ]; then
    cp "$IMAGES_JSON" "$LIST_COPY"
fi

echo "==> 完成"
echo "    镜像包: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
echo "    列表  : $LIST_COPY"
echo
echo "上传到服务器后执行:"
echo "    ./import-images.sh \"$(basename "$OUTPUT")\" \"$(basename "$IMAGES_JSON")\""
