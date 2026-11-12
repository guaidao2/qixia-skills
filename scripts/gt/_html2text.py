import sys,re,html,subprocess,urllib.parse
url=sys.argv[1]
h=subprocess.run(["curl","-sSL","--max-time","25","-A","Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","-H","Accept-Language: zh-CN,zh;q=0.9",url],capture_output=True,text=True).stdout
h=re.sub(r'<script.*?</script>','',h,flags=re.S)
h=re.sub(r'<style.*?</style>','',h,flags=re.S)
h=re.sub(r'<[^>]+>','\n',h); h=html.unescape(h)
lines=[l.strip() for l in h.split('\n') if l.strip()]
print('\n'.join(lines)[:8000])
