import os
import time
import requests
import concurrent.futures
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

def validate_proxies():
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
    
    # 输入验证URL
    test_url = input("请输入要验证的URL: ").strip()
    if not test_url.startswith(('http://', 'https://')):
        test_url = 'http://' + test_url
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认100): ") or 100)
    except:
        max_workers = 100
    
    print(f"开始验证 {len(proxies)} 个代理，使用 {max_workers} 线程...")
    
    valid_proxies = []
    timeout = 10
    
    def check_proxy(proxy):
        try:
            proxies_dict = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            response = requests.get(
                test_url, 
                proxies=proxies_dict, 
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            if response.status_code == 200:
                return proxy
        except:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(check_proxy, proxies))
    
    valid_proxies = [proxy for proxy in results if proxy is not None]
    
    # 保存有效代理
    output_file = os.path.join(os.getcwd(), 'http.txt')
    with open(output_file, 'w') as f:
        f.write('\n'.join(valid_proxies))
    
    print(f"验证完成！有效代理数: {len(valid_proxies)}")
    print(f"结果已保存到: {output_file}")

def speed_test_proxies():
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
    
    # 输入测速URL
    test_url = input("请输入要测速的URL: ").strip()
    if not test_url.startswith(('http://', 'https://')):
        test_url = 'http://' + test_url
    
    # 输入线程数
    try:
        max_workers = int(input("请输入线程数 (默认50): ") or 50)
    except:
        max_workers = 50
    
    print(f"开始测速 {len(proxies)} 个代理，使用 {max_workers} 线程...")
    
    results = []
    timeout = 15
    
    def test_speed(proxy):
        try:
            proxies_dict = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            
            start_time = time.time()
            response = requests.get(
                test_url, 
                proxies=proxies_dict, 
                timeout=timeout,
                stream=True,
                headers={'User-Agent': 'Mozilla/5.0'}
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
            return (proxy, round(speed, 2))
        except:
            return (proxy, 0)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(test_speed, proxies))
    
    # 按速度降序排序
    results.sort(key=lambda x: x[1], reverse=True)
    
    # 保存测速结果
    output_file = os.path.join(os.getcwd(), 'cs.txt')
    with open(output_file, 'w') as f:
        for proxy, speed in results:
            if speed > 0:
                f.write(f"{proxy} - {speed} KB/s\n")
    
    print(f"测速完成！有效代理数: {len([r for r in results if r[1] > 0])}")
    print(f"结果已保存到: {output_file}")

def main():
    while True:
        print("\n" + "="*50)
        print("代理工具菜单")
        print("1. 验证代理存活")
        print("2. 测速代理下载速度")
        print("3. 退出")
        print("="*50)
        
        choice = input("请选择功能 (1/2/3): ").strip()
        
        if choice == '1':
            validate_proxies()
        elif choice == '2':
            speed_test_proxies()
        elif choice == '3':
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main()
