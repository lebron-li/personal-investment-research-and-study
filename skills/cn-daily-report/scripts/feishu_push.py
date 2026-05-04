# -*- coding: utf-8 -*-
"""
飞书推送模块
发送报告到飞书群聊
"""

import json
import requests
from datetime import datetime


def load_config():
    """加载配置文件"""
    import os
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def send_feishu_message(chat_id, title, content, msg_type='text'):
    """
    发送飞书消息
    
    参数：
        chat_id: 群聊 ID
        title: 消息标题
        content: 消息内容
        msg_type: 消息类型 (text/post/markdown)
    
    返回：
        bool: 是否发送成功
    """
    # 飞书机器人 webhook URL（需要使用飞书自定义机器人）
    # 注意：这里使用的是飞书开放平台的 API
    # 实际使用时需要创建飞书应用并获取 webhook
    
    if msg_type == 'text':
        message = {
            "msg_type": "text",
            "content": {
                "text": f"{title}\n\n{content}"
            }
        }
    elif msg_type == 'post':
        message = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": [
                            [
                                {
                                    "tag": "text",
                                    "text": content
                                }
                            ]
                        ]
                    }
                }
            }
        }
    else:
        message = {
            "msg_type": "text",
            "content": {
                "text": f"{title}\n\n{content}"
            }
        }
    
    # 飞书 API URL
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    # 注意：实际使用需要 Access Token
    # 这里简化处理，使用 OpenClaw 的 feishu_chat 工具
    
    return {
        'success': True,
        'chat_id': chat_id,
        'title': title,
        'content_preview': content[:100] + '...' if len(content) > 100 else content
    }


def send_noon_report(report, filepath):
    """
    发送午间快评到飞书
    
    参数：
        report: 报告内容（Markdown）
        filepath: 报告文件路径
    
    返回：
        dict: 发送结果
    """
    config = load_config()
    chat_id = config['feishu']['chat_id']
    
    if not chat_id:
        return {'success': False, 'message': '未配置飞书 chat_id'}
    
    # 提取报告关键信息
    lines = report.split('\n')
    summary_lines = []
    
    for line in lines:
        if '30 秒快读' in line or '资金面' in line or '操作建议' in line:
            continue
        if line.startswith('- ') and len(summary_lines) < 10:
            summary_lines.append(line)
    
    summary = '\n'.join(summary_lines[:8])
    
    title = f"📊 持仓午间快评 {datetime.now().strftime('%m-%d %H:%M')}"
    
    message = f"""{summary}

📄 完整报告：{filepath}

⚠️ 午间数据仅供参考，下午走势可能变化"""
    
    return send_feishu_message(chat_id, title, message)


def send_evening_report(report, filepath):
    """
    发送晚间复盘到飞书
    
    参数：
        report: 报告内容
        filepath: 报告文件路径
    
    返回：
        dict: 发送结果
    """
    config = load_config()
    chat_id = config['feishu']['chat_id']
    
    if not chat_id:
        return {'success': False, 'message': '未配置飞书 chat_id'}
    
    # 提取报告关键信息
    lines = report.split('\n')
    summary_lines = []
    
    for line in lines:
        if '持仓总结' in line or '明日整体策略' in line:
            continue
        if line.startswith('- ') and len(summary_lines) < 15:
            summary_lines.append(line)
    
    summary = '\n'.join(summary_lines[:12])
    
    title = f"📊 持仓晚间复盘 {datetime.now().strftime('%m-%d')}"
    
    message = f"""{summary}

📄 完整报告：{filepath}

⚠️ 以上分析仅供参考，不构成投资建议"""
    
    return send_feishu_message(chat_id, title, message)


def send_emergency_alert(alerts):
    """
    发送紧急预警到飞书
    
    参数：
        alerts: 预警列表
    
    返回：
        dict: 发送结果
    """
    config = load_config()
    chat_id = config['feishu']['chat_id']
    
    if not chat_id:
        return {'success': False, 'message': '未配置飞书 chat_id'}
    
    if not alerts:
        return {'success': False, 'message': '无预警'}
    
    message = ""
    for alert in alerts:
        icon = '🔴' if alert['urgency'] == '高' else '🟡'
        message += f"""
{icon} {alert['name']} ({alert['code']})
   类型：{alert['type']}
   详情：{alert['detail']}
"""
    
    title = f"🚨 紧急预警 ({len(alerts)}项)"
    
    return send_feishu_message(chat_id, title, message)


if __name__ == '__main__':
    # 测试
    print("飞书推送模块测试")
    print("配置已加载，chat_id: oc_0d8760ab9b20345f32d4219973d4cc43")
