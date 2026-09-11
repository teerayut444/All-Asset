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
soup = BeautifulSoup(r.content.decode('cp874', errors='ignore'), 'html.parser')
oseckey_inp = soup.find('input', {'name': 'oseckey'})
oseckey = oseckey_inp.get('value', '') if oseckey_inp else ''

payload = {
    'region_name': '',
    'province': 'นนทบุรี',
    'oseckey': oseckey,
    'seckey': oseckey,
    'search': 'ok'
}

r1 = s.post("https://asset.led.go.th/newbidreg/default.asp", data=payload, verify=False, timeout=20)
html = r1.content.decode('cp874', errors='ignore')
soup1 = BeautifulSoup(html, 'html.parser')
forms = soup1.find_all('form')

count = 0
for f in forms:
    fname = f.get('name') or ''
    if re.match(r'^web\d+$', fname):
        count += 1
        inputs = {inp.get('name'): inp.get('value', '') for inp in f.find_all('input') if inp.get('name')}
        print(f"=== Item {count} ===")
        print(f"  AssetType: {inputs.get('assettypedesc')}")
        print(f"  Suit: {inputs.get('law_suit_no')}/{inputs.get('law_suit_year')}")
        print(f"  Deed No (เลขโฉนด): {inputs.get('deedno')}")
        print(f"  Land Type (เอกสารสิทธิ์): {inputs.get('landtype')}")
        print(f"  Location: {inputs.get('deedtumbol')} / {inputs.get('deedampur')} / {inputs.get('deedcity')}")
        if count >= 3:
            break
