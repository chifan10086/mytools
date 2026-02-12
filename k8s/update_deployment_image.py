#!/usr/bin/env python3
"""
通过 Rancher API（HTTP/curl）更新 Deployment 镜像

不使用 kubectl，仅使用 Rancher API（HTTP 请求）。

用法:
    python3 update_deployment_image.py <命名空间> <deployment名> <新镜像>

示例:
    python3 update_deployment_image.py default nginx nginx:1.20
    python3 update_deployment_image.py default myapp myrepo/myapp:v1.2.3
    python3 update_deployment_image.py --list default   # 列出 default 下的 Deployment
"""

# ========== 请在此填写 Rancher 配置 ==========
RANCHER_URL = 'https://10.10.32.84'           # Rancher 地址，如 https://rancher.example.com（不要末尾斜杠）
RANCHER_TOKEN =          # Rancher API Token（用户 -> API Keys 创建）
RANCHER_CLUSTER_ID = 'c-drqnr'    # 集群 ID；若报 404 可改为仅集群部分，如 c-drqnr（不要 :p-xxx）
RANCHER_INSECURE = True                   # True=跳过 SSL 证书验证（自签名/内网证书时使用）
# 基础镜像地址。完整镜像 = 基础地址 + 镜像名:tag（镜像名常与 deployment 同名）
# 例: sport-data-ingestion:test_0130_0815 -> 831926597243.dkr.ecr.ap-southeast-5.amazonaws.com/sport-data-ingestion:test_0130_0815
BASE_IMAGE_REGISTRY = '831926597243.dkr.ecr.ap-southeast-5.amazonaws.com/'
# ============================================

import argparse
import json
import sys
import os
import urllib.request
import urllib.error
import ssl


def resolve_image(image: str, base_registry: str) -> str:
    """若传入的镜像不含域名（不含 '.'），则拼上基础镜像地址"""
    if not base_registry or not image:
        return image
    base = base_registry.rstrip('/') + '/'
    # 已包含域名（含 '.'）则视为完整地址，不拼接
    if '.' in image.split('/')[0]:
        return image
    return base + image.lstrip('/')


def get_config(name: str, script_var: str, env_key: str, required: bool = True) -> str:
    """优先使用脚本内变量，否则使用环境变量"""
    val = (script_var or os.environ.get(env_key, '')).strip()
    if required and not val:
        print(f"错误: 请填写脚本顶部 {name} 或设置环境变量 {env_key}")
        sys.exit(1)
    return val


def rancher_request(
    method: str,
    url: str,
    token: str,
    data: dict = None,
    content_type: str = 'application/strategic-merge-patch+json'
) -> tuple:
    """
    发送 Rancher API 请求（等价于 curl）

    Returns:
        (success: bool, response_data: dict or str, status_code: int)
    """
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }
    if data is not None:
        headers['Content-Type'] = content_type
        body = json.dumps(data).encode('utf-8')
    else:
        body = None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    # 跳过 SSL 验证（自签名/内网证书时使用，脚本变量或环境变量 RANCHER_INSECURE=1）
    ctx = ssl.create_default_context()
    if os.environ.get('RANCHER_INSECURE') == '1' or RANCHER_INSECURE:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            raw = resp.read().decode('utf-8')
            try:
                return True, json.loads(raw) if raw else {}, resp.status
            except json.JSONDecodeError:
                return True, raw, resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8') if e.fp else ''
        try:
            err_body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            err_body = raw
        return False, err_body, e.code
    except Exception as e:
        return False, str(e), 0


def list_deployments(rancher_url: str, cluster_id: str, token: str, namespace: str) -> tuple:
    """GET 列出命名空间下的所有 Deployment"""
    url = (
        f"{rancher_url.rstrip('/')}/k8s/clusters/{cluster_id}"
        f"/apis/apps/v1/namespaces/{namespace}/deployments"
    )
    return rancher_request('GET', url, token, data=None)


def get_deployment(rancher_url: str, cluster_id: str, token: str, namespace: str, name: str) -> tuple:
    """GET 获取当前 Deployment"""
    url = (
        f"{rancher_url.rstrip('/')}/k8s/clusters/{cluster_id}"
        f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
    )
    return rancher_request('GET', url, token, data=None)


