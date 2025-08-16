import os
import time
import threading
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import uuid
import signal
import atexit
import logging
from werkzeug.utils import secure_filename

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("proxy_tool.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ProxyTool")

# 全局配置
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
TIMEOUT = 4
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'txt'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = 'supersecretkey'

# 全局会话对象
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

# 配置重试策略
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
SESSION.mount("http://", adapter)
SESSION.mount("https://", adapter)

# 任务状态字典
active_tasks = {}
task_lock = threading.Lock()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_proxy(proxy_str, selected_protocols):
    """解析代理字符串并返回格式化代理地址"""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return []
    
    proxies = []
    
    # 处理带协议前缀的代理
    if "://" in proxy_str:
        parts = proxy_str.split("://", 1)
        protocol = parts[0].lower()
        address = parts[1].strip()
        
        # 如果协议在选择的协议列表中，直接添加
        if protocol in selected_protocols:
            proxies.append(f"{protocol}://{address}")
    else:
        # 处理IP:PORT格式 - 为所有选择的协议生成代理
        for protocol in selected_protocols:
            proxies.append(f"{protocol}://{proxy_str}")
    
    return proxies

def test_connection(proxy, test_url, max_retries=0):
    """测试代理连接性"""
    proxies = {}
    proxy_type = proxy.split("://")[0].lower()
    
    # 设置代理字典
    if proxy_type in ['http', 'https']:
        proxies = {"http": proxy, "https": proxy}
    elif proxy_type in ['socks4', 'socks5']:
        proxies = {"http": f"socks5://{proxy.split('://')[1]}", 
                  "https": f"socks5://{proxy.split('://')[1]}"}
    
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            response = SESSION.get(
                test_url, 
                proxies=proxies, 
                timeout=TIMEOUT,
                verify=False  # 忽略SSL证书验证
            )
            response.raise_for_status()
            latency = int((time.time() - start_time) * 1000)  # 毫秒
            return True, latency
        except Exception as e:
            if attempt >= max_retries:
                return False, 0
    return False, 0

def test_download_speed(proxy, test_url, max_retries=0):
    """测试代理下载速度"""
    proxies = {}
    proxy_type = proxy.split("://")[0].lower()
    
    if proxy_type in ['http', 'https']:
        proxies = {"http": proxy, "https": proxy}
    elif proxy_type in ['socks4', 'socks5']:
        proxies = {"http": f"socks5://{proxy.split('://')[1]}", 
                  "https": f"socks5://{proxy.split('://')[1]}"}
    
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            with SESSION.get(
                test_url, 
                proxies=proxies, 
                stream=True,
                timeout=TIMEOUT,
                verify=False
            ) as response:
                response.raise_for_status()
                total_bytes = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        total_bytes += len(chunk)
                        # 测试10秒后中断
                        if time.time() - start_time > 10:
                            break
            
            duration = time.time() - start_time
            speed = total_bytes / duration / 1024  # KB/s
            return True, round(speed, 2)
        except Exception as e:
            if attempt >= max_retries:
                return False, 0
    return False, 0

def process_file(file_path, selected_protocols):
    """处理代理文件并返回有效代理列表"""
    valid_proxies = []
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return valid_proxies
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for line in lines:
            proxies = parse_proxy(line, selected_protocols)
            valid_proxies.extend(proxies)
    except Exception as e:
        logger.error(f"处理文件出错: {str(e)}")
    
    return valid_proxies

