import re
import os

# 1. Fix ddproperty
f1 = r'c:\Users\Teerayut.N\.vscode\extensions\All Asset Dashboard\Monthly all new\scrape_ddproperty_monthly.py'
with open(f1, 'r', encoding='utf-8') as f:
    c1 = f.read()

# Fix 1a
c1 = c1.replace('_detail_lock = threading.Lock()\n    \n    def worker(r):', 'def worker(r):')

# Fix 1b
lines = c1.split('\n')
new_lines = []
in_big_try = False

for i in range(len(lines)):
    line = lines[i]
    if line == '            script = soup.find("script", id="__NEXT_DATA__")':
        new_lines.append(line)
        continue
    if line == '                try:':
        if i > 0 and 'script and script.string:' in lines[i-1]:
            # skip this try
            in_big_try = True
            continue
    if in_big_try:
        if line == '                except Exception:':
            # check if next line is pass
            if i+1 < len(lines) and lines[i+1].strip() == 'pass':
                continue # skip except
        if line == '                    pass' and lines[i-1].strip() == 'except Exception:':
            in_big_try = False
            continue
        
        # unindent 4 spaces
        if line.startswith('    '):
            line = line[4:]
            
        # wrap floats
        if 'price = float(p_clean)' in line:
            indent = line[:len(line) - len(line.lstrip())]
            line = indent + 'try: ' + line.lstrip() + '\n' + indent + 'except Exception: pass'
        if 'lat = float(m_map.group(1)); lng = float(m_map.group(2))' in line:
            # this is already in a try/except, let's leave it
            pass
            
    new_lines.append(line)

with open(f1, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))


# 2. Fix zmyhome
f2 = r'c:\Users\Teerayut.N\.vscode\extensions\All Asset Dashboard\Monthly all new\scrape_zmyhome_monthly.py'
with open(f2, 'r', encoding='utf-8') as f:
    c2 = f.read()

c2 = c2.replace('def reverse_geocode_location(session, lat, lng):', '_nominatim_lock = threading.Lock()\n\ndef reverse_geocode_location(session, lat, lng):')
c2 = c2.replace('''    try:
        r = session.get(url, headers=headers, timeout=5)
        if r.status_code == 200:''', '''    try:
        with _nominatim_lock:
            r = session.get(url, headers=headers, timeout=5)
            time.sleep(1.0)
        if r.status_code == 200:''')

c2 = c2.replace('for future in concurrent.futures.as_completed(futures):', 'for future in futures:')

with open(f2, 'w', encoding='utf-8') as f:
    f.write(c2)


# 3. Fix taladnudbaan
f3 = r'c:\Users\Teerayut.N\.vscode\extensions\All Asset Dashboard\Monthly all new\scrape_taladnudbaan_monthly.py'
with open(f3, 'r', encoding='utf-8') as f:
    c3 = f.read()

c3 = c3.replace('for future in concurrent.futures.as_completed(futures):', 'for future in futures:')

with open(f3, 'w', encoding='utf-8') as f:
    f.write(c3)

print("Fixes applied.")
