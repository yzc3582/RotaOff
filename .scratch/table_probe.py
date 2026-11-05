"""看 wiki 页面上有几张表、表头是什么，找 artist 来源。"""
import re
import sys
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8")

html_text = open(".scratch/wiki_page.html", encoding="utf-8").read()

# 粗粒度：先按 <table> 切分
tables = re.findall(r"<table.*?</table>", html_text, re.S)
print("表格数量:", len(tables))

for i, t in enumerate(tables):
    ths = re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)
    clean = [re.sub(r"<[^>]+>", "", x).strip() for x in ths][:12]
    rows = t.count("<tr")
    print(f"\n表 {i}: {rows} 行, 表头 {clean}")
    # 第一行数据前 3 个 td
    first_tr = re.search(r"<tr.*?</tr>", t, re.S)
    if first_tr:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", first_tr.group(0), re.S)
        print("  首行td:", [re.sub(r"<[^>]+>", "", x).strip()[:40] for x in tds[:8]])
