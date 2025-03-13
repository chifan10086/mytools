#!/usr/bin/env python3
import re
import jenkins
import requests

# 替换为你的 Jenkins URL、用户名和 API Token
JENKINS_URL = 
USERNAME = 
API_TOKEN = 

# 创建 Jenkins 服务器连接
server = jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=API_TOKEN)

#jobs = server.get_all_jobs()
#jobs = server.get_job_info('bw-nsa-h5-bwgame321')
#for job in jobs:
#    print(f"作业名: {job['name']}, 作业 URL: {job['url']}")
#    print(job)

def deploypro(view_name,lines):
    task__dict = {}
    lines = [x for x in lines if x and x.strip()]
    for line in lines:
      jobs_in_view = server.get_jobs(view_name=view_name)
      try:
          sjob = line.split('-')[2]
      except IndexError:
          return (1, "标签格式不正确\n请核对重新输入", None) 
      pattern = r'.*-'+sjob+'.*'
      for job in jobs_in_view:
          job_name = job['name']
          match = re.match(pattern, job_name)
          if re.match(pattern, job_name):
              #if job_name.split('-')[2] == sjob:
                  task__dict[job_name] = line.strip()
                  print(task__dict[job_name])

    print(task__dict)
    print(len(task__dict))
    if task__dict:
        for job_name, tag in task__dict.items():
            params = {
                       'Tag': tag,  # 替换为实际参数名和值
                         }
            print(server.build_job(job_name, parameters=params))
        return (0, len(task__dict), None)
    else:
        return (2, "Job未找到!!", None)

def deployeks(view_name,lines):
    print(view_name,lines)
    task_dict = {}
    for line in lines:
        jobs_in_view = server.get_jobs(view_name=view_name)
        try:
            sjob = line.split(':')[0]
        except IndexError:
            return (1, "标签格式不正确\n请核对重新输入", None)
        pattern = r'.*'+sjob+'.*'
        for job in jobs_in_view:
            job_name = job['name']
            if re.match(pattern, job_name):
                task_dict[job_name] = line.strip().split(':')[1]
    print(task_dict)
    if task_dict:
        for job_name, tag in task_dict.items():
            params = {
                     'Tag': tag,
                       }
            print(server.build_job(job_name, parameters=params))
        return (0, len(task_dict), None)
    else:
        return (2, "Job未找到!!", None)

#              matched_jobs.append(job_name)
# if matched_jobs:
#          for matched_job in matched_jobs:
#              params = {
#                  'Tag': line,  # 替换为实际参数名和值
#                     }
#              print(server.build_job(matched_job, parameters=params))
#
#              return (0, "执行了", None)
#    else:
#        return (2, "Job未找到!!", None)

# 指定要查询的视图名称
#view_name = 'all' 
# 获取指定视图中的所有作业

# 设置正则表达式以匹配作业名称

# 存储匹配的作业
#matched_jobs = []

# 遍历作业并进行匹配
#for job in jobs_in_view:
#    job_name = job['name']
#    if re.match(pattern, job_name):
#        matched_jobs.append(job_name)

# 输出匹配的作业名称
#if matched_jobs:
#    print(f'{matched_jobs}')
#    print(matched_jobs)
#else:
#    print(f'No jobs matched the pattern in view "{view_name}".')


#job_name = 'admin-uat'  # 替换为你要触发的作业名称

# 定义要传递的参数
#params = {
#    'Tag': '1111admin-uat-20240930-01',  # 替换为实际参数名和值
#}

# 触发作业
#try:
#    server.build_job(job_name, parameters=params)
#    print(f'Job "{job_name}" triggered successfully with parameters: {params}')
#except jenkins.JenkinsException as e:
#    print(f'Error triggering job: {e}')
#namewo = 
lss = ['bw-nsa-brgame-20241018-01', 'bw-nsa-download-20241018-01']

#print(deploypro('BW-Sob-Web','bw-sob-download-20241010-01'))
