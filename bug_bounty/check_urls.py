import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urlunparse
import csv

# TODO: make modification here such we also log whether a login/signup/registration is present

def try_url_with_scheme(url):
    """Try a URL first with HTTPS, then with HTTP if HTTPS fails."""
    parsed = urlparse(url)
    
    # If no scheme is provided, try https then http
    if not parsed.scheme:
        # Try HTTPS first
        https_url = f"https://{url}"
        try:
            result = is_likely_homepage(https_url)
            return https_url, result
        except Exception as e:
            print(f"HTTPS failed for {url}: {e}")
            
            # If HTTPS fails, try HTTP
            http_url = f"http://{url}"
            try:
                result = is_likely_homepage(http_url)
                return http_url, result
            except Exception as e:
                print(f"HTTP failed for {url}: {e}")
                return url, False
    
    # If scheme is already provided, just try as is
    try:
        result = is_likely_homepage(url)
        return url, result
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return url, False

def is_likely_homepage(url):
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Check if we got a 200 status code
        if response.status_code != 200:
            return False
            
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check 1: URL structure
        parsed_url = urlparse(response.url)
        path = parsed_url.path
        if path in ['/', '/index.html', '/home', '/index.php', '']:
            url_score = 1
        else:
            url_score = 0
            
        # Check 2: Login/Signup presence
        auth_terms = ['login', 'log in', 'sign in', 'signin', 'sign up', 'signup', 
                      'register', 'create account', 'my account']
        auth_elements = soup.find_all(text=re.compile('|'.join(auth_terms), re.I))
        auth_buttons = soup.find_all('a', href=re.compile('|'.join(auth_terms), re.I))
        auth_forms = soup.find_all('form', id=re.compile('|'.join(auth_terms), re.I))
        auth_forms += soup.find_all('form', class_=re.compile('|'.join(auth_terms), re.I))
        
        auth_score = 1 if (len(auth_elements) + len(auth_buttons) + len(auth_forms)) > 0 else 0
        
        # Check 3: Navigation menu presence
        nav_elements = soup.find_all(['nav', 'menu'])
        nav_elements += soup.find_all(class_=re.compile('nav|menu', re.I))
        nav_elements += soup.find_all(id=re.compile('nav|menu', re.I))
        
        nav_score = 1 if len(nav_elements) > 0 else 0
        
        # Check 4: Title relevance
        title = soup.title.string if soup.title else ""
        title_keywords = ['home', 'welcome', 'official', 'main']
        title_score = 0
        if title:
            if len(title.split()) < 5:  # Short titles are more likely for homepages
                title_score += 0.5
            if any(keyword in title.lower() for keyword in title_keywords):
                title_score += 0.5
        
        # Check 5: Rich content indicators
        sections = soup.find_all(['section', 'div', 'article'])
        images = soup.find_all('img')
        links = soup.find_all('a')
        
        content_score = 0
        if len(sections) > 5:
            content_score += 0.3
        if len(images) > 3:
            content_score += 0.3
        if len(links) > 10:
            content_score += 0.4
            
        # Check 6: Footer presence (common on homepages)
        footer = soup.find('footer')
        footer_score = 0.5 if footer else 0
        
        # Check 7: Error page indicators (negative score)
        error_terms = ['not found', 'error', '404', 'sorry', 'unavailable', 'doesn\'t exist']
        error_elements = soup.find_all(text=re.compile('|'.join(error_terms), re.I))
        
        error_score = -1 if len(error_elements) > 2 else 0
        
        # Calculate final score
        total_score = url_score + auth_score + nav_score + title_score + content_score + footer_score + error_score
        
        # Decision threshold
        return total_score >= 2
        
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return False

def process_urls_file(input_file, output_file="checked.csv"):
    # Read URLs from the input file
    try:
        with open(input_file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    # Process URLs and write results to CSV
    with open(output_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["url", "check_status"])  # Write header
        
        for url in urls:
            final_url, result = try_url_with_scheme(url)
            writer.writerow([final_url, result])
            print(f"Processed {final_url}: {result}")  # Progress feedback

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python check_urls.py <input_file.txt>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    process_urls_file(input_file)
    print("Results have been written to checked.csv")