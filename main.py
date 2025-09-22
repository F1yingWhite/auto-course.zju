import ssl
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

ssl._create_default_https_context = ssl._create_unverified_context

JS_SCRIPT = r"""
const getRndInteger = (min, max) =>
  Math.floor(Math.random() * (max - min + 1)) + min;

function parseTime(duration) {
  let [minutes, seconds] = duration.split(":");
  return parseInt(minutes) * 60 + parseInt(seconds);
}

function genRndSeqs(seconds) {
  let time_seqs = [0];
  while (time_seqs[time_seqs.length - 1] < seconds) {
    let time_lag = getRndInteger(90, 110);
    // let time_lag = 120;
    let next_seq = time_seqs[time_seqs.length - 1] + time_lag;
    if (next_seq < seconds) {
      time_seqs.push(next_seq);
    } else {
      time_seqs.push(seconds);
      return time_seqs;
    }
  }
}

async function playVideo(video_id, start, end) {
  let bodystr = `{\"start\":${start},\"end\":${end}}`;
  let resp = await fetch(
    `https://courses.zju.edu.cn/api/course/activities-read/${video_id}`,
    {
      headers: {
        Accept: "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        Connection: "keep-alive",
        "Content-Length": bodystr.length,
        "Content-Type": "application/json",
        Cookie: document.cookie,
        Host: "courses.zju.edu.cn",
        Origin: "https://courses.zju.edu.cn",
        Referer: window.location.href.split("#")[0],
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua":
          'Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "Windows",
      },
      referrer: window.location.href.split("#")[0],
      referrerPolicy: "strict-origin-when-cross-origin",
      body: bodystr,
      method: "POST",
      mode: "cors",
      credentials: "include",
    }
  ).then((response) => response.json());
  return resp;
}
async function main() {
  let duration = document.getElementsByClassName("duration")[1].outerText;
  let hash = window.location.hash;
  let total_seconds = parseTime(duration);
  let video_id = hash.split("/")[1];
  console.log(total_seconds, video_id);
  let time_seqs = genRndSeqs(total_seconds);
  let complete = "";
  for (let i = 0; i < time_seqs.length - 1; i++) {
    let [start, end] = [time_seqs[i], time_seqs[i + 1]];
    console.log("Playing", start, end);
    let data = await playVideo(video_id, start, end);
    console.log(data, data.completeness);
    complete = data.completeness;
  }
  if (complete == "full") {
    alert("Watch this Video Successfully!");
  } else {
    alert("Some Error Occurred, Please Retry!");
  }
}
main();
"""


def init_driver():
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()
    return driver


def main():
    driver = init_driver()
    wait = WebDriverWait(driver, 30)

    try:
        print("🌐 正在打开登录页面...")
        driver.get("https://course.zju.edu.cn/learninginzju?locale=zh-CN")

        print("📱 请在浏览器中手动扫码或输入账号密码登录...")
        print("✅ 登录成功并跳转到对应课程页面后，请回到此窗口按回车继续...")
        input()

        print("🔎 正在查找所有视频元素...")
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.title.ng-binding.ng-scope")))
        except:
            print("❌ 未找到视频元素，请检查页面是否加载完成")
            return

        video_elements = driver.find_elements(By.CSS_SELECTOR, "a.title.ng-binding.ng-scope")
        total_videos = len(video_elements)
        print(f"🎯 找到 {total_videos} 个视频")

        if total_videos == 0:
            print("❌ 未找到任何视频")
            return

        success_count = 0

        for i in range(total_videos):
            try:
                print(f"\n🎬 正在处理第 {i + 1}/{total_videos} 个视频")

                video_elements = driver.find_elements(By.CSS_SELECTOR, "a.title.ng-binding.ng-scope")

                if i >= len(video_elements):
                    print("⚠️ 视频元素数量发生变化，跳过剩余")
                    break

                elem = video_elements[i]
                title = elem.text.strip()
                print(f"📝 视频标题: {title}")

                # 直接点击元素
                print("🖱️ 正在点击视频元素...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                time.sleep(1)
                elem.click()
                print("✅ 已点击，等待页面跳转...")

                # 等待视频页面加载
                try:
                    WebDriverWait(driver, 15).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".video-duration .attribute-value")),
                            EC.presence_of_element_located((By.CLASS_NAME, "duration")),
                            EC.presence_of_element_located((By.TAG_NAME, "video")),
                        )
                    )
                    time.sleep(3)
                    print("✅ 视频播放页加载完成")
                except:
                    print("⚠️ 视频页面加载超时，但仍尝试执行脚本")

                # 执行 JS 脚本
                print("⚙️ 正在执行观看进度脚本...")
                try:
                    result = driver.execute_script(JS_SCRIPT)
                    if result:
                        success_count += 1
                        print("✅ 视频进度标记成功")
                    else:
                        print("⚠️ 视频进度标记失败")
                except Exception as e:
                    print(f"❌ JS 脚本执行出错: {e}")

                # 等待几秒
                time.sleep(5)

                # 返回上一页
                print("⬅️ 返回课程列表页...")
                driver.back()

                # 等待列表页重新加载
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a.title.ng-binding.ng-scope"))
                    )
                    time.sleep(2)
                    print("✅ 已返回课程列表页")
                except:
                    print("⚠️ 返回列表页超时，尝试继续...")

            except Exception as e:
                print(f"❌ 处理第 {i + 1} 个视频时出错: {e}")
                try:
                    driver.back()
                    time.sleep(2)
                except:
                    pass
                continue

        print(f"\n🎉 全部完成！共处理 {total_videos} 个视频，成功 {success_count} 个")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

    finally:
        input("\n按回车键关闭浏览器...")
        driver.quit()


if __name__ == "__main__":
    main()
