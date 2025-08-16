import os
import re
import time
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from socks import create_connection, PROXY_TYPES
import socket
from urllib.parse import urlparse

# 全局配置
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
TIMEOUT = 15  # 单次请求超时时间
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

def parse_proxy(proxy_str, protocol):
    """解析代理字符串并返回格式化代理地址"""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    
    # 处理带协议前缀的代理
    if "://" in proxy_str:
        parts = proxy_str.split("://", 1)
        return f"{parts[0]}://{parts[1]}"
    
    # 处理IP:PORT格式
    if ":" in proxy_str:
        return f"{protocol}://{proxy_str}"
    
    return None

def test_connection(proxy, test_url, protocol, max_retries=0):
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

def test_download_speed(proxy, test_url, protocol, max_retries=0):
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

def process_file(file_path, protocol):
    """处理代理文件并返回有效代理列表"""
    valid_proxies = []
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return valid_proxies
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    for line in lines:
        proxy = parse_proxy(line, protocol)
        if proxy:
            valid_proxies.append(proxy)
    
    return valid_proxies

def main():
    print("=" * 50)
    print("代理工具 v1.0")
    print("1. 代理验证 (存活检测)")
    print("2. 代理测速 (下载速度)")
    print("=" * 50)
    
    choice = input("请选择功能 (1/2): ").strip()
    
    if choice == '1':
        file_path = input("请输入代理文件路径: ").strip()
        print("可选协议: http, https, socks4, socks5, all")
        protocol_choice = input("请选择协议: ").lower().strip()
        
        protocols = []
        if protocol_choice == 'all':
            protocols = ['http', 'https', 'socks4', 'socks5']
        elif protocol_choice in ['http', 'https', 'socks4', 'socks5']:
            protocols = [protocol_choice]
        else:
            print("无效的协议选择!")
            return
        
        test_url = input("请输入测试URL: ").strip()
        max_retries = int(input("输入重试次数 (0=不重试): "))
        threads = int(input("输入线程数: "))
        
        # 处理所有协议
        all_proxies = []
        for proto in protocols:
            all_proxies.extend(process_file(file_path, proto))
        
        print(f"找到 {len(all_proxies)} 个代理，开始验证...")
        
        valid_proxies = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    test_connection, 
                    proxy, 
                    test_url, 
                    proxy.split("://")[0],
                    max_retries
                ): proxy for proxy in all_proxies
            }
            
            for future in concurrent.futures.as_completed(futures):
                proxy = futures[future]
                try:
                    success, latency = future.result()
                    if success:
                        print(f"[✓] {proxy} 有效 | 延迟: {latency}ms")
                        valid_proxies.append(proxy)
                    else:
                        print(f"[✗] {proxy} 无效")
                except Exception as e:
                    print(f"[!] {proxy} 测试出错: {str(e)}")
        
        # 保存结果
        with open("http.txt", "w", encoding="utf-8") as f:
            for proxy in valid_proxies:
                f.write(f"{proxy}\n")
        print(f"验证完成! 有效代理已保存到 http.txt (总数: {len(valid_proxies)})")
    
    elif choice == '2':
        file_path = input("请输入代理文件路径: ").strip()
        print("可选协议: http, https, socks4, socks5, all")
        protocol_choice = input("请选择协议: ").lower().strip()
        
        protocols = []
        if protocol_choice == 'all':
            protocols = ['http', 'https', 'socks4', 'socks5']
        elif protocol_choice in ['http', 'https', 'socks4', 'socks5']:
            protocols = [protocol_choice]
        else:
            print("无效的协议选择!")
            return
        
        test_url = input("请输入测速文件URL: ").strip()
        max_retries = int(input("输入重试次数 (0=不重试): "))
        threads = int(input("输入线程数: "))
        
        # 处理所有协议
        all_proxies = []
        for proto in protocols:
            all_proxies.extend(process_file(file_path, proto))
        
        print(f"找到 {len(all_proxies)} 个代理，开始测速...")
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(
                    test_download_speed, 
                    proxy, 
                    test_url, 
                    proxy.split("://")[0],
                    max_retries
                ): proxy for proxy in all_proxies
            }
            
            for future in concurrent.futures.as_completed(futures):
                proxy = futures[future]
                try:
                    success, speed = future.result()
                    if success:
                        print(f"[✓] {proxy} 速度: {speed} KB/s")
                        results.append((proxy, speed))
                    else:
                        print(f"[✗] {proxy} 测速失败")
                except Exception as e:
                    print(f"[!] {proxy} 测速出错: {str(e)}")
        
        # 按速度排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        # 保存结果
        with open("cs.txt", "w", encoding="utf-8") as f:
            for proxy, speed in results:
                f.write(f"{proxy} | {speed} KB/s\n")
        print(f"测速完成! 结果已保存到 cs.txt (总数: {len(results)})")
    
    else:
        print("无效选择!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已终止")
    except Exception as e:
        print(f"发生错误: {str(e)}")meout,
                stream=True,
                headers=get_random_headers(),
                verify=False  # 关键修改：忽略证书验证
            )
            response.raise_for_status()
            
            # 读取1MB数据计算速度
            chunk_size = 1024
            total_bytes = 0
            max_bytes = 1024 * 1024  # 1MB
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                total_bytes += len(chunk)
                if total_bytes >= max_bytes:
                    break
            
            elapsed = time.time() - start_time
            speed = total_bytes / elapsed / 1024  # KB/s
            return prefix, round(speed, 2)
        except Exception as e:
            # 忽略所有连接错误
            return None, 0
    
    def test_proxy(proxy):
        """测试单个代理的速度"""
        proxy_results = []
        fastest_speed = 0
        fastest_protocol = ""
        
        # 测试所有选择的协议
        for protocol in selected_protocols:
            prefix, speed = test_speed_for_protocol(proxy, protocol)
            if speed > 0:
                # 记录区域2结果
                proxy_addr = f"{prefix}{proxy}"
                region2_results.append((proxy_addr, speed))
                proxy_results.append((prefix, speed))
                
                # 记录最快协议
                if speed > fastest_speed:
                    fastest_speed = speed
                    fastest_protocol = prefix
        
        # 如果有可用的协议，记录区域1结果
        if fastest_speed > 0:
            region1_results.append((proxy, fastest_speed, fastest_protocol))
        
        return proxy, proxy_results
    
    # 进度计数器
    processed = 0
    total = len(proxies)
    
    def update_progress():
        nonlocal processed
        processed += 1
        if processed % 50 == 0 or processed == total:
            print(f"已处理: {processed}/{total} ({processed/total*100:.1f}%)")
    
    # 使用线程池处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for proxy in proxies:
            future = executor.submit(test_proxy, proxy)
            future.add_done_callback(lambda x: update_progress())
            futures.append(future)
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            pass  # 结果已经在回调中收集
    
    # 按速度降序排序
    region1_results.sort(key=lambda x: x[1], reverse=True)
    region2_results.sort(key=lambda x: x[1], reverse=True)
    
    # 保存测速结果
    output_file = os.path.join(os.getcwd(), 'cs.txt')
    with open(output_file, 'w') as f:
        # 区域1: IP:端口 速度
        f.write("[区域1: IP:PORT 速度]\n")
        f.write("=" * 50 + "\n")
        for proxy, speed, protocol in region1_results:
            f.write(f"{proxy} - {speed} KB/s\n")
        
        # 区域2: 协议:IP:端口 速度
        f.write("\n\n[区域2: 协议:IP:PORT 速度]\n")
        f.write("=" * 50 + "\n")
        for proxy_addr, speed in region2_results:
            f.write(f"{proxy_addr} - {speed} KB/s\n")
    
    # 统计信息
    valid_proxies_count = len(region1_results)
    total_speeds = sum(item[1] for item in region1_results)
    avg_speed = total_speeds / valid_proxies_count if valid_proxies_count > 0 else 0
    
    print(f"\n测速完成！有效代理数: {valid_proxies_count}")
    print(f"最高速度: {region1_results[0][1] if region1_results else 0} KB/s")
    print(f"平均速度: {avg_speed:.2f} KB/s")
    print(f"结果已保存到: {output_file}")

