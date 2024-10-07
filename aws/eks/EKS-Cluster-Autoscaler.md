# AWS EKS 集群自动扩容 Cluster Autoscaler


- Cluster Autoscaler 是一个可以自动调整Kubernetes集群大小的组件，以便所有pod都有运行的地方，并且没有不需要的节点。支持多个公共云提供商。

- AWS EKS集群自动扩容功能可以基于Cluster Autoscaler自动调整集群中node的数量以适应需求变化。

- Cluster Autoscaler一般以Deployment的方式部署在K8s中，通过service account赋予的权限来访问AWS autoscaling group资源，并控制node（EC2）的增减。

- AWS EKS Cluster Autoscaler 以 Amazon EC2 Auto Scaling Groups服务为基础对node进行扩容，所以其扩容或缩容时，也要遵守节点组扩缩中的配置

- 当有新的Pod无法在现有node上schedule时会触发扩容，当node空闲超过10min时，会触发缩容。

* Cluster Autoscaler的镜像版本要求与K8s版本匹配，所以当EKS(K8s)升级时，Cluster Autoscaler的镜像也要进行升级。



### 给ASG增加标签 （默认都有 如果没有加一下）

* tag键值：

| Tag Key     | Tag Values |
| ----------- | ----------- |
| k8s.io/cluster-autoscaler/enabled| true       |
| k8s.io/cluster-autoscaler/cluster name    | owned        |

 ```shell
vi cluster-autoscaler-policy.json
```
 ```json
 {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "autoscaling:DescribeLaunchConfigurations",
                "autoscaling:DescribeScalingActivities",
                "autoscaling:DescribeTags",
                "autoscaling:SetDesiredCapacity",
                "autoscaling:TerminateInstanceInAutoScalingGroup",
                "ec2:DescribeLaunchTemplateVersions",
                "eks:DescribeNodegroup"
            ],
            "Resource": "*",
            "Effect": "Allow"
        }
    ]
}

 ```
 ```shell
aws iam create-policy \
    --policy-name AmazonEKSClusterAutoscalerPolicy \
    --policy-document file://cluster-autoscaler-policy.json

```

#### 2-2.创建 IAM Role
```shell
vi  trust-policy.json

{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::912315591492:oidc-provider/oidc.eks.ap-southeast-1.amazonaws.com/id/"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.ap-southeast-1.amazonaws.com/id/:sub": "system:serviceaccount:kube-system:cluster-autoscaler"
        }
      }
    }
  ]
}

```
- trust-policy.json 在创建 Role 时，指定“Trust relationships”中的内容
- 修改“252557384592”为自己的 AWS Account
- 修改“us-east-1”为自己的 Region
- 修改“EE037BDA75FA79D4F8DCE5771A4642E5”为自己 EKS 的 OpenID Connect provider URL 中最后的字符串
```shell
aws iam create-role \
  --role-name AmazonEKSClusterAutoscalerRole \
  --assume-role-policy-document file://"trust-policy.json"

  role-name：自定义 Role 的名称
assume-role-policy-document：指定本地 trust-policy 文件
```

最后，运行下列命令为 Role 添加我们在第一步中创建的 Policy

```shell
aws iam attach-role-policy \
  --policy-arn arn:aws:iam::252557384592:policy/AmazonEKSClusterAutoscalerPolicy \
  --role-name AmazonEKSClusterAutoscalerRole
```
```shell

curl -o cluster-autoscaler-autodiscover.yaml https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
```

- 修改yaml文件配置
   - 打开Cluster Autoscaler的github地址，查看与EKS版本匹配的最新Autoscaler镜像版本

1. 把cluster-autoscaler的镜像版本换成上面查到的版本1.26.3
2. 查找并替换“”为我们EKS的名称: eks
3. 在EKS的名称“tsEKS”下面，并添加以下两行
- --balance-similar-node-groups
- --skip-nodes-with-system-pods=false

* --balance-similar-node-groups：此选项用于启用集群节点组的负载均衡功能。当你有多个具有相似容量的节点组时，启用此选项可以确保 Cluster Autoscaler 尽可能均衡地在这些节点组之间分配 Pod。它帮助确保节点组的资源利用率更加平衡，以提高集群的整体性能。
* --skip-nodes-with-system-pods=false：此选项用于设置是否跳过具有系统 Pod 的节点。默认情况下，Cluster Autoscaler 会跳过具有系统 Pod（如 kube-system 命名空间中的核心组件）的节点，以确保这些关键组件的正常运行。将该选项设置为 false，即禁用跳过具有系统 Pod 的节点，可以让 Cluster Autoscaler 考虑包括具有系统 Pod 的节点在内的所有节点进行调整。
```shell
kubectl apply -f cluster-autoscaler-autodiscover.yaml
```
绑定 Role
运行以下命令，为 service account “cluster-autoscaler”绑定 IAM Role
```shell
kubectl annotate serviceaccount cluster-autoscaler \
  -n kube-system \
  eks.amazonaws.com/role-arn=arn:aws:iam::252557384592:role/AmazonEKSClusterAutoscalerRole
```
- 给autoscaler deployment打patch，增加annotation
- 这个注解的作用是告诉 Kubernetes 系统不要将这些 Pod 标记为可以被安全驱逐（evict）的 Pod。
- 通过将 cluster-autoscaler 部署的 Pod 标记为不可安全驱逐，可以避免 Cluster Autoscaler 将这些关键组件的 Pod 视为可以被删除的对象。
```shell
$ kubectl patch deployment cluster-autoscaler \
  -n kube-system \
  -p '{"spec":{"template":{"metadata":{"annotations":{"cluster-autoscaler.kubernetes.io/safe-to-evict": "false"}}}}}'
deployment.apps/cluster-autoscaler patched
```