def run_verification_task(task_id, file_path, selected_protocols, test_url, max_retries, max_latency, threads):
    """运行验证任务"""
    with task_lock:
        active_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "total": 0,
            "completed": 0,
            "valid": 0,
            "result_file": None
        }
    
    # 处理文件
    all_proxies = process_file(file_path, selected_protocols)
    total_proxies = len(all_proxies)
    
    with task_lock:
        active_tasks[task_id]["total"] = total_proxies
        active_tasks[task_id]["progress"] = 0
    
    if total_proxies == 0:
        with task_lock:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["message"] = "未找到有效代理"
        return
    
    logger.info(f"任务 {task_id} 开始验证 {total_proxies} 个代理...")
    
    valid_proxies = []
    completed = 0
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    test_connection, 
                    proxy, 
                    test_url,
                    max_retries
                ): proxy for proxy in all_proxies
            }
            
            for future in concurrent.futures.as_completed(futures):
                proxy = futures[future]
                try:
                    success, latency = future.result()
                    completed += 1
                    
                    if success:
                        if max_latency == 0 or latency <= max_latency:
                            valid_proxies.append(proxy)
                            with task_lock:
                                active_tasks[task_id]["valid"] += 1
                    
                    # 更新进度
                    with task_lock:
                        active_tasks[task_id]["completed"] = completed
                        active_tasks[task_id]["progress"] = int((completed / total_proxies) * 100)
                        
                except Exception as e:
                    logger.error(f"测试代理出错: {str(e)}")
                    completed += 1
                    with task_lock:
                        active_tasks[task_id]["completed"] = completed
                        active_tasks[task_id]["progress"] = int((completed / total_proxies) * 100)
    except Exception as e:
        logger.error(f"任务执行出错: {str(e)}")
        with task_lock:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["message"] = f"任务执行出错: {str(e)}"
        return
    
    # 保存结果
    result_filename = f"http_{task_id}.txt"
    result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)
    
    try:
        with open(result_path, 'w', encoding="utf-8") as f:
            for proxy in valid_proxies:
                f.write(f"{proxy}\n")
        
        with task_lock:
            active_tasks[task_id]["status"] = "completed"
            active_tasks[task_id]["result_file"] = result_filename
            active_tasks[task_id]["valid_count"] = len(valid_proxies)
        
        logger.info(f"任务 {task_id} 完成! 有效代理: {len(valid_proxies)}")
    except Exception as e:
        logger.error(f"保存结果出错: {str(e)}")
        with task_lock:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["message"] = f"保存结果出错: {str(e)}"

def run_speed_test_task(task_id, file_path, selected_protocols, test_url, max_retries, threads):
    """运行测速任务"""
    with task_lock:
        active_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "total": 0,
            "completed": 0,
            "result_file": None
        }
    
    # 处理文件
    all_proxies = process_file(file_path, selected_protocols)
    total_proxies = len(all_proxies)
    
    with task_lock:
        active_tasks[task_id]["total"] = total_proxies
        active_tasks[task_id]["progress"] = 0
    
    if total_proxies == 0:
        with task_lock:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["message"] = "未找到有效代理"
        return
    
    logger.info(f"任务 {task_id} 开始测速 {total_proxies} 个代理...")
    
    results = []
    completed = 0
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    test_download_speed, 
                    proxy, 
                    test_url,
                    max_retries
                ): proxy for proxy in all_proxies
            }
            
            for future in concurrent.futures.as_completed(futures):
                proxy = futures[future]
                try:
                    success, speed = future.result()
                    completed += 1
                    
                    if success:
                        results.append((proxy, speed))
                    
                    # 更新进度
                    with task_lock:
                        active_tasks[task_id]["completed"] = completed
                        active_tasks[task_id]["progress"] = int((completed / total_proxies) * 100)
                        
                except Exception as e:
                    logger.error(f"测试代理出错: {str(e)}")
                    completed += 1
                    with task_lock:
                        active_tasks[task_id]["completed"] = completed
                        active_tasks[task_id]["progress"] = int((completed / total_proxies) * 100)
    except Exception as e:
        logger.error(f"任务执行出错: {str(e)}")
        with task_lock:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["message"] = f"任务执行出错: {str(e)}"
        return
    
    # 按速度排序
    results.sort(key=lambda x: x[1], reverse=True)
    
    # 保存结果
    result_filename = f"cs_{task_id}.txt"
    result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)
    
    try:
        with open(result_path, 'w', encoding="utf-8") as f:
            for proxy, speed in results:
                f.write(f"{proxy} | {speed} KB/s\n")
        
        with task_lock:
            active_tasks[task_id]["status"] = "completed"
            active_tasks[task_id]["result_file"] = result_filename
            active_tasks[task_id]["valid_count"] = len(results)
        
        logger.info(f"任务 {task_id} 完成! 有效代理: {len(results)}")
    except Exception as e:
        logger.error(f"保存结果出错: {str(e)}")
        with task_lock:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["message"] = f"保存结果出错: {str(e)}"

def cleanup():
    """清理资源"""
    logger.info("正在清理资源...")
    SESSION.close()
    logger.info("资源清理完成")

# 注册退出处理
atexit.register(cleanup)

