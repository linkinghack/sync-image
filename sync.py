import argparse
import json
import subprocess
from typing import List

#  command template
tmpl = """
set -xeu
docker pull --platform=linux/arm64 ${image_repo}/${image_name}
docker tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-arm64
docker push ${private_repo}/${image_name}-arm64

docker pull --platform=linux/amd64 ${image_repo}/${image_name}
docker tag  ${image_repo}/${image_name} ${private_repo}/${image_name}-amd64
docker push ${private_repo}/${image_name}-amd64

docker manifest rm ${private_repo}/${image_name} || echo "manifest does not exists, now create it"
docker manifest create ${private_repo}/${image_name} ${private_repo}/${image_name}-arm64 ${private_repo}/${image_name}-amd64
docker manifest push ${private_repo}/${image_name}
"""


def sync_image(img_list: List[str], target_repo: str):
    for img in img_list:
        #  split repo and name
        repo_end_idx = img.find('/')
        print('image=', img, 'repo_end_idx=', repo_end_idx)
        image_repo = img[:repo_end_idx]
        image_name = img[repo_end_idx+1:]
        print('image_name=', image_name, 'image_repo=', image_repo)

        # sync multi-arch
        script = tmpl.replace("${image_repo}", image_repo)
        script = script.replace("${image_name}", image_name)
        script = script.replace("${private_repo}", target_repo)
        tmpSh = open('tmp.sh', 'w')
        tmpSh.write(script)
        tmpSh.close()
        # exec shell
        subprocess.call(["bash", "tmp.sh"])

arg_parser = argparse.ArgumentParser('sync-image')
arg_parser.add_argument('-r', '--repo')
arg_parser.add_argument('-l', '--imagelist', default='list.json')

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
    print(image_list)
    sync_image(image_list, target_repo)

if __name__ == "__main__":
    main()

