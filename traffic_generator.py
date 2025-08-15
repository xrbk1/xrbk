import os
import sys
import time
import random
import threading
import requests
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

app = Flask(__name__)

class TrafficGenerator:
    def __init__(self):
        self.proxies = []
        self.user_agents = []
        self.active = False
        self.paused = False
        self.start_time = None
        self.duration = 0
        self.total_requests = 0
        self.successful_requests = 0
        self.lock = threading.Lock()
        self.executor = None
        self.thread_count = 50  # 默认线程数
        
        # 初始化User-Agents
        self._load_default_user_agents()
        
    def _load_default_user_agents(self):
        """加载默认的User-Agents列表"""
        self.user_agents = [
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5; rv:109.0) Gecko/20100101 Firefox/116.0",
            "Mozilla/5.0 (X11; Linux i686; rv:109.0) Gecko/20100101 Firefox/116.0",
            
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203",
            
            # Mobile
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36"
        ]
    
    def load_proxies(self, file_path):
        """从文件加载代理列表"""
        if not os.path.exists(file_path):
            print(f"代理文件不存在: {file_path}")
            return False
        
        try:
            with open(file_path, 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]
            
            if not proxies:
                print("代理文件为空")
                return False
                
            self.proxies = proxies
            print(f"成功加载 {len(proxies)} 个代理")
            return True
        except Exception as e:
            print(f"加载代理文件错误: {str(e)}")
            return False
    
    def get_random_ua(self):
        """获取随机User-Agent"""
        return random.choice(self.user_agents)
    
    def get_random_proxy(self):
        """获取随机代理"""
        if not self.proxies:
            return None
        return random.choice(self.proxies)
    
    def send_request(self, target_url):
        """发送HTTP请求到目标URL"""
        if self.paused:
            return
            
        headers = {'User-Agent': self.get_random_ua()}
        proxy = self.get_random_proxy()
        proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'} if proxy else None
        
        try:
            response = requests.get(
                target_url, 
                headers=headers, 
                proxies=proxies,
                timeout=10
            )
            
            with self.lock:
                self.total_requests += 1
                if response.status_code == 200:
                    self.successful_requests += 1
                    
            return response.status_code
        except Exception as e:
            with self.lock:
                self.total_requests += 1
            return str(e)
    
    def worker(self, target_url):
        """工作线程函数"""
        while self.active:
            if self.paused:
                time.sleep(0.5)
                continue
                
            self.send_request(target_url)
            
            # 随机延迟，避免过于频繁的请求
            time.sleep(random.uniform(0.1, 0.5))
    
    def start(self, target_url, duration_minutes=10, thread_count=50, proxy_file=None):
        """启动流量生成"""
        if proxy_file:
            self.load_proxies(proxy_file)
            
        if not self.active:
            self.active = True
            self.paused = False
            self.start_time = datetime.now()
            self.duration = duration_minutes
            self.thread_count = thread_count
            self.total_requests = 0
            self.successful_requests = 0
            
            # 创建线程池执行器
            self.executor = ThreadPoolExecutor(max_workers=thread_count)
            
            # 启动多个工作线程
            for _ in range(thread_count):
                self.executor.submit(self.worker, target_url)
            
            # 设置定时停止
            if duration_minutes > 0:
                stop_time = self.start_time + timedelta(minutes=duration_minutes)
                threading.Timer(
                    duration_minutes * 60, 
                    self.stop
                ).start()
                
            print(f"任务已启动，线程数: {thread_count}, 持续时间: {duration_minutes}分钟")
            return True
        return False
    
    def pause(self):
        """暂停任务"""
        if self.active and not self.paused:
            self.paused = True
            print("任务已暂停")
            return True
        return False
    
    def resume(self):
        """恢复任务"""
        if self.active and self.paused:
            self.paused = False
            print("任务已恢复")
            return True
        return False
    
    def stop(self):
        """停止任务"""
        if self.active:
            self.active = False
            self.paused = False
            
            # 关闭线程池
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            
            # 输出统计信息
            elapsed = datetime.now() - self.start_time
            print("\n任务已停止")
            print(f"总运行时间: {elapsed}")
            print(f"总请求数: {self.total_requests}")
            print(f"成功请求: {self.successful_requests}")
            if self.total_requests > 0:
                print(f"成功率: {self.successful_requests/self.total_requests*100:.2f}%")
            return True
        return False
    
    def status(self):
        """获取当前状态"""
        elapsed = 0
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).seconds
            
        return {
            'active': self.active,
            'paused': self.paused,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'duration_minutes': self.duration,
            'elapsed_seconds': elapsed,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'proxy_count': len(self.proxies),
            'thread_count': self.thread_count
        }

