#!/usr/bin/env python3
"""
Parameter Finder - پیدا کردن پارامترهای سایت
"""

import requests
import sys
import time
import re
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
import argparse

# ============================================
# تنظیمات
# ============================================
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIMEOUT = 10
DELAY = 1  # تاخیر بین درخواست‌ها

# ============================================
# پارامترهای رایج
# ============================================
COMMON_PARAMS = [
    # وردپرس
    "s", "p", "page_id", "cat", "tag", "author",
    "order", "orderby", "post_type", "paged", "page",
    "name", "attachment_id", "preview", "feed",
    # WooCommerce
    "product_cat", "product_tag", "product_id",
    "min_price", "max_price", "add-to-cart",
    "variation_id", "attribute", "rating_filter",
    # عمومی
    "id", "user", "user_id", "search", "q", "keyword",
    "email", "action", "nonce", "ajax", "redirect",
    "url", "file", "path", "dir", "cmd", "exec",
    "include", "require", "load", "read", "view",
    "lang", "locale", "currency", "sort", "filter",
    "type", "mode", "debug", "test", "admin",
]

# ============================================
# کلاس اصلی
# ============================================
class ParamFinder:
    def __init__(self, url, delay=1, threads=5, verbose=False):
        self.url = url.rstrip('/')
        self.delay = delay
        self.threads = threads
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.found_params = []
        self.links = set()
        self.js_files = set()
        self.results = {}
    
    def log(self, msg, level="INFO"):
        """چاپ پیام"""
        symbols = {
            "INFO": "[*]",
            "OK": "[+]",
            "WARN": "[!]",
            "ERROR": "[-]",
            "DEBUG": "[D]",
        }
        print(f"{symbols.get(level, '[*]')} {msg}")
    
    def fetch(self, url):
        """درخواست GET با مدیریت خطا"""
        try:
            resp = self.session.get(url, timeout=TIMEOUT, allow_redirects=True)
            return resp
        except requests.exceptions.Timeout:
            self.log(f"Timeout: {url}", "WARN")
            return None
        except requests.exceptions.ConnectionError:
            self.log(f"Connection Error: {url}", "ERROR")
            return None
        except Exception as e:
            self.log(f"Error: {e}", "ERROR")
            return None
    
    def test_param(self, param):
        """تست یه پارامتر"""
        url1 = f"{self.url}/?{param}=1"
        url2 = f"{self.url}/?{param}=aaaa"
        
        resp1 = self.fetch(url1)
        time.sleep(self.delay)
        resp2 = self.fetch(url2)
        time.sleep(self.delay)
        
        if not resp1 or not resp2:
            return None
        
        size1 = len(resp1.content)
        size2 = len(resp2.content)
        
        result = {
            "param": param,
            "size1": size1,
            "size2": size2,
            "dynamic": size1 != size2,
            "status1": resp1.status_code,
            "status2": resp2.status_code,
        }
        
        if self.verbose:
            self.log(f"  {param}: {size1} vs {size2}", "DEBUG")
        
        return result
    
    def find_params(self):
        """پیدا کردن پارامترها با ترد"""
        self.log("شروع پیدا کردن پارامترها...")
        self.log(f"تعداد پارامترها: {len(COMMON_PARAMS)}")
        self.log(f"تاخیر: {self.delay} ثانیه")
        self.log(f"تعداد ترد: {self.threads}")
        print()
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self.test_param, param): param 
                      for param in COMMON_PARAMS}
            
            for future in futures:
                try:
                    result = future.result()
                    if result and result["dynamic"]:
                        self.results[result["param"]] = result
                        self.log(f"✅ {result['param']} → dynamic ({result['size1']} vs {result['size2']})", "OK")
                except Exception as e:
                    self.log(f"خطا: {e}", "ERROR")
        
        return self.results
    
    def crawl(self):
        """خزش سایت"""
        self.log("شروع خزش سایت...")
        
        resp = self.fetch(self.url)
        if not resp:
            return
        
        # استخراج لینک‌ها
        links = re.findall(r'href=["\']([^"\']+)["\']', resp.text)
        for link in links:
            if link.startswith('/'):
                link = self.url + link
            if link.startswith(self.url):
                self.links.add(link)
        
        # استخراج JSها
        js_files = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', resp.text)
        for js in js_files:
            if js.startswith('//'):
                js = 'https:' + js
            elif js.startswith('/'):
                js = self.url + js
            elif not js.startswith('http'):
                js = self.url + '/' + js
            if js.startswith('http'):
                self.js_files.add(js)
        
        self.log(f"لینک‌ها: {len(self.links)}", "OK")
        self.log(f"فایل‌های JS: {len(self.js_files)}", "OK")
        
        return self.links, self.js_files
    
    def extract_params_from_links(self):
        """استخراج پارامترها از لینک‌ها"""
        self.log("استخراج پارامترها از لینک‌ها...")
        
        params = set()
        for link in self.links:
            if '?' in link:
                query = link.split('?')[1]
                for pair in query.split('&'):
                    if '=' in pair:
                        param = pair.split('=')[0]
                        params.add(param)
        
        if params:
            self.log(f"پارامترهای پیدا شده از لینک‌ها:", "OK")
            for p in sorted(params):
                print(f"    ✅ {p}")
        else:
            self.log("پارامتری از لینک‌ها پیدا نشد", "WARN")
        
        return params
    
    def analyze_js(self):
        """تحلیل فایل‌های JS"""
        self.log("تحلیل فایل‌های JS...")
        
        params = set()
        for js_url in list(self.js_files)[:10]:
            resp = self.fetch(js_url)
            if not resp:
                continue
            
            # دنبال پارامترها
            found = re.findall(r'[\?&]([a-zA-Z_][a-zA-Z0-9_]*)=', resp.text)
            for p in found:
                params.add(p)
            
            time.sleep(self.delay)
        
        if params:
            self.log(f"پارامترهای پیدا شده از JS:", "OK")
            for p in sorted(params):
                print(f"    ✅ {p}")
        else:
            self.log("پارامتری از JS پیدا نشد", "WARN")
        
        return params
    
    def test_hidden_params(self):
        """تست پارامترهای مخفی"""
        self.log("تست پارامترهای مخفی...")
        
        # لیست کوچیک برای تست سریع
        hidden = ["debug", "test", "admin", "dev", "api", "key", "token"]
        
        for param in hidden:
            resp = self.fetch(f"{self.url}/?{param}=1")
            if resp and resp.status_code == 200:
                if "error" in resp.text.lower() or "warning" in resp.text.lower():
                    self.log(f"⚠️ {param} → مشکوک!", "WARN")
        
        return []
    
    def run(self):
        """اجرای کامل"""
        print("=" * 60)
        print(f"  Parameter Finder")
        print(f"  Target: {self.url}")
        print("=" * 60)
        print()
        
        # مرحله ۱: تست پارامترهای رایج
        print("=" * 60)
        print("  مرحله ۱: تست پارامترهای رایج")
        print("=" * 60)
        print()
        
        self.find_params()
        
        # مرحله ۲: خزش
        print()
        print("=" * 60)
        print("  مرحله ۲: خزش سایت")
        print("=" * 60)
        print()
        
        self.crawl()
        
        # مرحله ۳: استخراج از لینک‌ها
        print()
        print("=" * 60)
        print("  مرحله ۳: استخراج از لینک‌ها")
        print("=" * 60)
        print()
        
        link_params = self.extract_params_from_links()
        
        # مرحله ۴: تحلیل JS
        print()
        print("=" * 60)
        print("  مرحله ۴: تحلیل JS")
        print("=" * 60)
        print()
        
        js_params = self.analyze_js()
        
        # مرحله ۵: پارامترهای مخفی
        print()
        print("=" * 60)
        print("  مرحله ۵: پارامترهای مخفی")
        print("=" * 60)
        print()
        
        self.test_hidden_params()
        
        # خلاصه
        print()
        print("=" * 60)
        print("  خلاصه")
        print("=" * 60)
        print()
        
        all_params = set()
        all_params.update(self.results.keys())
        all_params.update(link_params)
        all_params.update(js_params)
        
        if all_params:
            print(f"  ✅ {len(all_params)} پارامتر پیدا شد:")
            print()
            for p in sorted(all_params):
                source = []
                if p in self.results:
                    source.append("dynamic")
                if p in link_params:
                    source.append("link")
                if p in js_params:
                    source.append("js")
                print(f"    • {p} ({', '.join(source)})")
        else:
            print("  ❌ هیچ پارامتری پیدا نشد")
        
        print()
        print("=" * 60)
        print("  DONE")
        print("=" * 60)
        
        return all_params


# ============================================
# Main
# ============================================
def main():
    parser = argparse.ArgumentParser(description="Parameter Finder")
    parser.add_argument("-u", "--url", required=True, help="Target URL")
    parser.add_argument("-d", "--delay", type=float, default=1, help="Delay between requests (seconds)")
    parser.add_argument("-t", "--threads", type=int, default=5, help="Number of threads")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose mode")
    
    args = parser.parse_args()
    
    finder = ParamFinder(
        url=args.url,
        delay=args.delay,
        threads=args.threads,
        verbose=args.verbose,
    )
    
    finder.run()


if __name__ == "__main__":
    main()
