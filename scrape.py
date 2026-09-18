import re,time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

START_URL="https://fccprod.servicenowservices.com/icfs"
DOWNLOAD_ROOT=Path("fcc_recent_filings")
WAIT_SECONDS=60
DOWNLOAD_TIMEOUT=120
RENDER_DELAY=6

FILING_PATTERN=re.compile(r"\b[A-Za-z0-9]{2,10}-[A-Za-z0-9/]{1,10}-\d{8}-\d{5}\b")

def text(e):
    try:return re.sub(r"\s+"," ",e.text or "").strip()
    except:return ""

def visible(e):
    try:return e.is_displayed()
    except:return False

def safe(s):
    return re.sub(r"\s+"," ",re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",s)).strip(" .")

def unique(p):
    if not p.exists():return p
    n=1
    while (q:=p.with_name(f"{p.stem}_{n}{p.suffix}")).exists():n+=1
    return q

def wait_page(d):
    WebDriverWait(d,WAIT_SECONDS).until(lambda x:x.execute_script("return document.readyState")=="complete")

def wait_download(directory,before):
    end=time.time()+DOWNLOAD_TIMEOUT
    while time.time()<end:
        files=set(directory.iterdir())
        new=files-before
        tmp=[x for x in files if x.name.endswith(".crdownload")]
        done=[x for x in new if x.is_file() and not x.name.endswith(".crdownload")]
        if done and not tmp:return max(done,key=lambda x:x.stat().st_mtime)
        time.sleep(.5)
    raise TimeoutException("Download timeout")

def switch_new_window(d,old,timeout=15):
    end=time.time()+timeout
    while time.time()<end:
        new=[h for h in d.window_handles if h not in old]
        if new:
            d.switch_to.window(new[0])
            return True
        time.sleep(.5)
    return False

def find_recent(d):
    xpaths=[
        "//*[self::a or self::button][contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'recent filings')]",
        "//*[@role='tab'][contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'recent filings')]",
        "//*[contains(@aria-label,'Recent Filings')]",
        "//*[contains(@title,'Recent Filings')]"
    ]
    for x in xpaths:
        try:
            for e in d.find_elements(By.XPATH,x):
                if visible(e):return e
        except:pass
    return None

def go_recent(d):
    print("Navigating to Recent Filings...")
    e=find_recent(d)
    if not e:
        time.sleep(3)
        e=find_recent(d)
    if not e:
        print("Recent Filings link not found.")
        return False
    old=set(d.window_handles)
    d.execute_script("arguments[0].scrollIntoView({block:'center'});",e)
    time.sleep(1)
    try:d.execute_script("arguments[0].click();",e)
    except:
        try:e.click()
        except:return False
    switch_new_window(d,old,10)
    wait_page(d)
    time.sleep(RENDER_DELAY)
    print("Recent Filings loaded:",d.current_url)
    return True

def find_table(d):
    for _ in range(15):
        for e in d.find_elements(By.XPATH,"//table|//*[@role='grid']"):
            try:
                if not visible(e):continue
                s=text(e).lower()
                if "file number" in s and "applicant name" in s:return e
            except:pass
        time.sleep(2)
    return None

def get_rows(table):
    result=[]
    seen=set()
    for selector in [".//tr",".//*[@role='row']"]:
        try:
            for r in table.find_elements(By.XPATH,selector):
                try:
                    s=text(r)
                    if s and s not in seen:
                        seen.add(s)
                        result.append(r)
                except:pass
        except:pass
    return result

def find_filing_element(row,number):
    try:elements=row.find_elements(By.XPATH,".//*[contains(.,%s)]"%repr(number))
    except:elements=[]
    candidates=[]
    for e in elements:
        try:
            if visible(e) and number in text(e):candidates.append(e)
        except:pass
    for e in candidates:
        try:
            tag=e.tag_name.lower()
            role=(e.get_attribute("role") or "").lower()
            cls=(e.get_attribute("class") or "").lower()
            if tag in ["a","button"] or role in ["link","button"] or e.get_attribute("href") or e.get_attribute("onclick") or "link" in cls or "click" in cls:
                return e
        except:pass
    return candidates[-1] if candidates else None

def get_filings(d):
    table=find_table(d)
    if not table:raise RuntimeError("Recent Filings table not found.")
    filings=[]
    seen=set()
    for i,row in enumerate(get_rows(table),1):
        s=text(row)
        m=FILING_PATTERN.search(s)
        if not m:continue
        number=m.group(0)
        if number not in seen:
            seen.add(number)
            filings.append({"number":number,"text":s})
            print(f"ROW {i}: {number} MATCH")
    return filings

def find_filing(d,number):
    table=find_table(d)
    if not table:return None
    for row in get_rows(table):
        if number in text(row):
            return find_filing_element(row,number)
    return None

def get_documents(d):
    result=[]
    seen=set()
    selectors=[
        "//a[contains(@href,'sys_attachment')]",
        "//a[contains(@href,'attachment')]",
        "//a[contains(@href,'download')]",
        "//a[@download]"
    ]
    for selector in selectors:
        try:
            for a in d.find_elements(By.XPATH,selector):
                try:
                    href=a.get_attribute("href")
                    if visible(a) and href and href not in seen:
                        seen.add(href)
                        result.append({"text":text(a) or "document","href":href})
                except:pass
        except:pass
    return result

def return_home(d):
    print("Returning to ICFS home...")
    d.get(START_URL)
    wait_page(d)
    time.sleep(RENDER_DELAY)
    print("Home loaded:",d.current_url)

DOWNLOAD_ROOT.mkdir(parents=True,exist_ok=True)

o=Options()
o.binary_location="/opt/google/chrome/chrome"
o.add_experimental_option("prefs",{
    "download.default_directory":str(DOWNLOAD_ROOT.resolve()),
    "download.prompt_for_download":False,
    "download.directory_upgrade":True,
    "plugins.always_open_pdf_externally":True
})
o.add_argument("--start-maximized")
o.add_argument("--disable-notifications")

d=webdriver.Chrome(service=Service(),options=o)

try:
    d.get(START_URL)
    wait_page(d)
    time.sleep(RENDER_DELAY)

    if not go_recent(d):
        raise RuntimeError("Could not navigate to Recent Filings.")

    filings=get_filings(d)

    print("\nFILINGS FOUND:",len(filings))
    for i,f in enumerate(filings,1):
        print(f"{i}. {f['number']} | {f['text']}")

    for index,f in enumerate(filings,1):
        print("\n"+"="*75)
        print(f"PROCESSING FILING {index}/{len(filings)}")
        print(f["text"])
        print("="*75)

        if index>1:
            return_home(d)
            if not go_recent(d):
                raise RuntimeError("Could not re-navigate to Recent Filings.")

        element=find_filing(d,f["number"])

        if not element:
            print("Could not find filing:",f["number"])
            continue

        folder=DOWNLOAD_ROOT/safe(f"{index:03d}_{f['text']}")
        folder.mkdir(parents=True,exist_ok=True)

        recent_window=d.current_window_handle
        old_handles=set(d.window_handles)

        d.execute_script("arguments[0].scrollIntoView({block:'center'});",element)
        time.sleep(1)

        try:d.execute_script("arguments[0].click();",element)
        except:
            try:element.click()
            except Exception as e:
                print("CLICK ERROR:",e)
                continue

        new_window=switch_new_window(d,old_handles,10)

        try:
            WebDriverWait(d,20).until(lambda x:x.current_url!=START_URL or len(x.window_handles)>1)
        except:pass

        wait_page(d)
        time.sleep(RENDER_DELAY)

        filing_window=d.current_window_handle

        print("Filing page:",d.current_url)

        docs=get_documents(d)
        print("Documents found:",len(docs))

        for n,doc in enumerate(docs,1):
            print(f"Downloading {n}/{len(docs)}: {doc['text']}")

            before=set(DOWNLOAD_ROOT.iterdir())
            old=set(d.window_handles)

            try:
                d.execute_script("window.open(arguments[0],'_blank');",doc["href"])

                if not switch_new_window(d,old,15):
                    raise RuntimeError("Download tab did not open.")

                time.sleep(2)

                downloaded=wait_download(DOWNLOAD_ROOT,before)
                destination=unique(folder/downloaded.name)
                downloaded.rename(destination)

                print("SAVED:",destination)

                d.close()
                d.switch_to.window(filing_window)

            except Exception as e:
                print("DOWNLOAD ERROR:",e)
                try:
                    while len(d.window_handles)>1:
                        d.switch_to.window(d.window_handles[-1])
                        d.close()
                    d.switch_to.window(filing_window)
                except:pass

        print(f"Finished filing {f['number']}.")

        if filing_window!=recent_window:
            try:
                d.switch_to.window(filing_window)
                d.close()
            except:pass

        if recent_window in d.window_handles:
            d.switch_to.window(recent_window)

        print("Returning to home before next filing...")
        return_home(d)

        if index<len(filings):
            print("Re-navigating to Recent Filings for next filing...")
            if not go_recent(d):
                raise RuntimeError("Could not re-navigate to Recent Filings.")

    print("\n"+"="*75)
    print("DOWNLOAD COMPLETE")
    print("Filings processed:",len(filings))
    print("Output:",DOWNLOAD_ROOT.resolve())
    print("="*75)

finally:
    print("Closing browser...")
    d.quit()
