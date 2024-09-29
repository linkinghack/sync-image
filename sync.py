import argparse
import json
import subprocess
import platform
from typing import List
from datetime import datetime


powershell_preconfig = """
$ErrorActionPreference = "Stop"
$ErrorView = "NormalView"
Set-StrictMode -Version Latest

"""

bash_preconfig = """
#!/bin/bash
set -xeu

"""

linux_create_manifest = """
${container_cli} manifest rm ${private_repo}/${image_name} || echo "manifest does not exists, now create it"
${container_cli} manifest create ${private_repo}/${image_name} ${private_repo}/${image_name}-arm64 ${private_repo}/${image_name}-amd64
${container_cli} manifest push ${private_repo}/${image_name}
"""

windows_create_manifest = """
${container_cli} manifest rm ${private_repo}/${image_name}
${container_cli} manifest create ${private_repo}/${image_name} ${private_repo}/${image_name}-arm64 ${private_repo}/${image_name}-amd64
${container_cli} manifest push ${private_repo}/${image_name}
"""

#  command template
## for push an image immediately after pull and retag.
tmpl_immediate_sync_mutli_arch = """
${shell_preconfig}

${container_cli} pull --platform=linux/arm64 ${image_repo}/${image_name}
${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-arm64
${container_cli} push ${private_repo}/${image_name}-arm64

${container_cli} pull --platform=linux/amd64 ${image_repo}/${image_name}
${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-amd64
${container_cli} push ${private_repo}/${image_name}-amd64

${create_manifest}
"""

tmpl_immediate_sync = """
${shell_preconfig}

${container_cli} pull  ${image_repo}/${image_name}
${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}
${container_cli} push ${private_repo}/${image_name}
"""

## for temporarily cache image in local repo
tmpl_cache_locally = """
MULTI_ARCH="${MULTI_ARCH}"
TARGET_ARCH="${TARGET_ARCH}"
if [ "$MULTI_ARCH" = "true" ]; then
    ${container_cli} pull --platform=linux/arm64 ${image_repo}/${image_name}
    ${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-arm64
    ${container_cli} pull --platform=linux/amd64 ${image_repo}/${image_name}
    ${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-amd64
else
    ${container_cli} pull --platform=$TARGET_ARCH ${image_repo}/${image_name}
    ${container_cli} tag  ${image_repo}/${image_name}  ${private_repo}/${image_name}
fi
"""


def sync_image(img_list: List[str], target_repo: str, container_cli: str, multi_arch: bool):
    # check current OS type and set preconfig script
    shell_preconfig = bash_preconfig
    create_manifest = linux_create_manifest
    if platform.system() == "Windows" :
        shell_preconfig = powershell_preconfig
        create_manifest = windows_create_manifest

    for img in img_list:
        script = ""
        if multi_arch:
            script = tmpl_immediate_sync_mutli_arch.replace("${shell_preconfig}", shell_preconfig)
        else:
            script = tmpl_immediate_sync.replace("${shell_preconfig}", shell_preconfig)
        script = script.replace("${create_manifest}", create_manifest)
        execute_template_script(img, script, target_repo, container_cli)

def cache_images_locally(img_list: List[str], target_repo: str, container_cli: str, multi_arch: bool, target_arch) -> List[str]:
    # check current OS type and set preconfig script
    shell_preconfig = bash_preconfig
    if platform.system() == "Windows" :
        shell_preconfig = powershell_preconfig

    tagged_images_list = []
    for img in img_list:
        repo_end_idx = img.find('/')
        print('image=', img, 'repo_end_idx=', repo_end_idx)
        image_repo = img[:repo_end_idx]
        image_name = img[repo_end_idx+1:]
        private_repo = target_repo

        script = ""
        if multi_arch:
            script = tmpl_cache_locally.replace("${MULTI_ARCH}", "true")
            tagged_images_list.append(f"{private_repo}/{image_name}-arm64")
            tagged_images_list.append(f"{private_repo}/{image_name}-amd64")
            
        else:
            script = tmpl_cache_locally.replace("${MULTI_ARCH}", "false")
            tagged_images_list.append(f"${private_repo}/${image_name}")
        script = script.replace("${TARGET_ARCH}", target_arch)
        execute_template_script(img, script, target_repo, container_cli)
    return tagged_images_list

