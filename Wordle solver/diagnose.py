"""Run this once to capture the live DOM and a screenshot for debugging."""
import time, os, sys
from selenium.webdriver.chrome.webdriver import WebDriver as Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--start-maximized")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get("https://wordleunlimited.org/")

print("Waiting 5s for page to fully render…")
time.sleep(5)

base = os.path.dirname(os.path.abspath(__file__))

# Screenshot before dismissing anything
driver.save_screenshot(os.path.join(base, "diag_before_dismiss.png"))
print("Screenshot saved: diag_before_dismiss.png")

# Dump full page source
src = driver.page_source
with open(os.path.join(base, "diag_page_source.html"), "w", encoding="utf-8") as f:
    f.write(src)
print("Page source saved: diag_page_source.html")

# Dump all elements with class/id that might be popup or board-related
script = """
var results = [];
var all = document.querySelectorAll('*');
for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var cls = el.className || '';
    var id = el.id || '';
    var tag = el.tagName || '';
    var txt = (el.innerText || '').trim().substring(0, 80);
    if (cls || id) {
        results.push(tag + ' | id=' + id + ' | class=' + cls + ' | text=' + txt);
    }
}
return results;
"""
elements = driver.execute_script(script)
with open(os.path.join(base, "diag_elements.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(elements))
print(f"Element dump saved: diag_elements.txt  ({len(elements)} elements)")

# Also try shadow DOM
shadow_script = """
function dumpShadow(root, depth) {
    var lines = [];
    var els = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (var i = 0; i < els.length; i++) {
        var el = els[i];
        var line = ' '.repeat(depth*2) + el.tagName;
        if (el.id) line += '#' + el.id;
        if (el.className) line += '.' + el.className;
        // attributes
        for (var j = 0; j < el.attributes.length; j++) {
            line += ' [' + el.attributes[j].name + '=' + el.attributes[j].value + ']';
        }
        lines.push(line);
        if (el.shadowRoot) {
            lines.push(' '.repeat((depth+1)*2) + '>>> SHADOW ROOT <<<');
            lines = lines.concat(dumpShadow(el.shadowRoot, depth+2));
        }
    }
    return lines;
}
return dumpShadow(document, 0).join('\\n');
"""
try:
    shadow_dump = driver.execute_script(shadow_script)
    with open(os.path.join(base, "diag_shadow_dom.txt"), "w", encoding="utf-8") as f:
        f.write(shadow_dump)
    print("Shadow DOM dump saved: diag_shadow_dom.txt")
except Exception as e:
    print(f"Shadow DOM dump failed: {e}")

input("\nDone! Press ENTER to close the browser…")
driver.quit()
