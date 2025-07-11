from src.llm_models import openai_41, openai_4o
from src.llm_provider import LMP

AGENT_STEPS_COMBINED = """
[12] 15:49:09:[run:285] - Reflection:
Start by viewing the lab’s home page so we can identify any reflected parameters or forms that echo user-supplied data.  We’ll download and print a short slice of the HTML so that on the next turn we can choose an input point (e.g. search?q=) and begin our usual XSS marker probing.
[12] 15:49:09:[run:286] - Generated script:
import requests, textwrap, re, sys, html

BASE = 'https://0a0300ba040063ae838f2df900140072.web-security-academy.net/'

try:
    r = requests.get(BASE, timeout=10)
    r.raise_for_status()
except Exception as e:
    print('error:', e)
    sys.exit()

# Print a trimmed view of the HTML to understand structure (first 400 lines)
html_text = r.text.split('\n')[:400]
for line in html_text:
    print(line)

print('\n----\nStatus:', r.status_code, 'Length:', len(r.text))
[12] 15:49:09:[run:287] - Scratchpad:

[12] 15:49:09:[_log_execution_output:348] - Execution output (truncated to 8192 chars):
[home] 200 5066
<!DOCTYPE html>
<html>
    <head>
        <link href=/resources/labheader/css/academyLabHeader.css rel=stylesheet>
        <link href=/resources/css/labsBlog.css rel=stylesheet>
    </head>
    <body>
        <script src="/resources/labheader/js/labHeader.js"></script>
        <div id="academyLabHeader">
            <section class='academyLabBanner'>
                <div class=container>
                    <div class=logo></div>
                        <div class=title-container>
                                Back&nbsp;to&nbsp;lab&nbsp;description&nbsp;
                                <svg version=1.1 id=Layer_1 xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' x=0px y=0px viewBox='0 0 28 30' enable-background='new 0 0 28 30' xml:space=preserve title=back-arrow>
                                    <g>
                                        <polygon points='1.4,0 0,1.2 12.6,15 0,28.8 1.4,30 15.1,15'></polygon>
                                        <polygon points='14.3,0 12.9,1.2 25.6,15 12.9,28.8 14.3,30 28,15'></polygon>
                                    </g>
                                </svg>
                            </a>
                        </div>
                        <div class='widgetcontainer-lab-status is-notsolved'>
                            <span>LAB</span>
                            <p>Not solved</p>
                            <span class=lab-status-icon></span>
                        </div>
                    </div>
                </div>
            </section>
        </div>
        <div theme="blog">
            <section class="maincontainer">
                <div class="container is-page">
                    <header class="navigation-header">
                        <section class="top-links">
                            <a href=/>Home</a><p>|</p>
                        </section>
                    </header>
                    <header class="notification-header">
                    </header>
                    <section class="blog-header">
                        <img src="/resources/images/blog.svg">
                    </section>
                    <section class="blog-list">
                        <div class="blog-post">
                        <a href="/post?postId=1"><img src="/image/blog/posts/28.jpg"></a>
                        <p>The 'discovery' of port dates back to the late Seventeenth Century when British sailors stumbled upon the drink in Portugal and then stumbled even more slowly home with several more bottles. It has been said since then that Portugal is...</p>
                        <a class="button is-small" href="/post?postId=1">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=5"><img src="/image/blog/posts/6.jpg"></a>
                        <p>Is it just me that finds the way people share things on social media, without checking into them really disturbing? I've started checking things out now, not because I want to share but so I can somehow, politely, let them...</p>
                        <a class="button is-small" href="/post?postId=5">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=3"><img src="/image/blog/posts/29.jpg"></a>
                        <p>It is perhaps fair to say that volunteering conjures up feelings of helping those in need or taking time out of your own life to give back to society, family or friends. However, what often goes unspoken is that to...</p>
                        <a class="button is-small" href="/post?postId=3">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=7"><img src="/image/blog/posts/17.jpg"></a>
                        <p>There are three types of password users in the world; those who remember them, those who don't, and those who write them down.</p>
                        <a class="button is-small" href="/post?postId=7">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=4"><img src="/image/blog/posts/58.jpg"></a>
                        <p>Tis better to have loved and lost than to never to have loved at all? A beautiful thought, but maybe Tennyson never had to go around his exe's house to collect his parchment and quills after an awkward break up....</p>
                        <a class="button is-small" href="/post?postId=4">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=6"><img src="/image/blog/posts/30.jpg"></a>
                        <p>Travelling is such an emotive word. It can excite some, scare others and conjure images of grubby millennials backpacking around the far reaches of the earth for a few. It is however, a word that can mean whatever it is...</p>
                        <a class="button is-small" href="/post?postId=6">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=8"><img src="/image/blog/posts/9.jpg"></a>
                        <p>When it comes the holidays more and more people are finding it hard to make ends meet. They turn to Social Media and ask for advice, how they can make Christmas magical for their little ones when they don't have...</p>
                        <a class="button is-small" href="/post?postId=8">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=9"><img src="/image/blog/posts/13.jpg"></a>
                        <p>I remember the first time I told a lie. That's not to say I didn't do it before then, I just don't remember. I was nine years old and at my third school already. Fitting into already established friendship groups...</p>
                        <a class="button is-small" href="/post?postId=9">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=2"><img src="/image/blog/posts/54.jpg"></a>
                        <p>Forget electricity, we know that's still a drain on the National Grid. Some clever little inventors in Ohio have come up with a way of getting your car moving with nothing but air. And better still, air from your own...</p>
                        <a class="button is-small" href="/post?postId=2">View post</a>
                        </div>
                        <div class="blog-post">
                        <a href="/post?postId=10"><img src="/image/blog/posts/23.jpg"></a>
                        <p>When the leaflet dropped through my letterbox I thought it was a joke. The Peopleless Circus was in town. At the risk of sounding like a negative Nancy, I couldn't help thinking what is the world coming to. I'm not...</p>
                        <a class="button is-small" href="/post?postId=10">View post</a>
                        </div>
                    </section>
                </div>
            </section>
            <div class="footer-wrapper">
            </div>
        </div>
    </body>
</html>

----
Status: 200 Length: 7351

[12] 15:49:09:[run:251] - ========== STEP 2 ==========
[12] 15:49:39:[run:285] - Reflection:
We need to identify the user-controlled parameter that is reflected.  The blog labs normally have a “search” feature, so our next step is to probe BASE/?search=XSS_MARK and see if that string is echoed.  We’ll also fetch /post?postId=1 to check for any comment form/parameter in case the search is not present.  For each response we’ll show a short context around the marker so we can see the injection point.
[12] 15:49:39:[run:286] - Generated script:
import requests, re, textwrap, sys, html
from bs4 import BeautifulSoup

BASE = 'https://0a0300ba040063ae838f2df900140072.web-security-academy.net/'
marker = 'XSS_9c2b1'


def probe(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print('Error fetching', url, e)
        return None
    if marker in r.text:
        print('\n[+] Marker reflected in', url)
        # print a little context around each occurrence
        for m in re.finditer(marker, r.text):
            start = max(m.start()-60, 0)
            end   = min(m.end()+60, len(r.text))
            snippet = r.text[start:end]
            print('...'+snippet+'...')
    else:
        print('[-] Marker NOT reflected in', url, 'len', len(r.text))
    return r.text

# 1. Probe ?search=
probe(BASE + '?search=' + marker)

# 2. Check an individual post page for forms/inputs
html_post1 = probe(BASE + 'post?postId=1')
if html_post1:
    soup = BeautifulSoup(html_post1, 'html.parser')
    forms = soup.find_all('form')
    for idx, f in enumerate(forms, 1):
        print(f"\nForm #{idx}: action={f.get('action')} method={f.get('method')}")
        print(f.prettify()[:300])
[12] 15:49:39:[run:287] - Scratchpad:

[12] 15:49:39:[_log_execution_output:348] - Execution output (truncated to 8192 chars):
Error fetching https://0a0300ba040063ae838f2df900140072.web-security-academy.net/?search=XSS_9c2b1 name 'requests' is not defined
Error fetching https://0a0300ba040063ae838f2df900140072.web-security-academy.net/post?postId=1 name 'requests' is not defined
"""

prompt = """
Generate a short summary of the agent steps
In particular, highlight what 

{steps}
""".format(steps=AGENT_STEPS_COMBINED)

res = openai_4o().invoke(prompt)
print(res.content)