测试命令
```shell
kubectl apply -f nginx.yaml
kubectl get deployments
kubectl scale deploy nginx-deployment --replicas 50 -n test
```


- [https://aws.github.io/aws-eks-best-practices/cluster-autoscaling/](https://aws.github.io/aws-eks-best-practices/cluster-autoscaling/)
- [https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md)
- [https://cast.ai/blog/eks-cluster-autoscaler-6-best-practices-for-effective-autoscaling/](https://cast.ai/blog/eks-cluster-autoscaler-6-best-practices-for-effective-autoscaling/)
- [https://blog.hanqunfeng.com/2023/07/18/aws-eks18-autoscaler-cas/](https://blog.hanqunfeng.com/2023/07/18/aws-eks18-autoscaler-cas/)
- [https://www.wake.wiki/archives/awseks%E9%9B%86%E7%BE%A4%E8%87%AA%E5%8A%A8%E6%89%A9%E5%AE%B9clusterautoscaler](https://www.wake.wiki/archives/awseks%E9%9B%86%E7%BE%A4%E8%87%AA%E5%8A%A8%E6%89%A9%E5%AE%B9clusterautoscaler)

在 AWS EKS 中，Cluster Autoscaler 通过命令行参数配置集群的自动扩展和缩减行为。你可以根据不同需求，调整这些参数以优化集群的性能和成本。以下是 Cluster Autoscaler 中常用的可选参数及其说明。

常用可选参数：

	1.	–cloud-provider
	•	描述：指定云提供商。对于 EKS，需要设置为 aws。
	•	示例：--cloud-provider=aws
	2.	–nodes
	•	描述：指定节点组的最小和最大节点数，格式为 <min>:<max>:<node-group-name>。
	•	示例：--nodes=1:10:my-node-group
	3.	–scale-down-enabled
	•	描述：启用或禁用缩容。如果启用，Cluster Autoscaler 会缩减空闲节点。
	•	默认值：true
	•	示例：--scale-down-enabled=true
	4.	–scale-down-delay-after-add
	•	描述：节点加入集群后，等待多久才开始考虑缩容。
	•	默认值：10m
	•	示例：--scale-down-delay-after-add=10m
	5.	–scale-down-unneeded-time
	•	描述：节点处于未被充分利用状态多长时间后会被认为是“多余”的，并可以缩减。
	•	默认值：10m
	•	示例：--scale-down-unneeded-time=10m
	6.	–scale-down-unready-time
	•	描述：节点处于不可用状态多长时间后才考虑进行缩减。
	•	默认值：20m
	•	示例：--scale-down-unready-time=20m
	7.	–balance-similar-node-groups
	•	描述：启用节点组的负载平衡。Cluster Autoscaler 会尝试平衡相似节点组中的节点数，避免某些节点组扩容过多。
	•	默认值：false
	•	示例：--balance-similar-node-groups=true
	8.	–skip-nodes-with-local-storage
	•	描述：是否跳过带有本地存储的节点，以防止缩容时数据丢失。
	•	默认值：false
	•	示例：--skip-nodes-with-local-storage=true
	9.	–expander
	•	描述：指定扩容策略。常见选项包括：
	•	least-waste：优先选择浪费资源最少的节点组。
	•	random：随机选择节点组进行扩展。
	•	most-pods：优先选择可以调度最多 Pod 的节点组。
	•	示例：--expander=least-waste
	10.	–max-empty-bulk-delete
	•	描述：在一次缩容操作中最多可以删除的空闲节点数量。
	•	默认值：10
	•	示例：--max-empty-bulk-delete=5
	11.	–new-pod-scale-up-delay
	•	描述：当新的 Pod 无法调度时，等待多久后开始扩展节点。
	•	默认值：0s（即不延迟）
	•	示例：--new-pod-scale-up-delay=30s
	12.	–scan-interval
	•	描述：Cluster Autoscaler 进行扩缩容操作的扫描间隔。
	•	默认值：10s
	•	示例：--scan-interval=10s
	13.	–scale-down-candidates-pool-min-count
	•	描述：缩容候选节点的最小数量。如果候选节点数少于这个值，缩容将不会执行。
	•	默认值：50
	•	示例：--scale-down-candidates-pool-min-count=30
	14.	–scale-down-candidates-pool-ratio
	•	描述：缩容候选节点池的比例，表示可供缩容评估的节点数量占整个集群的百分比。
	•	默认值：0.1（即 10%）
	•	示例：--scale-down-candidates-pool-ratio=0.2
	15.	–write-status-configmap
	•	描述：是否将当前状态写入 ConfigMap 中，用于调试和监控。
	•	默认值：true
	•	示例：--write-status-configmap=false