# 处理信号
def handle_signal(signum, frame):
    logger.info(f"收到信号 {signum}, 正在退出...")
    cleanup()
    os._exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGHUP, handle_signal)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        # 检查文件上传
        if 'file' not in request.files:
            flash('没有文件部分', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('没有选择文件', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            flash('文件类型不允许', 'danger')
            return redirect(request.url)
        
        # 获取表单数据
        protocol_choice = request.form.get('protocol', 'all').lower()
        test_url = request.form.get('test_url', '').strip()
        max_retries = int(request.form.get('max_retries', 0))
        max_latency = int(request.form.get('max_latency', 0))
        threads = int(request.form.get('threads', 50))
        
        # 验证输入
        if not test_url:
            flash('请输入测试URL', 'danger')
            return redirect(request.url)
        
        # 协议处理
        selected_protocols = []
        if protocol_choice == 'all':
            selected_protocols = ['http', 'https', 'socks4', 'socks5']
        elif protocol_choice in ['http', 'https', 'socks4', 'socks5']:
            selected_protocols = [protocol_choice]
        else:
            flash('无效的协议选择', 'danger')
            return redirect(request.url)
        
        # 创建任务
        task_id = str(uuid.uuid4())
        
        # 启动任务线程
        task_thread = threading.Thread(
            target=run_verification_task,
            args=(task_id, file_path, selected_protocols, test_url, max_retries, max_latency, threads),
            daemon=True
        )
        task_thread.start()
        
        flash(f'任务已启动，ID: {task_id}', 'success')
        return redirect(url_for('task_status', task_id=task_id))
    
    return render_template('verify.html')

@app.route('/speed', methods=['GET', 'POST'])
def speed():
    if request.method == 'POST':
        # 检查文件上传
        if 'file' not in request.files:
            flash('没有文件部分', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('没有选择文件', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            flash('文件类型不允许', 'danger')
            return redirect(request.url)
        
        # 获取表单数据
        protocol_choice = request.form.get('protocol', 'all').lower()
        test_url = request.form.get('test_url', '').strip()
        max_retries = int(request.form.get('max_retries', 0))
        threads = int(request.form.get('threads', 50))
        
        # 验证输入
        if not test_url:
            flash('请输入测试URL', 'danger')
            return redirect(request.url)
        
        # 协议处理
        selected_protocols = []
        if protocol_choice == 'all':
            selected_protocols = ['http', 'https', 'socks4', 'socks5']
        elif protocol_choice in ['http', 'https', 'socks4', 'socks5']:
            selected_protocols = [protocol_choice]
        else:
            flash('无效的协议选择', 'danger')
            return redirect(request.url)
        
        # 创建任务
        task_id = str(uuid.uuid4())
        
        # 启动任务线程
        task_thread = threading.Thread(
            target=run_speed_test_task,
            args=(task_id, file_path, selected_protocols, test_url, max_retries, threads),
            daemon=True
        )
        task_thread.start()
        
        flash(f'任务已启动，ID: {task_id}', 'success')
        return redirect(url_for('task_status', task_id=task_id))
    
    return render_template('speed.html')

@app.route('/status/<task_id>', methods=['GET'])
def task_status(task_id):
    with task_lock:
        task_info = active_tasks.get(task_id, {})
    
    if not task_info:
        flash('任务不存在或已过期', 'danger')
        return redirect(url_for('index'))
    
    return render_template('status.html', task_id=task_id, task_info=task_info)

@app.route('/download/<task_id>', methods=['GET'])
def download_result(task_id):
    with task_lock:
        task_info = active_tasks.get(task_id, {})
    
    if not task_info or task_info['status'] != 'completed' or not task_info['result_file']:
        flash('结果文件不可用', 'danger')
        return redirect(url_for('index'))
    
    return send_from_directory(
        app.config['RESULT_FOLDER'],
        task_info['result_file'],
        as_attachment=True,
        download_name=task_info['result_file']
    )

if __name__ == '__main__':
    # 设置守护进程模式
    logger.info("代理工具Web版启动中...")
    logger.info(f"上传目录: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"结果目录: {app.config['RESULT_FOLDER']}")
    
    # 在后台运行
    try:
        # 使用更可靠的服务器配置
        app.run(
            host='0.0.0.0', 
            port=5000, 
            threaded=True,
            use_reloader=False,
            debug=False
        )
    except Exception as e:
        logger.error(f"服务器启动失败: {str(e)}")
        cleanup()
