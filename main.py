import configparser
import os
import threading
import time

import requests
from selenium import webdriver

# 抖音最新歌曲
MUSIC_HTML = "douyinzuixingequ"
# 抖音最火最热歌曲
# MUSIC_HTML = "douyinzuihuozuiregequ"
# 抖音中文歌曲
# MUSIC_HTML = "douyinzhongwengequ"
# 抖音DJ舞曲
# MUSIC_HTML = "douyinDJwuqu"
# 抖音英文歌曲
# MUSIC_HTML = "douyinyingwengequ"
MP3_HTML_SECTION = "mp3-html"
MP3_SRC_SECTION = "mp3-src"
PAGE_SECTION = "page"
MP3_INI = os.sep + "mp3.ini"


def getBrowser():
    print("设置浏览器参数")
    chrome_options = webdriver.ChromeOptions()
    # 无头模式
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    browser = webdriver.Chrome(executable_path="driver/chromedriver", options=chrome_options)

    return browser


def doBrowser(driver, open_url, dir_path):
    mkdirPath(dir_path)
    ini_file = dir_path + MP3_INI
    cf = configparser.ConfigParser()
    cf.read(ini_file)
    if not cf.has_section(MP3_HTML_SECTION):
        cf.add_section(MP3_HTML_SECTION)

    if not cf.has_section(PAGE_SECTION):
        cf.add_section(PAGE_SECTION)

    # 收集页数
    driver.get(open_url)
    contents = driver.find_elements_by_xpath("/html/body/div[2]/center/div/div[1]/div/div/div[5]")
    for c in contents:
        page = c.find_element_by_class_name("page")
        pages = page.find_elements_by_tag_name("a")
        for p in pages:
            if not cf.has_option(PAGE_SECTION, p.text):
                cf.set(PAGE_SECTION, p.text, p.get_attribute("href"))

    cf.write(open(ini_file, 'w'))
    # 收集每页的mp3列表
    processorPage(driver, ini_file)


def processorPage(driver, ini_file):
    cf = configparser.ConfigParser()
    cf.read(ini_file)
    options = cf.options(PAGE_SECTION)
    for p in options:
        page_url = cf.get(PAGE_SECTION, p)
        driver.get(page_url)
        print("当前第[", p, "]页, 页面地址:", driver.current_url)
        contents = driver.find_elements_by_xpath("/html/body/div[2]/center/div/div[1]/div/div/div[5]")
        for c in contents:
            # 歌曲列表
            songs = c.find_elements_by_xpath(".//form/ul/li")
            print("歌曲数量:", len(songs))
            for song in songs:
                mp3_name = song.text + ".mp3"
                if not cf.has_option(MP3_HTML_SECTION, mp3_name):
                    a = song.find_element_by_xpath(".//a[1]")
                    href_url = a.get_attribute("href")
                    cf.set(MP3_HTML_SECTION, mp3_name, href_url)

                cf.write(open(ini_file, 'w'))

    downloadMp3(driver, ini_file)


def downloadMp3(driver, ini_file):
    music_ini = os.path.dirname(os.path.dirname(ini_file)) + os.sep + "music.ini"
    # 音乐配置
    music_cf = configparser.ConfigParser()
    music_cf.read(music_ini)
    if not music_cf.has_section(MP3_SRC_SECTION):
        music_cf.add_section(MP3_SRC_SECTION)

    download_index = 0
    start_download_mp3 = None
    # HTML配置
    html_cf = configparser.ConfigParser()
    html_cf.read(ini_file)
    music_urls = html_cf.options(MP3_HTML_SECTION)
    for mp3 in music_urls:
        if not music_cf.has_option(MP3_SRC_SECTION, mp3):
            driver.get(html_cf.get(MP3_HTML_SECTION, mp3))
            # print(web_driver.title)
            # 睡3秒,避免src元素还没有渲染完毕
            time.sleep(3)
            if driver.title != "无法找到该页":
                audio = driver.find_element_by_id("jp_audio_0")
                # print(audio)
                if audio is not None:
                    src = audio.get_attribute("src")
                    print("歌曲名称:", mp3, "歌曲链接:", src)
                    music_cf.set(MP3_SRC_SECTION, mp3, src)
                    music_cf.write(open(music_ini, 'w'))
            if download_index == 0:
                start_download_mp3 = mp3
                download_index += 1
        else:
            if download_index == 0:
                start_download_mp3 = mp3
                download_index += 1

    download_index = music_cf.options(MP3_SRC_SECTION).index(start_download_mp3)
    # 下载歌曲
    music_dir = os.path.dirname(music_ini) + os.sep + "music"
    mkdirPath(music_dir)
    music_urls = music_cf.options(MP3_SRC_SECTION)
    print("歌曲总数量:", len(music_urls), "从[", download_index, "]开始下载")

    # 使用多线程处理, 需要将数量进行分割处理
    print("====================多线程下载================")
    pages = html_cf.options(PAGE_SECTION)
    threads = []
    index = -1
    index_start = download_index
    index_end = 100 + download_index
    # 根据页数创建线程, 每页一个线程
    for p in pages:
        index += 1
        if index > 0:
            index_start = index * 100 + download_index
            index_end += 100
        thread_name = "t-" + str(index)
        print(thread_name, "下载开始位置:", index_start, "下载结束位置:", index_end)
        mp3s = music_urls[index_start:index_end]
        t = threading.Thread(target=doDownload, args=(mp3s, music_dir, music_cf,), name=thread_name, daemon=True)
        threads.append(t)

    for t in threads:
        t.start()
        time.sleep(1)

    for t in threads:
        if t.is_alive():
            t.join()

    print("=====================下载完成=================")


def doDownload(options, music_dir, music_cf):
    print(threading.current_thread().name, "==>下载数量:", len(options))
    for src in options:
        file_path = os.path.join(music_dir, src)
        # 只下载一次,存在则不下载
        if os.path.exists(file_path):
            continue
        print(threading.current_thread().name, ">>> 正在下载:", src)
        res = requests.get(music_cf.get(MP3_SRC_SECTION, src))
        with open(file_path, 'wb') as fd:
            for r in res.iter_content():
                fd.write(r)


def mkdirPath(dir_path):
    dirExists = os.path.exists(dir_path)
    if not dirExists:
        os.mkdir(dir_path)


if __name__ == '__main__':
    # 抖音音乐网
    url = "http://www.yy987.net/" + MUSIC_HTML
    mp3_dir = os.path.dirname(__file__) + os.sep + "mp3" + os.sep + MUSIC_HTML
    # print(mp3_dir)
    web_driver = getBrowser()
    try:
        doBrowser(web_driver, url, mp3_dir)
    except Exception as e:
        print(e)
    finally:
        web_driver.quit()