def execute_template_script(img: str, script: str, target_repo: str, container_cli: str):
    #  split repo and name
    repo_end_idx = img.find('/')
    print('image=', img, 'repo_end_idx=', repo_end_idx)
    image_repo = img[:repo_end_idx]
    image_name = img[repo_end_idx+1:]
    print('image_name=', image_name, 'image_repo=', image_repo)

    # sync multi-arch
    script = script.replace("${image_repo}", image_repo)
    script = script.replace("${image_name}", image_name)
    script = script.replace("${private_repo}", target_repo)
    script = script.replace("${container_cli}", container_cli)

    if platform.system() == "Windows": 
        tmpSh = open('tmp.ps1', 'w')
        tmpSh.write(script)
        tmpSh.close()
        subprocess.call(["powershell", "./tmp.ps1"])
    else:
        tmpSh = open('tmp.sh', 'w')
        tmpSh.write(script)
        tmpSh.close()
        subprocess.call(["bash", "tmp.sh"])


def save_images_list(images: List[str], file_name: str):
    json_data = json.dumps(images, indent=2)
    with open(file_name, 'w') as json_file:
        json_file.write(json_data)

arg_parser = argparse.ArgumentParser('sync-image')
arg_parser.add_argument('-r', '--target-repo', required=True, type=str, dest='repo')
arg_parser.add_argument('-l', '--image-list', default='list.json', dest='image_list', type=str)
arg_parser.add_argument('-c', '--container-cli', default='docker', dest='container_cli', choices=['docker', 'podman'], type=str) # podman or docker
arg_parser.add_argument('-m', '--multi-arch', default=False, type=bool, dest="multi_arch", choices=[True, False])
arg_parser.add_argument('-t', '--cache-only', default=False, type=bool, dest="cache_only", choices=[True, False])
arg_parser.add_argument('-a', '--target_arch', default='linux/amd64', type=str, dest="target_arch")

def generate_push_script(tagged_images: List[str], target_repo: str, container_cli: str) -> str:
    script_lines = []

    # 先去重
    tagged_images = list(set(tagged_images))
    
    # 提取需要的镜像名称
    image_map = {}
    for img in tagged_images:
        # 找到最后一个冒号的位置
        last_colon_index = img.rfind(':')
        base_name = img[:last_colon_index]  # 获取base_name
        arch = img[last_colon_index + 1:]  # 获取架构部分
        if base_name not in image_map:
            image_map[base_name] = {}
        image_map[base_name][arch] = img

    for base_name, arches in image_map.items():
        # 检查是否同时存在 arm64 和 amd64
        if 'arm64' in arches and 'amd64' in arches:
            # 推送每个架构的镜像
            script_lines.append(f"{container_cli} push {arches['arm64']}")
            script_lines.append(f"{container_cli} push {arches['amd64']}")
            # 创建和推送 manifest
            script_lines.append(f"{container_cli} manifest create {target_repo}/{base_name} {arches['arm64']} {arches['amd64']}")
            script_lines.append(f"{container_cli} manifest push {target_repo}/{base_name}")
        else:
            # 推送单架构镜像
            single_arch = arches.get('arm64', arches.get('amd64'))
            script_lines.append(f"{container_cli} push {single_arch}")

    return "\n".join(script_lines)

def main():
    parsed = arg_parser.parse_args()
    print(parsed)

    print("private_repo: " + parsed.repo)
    lf = open(parsed.image_list, 'r')
    image_list = json.load(lf)
    print(f"image list: {image_list}")

    if parsed.cache_only:
        tagged_images = cache_images_locally(image_list, parsed.repo, parsed.container_cli, parsed.multi_arch, parsed.target_arch)
        current_time = datetime.now()
        current_time.strftime("%y%m%d-%H%M%S")
        print(f"cached images: {tagged_images}")
        save_images_list(tagged_images, f"images_cached-{current_time}.json")

        # 生成 push 脚本并保存
        push_script = generate_push_script(tagged_images, parsed.repo, parsed.container_cli)
        with open(f"push_script-{current_time}.sh", 'w') as script_file:
            script_file.write(push_script)
        print(f"Generated push script: push_script-{current_time}.sh")
    else:
        sync_image(image_list, parsed.repo, parsed.container_cli, parsed.multi_arch)

if __name__ == "__main__":
    main()
