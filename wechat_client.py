import os
import json
import time
import re
import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WeChatAPIError(Exception):
    """微信 API 调用异常基类"""
    def __init__(self, errcode, errmsg):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"微信 API 错误 [代码 {errcode}]: {errmsg}")

class WeChatIPWhitelistError(WeChatAPIError):
    """微信 IP 白名单未加白异常"""
    def __init__(self, errcode, errmsg):
        super().__init__(errcode, errmsg)
        # 尝试从错误信息中提取当前 IP
        # 典型微信报错信息: "invalid ip 180.110.12.34, not in whitelist" 或 "invalid ip 111.111.111.111 ipv6 ::1, not in whitelist"
        self.ip = "未知"
        ip_match = re.search(r'invalid ip ([\d\.]+)', errmsg)
        if ip_match:
            self.ip = ip_match.group(1)
        elif "ip" in errmsg:
            # 备用匹配逻辑
            ips = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', errmsg)
            if ips:
                self.ip = ips[0]

    def __str__(self):
        return (
            f"\n"
            f"======================================================================\n"
            f"[ERROR] 微信 API 报错：40164 (IP 白名单错误)\n"
            f"----------------------------------------------------------------------\n"
            f"【原因】您当前运行此工具的服务器/本地公网 IP ({self.ip}) 未被加入到微信公众号的 IP 白名单中。\n"
            f"【解决办法】:\n"
            f"  1. 登录「微信公众平台」(mp.weixin.qq.com)。\n"
            f"  2. 进入左侧菜单:「设置与开发」 -> 「基本配置」。\n"
            f"  3. 找到「IP白名单」配置项，点击「修改」或「查看」。\n"
            f"  4. 将您当前的公网 IP 地址 【 {self.ip} 】 添加到白名单列表中，保存生效。\n"
            f"  5. 稍等 1-2 分钟（微信生效有短暂延迟）后，重新运行此程序。\n"
            f"======================================================================"
        )

