import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from config import Config
from captcha_handler import ModelApiError

logger = logging.getLogger(__name__)


def bj_now_str():
    """北京时间（UTC+8），精确到秒"""
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


class CheckInAutomation:
    """签到自动化主类"""
    def __init__(self, config: Config):
        self.config = config
        try:
            from captcha_handler import CaptchaHandler
        except ImportError:
            from captcha_handler import CaptchaHandler  # 如果模块名不同
        self.captcha_handler = CaptchaHandler(config)
        try:
            from human_simulator import HumanSimulator
        except ImportError:
            from human_simulator import HumanSimulator  # 如果模块名不同
        self.simulator = HumanSimulator()
        self.max_retries = config.max_retries
        # 签到结果（供 send_email.py 构造干净邮件）
        self.result = {
            "success": False,
            "status": "失败",
            "time": "",
            "before_flow": "--",
            "gained_flow": "--",
            "days": None,
            "after_flow": "--",
            "note": "",
        }

    def _save_result(self):
        """把签到结果写入 sign_result.json，供 send_email.py 读取"""
        self.result["time"] = bj_now_str()
        with open("sign_result.json", "w", encoding="utf-8") as f:
            json.dump(self.result, f, ensure_ascii=False, indent=2)
        logger.info(f"签到结果已写入 sign_result.json: {self.result}")

    def run(self):
        """执行签到流程"""
        # GitHub Actions 环境自动使用 headless 模式
        headless = os.getenv('CI') == 'true' or os.getenv('HEADLESS', 'false').lower() == 'true'

        try:
            with sync_playwright() as playwright:
                browser = None
                try:
                    logger.info("正在初始化 Playwright Chromium...")
                    launch_options = {
                        "headless": headless,
                        "args": [
                            "--window-size=1280,800",
                            "--disable-blink-features=AutomationControlled",
                            "--no-proxy-server",
                            "--lang=zh-CN",
                            "--disable-gpu",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                        ],
                    }
                    chrome_path = self._resolve_chrome_path()
                    if chrome_path:
                        logger.info(f"使用 Chrome 路径: {chrome_path}")
                        launch_options["executable_path"] = chrome_path

                    browser = playwright.chromium.launch(**launch_options)
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        locale="zh-CN",
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                    )
                    context.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                    )
                    page = context.new_page()
                    page.set_default_timeout(20000)

                    # 步骤1: 登录
                    if not self._login(page):
                        self.result["note"] = "登录失败"
                        logger.error("登录失败")
                        self._save_result()
                        return

                    # 步骤2: 跳转到 SakuraFrp 仪表板（含年龄弹窗处理）
                    if not self._navigate_to_sakurafrp(page):
                        self.result["note"] = "跳转到 SakuraFrp 失败"
                        logger.error("跳转到 SakuraFrp 失败")
                        self._save_result()
                        return

                    # 步骤3: 执行签到并记录流量统计
                    if not self._perform_checkin(page):
                        if not self.result["note"]:
                            self.result["note"] = "签到失败"
                        logger.error("签到失败")
                        try:
                            page.screenshot(path="error_screenshot.png", full_page=True)
                        except Exception:
                            pass
                        self._save_result()
                        return

                    self.result["note"] = self.result.get("note") or "签到成功"
                    logger.info("✓ 签到流程完成")
                    self._save_result()

                except ModelApiError:
                    self.result["note"] = "模型 API 调用失败，终止签到流程"
                    logger.error("模型 API 调用失败，终止签到流程")
                    self._save_result()
                    return
                except Exception as e:
                    self.result["note"] = f"执行过程中发生错误: {e}"
                    logger.error(f"执行过程中发生错误: {e}", exc_info=True)
                    self._save_result()
                finally:
                    if browser and headless:
                        browser.close()
                    logger.info("脚本执行完毕")

        except Exception as e:
            # 最外层兜底，保证 sign_result.json 总是被写入
            self.result["note"] = f"严重异常: {e}"
            logger.error(f"严重异常: {e}", exc_info=True)
            self._save_result()

    def _resolve_chrome_path(self):
        """优先使用环境变量指定的 Chrome，其次查找系统 Chrome。"""
        if self.config.chrome_binary_path and os.path.exists(self.config.chrome_binary_path):
            return self.config.chrome_binary_path

        candidate_paths = [
            os.path.join(
                os.environ.get("PROGRAMFILES", ""),
                "Google",
                "Chrome",
                "Application",
                "chrome.exe",
            ),
            os.path.join(
                os.environ.get("PROGRAMFILES(X86)", ""),
                "Google",
                "Chrome",
                "Application",
                "chrome.exe",
            ),
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Google",
                "Chrome",
                "Application",
                "chrome.exe",
            ),
        ]

        for executable in ("google-chrome", "google-chrome-stable", "chrome", "chromium"):
            found = shutil.which(executable)
            if found:
                return found

        for path in candidate_paths:
            if path and os.path.exists(path):
                return path

        return None

    def _login(self, page: Page) -> bool:
        """执行登录"""
        login_url = "https://www.natfrp.com/user/"
        logger.info(f"导航到登录页面: {login_url}")
        page.goto(login_url, wait_until="domcontentloaded")

        try:
            username_input = page.locator("#username")
            password_input = page.locator("#password")
            username_input.wait_for(state="visible")
            password_input.wait_for(state="visible")

            logger.info("输入登录凭据...")
            username_input.fill("")
            self.simulator.type_text(username_input, self.config.sakurafrp_user)
            password_input.fill("")
            self.simulator.type_text(password_input, self.config.sakurafrp_pass)

            login_button = page.locator("#login")
            login_button.wait_for(state="visible")
            logger.info("点击登录按钮...")
            login_button.click()

            self.simulator.random_sleep(3, 5)
            logger.info("登录成功")
            return True

        except PlaywrightTimeoutError:
            logger.error("登录页面元素加载超时")
            return False
        except Exception as e:
            logger.error(f"登录过程出错: {e}", exc_info=True)
            return False

    def _navigate_to_sakurafrp(self, page: Page) -> bool:
        """跳转到 SakuraFrp 仪表板"""
        try:
            # 处理年龄确认弹窗（如果存在）
            try:
                age_confirm = page.locator("div.yes a", has_text="是，我已满18岁")
                age_confirm.wait_for(state="visible", timeout=5000)
                logger.info("处理年龄确认弹窗...")
                age_confirm.click()
                self.simulator.random_sleep(2, 3)
            except PlaywrightTimeoutError:
                logger.info("未检测到年龄确认弹窗")

            # 关闭页面广告弹窗（会滚动移动位置，可能遮挡签到按钮/统计信息）
            self._close_ad_popup(page)

            logger.info("成功跳转到 SakuraFrp 仪表板")
            return True

        except PlaywrightTimeoutError:
            logger.warning("SakuraFrp 跳转链接未找到，可能已在目标页面")
            return True
        except Exception as e:
            logger.error(f"跳转过程出错: {e}", exc_info=True)
            return False

    def _close_ad_popup(self, page: Page):
        """
        关闭/移除页面广告弹窗。
        该弹窗（"【查看帮助文档】立刻自助解决99%的问题"）位置会滚动移动，
        可能遮挡"点击这里签到"按钮和"统计信息"入口。
        优先用 JS 直接移除 DOM，其次点击"关闭"按钮兜底。
        """
        try:
            removed = page.evaluate("""
                () => {
                    let count = 0;
                    const all = document.querySelectorAll('div, section, aside, span');
                    for (const el of all) {
                        const t = (el.textContent || '').replace(/\\s+/g, '');
                        if ((t.includes('查看帮助文档') || t.includes('立刻自助解决'))
                                && t.length < 200) {
                            let cur = el;
                            for (let i = 0; i < 8; i++) {
                                if (!cur || !cur.parentElement) break;
                                const st = window.getComputedStyle(cur);
                                if (st.position === 'fixed' || st.position === 'absolute'
                                        || (st.zIndex && parseInt(st.zIndex, 10) >= 100)) {
                                    cur.remove();
                                    count++;
                                    break;
                                }
                                cur = cur.parentElement;
                            }
                        }
                    }
                    return count;
                }
            """)
            if removed:
                logger.info(f"已移除广告弹窗 x{removed}")
        except Exception as e:
            logger.warning(f"JS 移除广告弹窗失败: {e}")

        # 兜底：若仍存在，点击"关闭"按钮
        try:
            close_btn = page.locator("text=关闭").first
            if close_btn.is_visible(timeout=800):
                close_btn.click()
                logger.info("点击'关闭'按钮")
        except Exception:
            pass

        self.simulator.random_sleep(1, 2)

    def _get_sign_stats(self, page: Page) -> dict:
        """
        读取"统计信息"弹窗（hover 触发）。
        返回 {"days": 累计签到天数, "total_flow": 共获得流量(GiB数值),
              "total_flow_text": "5.6 GiB", "last_sign": "2026-09-07"}
        """
        stats = {
            "days": None,
            "total_flow": None,
            "total_flow_text": None,
            "last_sign": None,
        }
        try:
            self._close_ad_popup(page)
            info_btn = page.get_by_text("统计信息", exact=True).last
            info_btn.hover()
            time.sleep(1.5)

            body = page.inner_text("body")
            m_days = re.search(r"总计签到\s*(\d+)\s*天", body)
            m_flow = re.search(r"共获得流量\s*([\d.]+)\s*(GiB|MiB|TiB|GB|MB|TB)?", body)
            m_last = re.search(r"上次签到于\s*([\d\-]+)", body)

            if m_days:
                stats["days"] = int(m_days.group(1))
            if m_flow:
                num = float(m_flow.group(1))
                unit = m_flow.group(2) or "GiB"
                stats["total_flow_text"] = f"{num:g} {unit}"
                # 统一转为 GiB 数值便于计算本次获得
                if unit in ("MiB", "MB"):
                    num = num / 1024.0
                elif unit in ("TiB", "TB"):
                    num = num * 1024.0
                stats["total_flow"] = round(num, 4)
            if m_last:
                stats["last_sign"] = m_last.group(1)

            logger.info(f"统计信息: {stats}")
        except Exception as e:
            logger.warning(f"读取统计信息失败: {e}")

        # 关闭 popover，避免遮挡后续按钮
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        self.simulator.random_sleep(1, 2)
        return stats

    def _perform_checkin(self, page: Page) -> bool:
        """
        执行签到，并记录签到前后的"共获得流量"（统计信息弹窗）。
        本次获得流量 = 签到后共获得流量 - 签到前共获得流量（GiB）。
        """
        # 1. 签到前读取统计
        self._close_ad_popup(page)
        before_stats = self._get_sign_stats(page)
        self.result["before_flow"] = before_stats.get("total_flow_text") or "--"
        self.result["days"] = before_stats.get("days")

        # 2. 检查是否已签到
        self._close_ad_popup(page)
        try:
            page.locator("p", has_text="今天已经签到过啦").wait_for(state="visible", timeout=2000)
            logger.info("今日已签到")
            self.result["success"] = True
            self.result["status"] = "成功"
            self.result["gained_flow"] = "0.00 GiB"
            self.result["note"] = "今日已签到过"
            self.result["after_flow"] = self.result["before_flow"]
            return True
        except PlaywrightTimeoutError:
            pass

        # 3. 循环签到（点击"点击这里签到"→ 极验验证码 → 刷新确认）
        signed = False
        for attempt in range(1, self.max_retries + 1):
            self._close_ad_popup(page)
            try:
                btn = page.locator("button", has_text="点击这里签到")
                btn.wait_for(state="visible", timeout=5000)
            except PlaywrightTimeoutError:
                # 按钮消失 → 检查是否已签到
                try:
                    page.locator("p", has_text="今天已经签到过啦").wait_for(state="visible", timeout=2000)
                    signed = True
                    break
                except PlaywrightTimeoutError:
                    logger.error("未找到签到按钮或已签到标识")
                    return False

            try:
                logger.info(f"点击签到按钮 ({attempt}/{self.max_retries})")
                btn.click()
                self.simulator.random_sleep(2, 4)
                self.captcha_handler.handle_geetest_captcha(page)
                page.reload(wait_until="domcontentloaded")
                time.sleep(5)
                signed = True
                break
            except ModelApiError:
                raise
            except Exception as e:
                logger.error(f"签到过程出错: {e}", exc_info=True)
                if attempt >= self.max_retries:
                    return False
                time.sleep(3)

        if not signed:
            # 循环结束后按钮消失，视为签到成功
            signed = True

        # 4. 签到后读取统计（reload 确保数据最新）
        self._close_ad_popup(page)
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
        time.sleep(4)
        after_stats = self._get_sign_stats(page)
        self.result["after_flow"] = after_stats.get("total_flow_text") or "--"
        self.result["days"] = after_stats.get("days") or self.result.get("days")

        # 5. 计算本次获得流量（签到后 - 签到前，GiB）
        before_val = before_stats.get("total_flow")
        after_val = after_stats.get("total_flow")
        if before_val is not None and after_val is not None:
            gained = after_val - before_val
            if gained < 0:
                gained = 0.0
            self.result["gained_flow"] = f"{gained:.2f} GiB"
        else:
            self.result["gained_flow"] = "--"

        self.result["success"] = True
        self.result["status"] = "成功"
        self.result["note"] = "签到成功"
        return True
