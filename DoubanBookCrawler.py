# -*- coding:utf-8 -*-

import requests
import re
import sqlite3
import time
from bs4 import BeautifulSoup

'''
技术路线：requests->re->BeautifulSoup->Sqlite
Python版本：2.7
爬虫简介：这是一个豆瓣读书爬虫，获取图书信息并写入如数据库。
实现思路：先从某一门图书开始，在该图书页面爬取其他图书的url地址，并放入队列，再从当前页面爬取该图书信息并插入数据库。
为了防止对某一页面重复爬取，使用哈希表对需要爬取的页面进行检查，当某页面加入队列前，先在哈希表中对该页面进行查找，
若在哈希表中查找到了该地址，则跳过该地址，若没有找到该地址，则该地址加入队列以及哈希表。
'''

class DoubanBookCrawler:

    def __init__(self):
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept - Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.6,de;q=0.4,ja;q=0.2,zh-TW;q=0.2,pt;q=0.2",
            "User-Agent": "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 2.0.50727; ."
                          "NET CLR 3.0.04506.648; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)",
        }
        self.queue = []
        self.hash_set = set([])
        self.basic_url = "https://book.douban.com/subject/"
        self.db_connect = sqlite3.connect('book.db')
        self.initDatabase()
        self.commit_cnt = 1

    # 初始化数据库并建表
    def initDatabase(self):
        if self.db_connect:
            sql = "CREATE TABLE IF NOT EXISTS book (" \
                  "id VARCHAR(255) PRIMARY KEY NOT NULL," \
                  "name VARCHAR(255) NOT NULL," \
                  "source VARCHAR(255) NOT NULL," \
                  "authors VARCHAR(255) NOT NULL," \
                  "translators VARCHAR(255) NOT NULL," \
                  "score double NOT NULL," \
                  "date VARCHAR(255) NOT NULL," \
                  "money VARCHAR(255) NOT NULL," \
                  "company VARCHAR(255) NOT NULL," \
                  "page int NOT NULL," \
                  "mode VARCHAR(255) NOT NULL," \
                  "ISBN VARCHAR(255) NOT NULL)"
            self.db_connect.execute(sql)

    def pushQueue(self, book_id):
        self.queue.append(book_id)
        self.hash_set.add(book_id)

    # 获取html页面
    def getHTMLText(self, url):
        try:
            r = requests.get(url, timeout=30, headers=self.headers)
            r.raise_for_status()
            r.encoding = 'utf-8'
            return r.text
        except Exception, e:
            print e.message
            return ""

    # 对抓取的作者和译者进行字符串格式化
    def formatAuthor(self, author):
        author = author.replace('\n', '')
        author = re.sub(r'[ ]+', ' ', author)
        author = author.strip()
        return author

    # 使用正则对其他图书页面进行爬取，并加入队列
    def parseBookID(self, html):
        try:
            expression = "https://book.douban.com/subject/(\d+)/"
            pattern = re.compile(expression, re.S)
            items = re.findall(pattern, html)
            for item in items:
                book_id = item
                # 加入队列前先在哈希表中检查，若不再哈希表中，则加入队列以及哈希表
                if book_id not in self.hash_set:
                    self.pushQueue(book_id)
        except Exception, e:
            print e.message

    # 解析图书信息
    def parseBookInfo(self, html, book_id):
        try:
            book_dict = {'id': book_id}

            # 先通过正则表达式对图书名称和评分进行爬取
            pattern = re.compile(r'<img src=".*?" title=".*?" alt="(.*?)"', re.S)
            name = re.findall(pattern, html)[0]
            book_dict['name'] = name.encode('utf-8')

            pattern = re.compile(r'<strong class="ll rating_num " property="v:average"> (.*?) </strong>', re.S)
            score = re.findall(pattern, html)[0]
            if len(score) < 1:
                book_dict['score'] = 0
            else:
                try:
                    book_dict['score'] = float(score)
                except:
                    book_dict['source'] = 0

            # 通过beautifulsoup对包含所有的图书信息的html标签进行查找
            # 由于图书具体的信息并不再标签中包含，所以再次使用正则对标签中的具体信息进行匹配
            # 并且以下信息并不是每一本图书均会包含，所以进行正则匹配后对匹配到的信息进行检查，若匹配到信息，则加入字典中
            soup = BeautifulSoup(html, 'html.parser')
            book_info = str(soup.find('div', attrs={"id": "info", "class": ""}))

            pattern = re.compile(r'<span class="pl">作者:</span>(.*?)</span>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0:
                authors_info = items[0]
                pattern = re.compile(r'<a href="https://book.douban.com/search/.*?/">(.*?)</a>', re.S)
                author_lst = re.findall(pattern, authors_info)
                # 替换所有的换行符，使用正则表达使得所有字符串的空格长度都变为1,并去除开头和结尾的空格
                author_lst = map(self.formatAuthor, [x for x in author_lst])
                book_dict['authors'] = '/'.join(author_lst)

            pattern = re.compile(r'<span class="pl">译者:</span>(.*?)</span>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0:
                translators_info = items[0]
                pattern = re.compile('<a href="https://book.douban.com/search/.*?/">(.*?)</a>', re.S)
                translators_lst = re.findall(pattern, translators_info)
                translators_lst = map(self.formatAuthor, [x for x in translators_lst])
                book_dict['translators'] = '/'.join(translators_lst)

            pattern = re.compile(r'<span class="pl">出版社:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0: book_dict['company'] = items[0]

            pattern = re.compile(r'<span class="pl">原作名:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0: book_dict['source'] = items[0]

            pattern = re.compile(r'<span class="pl">出版年:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0: book_dict['date'] = items[0]

            pattern = re.compile(r'<span class="pl">页数:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0:
                try:
                    book_dict['page'] = int(items[0])
                except:
                    book_dict['page'] = 0

            pattern = re.compile(r'<span class="pl">定价:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0: book_dict['money'] = items[0]

            pattern = re.compile(r'<span class="pl">装帧:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0: book_dict['mode'] = items[0]

            pattern = re.compile(r'<span class="pl">ISBN:</span> (.*?)<br/>', re.S)
            items = re.findall(pattern, book_info)
            if len(items) > 0: book_dict['ISBN'] = items[0]

            self.insertInfo(book_dict)
        except Exception, e:
            print e.message

    # 将信息插入数据库
    def insertInfo(self, book_dict):
        if self.db_connect:
            book_id = book_dict.get("id", "")
            name = book_dict.get("name", "")
            source = book_dict.get("source", "")
            authors = book_dict.get("authors", "")
            translators = book_dict.get("translators", "")
            score = book_dict.get("score", 0)
            date = book_dict.get("date", "")
            money = book_dict.get("money", "")
            company = book_dict.get("company", "")
            page = book_dict.get("page", 0)
            mode = book_dict.get("mode", "")
            ISBN = book_dict.get("ISBN", "")

            sql = 'INSERT INTO book VALUES("{id}","{name}","{source}","{authors}","{translators}",{score},"{date}",' \
                  '"{money}","{company}",{page},"{mode}","{ISBN}")'.format(id=book_id,name=name,source=source,
                                                                           authors=authors,translators=translators,
                                                                           score=str(score),date=date,money=money,
                                                                           company=company,page=str(page),mode=mode,
                                                                           ISBN=ISBN)

            print sql
            self.db_connect.execute(sql)
            # 每插入10条提交一次
            if self.commit_cnt > 9:
                self.db_connect.commit()
                self.commit_cnt = 1
            else:
                self.commit_cnt += 1

    # 将最初的图书信息放入队列以及哈希表
    def startCrawl(self, start_id):
        self.pushQueue(start_id)

        # 若队列无信息，任务中止
        while len(self.queue) > 0:
            book_id = self.queue.pop(0)
            url = self.basic_url + book_id
            html = self.getHTMLText(url)
            if html == '':
                continue
            self.parseBookID(html)
            self.parseBookInfo(html, book_id)
            # 若对该网站访问速度过快，一段时间后服务器会返回403错误
            time.sleep(2)

        if self.db_connect:
            self.db_connect.close()

if __name__ == "__main__":

    crawler = DoubanBookCrawler()
    # 在startCrawl函数参数中添加需要爬取图书的豆瓣ID，也就是爬虫爬取的起点
    crawler.startCrawl("20432061")