class WeChatClient:
    """微信公众号 API 客户端，封装 Token 管理、媒体上传和草稿创建"""
    
    def __init__(self, appid, secret, token_cache_path=".wechat_token.json"):
        if not appid or not secret:
            raise ValueError("初始化失败: AppID 和 AppSecret 不能为空，请检查配置文件")
        self.appid = appid
        self.secret = secret
        self.token_cache_path = token_cache_path
        self._access_token = None
        self._token_expires_at = 0

    def _handle_response(self, response_data):
        """解析微信 API 响应，发现错误抛出异常"""
        if isinstance(response_data, dict):
            errcode = response_data.get("errcode", 0)
            if errcode != 0:
                errmsg = response_data.get("errmsg", "")
                if errcode == 40164:
                    raise WeChatIPWhitelistError(errcode, errmsg)
                raise WeChatAPIError(errcode, errmsg)
        return response_data

    def get_access_token(self):
        """
        获取 Access Token，优先读取本地缓存，过期自动刷新
        """
        # 1. 检查内存缓存
        now = time.time()
        if self._access_token and now < self._token_expires_at - 300: # 提前 5 分钟刷新
            return self._access_token

        # 2. 检查本地 JSON 文件缓存
        if os.path.exists(self.token_cache_path):
            try:
                with open(self.token_cache_path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    # 确保格式正确且未过期
                    if cache.get("appid") == self.appid and cache.get("expires_at", 0) - 300 > now:
                        self._access_token = cache.get("access_token")
                        self._token_expires_at = cache.get("expires_at")
                        logger.info("从本地缓存成功读取微信 Access Token")
                        return self._access_token
            except Exception as e:
                logger.warning(f"读取本地 Token 缓存文件失败，将重新请求微信接口: {e}")

        # 3. 缓存失效，向微信服务器请求
        logger.info("Access Token 不存在或已过期，正在向微信服务器请求新 Token...")
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.secret
        }
        
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            self._handle_response(data)
            
            access_token = data["access_token"]
            expires_in = data["expires_in"] # 默认 7200 秒
            
            # 保存到内存
            self._access_token = access_token
            self._token_expires_at = now + expires_in
            
            # 写入本地缓存文件
            cache_data = {
                "appid": self.appid,
                "access_token": access_token,
                "expires_at": self._token_expires_at
            }
            with open(self.token_cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info("获取新 Access Token 成功，并已缓存至本地")
            return access_token
            
        except requests.RequestException as e:
            raise RuntimeError(f"请求微信 Access Token 失败: 网络异常 {e}")

    def upload_body_image(self, image_path):
        """
        上传图文内图片 (正文插图)
        接口：POST https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=ACCESS_TOKEN
        格式：multipart/form-data
        返回：微信 CDN 图片 URL (例如：http://mmbiz.qpic.cn/...)
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"正文图片文件不存在: {image_path}")

        token = self.get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"
        
        filename = os.path.basename(image_path)
        logger.info(f"正在上传正文图片到微信 CDN: {filename}...")
        
        # 根据后缀简单判断 Content-Type
        content_type = "image/png"
        if filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = "image/jpeg"
        elif filename.lower().endswith('.gif'):
            content_type = "image/gif"
            
        try:
            with open(image_path, "rb") as f:
                files = {
                    "media": (filename, f, content_type)
                }
                res = requests.post(url, files=files, timeout=30)
                res.raise_for_status()
                data = res.json()
                self._handle_response(data)
                
                cdn_url = data.get("url")
                logger.info(f"图片上传成功，获取 CDN URL: {cdn_url}")
                return cdn_url
        except requests.RequestException as e:
            raise RuntimeError(f"上传正文图片失败: 网络异常 {e}")

    def upload_cover_image(self, image_path):
        """
        新增永久图片素材 (通常用于封面图)
        接口：POST https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=ACCESS_TOKEN&type=image
        格式：multipart/form-data
        返回：{"media_id": MEDIA_ID, "url": URL}
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"封面图片文件不存在: {image_path}")

        token = self.get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
        
        filename = os.path.basename(image_path)
        logger.info(f"正在上传永久图片素材 (作为封面图): {filename}...")
        
        content_type = "image/png"
        if filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = "image/jpeg"
        elif filename.lower().endswith('.gif'):
            content_type = "image/gif"

        try:
            with open(image_path, "rb") as f:
                files = {
                    "media": (filename, f, content_type)
                }
                res = requests.post(url, files=files, timeout=30)
                res.raise_for_status()
                data = res.json()
                self._handle_response(data)
                
                media_id = data.get("media_id")
                logger.info(f"封面素材上传成功，获取 media_id: {media_id}")
                return media_id
        except requests.RequestException as e:
            raise RuntimeError(f"上传封面素材失败: 网络异常 {e}")

    def create_draft(self, title, content, thumb_media_id, author=None, digest=None, 
                     content_source_url=None, need_open_comment=0, only_less_tags=0):
        """
        新建草稿箱草稿
        接口：POST https://api.weixin.qq.com/cgi-bin/draft/add?access_token=ACCESS_TOKEN
        """
        token = self.get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
        
        article = {
            "title": title,
            "thumb_media_id": thumb_media_id,
            "content": content,
            "need_open_comment": need_open_comment,
            "only_less_tags": only_less_tags
        }
        
        if author:
            article["author"] = author
        if digest:
            article["digest"] = digest
        if content_source_url:
            article["content_source_url"] = content_source_url

        payload = {
            "articles": [article]
        }
        
        logger.info(f"正在新建草稿箱草稿，标题:「{title}」...")
        try:
            # 微信 API 要求正文使用 UTF-8 编码，且必须为 JSON 格式
            headers = {"Content-Type": "application/json; charset=utf-8"}
            # 使用 json.dumps 并禁用 ascii 确保中文以 UTF-8 传输而不会变成 Unicode 逃逸字符
            payload_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            res = requests.post(url, data=payload_json, headers=headers, timeout=20)
            res.raise_for_status()
            data = res.json()
            self._handle_response(data)
            
            media_id = data.get("media_id")
            logger.info(f"草稿创建成功! 草稿 media_id: {media_id}")
            return media_id
        except requests.RequestException as e:
            raise RuntimeError(f"新建草稿失败: 网络异常 {e}")
