import re

# Test /etc/passwd content
passwd_content = """root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin"""

# Regex to match passwd entries
passwd_pattern = re.compile(r'^[^:]+:[^:]*:\d+:\d+:[^:]*:[^:]*:[^:]*$', re.MULTILINE)
matches = passwd_pattern.findall(passwd_content)

print(f"Found {len(matches)} passwd entries:")
for match in matches:
   print(match)

# Check if it's a valid passwd file
is_passwd = bool(re.search(r'^root:[^:]*:0:0:', passwd_content, re.MULTILINE))
print(f"\nValid /etc/passwd file: {is_passwd}")