import google.generativeai as genai
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

# Configure Gemini
genai.configure(api_key="AIzaSyDgORyXsBcfO5Y8QYZZ2rYmaKQ0JA6n6Bw")
gemini_model = genai.GenerativeModel("gemini-2.0-flash")

def summarize_with_gemini(content: str, CourseStructure: str) -> str:
    prompt = f"""You are a helpful assistant. I will give you raw content from a Microsoft Learn training module.
Summarize it using the same format as the example below.

---
Example Summary:
{CourseStructure}

---
Module Content:
{content}
"""
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[Gemini Error] {e}"

def get_learning_paths(course_url, headless=True):
    learning_paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(course_url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(3000)
        anchors = page.query_selector_all("a.card-title")
        for a in anchors:
            href = a.get_attribute("href") or ""
            text = (a.inner_text() or "").strip()
            if "/training/paths/" in href:
                full_url = urljoin(course_url, href)
                learning_paths.append({"url": full_url, "title": text})
        browser.close()
    return learning_paths

def get_inner_modules(path_url, headless=True):
    module_links = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(path_url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(2000)
        anchors = page.query_selector_all("a.unit-title, a.module-title")
        if not anchors:
            anchors = [
                a for a in page.query_selector_all("a[data-linktype='relative-path']") 
                if "/training/modules/" in (a.get_attribute("href") or "")
            ]
        for a in anchors:
            href = a.get_attribute("href") or ""
            text = (a.inner_text() or "").strip()
            if "/training/modules/" in href:
                full_url = urljoin(path_url, href)
                module_links.append({"url": full_url, "title": text})
        browser.close()
    return module_links

def scrape_module_content(url, headless=True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector("h1", timeout=8000)
            title_elem = page.query_selector("h1")
            title = title_elem.inner_text().strip() if title_elem else "No Title Found"
            content_elem = page.query_selector("main") or page.query_selector("body")
            content = content_elem.inner_text().strip() if content_elem else ""
        except Exception as e:
            title = f"Error loading page: {url}"
            content = str(e)
        browser.close()
    return title, content
"""if __name__ == "__main__":
    course_url = "https://learn.microsoft.com/en-us/training/courses/mb-910t00"
    output_path = "test_output.txt"
    summary_path = "test_summary.txt"

    # Load example summary format from file
    with open("CourseStructure.txt", "r", encoding="utf-8") as f:
        CourseStructure = f.read()

    print("[TEST] Extracting first learning path...")
    learning_paths = get_learning_paths(course_url, headless=True)
    if not learning_paths:
        print("❌ No learning paths found.")
        exit()

    first_path = learning_paths[0]
    print(f"[INFO] Selected Path: {first_path['title']}\n{first_path['url']}")

    print("[TEST] Getting first module...")
    modules = get_inner_modules(first_path["url"], headless=True)
    if not modules:
        print("❌ No modules found in path.")
        exit()

    first_module = modules[0]
    print(f"[INFO] Selected Module: {first_module['title']}\n{first_module['url']}")

    print("[TEST] Scraping content...")
    title, content = scrape_module_content(first_module["url"], headless=True)

    print("[TEST] Summarizing with Gemini...")
    summary = summarize_with_gemini(content, CourseStructure)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n\nContent:\n{content}\n")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Summary for: {first_module['title']}\n{summary}\n")

    print(f"\n✅ Test finished.\nRaw content → {output_path}\nSummary → {summary_path}")

"""
if __name__ == "__main__":
    course_url = "https://learn.microsoft.com/en-us/training/courses/mb-910t00"
    output_path = "output.txt"
    summary_path = "summaries.txt"

    # Load example summary format from file
    with open("CourseStructure.txt", "r", encoding="utf-8") as f:
        CourseStructure = f.read()

    print("[STEP 1] Extracting learning paths...")
    learning_paths = get_learning_paths(course_url, headless=True)
    print(f"[INFO] Found {len(learning_paths)} learning paths.")

    with open(output_path, "w", encoding="utf-8") as f:
        for i, path in enumerate(learning_paths, 1):
            f.write(f"=== Learning Path {i}: {path['title']} ===\nURL: {path['url']}\n\n")
            print(f"[STEP 2] Getting modules in Path {i}: {path['title']}")
            modules = get_inner_modules(path["url"], headless=True)
            f.write(f"Found {len(modules)} modules in this path.\n")

            for j, mod in enumerate(modules, 1):
                f.write(f"\n--- Module {j}: {mod['title']} ---\nURL: {mod['url']}\n")
                print(f"[STEP 3] Scraping content for Module {j}: {mod['title']}")
                title, content = scrape_module_content(mod['url'], headless=True)
                f.write(f"Title: {title}\n\nContent:\n{content}\n")
                f.write("=" * 80 + "\n")

                # STEP 4: Summarize and write to summaries.txt
                print(f"[STEP 4] Summarizing Module {j}: {mod['title']}")
                summary = summarize_with_gemini(content, CourseStructure)
                with open(summary_path, "a", encoding="utf-8") as summary_file:
                    summary_file.write(f"=== Summary for Module {j}: {mod['title']} ===\n")
                    summary_file.write(f"URL: {mod['url']}\n\n")
                    summary_file.write(summary + "\n")
                    summary_file.write("=" * 100 + "\n\n")

            f.write("\n" + "=" * 120 + "\n\n")

    print(f"\n[INFO] All scraping and summarization done.")
    print(f"[INFO] Raw content saved to: {output_path}")
    print(f"[INFO] Summaries saved to: {summary_path}")
