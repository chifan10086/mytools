#grep 后批量替换

grep -rl 'pattern' /path/to/search/ | xargs sed -i 's/old-text/new-text/g'

使用 bash 循环
假设你要将当前目录下所有文件夹的前缀从 old_prefix_ 更改为 new_prefix_，你可以使用以下命令：

for dir in old_prefix_*; do
    mv "$dir" "new_prefix_${dir#old_prefix_}"
done
for dir in old_prefix_*：循环遍历所有以 old_prefix_ 开头的文件夹。
mv "$dir" "new_prefix_${dir#old_prefix_}"：使用 ${dir#old_prefix_} 去掉原始名称中的前缀并添加新前缀。
