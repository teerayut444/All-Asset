import requests
import re
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Origin': 'https://asset.led.go.th',
    'Referer': 'https://asset.led.go.th/newbidreg/'
})

r = s.get("https://asset.led.go.th/newbidreg/", verify=False, timeout=15)
soup = BeautifulSoup(r.content.decode('utf-8', errors='ignore'), 'html.parser')
oseckey_inp = soup.find('input', {'name': 'oseckey'})
oseckey = oseckey_inp.get('value', '') if oseckey_inp else ''
print("oseckey:", oseckey)

payload = {
    'region_name': '',
    'province': 'นนทบุรี',
    'oseckey': oseckey,
    'seckey': oseckey,
    'search': 'ok'
}

r1 = s.post("https://asset.led.go.th/newbidreg/default.asp", data=payload, verify=False, timeout=20)
soup1 = BeautifulSoup(r1.content.decode('utf-8', errors='ignore'), 'html.parser')
forms = soup1.find_all('form')
print("Forms found:", len(forms))

for f in forms:
    fname = f.get('name') or ''
    if re.match(r'^web\d+$', fname):
        inputs = {inp.get('name'): inp.get('value', '') for inp in f.find_all('input') if inp.get('name')}
        print(f"--- Form {fname} ---")
        for k, v in inputs.items():
            if any(term in k.lower() for term in ['deed', 'chanote', 'land', 'no', 'desc', 'num', 'auc']):
                print(f"  {k}: {v}")
        print("All keys:", list(inputs.keys()))
        break
