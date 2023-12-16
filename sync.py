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

${container_cli} manifest rm ${private_repo}/${image_name} || echo "manifest does not exists, now create it"
${container_cli} manifest create ${private_repo}/${image_name} ${private_repo}/${image_name}-arm64 ${private_repo}/${image_name}-amd64
${container_cli} manifest push ${private_repo}/${image_name}
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
if [ $MULT_ARCH == "true" ]; then
    ${container_cli} pull --platform=linux/arm64 ${image_repo}/${image_name}
    ${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-arm64
    ${container_cli} pull --platform=linux/amd64 ${image_repo}/${image_name}
    ${container_cli} tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-amd64
else
    ${container_cli} pull ${image_repo}/${image_name}
    ${container_cli} tag ${private_repo}/${image_name}
fi
"""


def sync_image(img_list: List[str], target_repo: str, container_cli: str, multi_arch: bool):
    # check current OS type and set preconfig script
    shell_preconfig = bash_preconfig
    if platform.system() == "Windows" :
        shell_preconfig = powershell_preconfig

    for img in img_list:
        script = ""
        if multi_arch:
            script = tmpl_immediate_sync_mutli_arch.replace("${shell_preconfig}", shell_preconfig)
        else:
            script = tmpl_immediate_sync.replace("${shell_preconfig}", shell_preconfig)
        execute_template_script(img, script, target_repo, container_cli)

def cache_images_locally(img_list: List[str], target_repo: str, container_cli: str, multi_arch: bool) -> List[str]:
    # check current OS type and set preconfig script
    shell_preconfig = bash_preconfig
    if platform.system() == "Windows" :
        shell_preconfig = powershell_preconfig

    tagged_images_list = [str]
    for img in img_list:
        script = ""
        if multi_arch:
            script = tmpl_cache_locally.replace("${MULTI_ARCH}", "true")
            tagged_images_list.append(f"${private_repo}/${image_name}-arm64")
            tagged_images_list.append(f"${private_repo}/${image_name}-amd64")
        else:
            script = tmpl_cache_locally.replace("${MULTI_ARCH}", "false")
            tagged_images_list.append(f"${private_repo}/${image_name}")
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
        json_file.write(jsondata)

arg_parser = argparse.ArgumentParser('sync-image')
arg_parser.add_argument('-r', '--target-repo', required=True, type=str, dest='repo')
arg_parser.add_argument('-l', '--image-list', default='list.json', dest='image_list', type=str)
arg_parser.add_argument('-c', '--container-cli', default='docker', dest='container_cli', choices=['docker', 'podman'], type=str) # podman or docker
arg_parser.add_argument('-m', '--multi-arch', default=False, type=bool, dest="multi_arch")
arg_parser.add_argument('-t', '--cache-only', default=False, type=bool, dest="cache_only")

def main():
    parsed = arg_parser.parse_args()
    print(parsed)

    print("private_repo: " + parsed.repo)
    lf = open(parsed.image_list, 'r')
    image_list = json.load(lf)
    print(f"image list: {image_list}")
    if parsed.cache_only:
        tagged_images = cache_images_locally(image_list, parsed.repo, parsed.container_cli, parsed.multi_arch)
        current_time = datetime().now()
        current_time.strftime("%y%m%d-%H%M%S")
        save_images_list(tagged_images, f"images_cached-${current_time}.json")
    else:
        sync_image(image_list, parsed.repo, parsed.container_cli, parsed.multi_arch)

if __name__ == "__main__":
    main()