def detect_proxy_countries():
    # 选择代理文件
    file_path = input("请输入代理文件路径: ").strip()
    if not os.path.exists(file_path):
        print("文件不存在！")
        return
    
    # 读取代理列表
    with open(file_path, 'r') as f:
        proxies = [line.strip() for line in f.readlines() if line.strip()]
    
    if not proxies:
        print("文件中没有找到有效的代理")
        return
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认50): ") or 50)
    except:
        max_workers = 50
    
    print(f"开始检测 {len(proxies)} 个代理的国家信息，使用 {max_workers} 线程...")
    
    # 存储结果：国家 -> [代理列表]
    country_proxies = {}
    
    # 提取IP地址的正则表达式
    ip_pattern = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    
    def extract_ip(proxy_str):
        """从代理字符串中提取IP地址"""
        match = ip_pattern.search(proxy_str)
        if match:
            return match.group(0)
        # 尝试解析主机名
        parts = proxy_str.split(':')
        if len(parts) >= 2:
            host = parts[0]
            try:
                return socket.gethostbyname(host)
            except:
                pass
        return None
    
    def get_country(proxy):
        """获取代理所属国家"""
        try:
            ip = extract_ip(proxy)
            if not ip:
                return "Unknown", proxy
            
            # 使用ipwhois查询国家信息
            obj = IPWhois(ip)
            results = obj.lookup_rdap()
            country = results.get('asn_country', 'Unknown')
            
            # 如果未获取到国家信息，尝试备用方法
            if country == 'Unknown':
                try:
                    # 使用HTTP而不是HTTPS，避免证书问题
                    response = requests.get(f"http://ipinfo.io/{ip}/country", timeout=5)
                    if response.status_code == 200:
                        country = response.text.strip() or 'Unknown'
                except:
                    pass
            
            return country, proxy
        except:
            return "Unknown", proxy
    
    # 进度计数器
    processed = 0
    total = len(proxies)
    
    def update_progress():
        nonlocal processed
        processed += 1
        if processed % 50 == 0 or processed == total:
            print(f"已处理: {processed}/{total} ({processed/total*100:.1f}%)")
    
    # 使用线程池处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for proxy in proxies:
            future = executor.submit(get_country, proxy)
            future.add_done_callback(lambda x: update_progress())
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            country, proxy = future.result()
            if country not in country_proxies:
                country_proxies[country] = []
            country_proxies[country].append(proxy)
    
    # 按国家名称排序
    sorted_countries = sorted(country_proxies.keys())
    
    # 保存结果
    output_file = os.path.join(os.getcwd(), 'gj.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        for country in sorted_countries:
            f.write(f"{country}:\n")
            for proxy in country_proxies[country]:
                f.write(f"{proxy}\n")
            f.write("\n")
    
    print(f"国家检测完成！已检测 {len(proxies)} 个代理")
    print(f"发现 {len(country_proxies)} 个国家")
    print(f"结果已保存到: {output_file}")

def main():
    while True:
        print("\n" + "="*50)
        print("代理工具菜单")
        print("1. 验证代理存活 (支持HTTP/HTTPS/SOCKS4/SOCKS5)")
        print("2. 测速代理下载速度 (支持HTTP/HTTPS/SOCKS4/SOCKS5/自动识别)")
        print("3. 检测代理国家")
        print("4. 退出")
        print("="*50)
        
        choice = input("请选择功能 (1/2/3/4): ").strip()
        
        if choice == '1':
            validate_proxies()
        elif choice == '2':
            speed_test_proxies()
        elif choice == '3':
            detect_proxy_countries()
        elif choice == '4':
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main()
