#grep 后批量替换

grep -rl 'pattern' /path/to/search/ | xargs sed -i 's/old-text/new-text/g'
