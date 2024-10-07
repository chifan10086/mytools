#!/bin/bash
#Mysql批量按日期创建表

# 设置起始和结束日期
start_date="2024-01-01"
end_date="2024-01-10"

# MySQL 连接信息
mysql_user="root"
mysql_password="password"
mysql_database="mydb"

# 当前日期
current_date="$start_date"

# 循环创建表
while [[ "$current_date" < "$end_date" ]]; do
  # 生成表名
  table_name="my_table_$(date -d "$current_date" '+%Y%m%d')"

  # 生成创建表的 SQL
  create_table_sql="CREATE TABLE IF NOT EXISTS $table_name (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );"

  # 执行创建表的 SQL
  echo "$create_table_sql" | mysql -u "$mysql_user" -p"$mysql_password" "$mysql_database"

  # 日期加1天
  current_date=$(date -d "$current_date +1 day" '+%Y-%m-%d')
done

