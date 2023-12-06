import argparse
import json
import subprocess
import platform
from typing import List


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
fi

"""


def sync_image(img_list: List[str], target_repo: str, container_cli: str, multi_arch: bool):
    # check current OS type and set preconfig script
    shell_preconfig = bash_preconfig
    if platform.system() == "Windows" :
        shell_preconfig = powershell_preconfig

    script = ""
    if multi_arch:
        script = tmpl_immediate_sync_mutli_arch.replace("${shell_preconfig}", shell_preconfig)
    else:
        script = tmpl_immediate_sync.replace("${shell_preconfig}", shell_preconfig)

    for img in img_list:
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
        # tmpSh = open('tmp.sh', 'w')
        # tmpSh.write(script)
        # tmpSh.close()
        # exec shell
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

# def local_cache_images(img_list: List[str]):
#     for img in img_list:
        

arg_parser = argparse.ArgumentParser('sync-image')
arg_parser.add_argument('-r', '--target-repo', required=True, type=str, dest='repo')
arg_parser.add_argument('-l', '--image-list', default='list.json', dest='imagelist', type=str)
arg_parser.add_argument('-c', '--container-cli', default='docker', dest='container_cli', choices=['docker', 'podman'], type=str) # podman or docker
arg_parser.add_argument('-m', '--multi-arch', default=False, type=bool, dest="multi_arch")

def main():
    target_repo = "docker.io"
    list_file = "list.json"
    parsed = arg_parser.parse_args()
    print(parsed)
    if type(parsed.repo) == str and len(parsed.repo) > 0:
        target_repo = parsed.repo
    if type(parsed.imagelist) == str and len(parsed.imagelist) > 0:
        list_file = parsed.imagelist

    print("private_repo: " + target_repo)
    lf = open(list_file, 'r')
    image_list = json.load(lf)
    print(f"image list: {image_list}")
    sync_image(image_list, target_repo, parsed.container_cli, parsed.multi_arch)

if __name__ == "__main__":
    main()

