k8s命令自动补全  
```
yum install -y bash-completion
source /usr/share/bash-completion/bash_completion
source <(kubectl completion bash)
echo "source <(kubectl completion bash)" >> ~/.bashrc

```  
对于 基于 Debian/Ubuntu 的发行版，安装命令为：

sudo apt-get install bash-completion -y
对于基于 Fedora/ Red Hat Enterprise Linux 的发行版，命令为：

sudo dnf install bash-completion -y

