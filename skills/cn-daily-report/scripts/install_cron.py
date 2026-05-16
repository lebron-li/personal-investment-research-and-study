# -*- coding: utf-8 -*-
"""
定时任务安装脚本
将 cron 配置注册到 OpenClaw
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  A 股持仓日报 - 定时任务安装")
print("=" * 60)

# 加载 cron 配置
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'openclaw_cron.json')

with open(config_path, 'r', encoding='utf-8') as f:
    cron_config = json.load(f)

print(f"\n📋 检测到 {len(cron_config['cron_jobs'])} 个定时任务:\n")

for job in cron_config['cron_jobs']:
    schedule = job['schedule']
    print(f"  [{job['enabled'] and '✅' or '❌'}] {job['name']}")
    print(f"      Cron: {schedule['cron']} (时区：{schedule['timezone']})")
    print(f"      说明：{job['description']}")
    print()

print("-" * 60)
print("\n⚙️  配置信息:")
print(f"  时区：{cron_config['global_settings']['timezone']}")
print(f"  Python: {cron_config['global_settings']['python_path']}")
print(f"  日志目录：{cron_config['global_settings']['log_dir']}")
print()

# 创建日志目录
log_dir = cron_config['global_settings']['log_dir']
os.makedirs(log_dir, exist_ok=True)
print(f"✅ 日志目录已创建：{log_dir}")

print("\n" + "=" * 60)
print("  安装说明")
print("=" * 60)

print("""
📝 要将这些定时任务注册到 OpenClaw，请执行以下步骤:

方法 1: 使用 OpenClaw 配置文件

1. 打开你的 OpenClaw 配置文件 (通常位于 ~/.openclaw/config.json)

2. 添加或更新 "cron" 部分:

   {
     "cron": [
       {
         "name": "📊 A 股持仓午间快评",
         "schedule": "35 11 * * 1-5",
         "command": "python C:\\\\Users\\\\<NAME>\\\\.openclaw\\\\workspace\\\\skills\\\\cn-daily-report\\\\scripts\\\\run_report.py noon",
         "timezone": "Asia/Shanghai",
         "enabled": true
       },
       {
         "name": "📊 A 股持仓晚间复盘",
         "schedule": "30 15 * * 1-5",
         "command": "python C:\\\\Users\\\\<NAME>\\\\.openclaw\\\\workspace\\\\skills\\\\cn-daily-report\\\\scripts\\\\run_report.py evening",
         "timezone": "Asia/Shanghai",
         "enabled": true
       },
       {
         "name": "🚨 A 股持仓紧急预警",
         "schedule": "0,30 9-15 * * 1-5",
         "command": "python C:\\\\Users\\\\<NAME>\\\\.openclaw\\\\workspace\\\\skills\\\\cn-daily-report\\\\scripts\\\\run_report.py emergency",
         "timezone": "Asia/Shanghai",
         "enabled": true
       }
     ]
   }

3. 保存并重启 OpenClaw

方法 2: 使用 OpenClaw 命令 (如果支持)

在 OpenClaw 中执行:
  /cron add --name "午间快评" --schedule "35 11 * * 1-5" --command "python ..."
  /cron add --name "晚间复盘" --schedule "30 15 * * 1-5" --command "python ..."
  /cron add --name "紧急预警" --schedule "0,30 9-15 * * 1-5" --command "python ..."

方法 3: 使用 Windows 任务计划程序

运行以下命令导入任务:
  schtasks /Create /XML "C:\\Users\\<NAME>\\.openclaw\\workspace\\skills\\cn-daily-report\\config\\windows_tasks.xml"

注：Windows 任务计划程序的 XML 文件需要额外生成

""")

print("=" * 60)
print("  验证安装")
print("=" * 60)

print("""
安装完成后，可以通过以下方式验证:

1. 手动运行一次:
   python run_report.py noon

2. 等待下一个交易日 11:35，检查是否自动执行

3. 查看日志文件:
   C:\\Users\\<NAME>\\.openclaw\\workspace\\skills\\cn-daily-report\\logs\\

4. 检查飞书是否收到推送

""")

print("=" * 60)
print("  配置完成!")
print("=" * 60)

# 输出配置摘要
summary = {
    "status": "ready",
    "jobs_count": len(cron_config['cron_jobs']),
    "timezone": "Asia/Shanghai",
    "feishu_chat_id": "oc_0d8760ab9b20345f32d4219973d4cc43",
    "report_output": "C:\\Users\\<NAME>\\Desktop\\持仓日报\\",
    "next_run": {
        "noon": "下一个交易日 11:35",
        "evening": "下一个交易日 15:30",
        "emergency": "交易时段每 30 分钟"
    }
}

print("\n📊 配置摘要:")
print(json.dumps(summary, ensure_ascii=False, indent=2))
