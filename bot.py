import asyncio, json, uuid, ssl, os, warnings, time, re, aiohttp, gc
from datetime import datetime
import paho.mqtt.client as mqtt
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

warnings.filterwarnings("ignore", category=DeprecationWarning)
console = Console()
gc.set_threshold(50, 5, 5)

class MessengerStablePro:
    def __init__(self):
        self.group_name_cache = {}
        self.is_running = True

    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log_msg(self, status, uid, msg):
        t = datetime.now().strftime("%H:%M:%S")
        icon = "[bold green]✔[/]" if status == "success" else "[bold red]✘[/]"
        console.print(f"[dim]{t}[/] {icon} [bold magenta][{uid[:5]}][/] [white]{msg}[/]")

    async def get_info(self, cookie):
        """Lấy thông tin nhóm/box (Cần thiết để ổn định ID)"""
        try:
            uid = re.search(r'c_user=(\d+)', cookie).group(1)
            headers = {'cookie': cookie, 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f'https://mbasic.facebook.com/privacy/touch/block/confirm/?bid={uid}') as resp:
                    text = await resp.text()
                    fb_dtsg = re.search('name="fb_dtsg" value="([^"]+)"', text).group(1)
                    jazoest = re.search('name="jazoest" value="([^"]+)"', text).group(1)
                
                query = {"o0": {"doc_id": "3336396659757871", "query_params": {"limit": 15, "tags": ["INBOX"]}}}
                form = {"av": uid, "__user": uid, "fb_dtsg": fb_dtsg, "jazoest": jazoest, "__a": "1", "queries": json.dumps(query)}
                async with session.post("https://www.facebook.com/api/graphqlbatch/", data=form) as res:
                    data = json.loads((await res.text()).replace('for (;;);', ''))
                    nodes = data.get("o0",{}).get("data",{}).get("viewer",{}).get("message_threads",{}).get("nodes", [])
                    for n in nodes:
                        self.group_name_cache[n["thread_key"]["thread_fbid"]] = n.get("name") or "Box Chat"
            return True
        except: return False

    async def send_loop(self, cookie, thread_ids, content, delay):
        try:
            uid = re.search(r'c_user=(\d+)', cookie).group(1)
        except: return

        # Dùng MQTTv31 để tương thích tốt nhất với Facebook
        client = mqtt.Client(client_id=f"nd_{uuid.uuid4().hex[:5]}", transport="websockets", protocol=mqtt.MQTTv31)
        client.username_pw_set(json.dumps({"u": uid, "s": 1, "chat_on": True, "fg": True, "d": str(uuid.uuid4()), "ct": "websocket", "aid": 219994525426954}))
        client.tls_set_context(ssl._create_unverified_context())
        client.ws_set_options(path="/chat", headers={"Cookie": cookie, "Origin": "https://www.facebook.com", "User-Agent": "Mozilla/5.0"})

        try:
            # Kết nối ổn định
            client.connect("edge-chat.facebook.com", 443, 60)
            client.loop_start()
            
            while self.is_running:
                for tid in thread_ids:
                    msg_id = str(int(time.time() * 1000))
                    # Payload đầy đủ tham số để Facebook không từ chối
                    payload = json.dumps({
                        "body": content, 
                        "msgid": msg_id, 
                        "sender_fbid": uid, 
                        "to": tid,
                        "offline_threading_id": msg_id
                    }, separators=(',', ':'))
                    
                    client.publish("/send_message2", payload, qos=1) # QoS 1 để đảm bảo tin tới đích
                    self.log_msg("success", uid, f"➥ {self.group_name_cache.get(tid, tid)}")
                    
                    del payload
                    gc.collect()

                await asyncio.sleep(max(float(delay), 0.5))
        except Exception as e:
            self.log_msg("error", uid, f"Lỗi kết nối: {e}")
        finally:
            client.loop_stop()
            client.disconnect()

    async def main_menu(self):
        while True:
            self.clear()
            console.print(Panel("[bold cyan]🚀 MESSENGER PRO V5 - TỐI ƯU RAM & CPU[/]\n[dim]Trạng thái: Ổn định 24/7 | RAM: < 256MB[/]", border_style="blue"))
            
            menu = Table(show_header=False, box=None)
            menu.add_row("[bold green]1.[/] 🟢 Kích hoạt Spam (Siêu nhẹ)")
            menu.add_row("[bold green]2.[/] 🔍 Quét ID Box Chat")
            menu.add_row("[bold red]0.[/] 🛑 Thoát")
            console.print(menu)
            
            choice = console.input("[bold yellow]➤ Lựa chọn: [/]")

            if choice == '1':
                cookies = []
                console.print("\n[cyan]Nhập Cookies (xong gõ 'done'):[/]")
                while True:
                    c = console.input(" ╰─> ").strip()
                    if c.lower() == 'done': break
                    if c: cookies.append(c)

                ids = []
                console.print("\n[cyan]Nhập ID Box (xong gõ 'done'):[/]")
                while True:
                    i = console.input(" ╰─> ").strip()
                    if i.lower() == 'done': break
                    if i: ids.append(i)

                file_name = console.input("\n[white]➤ Tên file nội dung (vd: noidung.txt): [/]") or "noidung.txt"
                delay = float(console.input("[white]➤ Delay (giây): [/]") or 35)

                if os.path.exists(file_name):
                    with open(file_name, 'r', encoding='utf-8') as f:
                        cached_content = f.read().strip()

                    tasks = []
                    for ck in cookies:
                        await self.get_info(ck)
                        tasks.append(asyncio.create_task(self.send_loop(ck, ids, cached_content, delay)))
                    
                    console.print(f"[bold green]🔥 Đang treo {len(tasks)} tài khoản...[/]")
                    await asyncio.gather(*tasks)
                else:
                    console.print("[red]Lỗi: Không thấy file nội dung![/]")
                    time.sleep(2)
            elif choice == '0': break

if __name__ == "__main__":
    # Task dọn RAM nền
    async def global_cleaner():
        while True:
            gc.collect()
            await asyncio.sleep(300)

    bot = MessengerStablePro()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.create_task(global_cleaner())
        loop.run_until_complete(bot.main_menu())
    except KeyboardInterrupt: pass
    