def patch_deployment_image(
    rancher_url: str,
    cluster_id: str,
    token: str,
    namespace: str,
    deployment_name: str,
    new_image: str,
    container_name: str = None
) -> bool:
    """
    通过 Rancher API PATCH 更新 Deployment 镜像
    """
    ok, deployment, status = get_deployment(rancher_url, cluster_id, token, namespace, deployment_name)
    if not ok:
        if status == 404:
            print(f"错误: 在命名空间 '{namespace}' 中未找到 Deployment '{deployment_name}'")
            print(f"  可用命令查看列表: python update_deployment_image.py --list {namespace}")
            print(f"  若仍报错，请检查 RANCHER_CLUSTER_ID 是否需只填集群部分（如 c-drqnr 而非 c-drqnr:p-zgz2w）")
        else:
            print(f"GET 失败: HTTP {status} - {deployment}")
        return False

    spec = deployment.get('spec') or {}
    template = spec.get('template') or {}
    pod_spec = template.get('spec') or {}
    containers = pod_spec.get('containers') or []

    if not containers:
        print("错误: Deployment 中没有定义容器")
        return False

    # 构建 patch：只更新 image
    new_containers = []
    for c in containers:
        cname = c.get('name', '')
        old_image = c.get('image', '')
        if container_name and cname != container_name:
            new_containers.append({"name": cname, "image": old_image})
        else:
            new_containers.append({"name": cname, "image": new_image})
            print(f"容器 '{cname}': {old_image} -> {new_image}")

    patch_body = {
        "spec": {
            "template": {
                "spec": {
                    "containers": new_containers
                }
            }
        }
    }

    url = (
        f"{rancher_url.rstrip('/')}/k8s/clusters/{cluster_id}"
        f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}"
    )
    ok, result, status = rancher_request('PATCH', url, token, data=patch_body)
    if not ok:
        print(f"PATCH 失败: HTTP {status} - {result}")
        return False

    print(f"Deployment '{deployment_name}' 在命名空间 '{namespace}' 中已更新为镜像: {new_image}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='通过 Rancher API（HTTP）更新 Deployment 镜像，不使用 kubectl',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 update_deployment_image.py default nginx nginx:1.20
  python3 update_deployment_image.py default myapp myrepo/myapp:v1.2.3
  python3 update_deployment_image.py production nginx nginx:1.21 -c nginx
  python3 update_deployment_image.py --list default

配置方式（二选一）:
  1. 在脚本顶部填写 RANCHER_URL、RANCHER_TOKEN、RANCHER_CLUSTER_ID
  2. 或设置环境变量 RANCHER_URL、RANCHER_TOKEN、RANCHER_CLUSTER_ID
  RANCHER_INSECURE=1   可选，跳过 SSL 验证（自签名证书时）
        """
    )
    parser.add_argument('-l', '--list', dest='list_namespace', metavar='NS', nargs='?', const='default',
                        default=None, help='列出指定命名空间下的 Deployment（不指定 NS 则用 default）')
    parser.add_argument('namespace', nargs='?', help='命名空间')
    parser.add_argument('deployment', nargs='?', help='Deployment 名称')
    parser.add_argument('image', nargs='?', help='新镜像（完整地址，如 nginx:1.21 或 myrepo/app:v2）')
    parser.add_argument('-c', '--container', default=None, help='只更新指定容器名')

    args = parser.parse_args()

    rancher_url = get_config('RANCHER_URL', RANCHER_URL, 'RANCHER_URL')
    token = get_config('RANCHER_TOKEN', RANCHER_TOKEN, 'RANCHER_TOKEN')
    cluster_id = get_config('RANCHER_CLUSTER_ID', RANCHER_CLUSTER_ID, 'RANCHER_CLUSTER_ID')

    if args.list_namespace is not None:
        ns = args.list_namespace or 'default'
        ok, data, status = list_deployments(rancher_url, cluster_id, token, ns)
        if not ok:
            print(f"列出失败: HTTP {status} - {data}")
            if status == 404:
                print("  提示: 可尝试将 RANCHER_CLUSTER_ID 改为仅集群部分，如 c-drqnr")
            sys.exit(1)
        items = (data.get('items') or []) if isinstance(data, dict) else []
        if not items:
            print(f"命名空间 '{ns}' 下暂无 Deployment")
        else:
            print(f"命名空间 '{ns}' 下的 Deployment:")
            for d in items:
                name = d.get('metadata', {}).get('name', '')
                containers = (d.get('spec', {}).get('template', {}).get('spec', {}).get('containers') or [])
                images = [c.get('image', '') for c in containers]
                print(f"  - {name}  镜像: {', '.join(images)}")
        sys.exit(0)

    if not args.namespace or not args.deployment or not args.image:
        parser.error("需要提供 命名空间、deployment名、新镜像；或使用 --list NS 列出 Deployment")

    base_registry = (os.environ.get('BASE_IMAGE_REGISTRY') or BASE_IMAGE_REGISTRY or '').strip()
    full_image = resolve_image(args.image, base_registry)
    if full_image != args.image:
        print(f"镜像: {args.image} -> {full_image}")

    if not patch_deployment_image(
        rancher_url,
        cluster_id,
        token,
        args.namespace,
        args.deployment,
        full_image,
        container_name=args.container
    ):
        sys.exit(1)


if __name__ == '__main__':
    main()
