# -*- coding:utf-8 -*-
import sqlite3
import jieba
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator

db = sqlite3.connect('book.db')
sql = 'select name from book'
cursor = db.execute(sql)
words = []
for n in cursor:
    name = n[0].encode('utf-8')
    seg_lst = jieba.cut(name, cut_all=False)
    for w in seg_lst:
        words.append(w)
db.close()

print len(words)

wc = WordCloud(font_path='/System/Library/Fonts/PingFang.ttc',  # 设置字体
               background_color="black",  # 背景颜色
               max_words=2000,  # 词云显示的最大词数
               max_font_size=200,  # 字体最大值
               random_state=42,
               width=1024,
               height=768
               )
# 生成词云
wc.generate(' '.join(words))


plt.figure()
# 以下代码显示图片
plt.imshow(wc)
plt.axis("off")
plt.show()
# 绘制词云

# 保存图片
wc.to_file("cloud.png")
