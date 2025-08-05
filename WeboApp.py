from flask import Flask, jsonify, request
import google.generativeai as genai
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
import os
import json
import re

app = Flask(__name__)

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

def parse_summaries_file(file_path):
    """Parse the summaries.txt file and return structured JSON data"""
    if not os.path.exists(file_path):
        return {"error": "summaries.txt file not found"}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split content by module separators
        modules = re.split(r'=+ Summary for Module \d+:', content)
        modules = [m.strip() for m in modules if m.strip()]
        
        summaries_data = {
            "total_modules": len(modules),
            "modules": []
        }
        
        for i, module_content in enumerate(modules, 1):
            lines = module_content.split('\n')
            title = ""
            url = ""
            summary = ""
            
            # Extract title from first line if it contains "==="
            if lines and "===" in lines[0]:
                title = lines[0].replace("===", "").strip()
            
            # Extract URL
            for line in lines:
                if line.startswith("URL:"):
                    url = line.replace("URL:", "").strip()
                    break
            
            # Extract summary (everything after URL line)
            url_found = False
            summary_lines = []
            for line in lines:
                if url_found and line.strip() and not line.startswith("="):
                    summary_lines.append(line.strip())
                elif line.startswith("URL:"):
                    url_found = True
            
            summary = '\n'.join(summary_lines)
            
            summaries_data["modules"].append({
                "module_number": i,
                "title": title,
                "url": url,
                "summary": summary
            })
        
        return summaries_data
        
    except Exception as e:
        return {"error": f"Error parsing summaries file: {str(e)}"}

@app.route('/')
def home():
    return jsonify({
        "message": "Microsoft Learn Course Scraper API",
        "endpoints": {
            "/summaries": "GET - Returns summaries from summaries.txt as JSON",
            "/scrape": "POST - Scrapes a course and returns summaries",
            "/health": "GET - Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "message": "API is running"})

@app.route('/summaries', methods=['GET'])
def get_summaries():
    """Return the contents of summaries.txt as JSON"""
    summaries_data = parse_summaries_file("summaries.txt")
    return jsonify(summaries_data)

@app.route('/scrape', methods=['POST'])
def scrape_course():
    """Scrape a Microsoft Learn course and return summaries as JSON"""
    data = request.get_json()
    
    if not data or 'course_url' not in data:
        return jsonify({"error": "Missing 'course_url' in request body"}), 400
    
    course_url = data['course_url']
    
    try:
        # Load course structure
        if not os.path.exists("CourseStructure.txt"):
            return jsonify({"error": "CourseStructure.txt file not found"}), 500
            
        with open("CourseStructure.txt", "r", encoding="utf-8") as f:
            CourseStructure = f.read()
        
        # Get learning paths
        learning_paths = get_learning_paths(course_url, headless=True)
        
        if not learning_paths:
            return jsonify({"error": "No learning paths found"}), 404
        
        all_summaries = {
            "course_url": course_url,
            "total_paths": len(learning_paths),
            "learning_paths": []
        }
        
        for i, path in enumerate(learning_paths, 1):
            path_data = {
                "path_number": i,
                "title": path['title'],
                "url": path['url'],
                "modules": []
            }
            
            # Get modules in this path
            modules = get_inner_modules(path["url"], headless=True)
            
            for j, mod in enumerate(modules, 1):
                # Scrape module content
                title, content = scrape_module_content(mod['url'], headless=True)
                
                # Generate summary
                summary = summarize_with_gemini(content, CourseStructure)
                
                module_data = {
                    "module_number": j,
                    "title": mod['title'],
                    "url": mod['url'],
                    "scraped_title": title,
                    "summary": summary
                }
                
                path_data["modules"].append(module_data)
            
            all_summaries["learning_paths"].append(path_data)
        
        return jsonify(all_summaries)
        
    except Exception as e:
        return jsonify({"error": f"Error during scraping: {str(e)}"}), 500

@app.route('/scrape-single-module', methods=['POST'])
def scrape_single_module():
    """Scrape a single module and return its summary"""
    data = request.get_json()
    
    if not data or 'module_url' not in data:
        return jsonify({"error": "Missing 'module_url' in request body"}), 400
    
    module_url = data['module_url']
    
    try:
        # Load course structure
        if not os.path.exists("CourseStructure.txt"):
            return jsonify({"error": "CourseStructure.txt file not found"}), 500
            
        with open("CourseStructure.txt", "r", encoding="utf-8") as f:
            CourseStructure = f.read()
        
        # Scrape module content
        title, content = scrape_module_content(module_url, headless=True)
        
        # Generate summary
        summary = summarize_with_gemini(content, CourseStructure)
        
        return jsonify({
            "module_url": module_url,
            "title": title,
            "summary": summary,
            "content_length": len(content)
        })
        
    except Exception as e:
        return jsonify({"error": f"Error during scraping: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)