# 创建流量生成器实例
generator = TrafficGenerator()

# API路由
@app.route('/start', methods=['POST'])
def start_task():
    data = request.json
    target_url = data.get('url')
    duration = data.get('duration', 10)
    thread_count = data.get('thread_count', 50)
    proxy_file = data.get('proxy_file')
    
    if not target_url:
        return jsonify({'error': '缺少目标URL'}), 400
    
    # 验证线程数
    try:
        thread_count = int(thread_count)
        if thread_count < 1 or thread_count > 500:
            return jsonify({'error': '线程数必须在1-500之间'}), 400
    except:
        return jsonify({'error': '无效的线程数'}), 400
    
    if generator.start(target_url, duration, thread_count, proxy_file):
        return jsonify({'message': '任务已启动', 'status': generator.status()})
    return jsonify({'error': '任务已在运行中'}), 400

@app.route('/pause', methods=['POST'])
def pause_task():
    if generator.pause():
        return jsonify({'message': '任务已暂停', 'status': generator.status()})
    return jsonify({'error': '无法暂停任务'}), 400

@app.route('/resume', methods=['POST'])
def resume_task():
    if generator.resume():
        return jsonify({'message': '任务已恢复', 'status': generator.status()})
    return jsonify({'error': '无法恢复任务'}), 400

@app.route('/stop', methods=['POST'])
def stop_task():
    if generator.stop():
        return jsonify({'message': '任务已停止', 'status': generator.status()})
    return jsonify({'error': '没有正在运行的任务'}), 400

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify(generator.status())

# 控制台界面
def console_interface():
    print("网站流量测试工具")
    print("=" * 50)
    
    while True:
        print("\n菜单:")
        print("1. 启动任务")
        print("2. 暂停任务")
        print("3. 恢复任务")
        print("4. 停止任务")
        print("5. 查看状态")
        print("6. 退出")
        
        choice = input("请选择操作: ")
        
        if choice == '1':
            target_url = input("目标URL: ")
            duration = input("持续时间(分钟, 默认10): ")
            thread_count = input("线程数(默认50): ")
            proxy_file = input("代理文件路径(可选): ")
            
            try:
                duration = int(duration) if duration.strip() else 10
            except:
                duration = 10
                
            try:
                thread_count = int(thread_count) if thread_count.strip() else 50
                if thread_count < 1:
                    thread_count = 1
                elif thread_count > 500:
                    thread_count = 500
            except:
                thread_count = 50
                
            if proxy_file.strip() == '':
                proxy_file = None
                
            generator.start(target_url, duration, thread_count, proxy_file)
            
        elif choice == '2':
            if generator.pause():
                print("任务已暂停")
            else:
                print("无法暂停任务")
                
        elif choice == '3':
            if generator.resume():
                print("任务已恢复")
            else:
                print("无法恢复任务")
                
        elif choice == '4':
            if generator.stop():
                print("任务已停止")
            else:
                print("没有正在运行的任务")
                
        elif choice == '5':
            status = generator.status()
            print("\n当前状态:")
            print(f"运行中: {'是' if status['active'] else '否'}")
            print(f"已暂停: {'是' if status['paused'] else '否'}")
            print(f"开始时间: {status['start_time']}")
            print(f"持续时间: {status['duration_minutes']}分钟")
            print(f"已运行: {status['elapsed_seconds']//60}分{status['elapsed_seconds']%60}秒")
            print(f"总请求数: {status['total_requests']}")
            print(f"成功请求: {status['successful_requests']}")
            print(f"代理数量: {status['proxy_count']}")
            print(f"线程数: {status['thread_count']}")
            
        elif choice == '6':
            if generator.active:
                generator.stop()
            print("退出程序")
            break
            
        else:
            print("无效选择")

if __name__ == '__main__':
    # 在单独线程中启动API服务
    api_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    )
    api_thread.daemon = True
    api_thread.start()
    
    print(f"API服务已启动: http://localhost:5000")
    print("使用以下API端点控制流量生成:")
    print("POST /start - 启动任务 (参数: url, duration, thread_count, proxy_file)")
    print("POST /pause - 暂停任务")
    print("POST /resume - 恢复任务")
    print("POST /stop - 停止任务")
    print("GET /status - 获取当前状态")
    print("\n同时提供控制台界面:")
    
    # 启动控制台界面
    console_interface()
